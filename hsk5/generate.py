from __future__ import annotations

import os
import threading
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Literal, Protocol, TypeVar

from pydantic import BaseModel, ConfigDict, Field

from hsk5 import grok, imagine, store, tts
from hsk5.ids import new_id
from hsk5.models import (
    Choice,
    ChoiceKey,
    EssayItem,
    Exam,
    ListeningClip,
    McqItem,
    SentenceOrderItem,
    SpeakerLine,
)
from hsk5.scale import PartCounts, scale_counts
from hsk5.store import now_iso
from hsk5.vocab import Vocab, load_vocab

T = TypeVar("T", bound=BaseModel)
U = TypeVar("U")
ReportFn = Callable[[str, str], None]
SYSTEM = (
    "You write HSK 2.0 Level 5 (五级) exam items. Use only the provided vocabulary "
    "plus allowed names 小王/小李/小张/王明/李华 and digits. Simplified Chinese. "
    "Difficulty matches official HSK5. Four choices A-D, one correct. "
    "Each item must be a new situation, not a rewrite of a previous one. "
    "Do not include English. Output JSON that matches the schema."
)


def gen_concurrency() -> int:
    raw = os.environ.get("HSK5_GEN_CONCURRENCY", "4").strip() or "4"
    try:
        return max(1, min(16, int(raw)))
    except ValueError:
        return 4


class LLM(Protocol):
    def parse(self, model_type: type[T], system: str, user: str) -> T: ...


class GrokLLM:
    def parse(self, model_type: type[T], system: str, user: str) -> T:
        return grok.parse(model_type, system, user)


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ChoiceOut(_Strict):
    key: ChoiceKey
    text: str


class LineOut(_Strict):
    speaker: Literal["F1", "M1", "NARR"]
    text: str


class ListeningItemOut(_Strict):
    lines: list[LineOut]
    question: str
    choices: list[ChoiceOut]
    answer: ChoiceKey


class ListeningP1Out(_Strict):
    items: list[ListeningItemOut]


class ListeningQOut(_Strict):
    question: str
    choices: list[ChoiceOut]
    answer: ChoiceKey


class ListeningClipOut(_Strict):
    lines: list[LineOut]
    questions: list[ListeningQOut]


class ListeningP2Out(_Strict):
    clips: list[ListeningClipOut]


class ClozeBlankOut(_Strict):
    choices: list[ChoiceOut]
    answer: ChoiceKey


class ClozePassageOut(_Strict):
    text: str
    blanks: list[ClozeBlankOut]


class ReadingP1Out(_Strict):
    passages: list[ClozePassageOut]


class ReadingShortOut(_Strict):
    text: str
    choices: list[ChoiceOut]
    answer: ChoiceKey


class ReadingP2Out(_Strict):
    items: list[ReadingShortOut]


class ReadingLongOut(_Strict):
    text: str
    questions: list[ListeningQOut]


class ReadingP3Out(_Strict):
    passages: list[ReadingLongOut]


class SentenceOut(_Strict):
    words: list[str]
    gold: str


class WritingP1Out(_Strict):
    items: list[SentenceOut]


class KeywordsOut(_Strict):
    words: list[str] = Field(min_length=5, max_length=5)


class PictureOut(_Strict):
    prompt: str


def _vocab_block(vocab: Vocab, k: int = 200) -> str:
    sample = vocab.sample(k)
    return "Allowed words:\n" + "、".join(sample)


def _user(count: int, vocab: Vocab, extra: str, used: list[str] | None = None) -> str:
    parts = [f"count={count}", _vocab_block(vocab, 80), extra]
    if used:
        parts.append("Do not repeat these topics or situations:\n" + "\n".join(f"- {t}" for t in used[-20:]))
    return "\n".join(parts)


def _theme(*parts: str) -> str:
    blob = " ".join(p.strip() for p in parts if p and p.strip())
    return blob[:48]


def _text_of(model: BaseModel) -> str:
    return model.model_dump_json()


