from __future__ import annotations

from hsk5.ids import new_id
from hsk5.models import Choice, EssayItem, Exam, ListeningClip, McqItem, SentenceOrderItem, SpeakerLine
from hsk5.scale import scale_counts
from hsk5.store import now_iso


def _choices() -> list[Choice]:
    return [
        Choice(key="A", text="看书"),
        Choice(key="B", text="买书"),
        Choice(key="C", text="吃饭"),
        Choice(key="D", text="睡觉"),
    ]


def make_exam(size: int = 10, exam_id: str | None = None) -> Exam:
    counts = scale_counts(size)
    eid = exam_id or new_id()
    clips: list[ListeningClip] = []
    listening: list[McqItem] = []
    for i in range(counts.listening_total):
        clip_id = new_id()
        item_id = new_id()
        part = "listening_p1" if i < counts.listening_p1 else "listening_p2"
        lines = [
            SpeakerLine(speaker="M1", text="你今天去图书馆吗？"),
            SpeakerLine(speaker="F1", text="去，我要借几本书。"),
        ]
        clips.append(
            ListeningClip(
                id=clip_id,
                part="p1" if part.endswith("p1") else "p2",
                lines=lines,
                question_text="她要做什么？",
                item_ids=[item_id],
            )
        )
        listening.append(
            McqItem(
                id=item_id,
                part=part,
                prompt="",
                choices=_choices(),
                answer="A",
                clip_id=clip_id,
                transcript="M1: 你今天去图书馆吗？",
            )
        )
    reading = [
        McqItem(
            id=new_id(),
            part="reading_p2",
            prompt="选择与短文内容一致的一项。",
            passage="李华很喜欢看书。",
            choices=_choices(),
            answer="A",
        )
        for _ in range(counts.reading_total)
    ]
    sentences = [
        SentenceOrderItem(
            id=new_id(),
            words=["学校", "去", "我", "今天"],
            gold="我今天去学校。",
        )
        for _ in range(counts.writing_p1)
    ]
    essays: list[EssayItem] = []
    if counts.writing_p2 >= 1:
        essays.append(EssayItem(id=new_id(), kind="keywords", required_words=["环境", "保护", "责任", "习惯", "影响"]))
    if counts.writing_p2 >= 2:
        essays.append(EssayItem(id=new_id(), kind="picture", image_name="writing.png", image_prompt="park"))
    return Exam(
        id=eid,
        size=size,
        created_at=now_iso(),
        counts=counts,
        clips=clips,
        listening=listening,
        reading=reading,
        sentence_order=sentences,
        essays=essays,
    )
