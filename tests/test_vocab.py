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