def _parse(llm: LLM, model_type: type[T], vocab: Vocab, user: str) -> T:
    last_oov: list[str] = []
    out: T | None = None
    for attempt in range(3):
        prompt = user
        if last_oov:
            prompt += "\nDo not use: " + "、".join(last_oov[:30])
        out = llm.parse(model_type, SYSTEM, prompt)
        last_oov = vocab.oov(_text_of(out))
        if not last_oov:
            return out
    assert out is not None
    raise RuntimeError(f"OOV remaining after retries: {last_oov[:20]}")


def _choices(raw: list[ChoiceOut]) -> list[Choice]:
    return [Choice(key=c.key, text=c.text) for c in raw]


def _lines(raw: list[LineOut]) -> list[SpeakerLine]:
    return [SpeakerLine(speaker=ln.speaker, text=ln.text) for ln in raw]


def _transcript(lines: list[SpeakerLine], question: str) -> str:
    body = "\n".join(f"{ln.speaker}: {ln.text}" for ln in lines)
    return body + f"\nNARR: {question}"


def _slot_extra(extra: str, index: int, total: int) -> str:
    return f"{extra} This is empty slot {index + 1} of {total}; invent a distinct situation for this slot only."


def _parallel_map(
    n: int,
    fn: Callable[[int], U],
    *,
    label: str,
    note: Callable[[str, str], None],
    concurrency: int | None = None,
) -> list[U]:
    """Fill n empty slots with fn(i), preserving order. Progress counts completions."""
    if n <= 0:
        return []
    workers = concurrency or gen_concurrency()
    if n == 1 or workers <= 1:
        out: list[U] = []
        for i in range(n):
            note(label, f"{i + 1}/{n}")
            out.append(fn(i))
        return out

    slots: list[U | None] = [None] * n
    done = 0
    lock = threading.Lock()
    note(label, f"0/{n}")

    with ThreadPoolExecutor(max_workers=min(workers, n)) as pool:
        futures = {pool.submit(fn, i): i for i in range(n)}
        for fut in as_completed(futures):
            i = futures[fut]
            slots[i] = fut.result()
            with lock:
                done += 1
                note(label, f"{done}/{n}")
    return [slot for slot in slots if slot is not None]  # all filled; keep type narrow


def planned_steps(counts: PartCounts) -> list[str]:
    steps: list[str] = []
    if counts.listening_p1:
        steps.append("听力 第1部分")
    if counts.listening_p2:
        steps.append("听力 第2部分")
    if counts.reading_p1:
        steps.append("阅读 空所補充")
    if counts.reading_p2:
        steps.append("阅读 短文")
    if counts.reading_p3:
        steps.append("阅读 長文")
    if counts.writing_p1:
        steps.append("連詞成句")
    if counts.writing_p2:
        steps.append("作文の課題")
    if counts.listening_total:
        steps.append("音声合成")
    if counts.writing_p2 >= 2:
        steps.append("看图の画像")
    steps.append("保存")
    return steps


