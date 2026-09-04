from __future__ import annotations

import json
import random
from dataclasses import dataclass
from pathlib import Path

from hsk5.paths import VOCAB_PATH

ALLOWED_PROPER = frozenset(
    {
        "小王",
        "小李",
        "小张",
        "小刘",
        "小陈",
        "小赵",
        "小周",
        "王明",
        "李华",
        "张伟",
        "刘芳",
    }
)


@dataclass(frozen=True)
class Vocab:
    words: frozenset[str]
    entries: tuple[dict[str, str], ...]
    max_len: int

    def sample(self, k: int, rng: random.Random | None = None) -> list[str]:
        rng = rng or random.Random()
        pool = list(self.words)
        k = min(k, len(pool))
        return rng.sample(pool, k)

    def oov(self, text: str) -> list[str]:
        found: list[str] = []
        i = 0
        n = len(text)
        while i < n:
            ch = text[i]
            if not ("\u4e00" <= ch <= "\u9fff"):
                i += 1
                continue
            matched: str | None = None
            upper = min(self.max_len, n - i)
            for length in range(upper, 0, -1):
                piece = text[i : i + length]
                if piece in self.words or piece in ALLOWED_PROPER:
                    matched = piece
                    break
            if matched is None:
                found.append(ch)
                i += 1
            else:
                i += len(matched)
        return found


_CACHED: Vocab | None = None


def load_vocab(path: Path | None = None) -> Vocab:
    global _CACHED
    if path is None and _CACHED is not None:
        return _CACHED
    p = path or VOCAB_PATH
    raw = json.loads(p.read_text(encoding="utf-8"))
    words = frozenset(row["s"] for row in raw if row.get("s"))
    vocab = Vocab(words=words, entries=tuple(raw), max_len=max(len(w) for w in words))
    if path is None:
        _CACHED = vocab
    return vocab
