from __future__ import annotations

import logging

from hsk5 import generate, store
from hsk5.generate import GrokLLM, LLM, planned_steps
from hsk5.scale import scale_counts

log = logging.getLogger(__name__)


def run_generate(exam_id: str, size: int, *, llm: LLM | None = None) -> None:
    steps = planned_steps(scale_counts(size))

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
        exam = generate.generate_exam(exam_id, size, llm=llm or GrokLLM(), report=report)
        generate.attach_media(exam, report=report)
        report("保存")
        store.save_exam(exam)
    except Exception as e:
        log.exception("generate failed exam_id=%s", exam_id)
        detail = f"{type(e).__name__}: {e}"
        if len(detail) > 240:
            detail = detail[:237] + "..."
        store.set_status(exam_id, "failed", detail)
