"""Probable-backup detection: name / date / location signals -> confidence + age. Pure.

Advisory only: flagging never deletes anything. A group is treated as "has backups" only when
a real name or location signal is present, so ordinary duplicates are not mislabelled.
"""
from __future__ import annotations

import datetime as _dt
import os
import re

from linfilededuplication.core.model import DuplicateGroup, FileEntry

_BACKUP_EXT = {".bak", ".old", ".orig", ".save", ".swp", ".tmp", ".backup"}
_BACKUP_WORDS = re.compile(r"(?:\bbackup\b|\bbak\b|\bcopy\b|copy of|\bold\b|\barchive\b|~$|\bv\d+\b)",
                           re.IGNORECASE)
_BACKUP_DIRS = {"backup", "backups", "snapshot", "snapshots", "old", "archive", "archives", "bak"}
_DATE_RE = re.compile(r"(20\d{2}|19\d{2})[-_.]?(0[1-9]|1[0-2])[-_.]?(0[1-9]|[12]\d|3[01])")
_YEAR_RE = re.compile(r"\((20\d{2}|19\d{2})\)")


def embedded_date(name: str) -> float | None:
    """A timestamp parsed from a date embedded in the filename, or None."""
    m = _DATE_RE.search(name)
    if m:
        try:
            return _dt.datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))).timestamp()
        except ValueError:
            return None
    y = _YEAR_RE.search(name)
    if y:
        try:
            return _dt.datetime(int(y.group(1)), 1, 1).timestamp()
        except ValueError:
            return None
    return None


def classify(entry: FileEntry) -> None:
    """Set is_backup / backup_confidence / effective_date on the entry in place."""
    name = entry.name
    ext = os.path.splitext(name)[1].lower()
    parent = os.path.basename(entry.parent).lower()
    score = 0.0
    if name.endswith("~") or ext in _BACKUP_EXT:
        score += 0.6
    if _BACKUP_WORDS.search(name):
        score += 0.4
    if parent in _BACKUP_DIRS:
        score += 0.4
    date = embedded_date(name)
    if date is not None:
        score += 0.2
    entry.backup_confidence = min(1.0, score)
    entry.is_backup = score >= 0.5
    entry.effective_date = date if date is not None else entry.mtime


def analyze_group(group: DuplicateGroup) -> None:
    """Classify each file, then, if any is a backup, mark the newest one.

    A single dated filename is not enough on its own, but two or more dated siblings in the
    same group are a clear dated-backup series (``db-2023.sql``, ``db-2024.sql``).
    """
    for f in group.files:
        classify(f)
    dated = [f for f in group.files if embedded_date(f.name) is not None]
    if len(dated) >= 2:
        for f in dated:
            f.is_backup = True
            f.backup_confidence = max(f.backup_confidence, 0.6)
    group.has_backups = any(f.is_backup for f in group.files)
    if group.has_backups and group.files:
        newest = max(group.files, key=lambda f: f.effective_date)
        for f in group.files:
            f.is_newest = f is newest
