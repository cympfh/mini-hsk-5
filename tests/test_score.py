from __future__ import annotations

from hsk5.models import EssayGrokOut
from hsk5.score import apply_essay_guards, hanzi_count, score_exam, score_mcq_item, score_sentence
from tests.helpers import make_exam


def test_mcq_exact_match() -> None:
    exam = make_exam(10)
    item = exam.listening[0]
    pts = 10.0
    assert score_mcq_item(item, "A", pts) == pts
    assert score_mcq_item(item, "B", pts) == 0.0
    assert score_mcq_item(item, None, pts) == 0.0


def test_sentence_strips_punctuation() -> None:
    exam = make_exam(10)
    if not exam.sentence_order:
        exam = make_exam(100)
    item = exam.sentence_order[0]
    assert score_sentence(item, item.gold, 5) == 5
    assert score_sentence(item, item.gold + "。", 5) == 5
    assert score_sentence(item, "完全不对", 5) == 0


def test_essay_guard_missing_words_cannot_stay_high() -> None:
    raw = EssayGrokOut(band="high", score=28, char_count=80, comment_ja="x")
    text = "今天天气很好。" * 20
    assert hanzi_count(text) >= 75
    guarded = apply_essay_guards(raw, text, ["环境", "保护", "责任", "习惯", "影响"])
    assert guarded.band != "high"
    assert guarded.score <= 20


def test_essay_guard_short_cannot_stay_high() -> None:
    raw = EssayGrokOut(band="high", score=30, char_count=10, comment_ja="x")
    text = "环境保护责任习惯影响。"
    guarded = apply_essay_guards(raw, text, ["环境", "保护", "责任", "习惯", "影响"])
    assert guarded.band != "high"
    assert guarded.score <= 20


def test_essay_unrelated_image_cannot_stay_high() -> None:
    raw = EssayGrokOut(band="high", score=30, char_count=80, related_to_image=False, comment_ja="x")
    text = "环境保护是每个人的责任，我们应该养成好习惯，因为习惯会影响未来的生活。" * 2
    guarded = apply_essay_guards(raw, text, ["环境", "保护", "责任", "习惯", "影响"])
    assert guarded.band != "high"
    assert guarded.score <= 20


def test_essay_blank_is_zero() -> None:
    raw = EssayGrokOut(band="high", score=30, char_count=0, comment_ja="x")
    guarded = apply_essay_guards(raw, "   ", ["环境"])
    assert guarded.band == "zero"
    assert guarded.score == 0


def test_score_exam_perfect() -> None:
    exam = make_exam(10)
    mcq = {it.id: it.answer for it in exam.listening + exam.reading}
    sentence = {it.id: it.gold for it in exam.sentence_order}
    essays = {}
    grok_out = {}
    long = "环境保护是每个人的责任，我们应该养成好习惯，因为习惯会影响未来。" * 3
    for it in exam.essays:
        essays[it.id] = long
        grok_out[it.id] = EssayGrokOut(band="high", score=30, char_count=hanzi_count(long), comment_ja="ok")
    result = score_exam(exam, {"mcq": mcq, "sentence": sentence, "essay": essays}, grok_out)
    if exam.listening:
        assert abs(result["listening"] - 100) < 1e-6
    if exam.reading:
        assert abs(result["reading"] - 100) < 1e-6
    if exam.sentence_order or exam.essays:
        assert result["writing"] > 0
        assert result["total"] > 0
