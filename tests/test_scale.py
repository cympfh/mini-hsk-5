from __future__ import annotations

from hsk5.scale import scale_counts, score_weights


def test_size_100_is_official_paper() -> None:
    c = scale_counts(100)
    assert (c.listening_p1, c.listening_p2) == (20, 25)
    assert (c.reading_p1, c.reading_p2, c.reading_p3) == (15, 10, 20)
    assert (c.writing_p1, c.writing_p2) == (8, 2)
    assert c.total == 100
    assert c.listening_minutes == 30
    assert c.reading_minutes == 45
    assert c.writing_minutes == 40


def test_size_1_drops_empty_parts() -> None:
    c = scale_counts(1)
    assert c.total == 1
    present = [n for n in (c.listening_total, c.reading_total, c.writing_total) if n]
    assert len(present) == 1
    if c.listening_total == 0:
        assert c.listening_minutes == 0
    else:
        assert c.listening_minutes >= 1
    if c.reading_total == 0:
        assert c.reading_minutes == 0
    if c.writing_total == 0:
        assert c.writing_minutes == 0


def test_size_10_total_and_empty_minutes() -> None:
    c = scale_counts(10)
    assert c.total == 10
    if c.listening_total:
        assert c.listening_minutes >= 1
    else:
        assert c.listening_minutes == 0
    if c.reading_total:
        assert c.reading_minutes >= 1
    if c.writing_total:
        assert c.writing_minutes >= 1


def test_section_weights_sum_100() -> None:
    for size in (1, 10, 100):
        c = scale_counts(size)
        w = score_weights(c)
        if c.listening_total:
            assert abs(sum(w.listening) - 100) < 1e-9
            assert len(w.listening) == c.listening_total
        else:
            assert w.listening == ()
        if c.reading_total:
            assert abs(sum(w.reading) - 100) < 1e-9
        if c.writing_total:
            total = c.writing_p1 * w.writing_p1 + c.writing_p2 * w.writing_p2
            assert abs(total - 100) < 1e-9


def test_full_writing_keeps_5_and_30() -> None:
    w = score_weights(scale_counts(100))
    assert w.writing_p1 == 5
    assert w.writing_p2 == 30


def test_size_rejects_out_of_range() -> None:
    for bad in (0, 101, -1):
        try:
            scale_counts(bad)
        except ValueError:
            pass
        else:
            raise AssertionError(bad)


def test_picture_essay_slot_at_size_50() -> None:
    # size 50 has writing_p2==1; that single slot must be treated as 看图 in generation.
    c = scale_counts(50)
    assert c.writing_p2 >= 1
