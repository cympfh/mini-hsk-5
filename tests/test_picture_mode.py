from __future__ import annotations

from fastapi.testclient import TestClient

from hsk5.scale import counts_for, picture_counts


def test_picture_counts() -> None:
    c = picture_counts(3)
    assert c.listening_total == 0 and c.reading_total == 0
    assert c.writing_p1 == 0 and c.writing_p2 == 3


def test_counts_for_modes() -> None:
    assert counts_for(50, "full").writing_p2 >= 1
    assert counts_for(2, "picture").writing_p2 == 2


def test_scale_api(client: TestClient) -> None:
    r = client.get("/api/scale", params={"size": 50, "mode": "full"})
    assert r.status_code == 200
    body = r.json()
    assert body["listening_total"] > 0
    r2 = client.get("/api/scale", params={"size": 3, "mode": "picture"})
    assert r2.json()["writing_p2"] == 3
    assert r2.json()["listening_total"] == 0


def test_create_rejects_picture_over_20(client: TestClient) -> None:
    r = client.post("/api/exams", json={"size": 21, "mode": "picture"})
    assert r.status_code == 422
