from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse

from hsk5 import grok, jobs, store
from hsk5.ids import is_id, new_id
from hsk5.models import CreateIn, EssayGrokOut, EssayItem, SubmitIn
from hsk5.paths import MODEL, TEMPLATES
from hsk5.score import apply_essay_guards, hanzi_count, score_exam
from hsk5.store import ExamNotReady

if not os.environ.get("XAI_API_KEY"):
    raise SystemExit("XAI_API_KEY is required")

log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    ids = store.fail_interrupted_generating()
    if ids:
        log.warning("marked %d interrupted generating exam(s) failed: %s", len(ids), ",".join(ids))
    yield


app = FastAPI(title="mini-hsk-5", lifespan=lifespan)


def _prefix() -> str:
    return os.environ.get("ROOT_PATH", "").rstrip("/")


def _overtime(started_at: str, limits: dict[str, int]) -> bool:
    start = datetime.fromisoformat(started_at)
    now = datetime.now(timezone.utc)
    budget = 60 * (
        limits.get("listening_minutes", 0) + limits.get("reading_minutes", 0) + limits.get("writing_minutes", 0)
    )
    return (now - start).total_seconds() > budget if budget else False


def _require_id(value: str) -> str:
    if not is_id(value):
        raise HTTPException(404, "not found")
    return value


def _grade_essays(exam_id: str, items: list[EssayItem], texts: dict[str, str]) -> dict[str, EssayGrokOut]:
    out: dict[str, EssayGrokOut] = {}
    for item in items:
        text = texts.get(item.id, "")
        if not text.strip():
            out[item.id] = EssayGrokOut(band="zero", score=0, char_count=0, comment_ja="未記入")
            continue
        n = hanzi_count(text)
        image: bytes | None = None
        if item.kind == "picture" and item.image_name:
            path = store.image_path(exam_id, item.image_name, create=False)
            if path.is_file():
                image = path.read_bytes()
        user = (
            "HSK5 短文を採点する。バンド zero/low/mid/high と 0-30 点。\n"
            "見てよい: 字数、文法、意味が通るか、指定語の使用、画像との関連。\n"
            "見るな: 内容が事実か、嘘か、荒唐無稽か。見識の高低も減点しない。\n"
            f"kind={item.kind}\nrequired={item.required_words}\n"
            f"hanzi_count={n}\ntext:\n{text}\n"
            "画像がある場合は related_to_image を付ける。comment_ja は短い日本語。"
        )
        raw = grok.parse(EssayGrokOut, "You are an HSK5 writing rater. JSON only.", user, image=image)
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


@app.get("/api/scale")
def scale_preview(size: int = 10) -> dict[str, object]:
    from hsk5.scale import counts_for

    try:
        c = counts_for(size=size)
    except ValueError as e:
        raise HTTPException(400, str(e)) from None
    return {
        "size": c.size,
        "listening_p1": c.listening_p1,
        "listening_p2": c.listening_p2,
        "reading_p1": c.reading_p1,
        "reading_p2": c.reading_p2,
        "reading_p3": c.reading_p3,
        "writing_p1": c.writing_p1,
        "writing_keywords": c.writing_keywords,
        "writing_picture": c.writing_picture,
        "writing_p2": c.writing_p2,
        "listening_total": c.listening_total,
        "reading_total": c.reading_total,
        "writing_total": c.writing_total,
        "listening_minutes": c.listening_minutes,
        "reading_minutes": c.reading_minutes,
        "writing_minutes": c.writing_minutes,
    }


@app.post("/api/exams")
def create_exam(body: CreateIn, bg: BackgroundTasks) -> dict[str, str]:
    exam_id = new_id()
    mode = body.resolved_mode()
    store.create_exam_row(exam_id, body.size, mode)
    parts = None
    if body.parts is not None:
        parts = body.parts.model_dump()
    bg.add_task(jobs.run_generate, exam_id, body.size, mode=mode, parts=parts)
    return {"id": exam_id, "status": "generating"}


@app.get("/api/exams")
def exams() -> list[dict[str, object]]:
    return store.list_exams()


@app.get("/api/exams/{exam_id}")
def get_exam(exam_id: str) -> JSONResponse:
    _require_id(exam_id)
    row = store.get_exam_row(exam_id)
    if row is None:
        raise HTTPException(404, "exam not found")
    if row["status"] != "ready":
        return JSONResponse(
            {
                "id": exam_id,
                "size": row["size"],
                "mode": row["mode"] if "mode" in row.keys() else "full",
                "status": row["status"],
                "progress": store.parse_progress(row["progress"]),
                "error": row["error"],
                "created_at": row["created_at"],
            }
        )
    exam = store.load_exam(exam_id)
    return JSONResponse(exam.to_public(prefix=_prefix()))


@app.get("/api/exams/{exam_id}/audio/{clip_id}")
def get_audio(exam_id: str, clip_id: str) -> FileResponse:
    _require_id(exam_id)
    _require_id(clip_id)
    try:
        path = store.audio_path(exam_id, clip_id, create=False)
    except ValueError:
        raise HTTPException(404, "audio not found") from None
    if not path.is_file():
        raise HTTPException(404, "audio not found")
    return FileResponse(path, media_type="audio/mpeg")


@app.get("/api/exams/{exam_id}/images/{name}")
def get_image(exam_id: str, name: str) -> FileResponse:
    _require_id(exam_id)
    try:
        path = store.image_path(exam_id, name, create=False)
    except ValueError:
        raise HTTPException(404, "image not found") from None
    if not path.is_file():
        raise HTTPException(404, "image not found")
    return FileResponse(path)


@app.post("/api/exams/{exam_id}/cancel")
def cancel_exam(exam_id: str) -> dict[str, str]:
    _require_id(exam_id)
    try:
        return store.cancel_exam(exam_id)
    except KeyError:
        raise HTTPException(404, "exam not found") from None
    except ExamNotReady as e:
        raise HTTPException(409, f"exam is {e.status}") from None


@app.get("/api/exams/{exam_id}/attempts")
def list_exam_attempts(exam_id: str) -> list[dict[str, object]]:
    _require_id(exam_id)
    try:
        return store.list_attempts(exam_id)
    except KeyError:
        raise HTTPException(404, "exam not found") from None


@app.get("/api/attempts/{attempt_id}")
def get_attempt_review(attempt_id: str) -> dict[str, object]:
    _require_id(attempt_id)
    try:
        payload = store.load_attempt_review(attempt_id)
    except KeyError:
        raise HTTPException(404, "attempt not found") from None
    except ExamNotReady as e:
        raise HTTPException(409, f"attempt is {e.status}") from None
    exam = payload["exam"]
    public = exam.to_public(prefix=_prefix())
    return {
        "id": payload["id"],
        "exam_id": payload["exam_id"],
        "started_at": payload["started_at"],
        "submitted_at": payload["submitted_at"],
        "overtime": payload["overtime"],
        "exam": public,
        "result": payload["result"],
    }


@app.post("/api/exams/{exam_id}/attempts")
def start(exam_id: str) -> dict[str, object]:
    _require_id(exam_id)
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
    essay_scores = _grade_essays(exam.id, exam.essays, answers.get("essay") or {})
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
