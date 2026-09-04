from __future__ import annotations

import json as jsonlib
import re
from typing import Any

import httpx

FAKE_MP3 = b"ID3FAKEMP3" + b"\x00" * 32
FAKE_PNG = bytes.fromhex("89504e470d0a1a0a0000000d49484452") + b"\x00" * 16


def _count(user: str) -> int:
    m = re.search(r"count=(\d+)", user)
    return int(m.group(1)) if m else 1


def _mcq() -> dict[str, Any]:
    return {
        "choices": [
            {"key": "A", "text": "看书"},
            {"key": "B", "text": "买书"},
            {"key": "C", "text": "学习"},
            {"key": "D", "text": "工作"},
        ],
        "answer": "A",
    }


def _lines() -> list[dict[str, str]]:
    return [
        {"speaker": "M1", "text": "你今天去图书馆吗？"},
        {"speaker": "F1", "text": "去，我要借几本书。"},
    ]


def payload_for(name: str, user: str) -> dict[str, Any]:
    n = _count(user)
    if name == "ListeningP1Out":
        items = []
        for _ in range(n):
            items.append({"lines": _lines(), "question": "她要做什么？", **_mcq()})
        return {"items": items}
    if name == "ListeningP2Out":
        clips = []
        left = n
        while left > 0:
            qn = min(2, left)
            qs = [{"question": "我们要去哪里？", **_mcq()} for _ in range(qn)]
            clips.append({"lines": _lines() + [{"speaker": "M1", "text": "好的，我们一起去。"}], "questions": qs})
            left -= qn
        return {"clips": clips}
    if name == "ReadingP1Out":
        blanks = [{**_mcq()} for _ in range(n)]
        holes = "____，".join([""] * n) + "____。" if n else ""
        text = "李华今天去学校" + ("学习____。" if n else "学习。")
        if n > 1:
            text = "李华今天去学校" + ("____" * n) + "。"
        return {"passages": [{"text": text, "blanks": blanks}]}
    if name == "ReadingP2Out":
        return {"items": [{"text": "李华很喜欢在图书馆看书。", **_mcq()} for _ in range(n)]}
    if name == "ReadingP3Out":
        return {
            "passages": [
                {
                    "text": "现在有人喜欢在家里工作。可以节省时间。",
                    "questions": [{"question": "文章的主要内容是什么？", **_mcq()} for _ in range(n)],
                }
            ]
        }
    if name == "WritingP1Out":
        gold = "我今天坐公共汽车去学校。"
        words = ["我", "今天", "坐", "公共汽车", "去", "学校"]
        return {"items": [{"words": list(reversed(words)), "gold": gold} for _ in range(n)]}
    if name == "KeywordsOut":
        return {"words": ["环境", "保护", "责任", "习惯", "影响"]}
    if name == "PictureOut":
        return {"prompt": "Two students talking on a campus bench, photorealistic, no text"}
    if name == "EssayGrokOut":
        return {
            "band": "high",
            "score": 28,
            "char_count": 80,
            "used_required_words": ["环境", "保护", "责任", "习惯", "影响"],
            "related_to_image": True,
            "grammar_ok": True,
            "coherent": True,
            "comment_ja": "指定語を使い、内容もつながっている。",
        }
    raise KeyError(name)


class FakeResp:
    def __init__(self, json_data: Any | None = None, content: bytes = b"", status_code: int = 200) -> None:
        self._json = json_data
        self.content = content if json_data is None else jsonlib.dumps(json_data, ensure_ascii=False).encode()
        self.status_code = status_code
        self.headers: dict[str, str] = {}

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                "error", request=httpx.Request("POST", "http://x"), response=httpx.Response(self.status_code)
            )

    def json(self) -> Any:
        if self._json is None:
            return jsonlib.loads(self.content.decode())
        return self._json


class StubXAI:
    def __init__(self) -> None:
        self.urls: list[str] = []
        self.schema_calls: list[str] = []
        self.fail_first: set[str] = set()

    def post(
        self,
        url: str,
        *,
        json: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        content: bytes | None = None,
    ) -> FakeResp:
        self.urls.append(url)
        if "api.x.ai" not in url:
            raise RuntimeError(f"unexpected url {url}")
        if url.endswith("/chat/completions"):
            assert json is not None
            name = json["response_format"]["json_schema"]["name"]
            user = json["messages"][1]["content"]
            if isinstance(user, list):
                user = next(
                    (p.get("text", "") for p in user if isinstance(p, dict) and p.get("type") == "text"),
                    "",
                )
            self.schema_calls.append(name)
            if name in self.fail_first:
                self.fail_first.remove(name)
                bad = payload_for(name, user)
                blob = json_dumps_with_oov(bad)
                return FakeResp({"choices": [{"message": {"content": blob}}]})
            body = payload_for(name, user)
            return FakeResp({"choices": [{"message": {"content": jsonlib.dumps(body, ensure_ascii=False)}}]})
        if url.endswith("/tts"):
            return FakeResp(content=FAKE_MP3)
        if url.endswith("/images/generations"):
            return FakeResp({"data": [{"url": "http://stub.local/img.png"}]})
        raise RuntimeError(url)

    def get(self, url: str, *, headers: dict[str, str] | None = None) -> FakeResp:
        self.urls.append(url)
        if url == "http://stub.local/img.png":
            return FakeResp(content=FAKE_PNG)
        raise RuntimeError(url)


def json_dumps_with_oov(body: dict[str, Any]) -> str:
    raw = jsonlib.dumps(body, ensure_ascii=False)
    return raw.replace("图书馆", "量子纠缠")
