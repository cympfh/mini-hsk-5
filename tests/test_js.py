from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEMPLATES = ROOT / "templates"


def test_no_frontend_frameworks() -> None:
    blob = (
        (TEMPLATES / "app.js").read_text()
        + (TEMPLATES / "index.html").read_text()
        + (TEMPLATES / "app.css").read_text()
    ).lower()
    for needle in ("react", "vue", "jquery", "angular", "svelte", "cdn.jsdelivr", "unpkg"):
        assert needle not in blob, needle
    js = (TEMPLATES / "app.js").read_text()
    assert "import " not in js
    assert "export " not in js
    assert "require(" not in js
    html = (TEMPLATES / "index.html").read_text()
    assert 'src="/app.js' in html
    assert "cdn" not in html.lower()
    assert "試験開始" in js
    assert "data-start" in js


def test_app_js_runs_in_window() -> None:
    proc = subprocess.run(
        ["node", str(ROOT / "tests" / "js_load.js")],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "js-load ok" in proc.stdout
