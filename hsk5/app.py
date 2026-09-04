from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse

from hsk5 import grok, jobs, store
from hsk5.ids import new_id
from hsk5.models import CreateIn, EssayGrokOut, EssayItem, SubmitIn
from hsk5.paths import MODEL, TEMPLATES
from hsk5.score import apply_essay_guards, hanzi_count, score_exam
from hsk5.store import ExamNotReady

if not os.environ.get("XAI_API_KEY"):
    raise SystemExit("XAI_API_KEY is required")

app = FastAPI(title="mini-hsk-5")


def _prefix() -> str:
    return os.environ.get("ROOT_PATH", "").rstrip("/")


def _overtime(started_at: str, limits: dict[str, int]) -> bool:
    start = datetime.fromisoformat(started_at)
    now = datetime.now(timezone.utc)
    budget = 60 * (
        limits.get("listening_minutes", 0) + limits.get("reading_minutes", 0) + limits.get("writing_minutes", 0)
    )
    return (now - start).total_seconds() > budget if budget else False


def _grade_essays(items: list[EssayItem], texts: dict[str, str]) -> dict[str, EssayGrokOut]:
    out: dict[str, EssayGrokOut] = {}
    for item in items:
        text = texts.get(item.id, "")
        if not text.strip():
            out[item.id] = EssayGrokOut(band="zero", score=0, char_count=0, comment_ja="未記入")
            continue
        n = hanzi_count(text)
        user = (
            "HSK5 短文を採点する。バンド zero/low/mid/high と 0-30 点。\n"
            "見てよい: 字数、文法、意味が通るか、指定語の使用、画像との関連。\n"
            "見るな: 内容が事実か、嘘か、荒唐無稽か。見識の高低も減点しない。\n"
            f"kind={item.kind}\nrequired={item.required_words}\n"
            f"hanzi_count={n}\ntext:\n{text}\n"
            "comment_ja は短い日本語。"
        )
        raw = grok.parse(EssayGrokOut, "You are an HSK5 writing rater. JSON only.", user)
        out[item.id] = apply_essay_guards(raw, text, item.required_words)
    return out


@app.get("/api/health")
def health() -> dict[str, object]:
    return {"ok": True, "model": MODEL}


@app.get("/")
def index() -> HTMLResponse:
    html = (TEMPLATES / "index.html").read_text(encoding="utf-8")
    prefix = _prefix()
    if prefix:
        html = html.replace('href="/app.css', f'href="{prefix}/app.css').replace(
            'src="/app.js', f'src="{prefix}/app.js'
        )
    return HTMLResponse(html)


@app.get("/app.js")
def app_js() -> FileResponse:
    return FileResponse(TEMPLATES / "app.js", media_type="text/javascript")


@app.get("/app.css")
def app_css() -> FileResponse:
    return FileResponse(TEMPLATES / "app.css", media_type="text/css")


@app.post("/api/exams")
def create_exam(body: CreateIn, bg: BackgroundTasks) -> dict[str, str]:
    exam_id = new_id()
    store.create_exam_row(exam_id, body.size)
    bg.add_task(jobs.run_generate, exam_id, body.size)
    return {"id": exam_id, "status": "generating"}


@app.get("/api/exams")
def exams() -> list[dict[str, object]]:
    return store.list_exams()


@app.get("/api/exams/{exam_id}")
def get_exam(exam_id: str) -> JSONResponse:
    row = store.get_exam_row(exam_id)
    if row is None:
        raise HTTPException(404, "exam not found")
    if row["status"] != "ready":
        return JSONResponse(
            {
                "id": exam_id,
                "size": row["size"],
                "status": row["status"],
                "progress": row["progress"],
                "error": row["error"],
                "created_at": row["created_at"],
            }
        )
    exam = store.load_exam(exam_id)
    return JSONResponse(exam.to_public(prefix=_prefix()))


@app.get("/api/exams/{exam_id}/audio/{clip_id}")
def get_audio(exam_id: str, clip_id: str) -> FileResponse:
    path = store.audio_path(exam_id, clip_id)
    if not path.is_file():
        raise HTTPException(404, "audio not found")
    return FileResponse(path, media_type="audio/mpeg")


@app.get("/api/exams/{exam_id}/images/{name}")
def get_image(exam_id: str, name: str) -> FileResponse:
    if Path(name).name != name:
        raise HTTPException(400, "bad name")
    path = store.image_path(exam_id, name)
    if not path.is_file():
        raise HTTPException(404, "image not found")
    return FileResponse(path)


@app.post("/api/exams/{exam_id}/attempts")
def start(exam_id: str) -> dict[str, object]:
    try:
        return store.start_attempt(exam_id)
    except KeyError:
        raise HTTPException(404, "exam not found") from None
    except ExamNotReady as e:
        raise HTTPException(409, f"exam is {e.status}") from None


@app.post("/api/attempts/{attempt_id}/submit")
def submit(attempt_id: str, body: SubmitIn) -> dict[str, object]:
    row = store.get_attempt(attempt_id)
    if row is None:
        raise HTTPException(404, "attempt not found")
    if row["submitted_at"]:
        raise HTTPException(409, "already submitted")
    exam = store.load_exam(row["exam_id"])
    answers = body.model_dump()
    essay_scores = _grade_essays(exam.essays, answers.get("essay") or {})
    result = score_exam(exam, answers, essay_scores)
    limits = {
        "listening_minutes": exam.counts.listening_minutes,
        "reading_minutes": exam.counts.reading_minutes,
        "writing_minutes": exam.counts.writing_minutes,
    }
    overtime = _overtime(row["started_at"], limits)
    result["overtime"] = overtime
    result["pass_hint"] = 180
    store.save_attempt_result(attempt_id, exam.id, result, answers, overtime)
    public = exam.to_public(prefix=_prefix())
    return {"exam": public, "result": result}
