from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from hsk5.http import set_http_client
from hsk5.store import ExamNotReady, start_attempt
from tests.stub_xai import StubXAI


def _keys(obj: Any) -> set[str]:
    found: set[str] = set()

    def walk(x: Any) -> None:
        if isinstance(x, dict):
            found.update(x.keys())
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)

    walk(obj)
    return found


def test_create_exam_returns_generating_then_ready(client: TestClient, stub: StubXAI) -> None:
    r = client.post("/api/exams", json={"size": 10})
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "generating"
    exam_id = body["id"]
    got = client.get(f"/api/exams/{exam_id}")
    assert got.status_code == 200
    data = got.json()
    assert data["status"] == "ready"
    assert data["id"] == exam_id
    keys = _keys(data)
    assert "answer" not in keys
    assert "transcript" not in keys
    assert "gold" not in keys
    assert stub.urls
    assert all("api.x.ai" in u or u.startswith("http://stub.local") for u in stub.urls)


def test_generating_exam_cannot_start(data_dir: object) -> None:
    from hsk5 import store

    store.create_exam_row("deadbeef", 10)
    try:
        start_attempt("deadbeef")
    except ExamNotReady as e:
        assert e.status == "generating"
    else:
        raise AssertionError("expected ExamNotReady")


def test_start_generating_via_http_409(client: TestClient, stub: StubXAI) -> None:
    from hsk5 import store

    store.create_exam_row("cafebabe", 10)
    r = client.post("/api/exams/cafebabe/attempts")
    assert r.status_code == 409


def test_failed_exam_not_takeable(client: TestClient, stub: StubXAI) -> None:
    from hsk5 import store

    store.create_exam_row("badbad00", 10)
    store.set_status("badbad00", "failed", "boom")
    r = client.post("/api/exams/badbad00/attempts")
    assert r.status_code == 409


def test_submit_scores_and_best(client: TestClient, stub: StubXAI) -> None:
    r = client.post("/api/exams", json={"size": 10})
    exam_id = r.json()["id"]
    public = client.get(f"/api/exams/{exam_id}").json()
    started = client.post(f"/api/exams/{exam_id}/attempts")
    assert started.status_code == 200
    attempt_id = started.json()["attempt_id"]
    from hsk5.store import load_exam

    exam = load_exam(exam_id)
    mcq = {it.id: it.answer for it in exam.listening + exam.reading}
    sentence = {it.id: it.gold for it in exam.sentence_order}
    long = "环境保护是每个人的责任，我们应该养成好习惯，因为习惯会影响未来的生活。" * 3
    essays = {it.id: long for it in exam.essays}
    sub = client.post(
        f"/api/attempts/{attempt_id}/submit",
        json={"mcq": mcq, "sentence": sentence, "essay": essays},
    )
    assert sub.status_code == 200
    result = sub.json()["result"]
    assert "total" in result
    listing = client.get("/api/exams").json()
    row = next(x for x in listing if x["id"] == exam_id)
    assert row["best_total"] == result["total"]
    assert public["status"] == "ready"


def test_oov_retry_uses_second_generation(data_dir: object) -> None:
    stub = StubXAI()
    stub.fail_first.add("ListeningP1Out")
    set_http_client(stub)
    from hsk5.generate import generate_exam

    exam = generate_exam("abcd1234", 10)
    assert exam.listening
    assert stub.schema_calls.count("ListeningP1Out") >= 2
    set_http_client(None)


def test_audio_and_image_served(client: TestClient, stub: StubXAI) -> None:
    r = client.post("/api/exams", json={"size": 100})
    exam_id = r.json()["id"]
    exam = client.get(f"/api/exams/{exam_id}").json()
    clip_id = exam["listening"][0]["clip_id"]
    audio = client.get(f"/api/exams/{exam_id}/audio/{clip_id}")
    assert audio.status_code == 200
    assert audio.content.startswith(b"ID3")
    picture = next((e for e in exam["essays"] if e["kind"] == "picture"), None)
    assert picture is not None
    img = client.get(picture["image_url"])
    assert img.status_code == 200
