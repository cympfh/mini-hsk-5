from __future__ import annotations

from hsk5 import generate, store
from hsk5.generate import GrokLLM, LLM


def run_generate(exam_id: str, size: int, *, llm: LLM | None = None) -> None:
    try:
        store.set_progress(exam_id, "questions")
        exam = generate.generate_exam(exam_id, size, llm=llm or GrokLLM())
        store.set_progress(exam_id, "media")
        generate.attach_media(exam)
        store.save_exam(exam)
    except Exception as e:
        store.set_status(exam_id, "failed", str(e))
