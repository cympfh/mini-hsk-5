from __future__ import annotations

from hsk5.vocab import load_vocab


def test_vocab_size_near_2500() -> None:
    v = load_vocab()
    assert 2400 <= len(v.words) <= 2600
    assert "图书馆" in v.words
    assert "影响" in v.words


def test_oov_detects_unknown_hanzi() -> None:
    v = load_vocab()
    assert v.oov("我去图书馆看书。") == []
    assert v.oov("小王去学校。") == []
    oov = v.oov("量子纠缠")
    assert oov


def test_oov_allows_chars_from_listed_words() -> None:
    v = load_vocab()
    assert v.oov("你们好吗") == []
    assert v.oov("他们去了学校") == []
    assert v.oov("孩子们在公园玩") == []
    assert v.oov("我们一起去吃饭吧。") == []
    assert v.oov("请帮我做这件事。") == []
    assert v.oov("那个男人来了。") == []
    assert v.oov("一系列问题。") == []
