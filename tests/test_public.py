from __future__ import annotations

from typing import Any

from tests.helpers import make_exam


def _keys(obj: Any) -> set[str]:
    found: set[str] = set()

    def walk(x: Any) -> None:
        if isinstance(x, dict):
            found.update(x.keys())
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)

    walk(obj)
    return found


def test_public_view_omits_answers_transcripts_gold() -> None:
    exam = make_exam(10)
    public = exam.to_public()
    keys = _keys(public)
    assert "answer" not in keys
    assert "transcript" not in keys
    assert "gold" not in keys
    assert "image_prompt" not in keys
    assert "lines" not in keys
    assert public["listening"]
    assert public["listening"][0]["choices"]
    assert "id" in public["listening"][0]
    assert public["sentence_order"][0]["words"] if exam.sentence_order else True
