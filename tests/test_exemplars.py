from hsk5.exemplars import BY_PART, format_exemplars


def test_three_diverse_exemplars_per_part() -> None:
    assert len(BY_PART) >= 8
    for part, items in BY_PART.items():
        assert len(items) == 3, part
        assert len({x.strip() for x in items}) == 3, part
        blob = format_exemplars(part)
        assert "exemplar 1" in blob and "exemplar 3" in blob
        assert "do not copy" in blob.lower()


def test_exemplars_within_vocab() -> None:
    from hsk5.vocab import load_vocab

    vocab = load_vocab()
    for part, items in BY_PART.items():
        for i, block in enumerate(items, 1):
            oov = vocab.oov(block)
            assert not oov, f"{part}#{i}: {oov[:20]}"
