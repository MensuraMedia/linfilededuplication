"""Rotating file logging + excepthook + GLib/GTK message capture. GTK-free at import.

Writes to the XDG state directory. Captures Python exceptions AND GLib/GTK log messages
(warnings, criticals) so a silent GTK-level failure still leaves a trace.
"""
from __future__ import annotations

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from linfilededuplication import APP_ID, APP_NAME, __version__

LOGGER_NAME = "linfilededuplication"


def _log_dir() -> Path:
    base = os.environ.get("XDG_STATE_HOME") or str(Path.home() / ".local" / "state")
    return Path(base) / APP_ID


def log_file() -> Path:
    return _log_dir() / "linfilededuplication.log"


def _install_glib_capture(logger: logging.Logger) -> None:
    """Route GLib/GTK log messages into the Python logger (best effort)."""
    try:
        from gi.repository import GLib
    except Exception:
        return

    level_map = [
        (GLib.LogLevelFlags.LEVEL_ERROR, logging.ERROR),
        (GLib.LogLevelFlags.LEVEL_CRITICAL, logging.ERROR),
        (GLib.LogLevelFlags.LEVEL_WARNING, logging.WARNING),
        (GLib.LogLevelFlags.LEVEL_MESSAGE, logging.INFO),
        (GLib.LogLevelFlags.LEVEL_INFO, logging.INFO),
        (GLib.LogLevelFlags.LEVEL_DEBUG, logging.DEBUG),
    ]

    def handler(domain, level, message, _user):
        py_level = logging.WARNING
        for flag, lv in level_map:
            if level & flag:
                py_level = lv
                break
        logger.log(py_level, "[%s] %s", domain or "GLib", message)

    try:
        GLib.log_set_default_handler(handler, None)
    except Exception:
        pass


def setup(debug: bool = False) -> logging.Logger:
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(logging.DEBUG if debug else logging.INFO)
    if logger.handlers:
        return logger

    fmt = logging.Formatter("%(asctime)s %(levelname)-7s %(name)s: %(message)s")
    try:
        d = _log_dir()
        d.mkdir(parents=True, exist_ok=True)
        fh = RotatingFileHandler(d / "linfilededuplication.log", maxBytes=1_000_000, backupCount=3)
        fh.setFormatter(fmt)
        logger.addHandler(fh)
    except OSError:
        pass
    sh = logging.StreamHandler()
    sh.setFormatter(fmt)
    logger.addHandler(sh)

    def _excepthook(exc_type, exc, tb):
        logger.error("Uncaught exception", exc_info=(exc_type, exc, tb))
        sys.__excepthook__(exc_type, exc, tb)

    sys.excepthook = _excepthook
    _install_glib_capture(logger)

    logger.info("%s %s starting (pid %s, python %s)", APP_NAME, __version__,
                os.getpid(), sys.version.split()[0])
    return logger
