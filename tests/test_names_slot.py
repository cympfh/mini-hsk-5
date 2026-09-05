from __future__ import annotations

from hsk5.generate import _names_for_slot, _slot_user
from hsk5.vocab import ALLOWED_PROPER, load_vocab


def test_allowed_proper_pool_is_wide() -> None:
    assert len(ALLOWED_PROPER) >= 30


def test_names_for_slot_rotates() -> None:
    a = _names_for_slot(0)
    b = _names_for_slot(1)
    assert len(a) == 2 and len(b) == 2
    assert set(a) <= ALLOWED_PROPER
    assert a != b


def test_slot_user_embeds_names() -> None:
    v = load_vocab()
    text = _slot_user(v, "One short dialogue.", [], 3, 10)
    for name in _names_for_slot(3):
        assert name in text
