from __future__ import annotations

import os

from hsk5.http import get_http_client

IMAGE_URL = "https://api.x.ai/v1/images/generations"
IMAGE_MODEL = "grok-imagine-image-2.0"


def generate_image(prompt: str) -> bytes:
    key = os.environ.get("XAI_API_KEY") or ""
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    body = {"model": IMAGE_MODEL, "prompt": prompt}
    resp = get_http_client().post(IMAGE_URL, json=body, headers=headers)
    resp.raise_for_status()
    data = resp.json()
    url = data["data"][0]["url"]
    img = get_http_client().get(url)
    img.raise_for_status()
    return img.content
