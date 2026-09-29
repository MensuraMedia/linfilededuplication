"""Enforce core purity: no module under core/ may import GTK.

Runs in a subprocess with gi (and friends) blocked, so any leaked `import gi` fails.
"""
from __future__ import annotations

import pkgutil
import subprocess
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "src"


def _core_modules() -> list[str]:
    import linfilededuplication.core as core
    return [f"linfilededuplication.core.{m.name}"
            for m in pkgutil.iter_modules(core.__path__) if not m.name.startswith("_")]


def test_core_imports_no_gtk() -> None:
    sys.path.insert(0, str(SRC))
    modules = _core_modules()
    assert modules, "no core modules discovered"
    script = (
        "import sys\n"
        "for name in ('gi', 'gi.repository', 'cairo'):\n"
        "    sys.modules[name] = None\n"
        "import importlib\n"
        f"for m in {modules!r}:\n"
        "    importlib.import_module(m)\n"
        "print('pure')\n"
    )
    proc = subprocess.run(
        [sys.executable, "-c", script],
        env={"PYTHONPATH": str(SRC), "PATH": "/usr/bin:/bin"},
        capture_output=True, text=True,
    )
    assert proc.returncode == 0, f"core imported GTK:\n{proc.stderr}"
    assert proc.stdout.strip() == "pure"
