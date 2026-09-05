from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from hsk5 import store
from tests.stub_xai import StubXAI


def test_startup_fails_leftover_generating(data_dir: Path, stub: StubXAI) -> None:
    store.create_exam_row("abcd1234", 10, "full")
    assert store.get_exam_row("abcd1234")["status"] == "generating"

    from hsk5.app import app

    with TestClient(app):
        row = store.get_exam_row("abcd1234")
        assert row is not None
        assert row["status"] == "failed"
        assert row["error"] == "interrupted by restart"
