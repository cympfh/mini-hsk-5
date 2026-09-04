from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parent.parent


def test_health(client: TestClient) -> None:
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["model"] == "grok-4.6"


def test_index_html(client: TestClient) -> None:
    r = client.get("/")
    assert r.status_code == 200
    text = r.text
    assert "汉语水平考试" in text
    assert "app.js" in text
    assert "cdn" not in text.lower()


def test_root_path_prefixes_assets(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ROOT_PATH", "/mini-hsk5")
    r = client.get("/")
    assert 'src="/mini-hsk5/app.js' in r.text
    from tests.helpers import make_exam

    exam = make_exam(100)
    public = exam.to_public(prefix="/mini-hsk5")
    pic = next(e for e in public["essays"] if e["kind"] == "picture")
    assert pic["image_url"].startswith("/mini-hsk5/api/")


def test_no_key_exits() -> None:
    env = os.environ.copy()
    env.pop("XAI_API_KEY", None)
    env["PYTHONPATH"] = str(ROOT)
    proc = subprocess.run(
        [sys.executable, "-c", "import hsk5.app"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    assert proc.returncode != 0
    blob = proc.stderr + proc.stdout
    assert "XAI_API_KEY" in blob
