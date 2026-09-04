from __future__ import annotations

import os

from hsk5.http import get_http_client

TTS_URL = "https://api.x.ai/v1/tts"
VOICE_F = "eve"
VOICE_M = "rex"
VOICE_NARR = "ara"


def voice_for(speaker: str) -> str:
    if speaker == "F1":
        return VOICE_F
    if speaker == "M1":
        return VOICE_M
    return VOICE_NARR


def synth(text: str, voice_id: str) -> bytes:
    key = os.environ.get("XAI_API_KEY") or ""
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    body = {"text": text, "voice_id": voice_id, "language": "zh"}
    resp = get_http_client().post(TTS_URL, json=body, headers=headers)
    resp.raise_for_status()
    return resp.content
