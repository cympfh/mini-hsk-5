from __future__ import annotations

import random

from hsk5.generate import _names_for_slot, _slot_user, shuffle_proper_names
from hsk5.vocab import ALLOWED_PROPER, load_vocab


def test_allowed_proper_pool_is_100() -> None:
    assert len(ALLOWED_PROPER) == 100


def test_shuffle_proper_names_permutes() -> None:
    a = shuffle_proper_names(random.Random(1))
    b = shuffle_proper_names(random.Random(2))
    assert len(a) == 100 and set(a) == set(ALLOWED_PROPER)
    assert a != b


def test_names_for_slot_uses_shuffled_pool() -> None:
    pool = shuffle_proper_names(random.Random(0))
    a = _names_for_slot(0, pool=pool)
    b = _names_for_slot(1, pool=pool)
    assert a == pool[0:2]
    assert b == pool[2:4]
    assert a != b


def test_slot_user_embeds_names() -> None:
    v = load_vocab()
    pool = shuffle_proper_names(random.Random(3))
    text = _slot_user(v, "One short dialogue.", [], 3, 10, name_pool=pool)
    for name in _names_for_slot(3, pool=pool):
        assert name in text
