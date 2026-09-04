from __future__ import annotations

from typing import Any, Protocol

import httpx

_client: "HttpClient | None" = None


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
    return httpx.Client(timeout=120.0)
