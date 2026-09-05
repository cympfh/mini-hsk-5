from __future__ import annotations

import math
from typing import Any

from pydantic import BaseModel, Field, model_validator

SECTION_WEIGHTS = (45, 45, 10)
LISTENING_WEIGHTS = (20, 25)
READING_WEIGHTS = (15, 10, 20)
WRITING_WEIGHTS = (8, 2)
LISTEN_MINUTES_FULL = 30
READ_MINUTES_FULL = 45
WRITE_MINUTES_FULL = 40
P1_BASE = 5.0
P2_BASE = 30.0
SECTION_TOTAL = 100.0


class PartCounts(BaseModel):
    size: int
    listening_p1: int
    listening_p2: int
    reading_p1: int
    reading_p2: int
    reading_p3: int
    writing_p1: int
    writing_keywords: int = 0
    writing_picture: int = 0
    writing_p2: int = 0
    listening_minutes: int
    reading_minutes: int
    writing_minutes: int

    @model_validator(mode="before")
    @classmethod
    def _split_legacy_writing_p2(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "writing_keywords" not in data and "writing_picture" not in data:
                wp2 = int(data.get("writing_p2") or 0)
                data["writing_keywords"] = max(0, wp2 - 1)
                data["writing_picture"] = 1 if wp2 >= 1 else 0
            wk = int(data.get("writing_keywords") or 0)
            wpic = int(data.get("writing_picture") or 0)
            data["writing_p2"] = wk + wpic
        return data

    @property
    def listening_total(self) -> int:
        return self.listening_p1 + self.listening_p2

    @property
    def reading_total(self) -> int:
        return self.reading_p1 + self.reading_p2 + self.reading_p3

    @property
    def writing_total(self) -> int:
        return self.writing_p1 + self.writing_p2

    @property
    def total(self) -> int:
        return self.listening_total + self.reading_total + self.writing_total


class ScoreWeights(BaseModel):
    listening: tuple[float, ...]
    reading: tuple[float, ...]
    writing_p1: float
    writing_p2: float


def hamilton(weights: tuple[int, ...], total: int) -> list[int]:
    n = len(weights)
    if total <= 0:
        return [0] * n
    weight_sum = sum(weights)
    raw = [w * total / weight_sum for w in weights]
    floors = [math.floor(x) for x in raw]
    leftover = total - sum(floors)
    order = sorted(range(n), key=lambda i: (-(raw[i] - floors[i]), i))
    out = list(floors)
    for i in order[:leftover]:
        out[i] += 1
    return out


def _minutes(full: int, size: int, items: int) -> int:
    if items <= 0:
        return 0
    return max(1, round(full * size / 100))


def _essay_split(wp2: int) -> tuple[int, int]:
    """Match prior generator: last essay slot is 看图 when any essays exist."""
    if wp2 <= 0:
        return 0, 0
    return max(0, wp2 - 1), 1


def scale_counts(size: int) -> PartCounts:
    if size < 1 or size > 100:
        raise ValueError("size must be 1..100")
    listen_n, read_n, write_n = hamilton(SECTION_WEIGHTS, size)
    lp1, lp2 = hamilton(LISTENING_WEIGHTS, listen_n)
    rp1, rp2, rp3 = hamilton(READING_WEIGHTS, read_n)
    wp1, wp2 = hamilton(WRITING_WEIGHTS, write_n)
    wk, wpic = _essay_split(wp2)
    return PartCounts(
        size=size,
        listening_p1=lp1,
        listening_p2=lp2,
        reading_p1=rp1,
        reading_p2=rp2,
        reading_p3=rp3,
        writing_p1=wp1,
        writing_keywords=wk,
        writing_picture=wpic,
        writing_p2=wk + wpic,
        listening_minutes=_minutes(LISTEN_MINUTES_FULL, size, lp1 + lp2),
        reading_minutes=_minutes(READ_MINUTES_FULL, size, rp1 + rp2 + rp3),
        writing_minutes=_minutes(WRITE_MINUTES_FULL, size, wp1 + wp2),
    )


def custom_counts(
    *,
    listening_p1: int = 0,
    listening_p2: int = 0,
    reading_p1: int = 0,
    reading_p2: int = 0,
    reading_p3: int = 0,
    writing_p1: int = 0,
    writing_keywords: int = 0,
    writing_picture: int = 0,
    size: int | None = None,
) -> PartCounts:
    caps = {
        "listening_p1": 45,
        "listening_p2": 45,
        "reading_p1": 30,
        "reading_p2": 20,
        "reading_p3": 30,
        "writing_p1": 20,
        "writing_keywords": 10,
        "writing_picture": 20,
    }
    vals = {
        "listening_p1": listening_p1,
        "listening_p2": listening_p2,
        "reading_p1": reading_p1,
        "reading_p2": reading_p2,
        "reading_p3": reading_p3,
        "writing_p1": writing_p1,
        "writing_keywords": writing_keywords,
        "writing_picture": writing_picture,
    }
    for k, v in vals.items():
        if v < 0 or v > caps[k]:
            raise ValueError(f"{k} must be 0..{caps[k]}")
    total = sum(vals.values())
    if total <= 0:
        raise ValueError("need at least one item")
    sz = size if size is not None else min(100, max(1, total))
    wp2 = writing_keywords + writing_picture
    return PartCounts(
        size=sz,
        listening_p1=listening_p1,
        listening_p2=listening_p2,
        reading_p1=reading_p1,
        reading_p2=reading_p2,
        reading_p3=reading_p3,
        writing_p1=writing_p1,
        writing_keywords=writing_keywords,
        writing_picture=writing_picture,
        writing_p2=wp2,
        listening_minutes=_minutes(LISTEN_MINUTES_FULL, sz, listening_p1 + listening_p2),
        reading_minutes=_minutes(READ_MINUTES_FULL, sz, reading_p1 + reading_p2 + reading_p3),
        writing_minutes=_minutes(WRITE_MINUTES_FULL, sz, writing_p1 + wp2),
    )


def _equal_points(n: int, total: float = SECTION_TOTAL) -> tuple[float, ...]:
    if n <= 0:
        return ()
    each = total / n
    pts = [each] * (n - 1)
    pts.append(total - sum(pts))
    return tuple(pts)


def writing_item_points(p1: int, p2: int) -> tuple[float, float]:
    n = p1 + p2
    if n == 0:
        return (0.0, 0.0)
    base = p1 * P1_BASE + p2 * P2_BASE
    extra = (SECTION_TOTAL - base) / n
    return (
        (P1_BASE + extra) if p1 else 0.0,
        (P2_BASE + extra) if p2 else 0.0,
    )


def score_weights(counts: PartCounts) -> ScoreWeights:
    p1, p2 = writing_item_points(counts.writing_p1, counts.writing_p2)
    return ScoreWeights(
        listening=_equal_points(counts.listening_total),
        reading=_equal_points(counts.reading_total),
        writing_p1=p1,
        writing_p2=p2,
    )


def counts_for(size: int | None = None, parts: dict[str, int] | None = None) -> PartCounts:
    if parts is not None:
        return custom_counts(size=size, **parts)
    if size is None:
        size = 10
    return scale_counts(size)
