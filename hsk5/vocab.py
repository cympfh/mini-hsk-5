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
        "小吴",
        "小郑",
        "小孙",
        "小杨",
        "小黄",
        "小徐",
        "小马",
        "小朱",
        "小胡",
        "小郭",
        "小林",
        "小何",
        "小高",
        "小罗",
        "小梁",
        "小宋",
        "小唐",
        "小许",
        "王明",
        "李华",
        "张伟",
        "刘芳",
        "陈静",
        "赵强",
        "周敏",
        "吴磊",
        "郑丽",
        "孙涛",
        "杨雪",
        "黄勇",
        "徐芳",
        "马超",
        "朱婷",
        "胡军",
        "郭娜",
        "林峰",
        "何丽",
        "高强",
        "罗明",
        "梁静",
        "宋强",
        "唐丽",
        "许勇",
        "邓芳",
        "冯伟",
        "曹敏",
        "彭磊",
        "曾丽",
        "肖强",
        "田静",
        "董伟",
        "袁芳",
        "潘强",
        "蒋丽",
        "蔡伟",
        "余静",
        "杜强",
        "叶丽",
        "程伟",
        "苏静",
        "吕强",
        "魏丽",
        "蒋明",
        "沈芳",
        "韩伟",
        "杨明",
        "朱强",
        "秦丽",
        "尤伟",
        "许静",
        "何强",
        "吕丽",
        "施伟",
        "张敏",
        "王芳",
        "李强",
        "刘伟",
        "陈丽",
        "赵敏",
        "周强",
        "吴芳",
        "郑伟",
        "孙丽",
        "黄敏",
        "徐强",
        "马丽",
        "胡伟",
        "郭强",
        "林丽",
        "高伟",
        "梁强",
        "宋丽",
        "唐伟",
    }
)


@dataclass(frozen=True)
class Vocab:
    words: frozenset[str]
    chars: frozenset[str]
    entries: tuple[dict[str, str], ...]
    max_len: int

    def sample(self, k: int, rng: random.Random | None = None) -> list[str]:
        rng = rng or random.Random()
        pool = list(self.words)
        k = min(k, len(pool))
        return rng.sample(pool, k)

    def _allowed(self, piece: str) -> bool:
        if piece in self.words or piece in ALLOWED_PROPER:
            return True
        # Hanzi that appear in listed words count as inventory.
        return len(piece) == 1 and piece in self.chars

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
                if self._allowed(piece):
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
    chars = frozenset(ch for w in words for ch in w if "\u4e00" <= ch <= "\u9fff")
    vocab = Vocab(
        words=words,
        chars=chars,
        entries=tuple(raw),
        max_len=max(len(w) for w in words),
    )
    if path is None:
        _CACHED = vocab
    return vocab
