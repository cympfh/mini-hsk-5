from __future__ import annotations

import json
import os
from typing import TypeVar

from pydantic import BaseModel

from hsk5.http import get_http_client
from hsk5.paths import MODEL

T = TypeVar("T", bound=BaseModel)
CHAT_URL = "https://api.x.ai/v1/chat/completions"


class GrokError(RuntimeError):
    pass


def parse(model_type: type[T], system: str, user: str) -> T:
    key = os.environ.get("XAI_API_KEY") or ""
    schema = model_type.model_json_schema()
    body = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": model_type.__name__, "schema": schema, "strict": True},
        },
    }
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    resp = get_http_client().post(CHAT_URL, json=body, headers=headers)
    resp.raise_for_status()
    data = resp.json()
    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as e:
        raise GrokError(f"unexpected grok payload: {data!r}") from e
    if isinstance(content, list):
        content = "".join(part.get("text", "") for part in content if isinstance(part, dict))
    if not isinstance(content, str):
        raise GrokError(f"non-string grok content: {content!r}")
    return model_type.model_validate(json.loads(content))
