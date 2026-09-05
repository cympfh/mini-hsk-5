from __future__ import annotations

import threading
from typing import Any, Protocol

import httpx

_client: "HttpClient | None" = None
_default: httpx.Client | None = None
_default_lock = threading.Lock()


class HttpClient(Protocol):
    def post(
        self,
        url: str,
        *,
        json: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        content: bytes | None = None,
    ) -> Any: ...

    def get(self, url: str, *, headers: dict[str, str] | None = None) -> Any: ...


def set_http_client(client: HttpClient | None) -> None:
    global _client
    _client = client


def get_http_client() -> HttpClient:
    if _client is not None:
        return _client
    global _default
    if _default is None:
        with _default_lock:
            if _default is None:
                _default = httpx.Client(timeout=httpx.Timeout(600.0, connect=30.0))
    return _default
