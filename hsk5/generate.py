from __future__ import annotations

import os
import random
import threading
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Literal, Protocol, TypeVar, cast

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
from hsk5.scale import PartCounts, counts_for
from hsk5.store import now_iso
from hsk5.exemplars import format_exemplars
from hsk5.vocab import ALLOWED_PROPER, Vocab, load_vocab

T = TypeVar("T", bound=BaseModel)
U = TypeVar("U")
ReportFn = Callable[[str, str], None]
SYSTEM = (
    "You write HSK 2.0 Level 5 (五级) exam items. Use only the provided vocabulary "
    "plus allowed Chinese person names from the prompt and digits. Simplified Chinese. "
    "Write natural everyday Chinese like official HSK5: idiomatic collocations, normal "
    "word order, fluent dialogue; avoid stiff, literal, or machine-translated phrasing. "
    "Vary who appears: do not reuse the same person across items when possible. "
    "Difficulty matches official HSK5. Four choices A-D, one correct. "
    "Each item must be a new situation, not a rewrite of a previous one. "
    "When style exemplars are given, match their naturalness and diversity of situations, "
    "but invent original content — never copy exemplar plots or wording. "
    "Do not include English in item text (except picture image prompts when asked). "
    "Output JSON that matches the schema."
)


def shuffle_proper_names(rng: random.Random | None = None) -> list[str]:
    pool = list(ALLOWED_PROPER)
    (rng or random.Random()).shuffle(pool)
    return pool


def _names_for_slot(index: int, k: int = 2, *, pool: list[str] | None = None) -> list[str]:
    names = pool if pool is not None else sorted(ALLOWED_PROPER)
    n = len(names)
    if n == 0:
        return []
    k = min(k, n)
    start = (index * k) % n
    return [names[(start + j) % n] for j in range(k)]


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


class ListeningQOut(_Strict):
    question: str
    choices: list[ChoiceOut]
    answer: ChoiceKey


class ListeningClipOut(_Strict):
    lines: list[LineOut]
    questions: list[ListeningQOut]


class ClozeBlankOut(_Strict):
    choices: list[ChoiceOut]
    answer: ChoiceKey


class ClozePassageOut(_Strict):
    text: str
    blanks: list[ClozeBlankOut]


class ReadingShortOut(_Strict):
    text: str
    choices: list[ChoiceOut]
    answer: ChoiceKey


class ReadingLongOut(_Strict):
    text: str
    questions: list[ListeningQOut]


class SentenceOut(_Strict):
    words: list[str]
    gold: str


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


def _slot_user(
    vocab: Vocab,
    extra: str,
    avoid: list[str],
    index: int,
    total: int,
    *,
    count: int = 1,
    name_pool: list[str] | None = None,
    part: str | None = None,
) -> str:
    names = "、".join(_names_for_slot(index, pool=name_pool))
    slotted = (
        f"{extra} This is empty slot {index + 1} of {total}; invent a distinct situation for this slot only. "
        f"If the item needs person names, use only these for this slot: {names}. "
        "Do not invent other names."
    )
    if part:
        ex = format_exemplars(part)
        if ex:
            slotted = f"{slotted}\n{ex}"
    return _user(count, vocab, slotted, avoid)


def _parallel_map(
    n: int,
    fn: Callable[[int], U],
    *,
    label: str,
    note: Callable[[str, str], None],
    concurrency: int | None = None,
) -> list[U]:
    """Fill n slots with fn(i), preserve order, report completions."""
    if n <= 0:
        return []
    workers = concurrency or gen_concurrency()
    if n == 1 or workers <= 1:
        out: list[U] = []
        for i in range(n):
            note(label, f"{i + 1}/{n}")
            out.append(fn(i))
        return out

    missing: object = object()
    slots: list[object] = [missing] * n
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
    if any(slot is missing for slot in slots):
        raise RuntimeError(f"parallel map incomplete for {label}")
    return cast(list[U], slots)


