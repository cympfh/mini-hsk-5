from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("XAI_API_KEY", "test-dummy-key")

from hsk5.http import set_http_client  # noqa: E402
from tests.stub_xai import StubXAI  # noqa: E402


@pytest.fixture(autouse=True)
def block_live_xai(monkeypatch: pytest.MonkeyPatch) -> None:
    orig = httpx.Client.request

    def wrapped(self: httpx.Client, method: str, url: str | httpx.URL, **kwargs: Any) -> httpx.Response:
        if "api.x.ai" in str(url):
            raise RuntimeError(f"live xAI forbidden in tests: {url}")
        return orig(self, method, url, **kwargs)

    monkeypatch.setattr(httpx.Client, "request", wrapped)


@pytest.fixture
def data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("HSK5_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("XAI_API_KEY", "test-dummy-key")
    return tmp_path


@pytest.fixture
def stub(data_dir: Path) -> Iterator[StubXAI]:
    client = StubXAI()
    set_http_client(client)
    yield client
    set_http_client(None)


@pytest.fixture
def client(stub: StubXAI, data_dir: Path) -> Iterator[TestClient]:
    from hsk5.app import app

    with TestClient(app) as test_client:
        yield test_client
