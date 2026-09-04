from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from hsk5.ids import is_id, new_id
from hsk5.models import Exam
from hsk5.paths import db_path, exams_dir


class ExamNotReady(Exception):
    def __init__(self, status: str, exam_id: str):
        self.status = status
        self.exam_id = exam_id
        super().__init__(f"exam {exam_id} is {status}")


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _connect() -> sqlite3.Connection:
    path = db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS exams (
            id TEXT PRIMARY KEY,
            size INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            status TEXT NOT NULL,
            progress TEXT,
            best_total REAL,
            best_at TEXT,
            error TEXT
        )
        """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS attempts (
            id TEXT PRIMARY KEY,
            exam_id TEXT NOT NULL,
            started_at TEXT NOT NULL,
            submitted_at TEXT,
            total REAL,
            listening REAL,
            reading REAL,
            writing REAL,
            overtime INTEGER,
            answers_json TEXT,
            result_json TEXT
        )
        """)
    conn.commit()
    return conn


def exam_dir(exam_id: str, *, create: bool = True) -> Path:
    if not is_id(exam_id):
        raise ValueError("bad exam id")
    d = exams_dir() / exam_id
    if create:
        d.mkdir(parents=True, exist_ok=True)
        (d / "audio").mkdir(exist_ok=True)
        (d / "images").mkdir(exist_ok=True)
    return d


def create_exam_row(exam_id: str, size: int) -> None:
    created = now_iso()
    with _connect() as conn:
        conn.execute(
            "INSERT INTO exams (id, size, created_at, status, progress) VALUES (?, ?, ?, ?, ?)",
            (exam_id, size, created, "generating", "queued"),
        )
        conn.commit()
    exam_dir(exam_id)


def set_progress(exam_id: str, progress: str) -> None:
    with _connect() as conn:
        conn.execute("UPDATE exams SET progress = ? WHERE id = ?", (progress, exam_id))
        conn.commit()


def set_status(exam_id: str, status: str, error: str | None = None) -> None:
    with _connect() as conn:
        conn.execute(
            "UPDATE exams SET status = ?, error = ?, progress = ? WHERE id = ?",
            (status, error, "done" if status == "ready" else status, exam_id),
        )
        conn.commit()


def save_exam(exam: Exam) -> None:
    path = exam_dir(exam.id) / "exam.json"
    path.write_text(exam.model_dump_json(indent=2), encoding="utf-8")
    set_status(exam.id, "ready")


def load_exam(exam_id: str) -> Exam:
    path = exam_dir(exam_id, create=False) / "exam.json"
    return Exam.model_validate_json(path.read_text(encoding="utf-8"))


def get_exam_row(exam_id: str) -> sqlite3.Row | None:
    with _connect() as conn:
        cur = conn.execute("SELECT * FROM exams WHERE id = ?", (exam_id,))
        return cur.fetchone()


def list_exams() -> list[dict[str, Any]]:
    with _connect() as conn:
        rows = conn.execute("SELECT * FROM exams ORDER BY created_at DESC").fetchall()
    return [
        {
            "id": r["id"],
            "size": r["size"],
            "created_at": r["created_at"],
            "status": r["status"],
            "progress": r["progress"],
            "best_total": r["best_total"],
            "best_at": r["best_at"],
            "error": r["error"],
        }
        for r in rows
    ]


def start_attempt(exam_id: str) -> dict[str, Any]:
    row = get_exam_row(exam_id)
    if row is None:
        raise KeyError(exam_id)
    if row["status"] != "ready":
        raise ExamNotReady(row["status"], exam_id)
    attempt_id = new_id()
    started = now_iso()
    with _connect() as conn:
        conn.execute(
            "INSERT INTO attempts (id, exam_id, started_at) VALUES (?, ?, ?)",
            (attempt_id, exam_id, started),
        )
        conn.commit()
    exam = load_exam(exam_id)
    return {
        "attempt_id": attempt_id,
        "exam_id": exam_id,
        "started_at": started,
        "limits": {
            "listening_minutes": exam.counts.listening_minutes,
            "reading_minutes": exam.counts.reading_minutes,
            "writing_minutes": exam.counts.writing_minutes,
        },
    }


def get_attempt(attempt_id: str) -> sqlite3.Row | None:
    with _connect() as conn:
        return conn.execute("SELECT * FROM attempts WHERE id = ?", (attempt_id,)).fetchone()


def save_attempt_result(
    attempt_id: str,
    exam_id: str,
    result: dict[str, Any],
    answers: dict[str, Any],
    overtime: bool,
) -> None:
    submitted = now_iso()
    total = float(result["total"])
    with _connect() as conn:
        conn.execute(
            """
            UPDATE attempts SET submitted_at=?, total=?, listening=?, reading=?, writing=?,
                overtime=?, answers_json=?, result_json=? WHERE id=?
            """,
            (
                submitted,
                total,
                result["listening"],
                result["reading"],
                result["writing"],
                1 if overtime else 0,
                json.dumps(answers, ensure_ascii=False),
                json.dumps(result, ensure_ascii=False),
                attempt_id,
            ),
        )
        row = conn.execute("SELECT best_total FROM exams WHERE id = ?", (exam_id,)).fetchone()
        best = row["best_total"] if row else None
        if best is None or total > best:
            conn.execute(
                "UPDATE exams SET best_total = ?, best_at = ? WHERE id = ?",
                (total, submitted, exam_id),
            )
        conn.commit()


def audio_path(exam_id: str, clip_id: str, *, create: bool = True) -> Path:
    if not is_id(clip_id):
        raise ValueError("bad clip id")
    return exam_dir(exam_id, create=create) / "audio" / f"{clip_id}.mp3"


def image_path(exam_id: str, name: str, *, create: bool = True) -> Path:
    if Path(name).name != name or name in {".", ".."}:
        raise ValueError("bad image name")
    return exam_dir(exam_id, create=create) / "images" / name
