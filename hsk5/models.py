from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from hsk5.scale import PartCounts, scale_counts

ChoiceKey = Literal["A", "B", "C", "D"]
Speaker = Literal["F1", "M1", "NARR"]
EssayKind = Literal["keywords", "picture"]
Band = Literal["zero", "low", "mid", "high"]
ExamStatus = Literal["generating", "ready", "failed"]


class Choice(BaseModel):
    key: ChoiceKey
    text: str


class SpeakerLine(BaseModel):
    speaker: Speaker
    text: str


class ListeningClip(BaseModel):
    id: str
    part: Literal["p1", "p2"]
    lines: list[SpeakerLine]
    question_text: str
    item_ids: list[str]


class McqItem(BaseModel):
    id: str
    part: str
    prompt: str = ""
    passage: str | None = None
    choices: list[Choice]
    answer: ChoiceKey
    clip_id: str | None = None
    transcript: str | None = None


class SentenceOrderItem(BaseModel):
    id: str
    words: list[str]
    gold: str


class EssayItem(BaseModel):
    id: str
    kind: EssayKind
    required_words: list[str] = Field(default_factory=list)
    image_name: str | None = None
    image_prompt: str | None = None


class Exam(BaseModel):
    id: str
    size: int
    created_at: str
    mode: str = "full"
    counts: PartCounts
    clips: list[ListeningClip] = Field(default_factory=list)
    listening: list[McqItem] = Field(default_factory=list)
    reading: list[McqItem] = Field(default_factory=list)
    sentence_order: list[SentenceOrderItem] = Field(default_factory=list)
    essays: list[EssayItem] = Field(default_factory=list)

    def to_public(self, prefix: str = "") -> dict[str, Any]:
        clips = [{"id": c.id, "part": c.part, "item_ids": list(c.item_ids)} for c in self.clips]
        listening = [
            {
                "id": it.id,
                "part": it.part,
                "prompt": it.prompt,
                "choices": [ch.model_dump() for ch in it.choices],
                "clip_id": it.clip_id,
            }
            for it in self.listening
        ]
        reading = [
            {
                "id": it.id,
                "part": it.part,
                "prompt": it.prompt,
                "passage": it.passage,
                "choices": [ch.model_dump() for ch in it.choices],
            }
            for it in self.reading
        ]
        sentence_order = [{"id": it.id, "words": list(it.words)} for it in self.sentence_order]
        essays = [
            {
                "id": it.id,
                "kind": it.kind,
                "required_words": list(it.required_words),
                "image_url": (f"{prefix}/api/exams/{self.id}/images/{it.image_name}" if it.image_name else None),
            }
            for it in self.essays
        ]
        return {
            "id": self.id,
            "size": self.size,
            "mode": self.mode,
            "created_at": self.created_at,
            "status": "ready",
            "limits": {
                "listening_minutes": self.counts.listening_minutes,
                "reading_minutes": self.counts.reading_minutes,
                "writing_minutes": self.counts.writing_minutes,
            },
            "clips": clips,
            "listening": listening,
            "reading": reading,
            "sentence_order": sentence_order,
            "essays": essays,
        }


class EssayGrokOut(BaseModel):
    band: Band
    score: int
    char_count: int
    used_required_words: list[str] = Field(default_factory=list)
    related_to_image: bool | None = None
    grammar_ok: bool = True
    coherent: bool = True
    comment_ja: str = ""


class SubmitIn(BaseModel):
    mcq: dict[str, str] = Field(default_factory=dict)
    sentence: dict[str, str] = Field(default_factory=dict)
    essay: dict[str, str] = Field(default_factory=dict)


class PartsIn(BaseModel):
    listening_p1: int = Field(0, ge=0, le=45)
    listening_p2: int = Field(0, ge=0, le=45)
    reading_p1: int = Field(0, ge=0, le=30)
    reading_p2: int = Field(0, ge=0, le=20)
    reading_p3: int = Field(0, ge=0, le=30)
    writing_p1: int = Field(0, ge=0, le=20)
    writing_keywords: int = Field(0, ge=0, le=10)
    writing_picture: int = Field(0, ge=0, le=20)

    @property
    def total(self) -> int:
        return (
            self.listening_p1
            + self.listening_p2
            + self.reading_p1
            + self.reading_p2
            + self.reading_p3
            + self.writing_p1
            + self.writing_keywords
            + self.writing_picture
        )


class CreateIn(BaseModel):
    size: int = Field(default=10, ge=1, le=100)
    parts: PartsIn | None = None

    @model_validator(mode="after")
    def _parts_not_empty(self) -> CreateIn:
        if self.parts is not None and self.parts.total <= 0:
            raise ValueError("need at least one item")
        return self

    def resolved_mode(self) -> str:
        return "custom" if self.parts is not None else "full"


def counts_from_exam_size(size: int, parts: PartsIn | None = None) -> PartCounts:
    from hsk5.scale import counts_for

    if parts is None:
        return counts_for(size=size)
    return counts_for(
        size=size,
        parts={
            "listening_p1": parts.listening_p1,
            "listening_p2": parts.listening_p2,
            "reading_p1": parts.reading_p1,
            "reading_p2": parts.reading_p2,
            "reading_p3": parts.reading_p3,
            "writing_p1": parts.writing_p1,
            "writing_keywords": parts.writing_keywords,
            "writing_picture": parts.writing_picture,
        },
    )
