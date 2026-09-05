from __future__ import annotations

import json

from fastapi.testclient import TestClient

from hsk5 import store
from hsk5.score import score_exam
from tests.helpers import make_exam
from tests.stub_xai import StubXAI


def test_list_and_reopen_attempt_review(client: TestClient, stub: StubXAI, data_dir) -> None:
    exam = make_exam(10, exam_id="abcd1234")
    store.create_exam_row(exam.id, exam.size)
    store.save_exam(exam)
    store.set_status(exam.id, "ready", "done")

    started = store.start_attempt(exam.id)
    attempt_id = started["attempt_id"]

    answers = {
        "mcq": {exam.listening[0].id: exam.listening[0].answer, exam.reading[0].id: "B"},
        "sentence": {exam.sentence_order[0].id: exam.sentence_order[0].gold} if exam.sentence_order else {},
        "essay": {},
    }
    result = score_exam(exam, answers, {})
    result["overtime"] = False
    result["pass_hint"] = 180
    store.save_attempt_result(attempt_id, exam.id, result, answers, False)

    listed = client.get(f"/api/exams/{exam.id}/attempts").json()
    assert len(listed) == 1
    assert listed[0]["id"] == attempt_id
    assert listed[0]["total"] == result["total"]

    # open (unsubmitted) attempts are hidden
    store.start_attempt(exam.id)
    listed2 = client.get(f"/api/exams/{exam.id}/attempts").json()
    assert len(listed2) == 1

    review = client.get(f"/api/attempts/{attempt_id}").json()
    assert review["id"] == attempt_id
    assert review["exam"]["id"] == exam.id
    assert "answer" not in json.dumps(review["exam"].get("listening", [{}])[0])
    assert review["result"]["listening_items"][0]["answer"] == exam.listening[0].answer
    assert review["result"]["listening_items"][0]["given"] == exam.listening[0].answer

    open_id = store.start_attempt(exam.id)["attempt_id"]
    bad = client.get(f"/api/attempts/{open_id}")
    assert bad.status_code == 409