def _run_part(
    n: int,
    *,
    label: str,
    note: Callable[[str, str], None],
    used: list[str],
    build: Callable[[int, int, list[str]], tuple[U, str]],
) -> list[U]:
    """Build n items in parallel; append themes to used after the wave."""
    avoid = list(used)

    def fn(i: int) -> tuple[U, str]:
        return build(i, n, avoid)

    rows = _parallel_map(n, fn, label=label, note=note)
    items: list[U] = []
    for item, theme in rows:
        items.append(item)
        used.append(theme)
    return items


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
    if counts.writing_keywords or counts.writing_picture:
        steps.append("作文の課題")
    if counts.listening_total:
        steps.append("音声合成")
    if counts.writing_picture:
        steps.append("看图の画像")
    steps.append("保存")
    return steps


def _listening_pair(
    *,
    part: Literal["p1", "p2"],
    item_part: str,
    lines: list[SpeakerLine],
    question: str,
    choices: list[Choice],
    answer: ChoiceKey,
) -> tuple[tuple[ListeningClip, McqItem], str]:
    clip_id = new_id()
    item_id = new_id()
    clip = ListeningClip(
        id=clip_id,
        part=part,
        lines=lines,
        question_text=question,
        item_ids=[item_id],
    )
    item = McqItem(
        id=item_id,
        part=item_part,
        prompt="",
        choices=choices,
        answer=answer,
        clip_id=clip_id,
        transcript=_transcript(lines, question),
    )
    return (clip, item), _theme(question, *(ln.text for ln in lines))