def generate_exam(exam_id: str, size: int, *, llm: LLM | None = None, report: ReportFn | None = None) -> Exam:
    llm = llm or GrokLLM()
    vocab = load_vocab()
    counts = scale_counts(size)
    created = now_iso()
    clips: list[ListeningClip] = []
    listening: list[McqItem] = []
    reading: list[McqItem] = []
    sentences: list[SentenceOrderItem] = []
    essays: list[EssayItem] = []
    used: list[str] = []

    def _note(label: str, detail: str = "") -> None:
        if report:
            report(label, detail)

    def _avoid() -> list[str]:
        return list(used)

    # --- listening p1 ---
    n = counts.listening_p1
    avoid = _avoid()

    def _lp1(i: int) -> tuple[ListeningClip, McqItem, str]:
        raw = _parse(
            llm,
            ListeningItemOut,
            vocab,
            _user(
                1,
                vocab,
                _slot_extra(
                    "One short two-person dialogue. One question. Third person asks.",
                    i,
                    n,
                ),
                avoid,
            ),
        )
        clip_id = new_id()
        item_id = new_id()
        lines = _lines(raw.lines)
        clip = ListeningClip(
            id=clip_id,
            part="p1",
            lines=lines,
            question_text=raw.question,
            item_ids=[item_id],
        )
        item = McqItem(
            id=item_id,
            part="listening_p1",
            prompt="",
            choices=_choices(raw.choices),
            answer=raw.answer,
            clip_id=clip_id,
            transcript=_transcript(lines, raw.question),
        )
        return clip, item, _theme(raw.question, *(ln.text for ln in raw.lines))

    for clip, item, theme in _parallel_map(n, _lp1, label="听力 第1部分", note=_note):
        clips.append(clip)
        listening.append(item)
        used.append(theme)

    # --- listening p2 ---
    n = counts.listening_p2
    avoid = _avoid()

    def _lp2(i: int) -> tuple[ListeningClip, McqItem, str]:
        raw = _parse(
            llm,
            ListeningClipOut,
            vocab,
            _user(
                1,
                vocab,
                _slot_extra(
                    "One clip of 4-5 sentences (dialogue or monologue) with exactly one question.",
                    i,
                    n,
                ),
                avoid,
            ),
        )
        qs = raw.questions[:1]
        if not qs:
            raise RuntimeError("listening p2 missing question")
        clip_id = new_id()
        item_id = new_id()
        lines = _lines(raw.lines)
        q = qs[0]
        clip = ListeningClip(
            id=clip_id,
            part="p2",
            lines=lines,
            question_text=q.question,
            item_ids=[item_id],
        )
        item = McqItem(
            id=item_id,
            part="listening_p2",
            prompt="",
            choices=_choices(q.choices),
            answer=q.answer,
            clip_id=clip_id,
            transcript=_transcript(lines, q.question),
        )
        return clip, item, _theme(q.question, *(ln.text for ln in raw.lines))

    for clip, item, theme in _parallel_map(n, _lp2, label="听力 第2部分", note=_note):
        clips.append(clip)
        listening.append(item)
        used.append(theme)

    # --- reading p1 ---
    n = counts.reading_p1
    avoid = _avoid()

    def _rp1(i: int) -> tuple[McqItem, str]:
        passage = _parse(
            llm,
            ClozePassageOut,
            vocab,
            _user(
                1,
                vocab,
                _slot_extra("One short cloze passage with exactly one blank marked ____.", i, n),
                avoid,
            ),
        )
        if not passage.blanks:
            raise RuntimeError("cloze missing blank")
        blank = passage.blanks[0]
        item = McqItem(
            id=new_id(),
            part="reading_p1",
            prompt="选择合适的词语填空。",
            passage=passage.text,
            choices=_choices(blank.choices),
            answer=blank.answer,
        )
        return item, _theme(passage.text)

    for item, theme in _parallel_map(n, _rp1, label="阅读 空所補充", note=_note):
        reading.append(item)
        used.append(theme)

    # --- reading p2 ---
    n = counts.reading_p2
    avoid = _avoid()

    def _rp2(i: int) -> tuple[McqItem, str]:
        raw = _parse(
            llm,
            ReadingShortOut,
            vocab,
            _user(
                1,
                vocab,
                _slot_extra("One short paragraph. Choose the statement that matches.", i, n),
                avoid,
            ),
        )
        item = McqItem(
            id=new_id(),
            part="reading_p2",
            prompt="选择与短文内容一致的一项。",
            passage=raw.text,
            choices=_choices(raw.choices),
            answer=raw.answer,
        )
        return item, _theme(raw.text)

    for item, theme in _parallel_map(n, _rp2, label="阅读 短文", note=_note):
        reading.append(item)
        used.append(theme)

    # --- reading p3 ---
    n = counts.reading_p3
    avoid = _avoid()

    def _rp3(i: int) -> tuple[McqItem, str]:
        passage = _parse(
            llm,
            ReadingLongOut,
            vocab,
            _user(
                1,
                vocab,
                _slot_extra("One longer passage with exactly one multiple-choice question.", i, n),
                avoid,
            ),
        )
        if not passage.questions:
            raise RuntimeError("reading p3 missing question")
        q = passage.questions[0]
        item = McqItem(
            id=new_id(),
            part="reading_p3",
            prompt=q.question,
            passage=passage.text,
            choices=_choices(q.choices),
            answer=q.answer,
        )
        return item, _theme(q.question, passage.text)

    for item, theme in _parallel_map(n, _rp3, label="阅读 長文", note=_note):
        reading.append(item)
        used.append(theme)

    # --- writing p1 ---
    n = counts.writing_p1
    avoid = _avoid()

    def _wp1(i: int) -> tuple[SentenceOrderItem, str]:
        raw = _parse(
            llm,
            SentenceOut,
            vocab,
            _user(
                1,
                vocab,
                _slot_extra(
                    "One sentence-reordering item. words is shuffled; gold is the correct sentence.",
                    i,
                    n,
                ),
                avoid,
            ),
        )
        return SentenceOrderItem(id=new_id(), words=list(raw.words), gold=raw.gold), _theme(raw.gold)

    for item, theme in _parallel_map(n, _wp1, label="連詞成句", note=_note):
        sentences.append(item)
        used.append(theme)

    # writing p2: at most 2, run in parallel when both needed
    if counts.writing_p2 >= 1:
        avoid = _avoid()
        n_essays = counts.writing_p2

        def _essay(i: int) -> tuple[EssayItem, str]:
            if i == 0:
                kw = _parse(
                    llm,
                    KeywordsOut,
                    vocab,
                    _user(5, vocab, "Five related HSK5 words for an 80-character essay.", avoid),
                )
                return (
                    EssayItem(id=new_id(), kind="keywords", required_words=list(kw.words)[:5]),
                    _theme(*kw.words),
                )
            pic = _parse(
                llm,
                PictureOut,
                vocab,
                _user(
                    1,
                    vocab,
                    "English photo prompt of a simple everyday scene. No text in the image.",
                    avoid,
                ),
            )
            return (
                EssayItem(id=new_id(), kind="picture", image_prompt=pic.prompt, image_name="writing.png"),
                _theme(pic.prompt),
            )

        for item, theme in _parallel_map(n_essays, _essay, label="作文の課題", note=_note):
            essays.append(item)
            used.append(theme)

    if len(listening) != counts.listening_total:
        raise RuntimeError("listening count mismatch")
    if len(reading) != counts.reading_total:
        raise RuntimeError("reading count mismatch")
    if len(sentences) != counts.writing_p1:
        raise RuntimeError("writing p1 count mismatch")
    if len(essays) != counts.writing_p2:
        raise RuntimeError("writing p2 count mismatch")
    return Exam(
        id=exam_id,
        size=size,
        created_at=created,
        counts=counts,
        clips=clips,
        listening=listening,
        reading=reading,
        sentence_order=sentences,
        essays=essays,
    )


def attach_media(exam: Exam, report: ReportFn | None = None) -> None:
    nclips = len(exam.clips)

    def _note(label: str, detail: str = "") -> None:
        if report:
            report(label, detail)

    def _one_clip(i: int) -> None:
        clip = exam.clips[i]
        spoken = [ln.text for ln in clip.lines]
        if clip.question_text:
            spoken.append(clip.question_text)
        audio = tts.synth("\n".join(spoken), tts.voice_for("NARR"))
        if len(audio) < 16:
            raise RuntimeError("empty audio")
        store.audio_path(exam.id, clip.id).write_bytes(audio)

    _parallel_map(nclips, _one_clip, label="音声合成", note=_note)

    for essay in exam.essays:
        if essay.kind == "picture":
            if report:
                report("看图の画像", "")
            prompt = essay.image_prompt or "Photorealistic candid photo of two people talking in a city park, no text"
            blob = imagine.generate_image(prompt)
            if len(blob) < 32:
                raise RuntimeError("empty image")
            name = essay.image_name or "writing.png"
            store.image_path(exam.id, name).write_bytes(blob)
            essay.image_name = name
