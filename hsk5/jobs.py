from __future__ import annotations

import logging

from hsk5 import generate, store
from hsk5.generate import GrokLLM, LLM

log = logging.getLogger(__name__)


def run_generate(exam_id: str, size: int, *, llm: LLM | None = None) -> None:
    try:
        store.set_progress(exam_id, "questions")
        exam = generate.generate_exam(exam_id, size, llm=llm or GrokLLM())
        store.set_progress(exam_id, "media")
        generate.attach_media(exam)
        store.save_exam(exam)
    except Exception:
        log.exception("generate failed exam_id=%s", exam_id)
        store.set_status(exam_id, "failed", "generation failed")
