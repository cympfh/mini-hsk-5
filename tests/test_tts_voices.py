from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from hsk5 import store
from hsk5.generate import attach_media
from hsk5.tts import voice_for
from tests.helpers import make_exam


def test_attach_media_uses_per_speaker_voices(data_dir: Path) -> None:
    exam = make_exam(10, exam_id="abcd1234")
    store.exam_dir(exam.id)
    clip = exam.clips[0]

    calls: list[tuple[str, str]] = []

    def fake_synth(text: str, voice_id: str) -> bytes:
        calls.append((text, voice_id))
        return b"ID3" + text.encode("utf-8") + b"\x00" * 16

    with patch("hsk5.generate.tts.synth", side_effect=fake_synth):
        attach_media(exam)

    expected = [(ln.text, voice_for(ln.speaker)) for ln in clip.lines]
    if clip.question_text:
        expected.append((clip.question_text, voice_for("NARR")))
    assert calls[: len(expected)] == expected
    assert {v for _, v in expected} >= {"eve", "rex", "ara"}
    audio = store.audio_path(exam.id, clip.id).read_bytes()
    assert audio.startswith(b"ID3")
    assert clip.lines[0].text.encode("utf-8") in audio
