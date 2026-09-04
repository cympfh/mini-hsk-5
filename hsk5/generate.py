from __future__ import annotations

from collections.abc import Callable
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
ReportFn = Callable[[str, str], None]
SYSTEM = (
    "You write HSK 2.0 Level 5 (五级) exam items. Use only the provided vocabulary "
    "plus allowed names 小王/小李/小张/王明/李华 and digits. Simplified Chinese. "
    "Difficulty matches official HSK5. Four choices A-D, one correct. "
    "Do not include English. Output JSON that matches the schema."
)


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


def _user(count: int, vocab: Vocab, extra: str) -> str:
    return f"count={count}\n{_vocab_block(vocab)}\n{extra}"


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

    def _note(label: str, detail: str = "") -> None:
        if report:
            report(label, detail)

    if counts.listening_p1:
        _note("听力 第1部分")
        p1 = _parse(
            llm,
            ListeningP1Out,
            vocab,
            _user(counts.listening_p1, vocab, "Short two-person dialogues. One question each. Third person asks."),
        )
        for raw in p1.items[: counts.listening_p1]:
            clip_id = new_id()
            item_id = new_id()
            lines = _lines(raw.lines)
            clips.append(
                ListeningClip(
                    id=clip_id,
                    part="p1",
                    lines=lines,
                    question_text=raw.question,
                    item_ids=[item_id],
                )
            )
            listening.append(
                McqItem(
                    id=item_id,
                    part="listening_p1",
                    prompt="",
                    choices=_choices(raw.choices),
                    answer=raw.answer,
                    clip_id=clip_id,
                    transcript=_transcript(lines, raw.question),
                )
            )

    if counts.listening_p2:
        _note("听力 第2部分")
        p2 = _parse(
            llm,
            ListeningP2Out,
            vocab,
            _user(
                counts.listening_p2,
                vocab,
                "Longer clips of 4-5 sentences. Total questions across clips must equal count. Each clip 1-4 questions.",
            ),
        )
        remaining = counts.listening_p2
        for raw in p2.clips:
            if remaining <= 0:
                break
            clip_id = new_id()
            qs = raw.questions[:remaining]
            item_ids: list[str] = []
            lines = _lines(raw.lines)
            for q in qs:
                item_id = new_id()
                item_ids.append(item_id)
                listening.append(
                    McqItem(
                        id=item_id,
                        part="listening_p2",
                        prompt="",
                        choices=_choices(q.choices),
                        answer=q.answer,
                        clip_id=clip_id,
                        transcript=_transcript(lines, q.question),
                    )
                )
            clips.append(
                ListeningClip(
                    id=clip_id,
                    part="p2",
                    lines=lines,
                    question_text=" ".join(q.question for q in qs),
                    item_ids=item_ids,
                )
            )
            remaining -= len(qs)

    if counts.reading_p1:
        _note("阅读 空所補充")
        r1 = _parse(
            llm,
            ReadingP1Out,
            vocab,
            _user(
                counts.reading_p1,
                vocab,
                "Cloze passages. text uses ____ for each blank, in order. Total blanks = count.",
            ),
        )
        blanks_left = counts.reading_p1
        for passage in r1.passages:
            for blank in passage.blanks:
                if blanks_left <= 0:
                    break
                reading.append(
                    McqItem(
                        id=new_id(),
                        part="reading_p1",
                        prompt="选择合适的词语填空。",
                        passage=passage.text,
                        choices=_choices(blank.choices),
                        answer=blank.answer,
                    )
                )
                blanks_left -= 1

    if counts.reading_p2:
        _note("阅读 短文")
        r2 = _parse(
            llm,
            ReadingP2Out,
            vocab,
            _user(counts.reading_p2, vocab, "Short paragraphs. Choose the statement that matches."),
        )
        for raw in r2.items[: counts.reading_p2]:
            reading.append(
                McqItem(
                    id=new_id(),
                    part="reading_p2",
                    prompt="选择与短文内容一致的一项。",
                    passage=raw.text,
                    choices=_choices(raw.choices),
                    answer=raw.answer,
                )
            )

    if counts.reading_p3:
        _note("阅读 長文")
        r3 = _parse(
            llm,
            ReadingP3Out,
            vocab,
            _user(counts.reading_p3, vocab, "Long passages with several questions each. Total questions = count."),
        )
        left = counts.reading_p3
        for passage in r3.passages:
            for q in passage.questions:
                if left <= 0:
                    break
                reading.append(
                    McqItem(
                        id=new_id(),
                        part="reading_p3",
                        prompt=q.question,
                        passage=passage.text,
                        choices=_choices(q.choices),
                        answer=q.answer,
                    )
                )
                left -= 1

    if counts.writing_p1:
        _note("連詞成句")
        w1 = _parse(
            llm,
            WritingP1Out,
            vocab,
            _user(
                counts.writing_p1, vocab, "Sentence reordering. words is a shuffled list; gold is the correct sentence."
            ),
        )
        for raw in w1.items[: counts.writing_p1]:
            sentences.append(SentenceOrderItem(id=new_id(), words=list(raw.words), gold=raw.gold))

    if counts.writing_p2 >= 1:
        _note("作文の課題")
        kw = _parse(llm, KeywordsOut, vocab, _user(5, vocab, "Five related HSK5 words for an 80-character essay."))
        essays.append(EssayItem(id=new_id(), kind="keywords", required_words=list(kw.words)[:5]))
    if counts.writing_p2 >= 2:
        pic = _parse(
            llm,
            PictureOut,
            vocab,
            _user(1, vocab, "English photo prompt of a simple everyday scene. No text in the image."),
        )
        essays.append(EssayItem(id=new_id(), kind="picture", image_prompt=pic.prompt, image_name="writing.png"))

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
    for i, clip in enumerate(exam.clips, 1):
        if report:
            report("音声合成", f"{i}/{nclips}")
        spoken = [ln.text for ln in clip.lines]
        if clip.question_text:
            spoken.append(clip.question_text)
        audio = tts.synth("\n".join(spoken), tts.voice_for("NARR"))
        if len(audio) < 16:
            raise RuntimeError("empty audio")
        store.audio_path(exam.id, clip.id).write_bytes(audio)
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
