from __future__ import annotations

import logging

from hsk5 import generate, store
from hsk5.store import ExamCancelled
from hsk5.generate import GrokLLM, LLM, planned_steps
from hsk5.scale import counts_for

log = logging.getLogger(__name__)


def _public_error(exc: BaseException) -> str:
    """Expose safe diagnostics; never leak answers/transcripts into the exam list."""
    text = str(exc)
    if isinstance(exc, RuntimeError) and text.startswith("OOV remaining"):
        detail = f"RuntimeError: {text}"
        return detail if len(detail) <= 240 else detail[:237] + "..."
    return "generation failed"


def run_generate(exam_id: str, size: int, *, mode: str = "full", llm: LLM | None = None) -> None:
    steps = planned_steps(counts_for(size, mode))

    def report(label: str, detail: str = "") -> None:
        index = steps.index(label) + 1 if label in steps else 0
        store.set_progress_state(
            exam_id,
            index=index,
            total=len(steps),
            label=label,
            steps=steps,
            detail=detail,
        )

    try:
        report("準備")
        if store.is_cancelled(exam_id):
            raise ExamCancelled()
        exam = generate.generate_exam(exam_id, size, mode=mode, llm=llm or GrokLLM(), report=report)
        if store.is_cancelled(exam_id):
            raise ExamCancelled()
        generate.attach_media(exam, report=report)
        report("保存")
        store.save_exam(exam)
    except ExamCancelled:
        if not store.is_cancelled(exam_id):
            store.set_status(exam_id, "cancelled", "cancelled")
        return
    except Exception as e:
        log.exception("generate failed exam_id=%s", exam_id)
        store.set_status(exam_id, "failed", _public_error(e))
