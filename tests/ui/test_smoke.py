"""Headless smoke test: the app builds every page and exits cleanly.

Runs `python -m linfilededuplication --smoke` under xvfb. Skipped when the GTK 4 / Adwaita
stack or xvfb-run is unavailable, so the pure-core suite still runs anywhere.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _has_gtk() -> bool:
    try:
        import gi
        gi.require_version("Gtk", "4.0")
        gi.require_version("Adw", "1")
        return True
    except Exception:
        return False


@pytest.mark.skipif(not _has_gtk(), reason="GTK 4 / libadwaita not available")
def test_app_builds_headless():
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT / "src")
    env["LINFILEDEDUPLICATION_DATA_DIR"] = str(ROOT / "data")
    cmd = [sys.executable, "-m", "linfilededuplication", "--smoke"]
    if shutil.which("xvfb-run") and not env.get("DISPLAY"):
        cmd = ["xvfb-run", "-a", *cmd]
    elif not env.get("DISPLAY") and not shutil.which("xvfb-run"):
        pytest.skip("no display and no xvfb-run")
    proc = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=60)
    assert proc.returncode == 0, f"smoke run failed:\n{proc.stdout}\n{proc.stderr}"