def generate_exam(
    exam_id: str,
    size: int,
    *,
    mode: str = "full",
    parts: dict[str, int] | None = None,
    llm: LLM | None = None,
    report: ReportFn | None = None,
) -> Exam:
    llm = llm or GrokLLM()
    vocab = load_vocab()
    name_pool = shuffle_proper_names()
    counts = counts_for(size=size, parts=parts)
    if parts is not None:
        mode = "custom"
    created = now_iso()
    clips: list[ListeningClip] = []
    listening: list[McqItem] = []
    reading: list[McqItem] = []
    sentences: list[SentenceOrderItem] = []
    essays: list[EssayItem] = []
    used: list[str] = []

    def note(label: str, detail: str = "") -> None:
        if report:
            report(label, detail)

    def build_lp1(i: int, n: int, avoid: list[str]) -> tuple[tuple[ListeningClip, McqItem], str]:
        raw = _parse(
            llm,
            ListeningItemOut,
            vocab,
            _slot_user(
                vocab,
                "One short two-person dialogue. One question. Third person asks.",
                avoid,
                i,
                n,
                name_pool=name_pool,
                part="listening_p1",
            ),
        )
        return _listening_pair(
            part="p1",
            item_part="listening_p1",
            lines=_lines(raw.lines),
            question=raw.question,
            choices=_choices(raw.choices),
            answer=raw.answer,
        )

    def build_lp2(i: int, n: int, avoid: list[str]) -> tuple[tuple[ListeningClip, McqItem], str]:
        raw = _parse(
            llm,
            ListeningClipOut,
            vocab,
            _slot_user(
                vocab,
                "One clip of 4-5 sentences (dialogue or monologue) with exactly one question.",
                avoid,
                i,
                n,
                name_pool=name_pool,
                part="listening_p2",
            ),
        )
        if not raw.questions:
            raise RuntimeError("listening p2 missing question")
        q = raw.questions[0]
        return _listening_pair(
            part="p2",
            item_part="listening_p2",
            lines=_lines(raw.lines),
            question=q.question,
            choices=_choices(q.choices),
            answer=q.answer,
        )

    def build_rp1(i: int, n: int, avoid: list[str]) -> tuple[McqItem, str]:
        passage = _parse(
            llm,
            ClozePassageOut,
            vocab,
            _slot_user(
                vocab,
                "One short cloze passage with exactly one blank marked ____.",
                avoid,
                i,
                n,
                name_pool=name_pool,
                part="reading_p1",
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

    def build_rp2(i: int, n: int, avoid: list[str]) -> tuple[McqItem, str]:
        raw = _parse(
            llm,
            ReadingShortOut,
            vocab,
            _slot_user(
                vocab,
                "One short paragraph. Choose the statement that matches.",
                avoid,
                i,
                n,
                name_pool=name_pool,
                part="reading_p2",
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

    def build_rp3(i: int, n: int, avoid: list[str]) -> tuple[McqItem, str]:
        passage = _parse(
            llm,
            ReadingLongOut,
            vocab,
            _slot_user(
                vocab,
                "One longer passage with exactly one multiple-choice question.",
                avoid,
                i,
                n,
                name_pool=name_pool,
                part="reading_p3",
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

    def build_wp1(i: int, n: int, avoid: list[str]) -> tuple[SentenceOrderItem, str]:
        raw = _parse(
            llm,
            SentenceOut,
            vocab,
            _slot_user(
                vocab,
                "One sentence-reordering item. words is shuffled; gold is the correct sentence.",
                avoid,
                i,
                n,
                name_pool=name_pool,
                part="writing_p1",
            ),
        )
        return SentenceOrderItem(id=new_id(), words=list(raw.words), gold=raw.gold), _theme(raw.gold)

    def build_keywords(i: int, n: int, avoid: list[str]) -> tuple[EssayItem, str]:
        kw = _parse(
            llm,
            KeywordsOut,
            vocab,
            _user(
                5,
                vocab,
                "Five related HSK5 words for an 80-character essay.\n" + format_exemplars("writing_keywords"),
                avoid,
            ),
        )
        return EssayItem(id=new_id(), kind="keywords", required_words=list(kw.words)[:5]), _theme(*kw.words)

    def build_picture(i: int, n: int, avoid: list[str]) -> tuple[EssayItem, str]:
        pic = _parse(
            llm,
            PictureOut,
            vocab,
            _user(
                1,
                vocab,
                "English photo prompt of a simple everyday scene. No text in the image.\n"
                + format_exemplars("writing_picture"),
                avoid,
            ),
        )
        img = f"writing-{i + 1}.png"
        return (
            EssayItem(id=new_id(), kind="picture", image_prompt=pic.prompt, image_name=img),
            _theme(pic.prompt),
        )

    for clip, item in _run_part(counts.listening_p1, label="听力 第1部分", note=note, used=used, build=build_lp1):
        clips.append(clip)
        listening.append(item)
    for clip, item in _run_part(counts.listening_p2, label="听力 第2部分", note=note, used=used, build=build_lp2):
        clips.append(clip)
        listening.append(item)
    reading.extend(_run_part(counts.reading_p1, label="阅读 空所補充", note=note, used=used, build=build_rp1))
    reading.extend(_run_part(counts.reading_p2, label="阅读 短文", note=note, used=used, build=build_rp2))
    reading.extend(_run_part(counts.reading_p3, label="阅读 長文", note=note, used=used, build=build_rp3))
    sentences.extend(_run_part(counts.writing_p1, label="連詞成句", note=note, used=used, build=build_wp1))
    if counts.writing_keywords:
        essays.extend(
            _run_part(counts.writing_keywords, label="作文の課題", note=note, used=used, build=build_keywords)
        )
    if counts.writing_picture:
        essays.extend(_run_part(counts.writing_picture, label="作文の課題", note=note, used=used, build=build_picture))

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
        mode=mode,
        counts=counts,
        clips=clips,
        listening=listening,
        reading=reading,
        sentence_order=sentences,
        essays=essays,
    )


def attach_media(exam: Exam, report: ReportFn | None = None) -> None:
    def note(label: str, detail: str = "") -> None:
        if report:
            report(label, detail)

    def one_clip(i: int) -> None:
        clip = exam.clips[i]
        chunks: list[bytes] = []
        for ln in clip.lines:
            part = tts.synth(ln.text, tts.voice_for(ln.speaker))
            if len(part) < 16:
                raise RuntimeError("empty audio")
            chunks.append(part)
        if clip.question_text:
            part = tts.synth(clip.question_text, tts.voice_for("NARR"))
            if len(part) < 16:
                raise RuntimeError("empty audio")
            chunks.append(part)
        if not chunks:
            raise RuntimeError("empty audio")
        audio = b"".join(chunks)
        store.audio_path(exam.id, clip.id).write_bytes(audio)

    _parallel_map(len(exam.clips), one_clip, label="音声合成", note=note)

    for essay in exam.essays:
        if essay.kind != "picture":
            continue
        if report:
            report("看图の画像", "")
        prompt = essay.image_prompt or "Photorealistic candid photo of two people talking in a city park, no text"
        blob = imagine.generate_image(prompt)
        if len(blob) < 32:
            raise RuntimeError("empty image")
        name = essay.image_name or "writing.png"
        store.image_path(exam.id, name).write_bytes(blob)
        essay.image_name = name
