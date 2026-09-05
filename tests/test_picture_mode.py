from __future__ import annotations

from fastapi.testclient import TestClient

from hsk5.scale import custom_counts, scale_counts


def test_scale_splits_essays() -> None:
    c = scale_counts(100)
    assert c.writing_keywords == 1 and c.writing_picture == 1
    assert c.writing_p2 == 2


def test_custom_picture_only() -> None:
    c = custom_counts(writing_picture=3)
    assert c.listening_total == 0 and c.writing_picture == 3 and c.writing_p2 == 3


def test_scale_api(client: TestClient) -> None:
    r = client.get("/api/scale", params={"size": 100})
    assert r.status_code == 200
    body = r.json()
    assert body["writing_keywords"] == 1
    assert body["writing_picture"] == 1


def test_create_custom_parts(client: TestClient, stub) -> None:
    r = client.post(
        "/api/exams",
        json={
            "size": 10,
            "parts": {
                "listening_p1": 0,
                "listening_p2": 0,
                "reading_p1": 0,
                "reading_p2": 0,
                "reading_p3": 0,
                "writing_p1": 0,
                "writing_keywords": 0,
                "writing_picture": 2,
            },
        },
    )
    assert r.status_code == 200
    exam_id = r.json()["id"]
    row = client.get(f"/api/exams/{exam_id}").json()
    assert row["mode"] == "custom"


def test_create_rejects_empty_parts(client: TestClient) -> None:
    r = client.post(
        "/api/exams",
        json={
            "size": 10,
            "parts": {
                "listening_p1": 0,
                "listening_p2": 0,
                "reading_p1": 0,
                "reading_p2": 0,
                "reading_p3": 0,
                "writing_p1": 0,
                "writing_keywords": 0,
                "writing_picture": 0,
            },
        },
    )
    assert r.status_code == 422
