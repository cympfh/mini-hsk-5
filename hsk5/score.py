from __future__ import annotations

import re
from typing import Any

from hsk5.models import Band, EssayGrokOut, EssayItem, Exam, McqItem, SentenceOrderItem
from hsk5.scale import ScoreWeights, score_weights

_STRIP = re.compile(r"[\s，。！？、；：「」『』（）()\[\]【】《》—…·.,!?;:'\"\-　]")
BAND_RANGE: dict[Band, tuple[int, int]] = {
    "zero": (0, 0),
    "low": (1, 10),
    "mid": (11, 20),
    "high": (21, 30),
}
HANZI_SHORT = 75


def normalize_zh(text: str) -> str:
    return _STRIP.sub("", text)


def hanzi_count(text: str) -> int:
    return sum(1 for ch in text if "\u4e00" <= ch <= "\u9fff")


def used_required_words(text: str, required: list[str]) -> list[str]:
    return [w for w in required if w in text]


def score_mcq_item(item: McqItem, given: str | None, points: float) -> float:
    if given is None:
        return 0.0
    return points if given.strip().upper() == item.answer else 0.0


def score_sentence(item: SentenceOrderItem, given: str | None, points: float) -> float:
    if given is None:
        return 0.0
    return points if normalize_zh(given) == normalize_zh(item.gold) else 0.0


def clip_score_to_band(score: int, band: Band) -> int:
    lo, hi = BAND_RANGE[band]
    return max(lo, min(hi, score))


def apply_essay_guards(raw: EssayGrokOut, text: str, required: list[str]) -> EssayGrokOut:
    stripped = text.strip()
    n = hanzi_count(text)
    used = used_required_words(text, required)
    missing = [w for w in required if w not in used]
    if not stripped:
        return raw.model_copy(
            update={
                "band": "zero",
                "score": 0,
                "char_count": n,
                "used_required_words": used,
            }
        )
    band: Band = raw.band
    score = clip_score_to_band(raw.score, band)
    unrelated = raw.related_to_image is False
    if band == "high" and (missing or n < HANZI_SHORT or unrelated):
        band = "mid"
        score = min(score, 20)
        if score < 11:
            score = 11
    return raw.model_copy(
        update={
            "band": band,
            "score": score,
            "char_count": n,
            "used_required_words": used,
        }
    )


def essay_points(guarded: EssayGrokOut, item_points: float) -> float:
    return item_points * (guarded.score / 30.0)


def score_exam(
    exam: Exam,
    answers: dict[str, Any],
    essay_scores: dict[str, EssayGrokOut],
) -> dict[str, Any]:
    weights = score_weights(exam.counts)
    mcq_in = {k: str(v) for k, v in (answers.get("mcq") or {}).items()}
    sent_in = {k: str(v) for k, v in (answers.get("sentence") or {}).items()}
    listening_items: list[dict[str, Any]] = []
    listening_total = 0.0
    for i, item in enumerate(exam.listening):
        pts = weights.listening[i] if i < len(weights.listening) else 0.0
        got = score_mcq_item(item, mcq_in.get(item.id), pts)
        listening_total += got
        listening_items.append(
            {
                "id": item.id,
                "correct": got > 0,
                "answer": item.answer,
                "given": mcq_in.get(item.id),
                "points": got,
                "transcript": item.transcript,
            }
        )
    reading_items: list[dict[str, Any]] = []
    reading_total = 0.0
    for i, item in enumerate(exam.reading):
        pts = weights.reading[i] if i < len(weights.reading) else 0.0
        got = score_mcq_item(item, mcq_in.get(item.id), pts)
        reading_total += got
        reading_items.append(
            {
                "id": item.id,
                "correct": got > 0,
                "answer": item.answer,
                "given": mcq_in.get(item.id),
                "points": got,
            }
        )
    writing_total = 0.0
    sentence_items: list[dict[str, Any]] = []
    for item in exam.sentence_order:
        got = score_sentence(item, sent_in.get(item.id), weights.writing_p1)
        writing_total += got
        sentence_items.append(
            {
                "id": item.id,
                "correct": got > 0,
                "gold": item.gold,
                "given": sent_in.get(item.id),
                "points": got,
            }
        )
    essay_items: list[dict[str, Any]] = []
    essay_in = {k: str(v) for k, v in (answers.get("essay") or {}).items()}
    for item in exam.essays:
        text = essay_in.get(item.id, "")
        raw = essay_scores.get(item.id) or EssayGrokOut(band="zero", score=0, char_count=0)
        guarded = apply_essay_guards(raw, text, item.required_words)
        got = essay_points(guarded, weights.writing_p2)
        writing_total += got
        essay_items.append(
            {
                "id": item.id,
                "kind": item.kind,
                "band": guarded.band,
                "raw_score": guarded.score,
                "points": got,
                "char_count": guarded.char_count,
                "used_required_words": guarded.used_required_words,
                "comment_ja": guarded.comment_ja,
                "given": text,
            }
        )
    return {
        "listening": listening_total,
        "reading": reading_total,
        "writing": writing_total,
        "total": listening_total + reading_total + writing_total,
        "listening_items": listening_items,
        "reading_items": reading_items,
        "sentence_items": sentence_items,
        "essay_items": essay_items,
        "weights": {
            "listening": list(weights.listening),
            "reading": list(weights.reading),
            "writing_p1": weights.writing_p1,
            "writing_p2": weights.writing_p2,
        },
    }


def empty_section_score(weights: ScoreWeights, kind: str) -> float:
    if kind == "listening":
        return 0.0 if weights.listening else 0.0
    return 0.0
