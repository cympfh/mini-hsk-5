from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VOCAB_PATH = ROOT / "data" / "vocab" / "hsk5-old-inclusive.json"
TEMPLATES = ROOT / "templates"
MODEL = "grok-4.6"


def data_dir() -> Path:
    return Path(os.environ.get("HSK5_DATA_DIR", str(ROOT / "data")))


def exams_dir() -> Path:
    return data_dir() / "exams"


def db_path() -> Path:
    return data_dir() / "app.db"
