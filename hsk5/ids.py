from __future__ import annotations

import re
import uuid

ID_RE = re.compile(r"^[0-9a-f]{8}$")


def new_id() -> str:
    return uuid.uuid4().hex[:8]


def is_id(value: str) -> bool:
    return bool(ID_RE.match(value))
