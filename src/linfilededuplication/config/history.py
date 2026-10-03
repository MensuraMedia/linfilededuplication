"""Scan/dedup history: a tolerant JSON log of each completed deduplicate operation. GTK-free.

An entry is recorded whenever the user confirms a removal (Trash / Delete All Duplicates /
Hard-link), success or failure. The History page reads these to show the last operation (with
before/after bars and the space saved) and the ones before it.
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

from linfilededuplication import APP_ID

MAX_ENTRIES = 100


def _history_path() -> Path:
    base = os.environ.get("XDG_STATE_HOME") or str(Path.home() / ".local" / "state")
    return Path(base) / APP_ID / "history.json"


@dataclass
class HistoryEntry:
    when: float = field(default_factory=time.time)   # epoch seconds
    sources: list[str] = field(default_factory=list)  # roots that were scanned
    action: str = "trash"                            # "trash" | "hardlink"
    ok: bool = True
    error: str = ""
    before_bytes: int = 0                            # footprint of the duplicate set at scan time
    freed_bytes: int = 0                             # bytes reclaimed by this operation
    files_removed: int = 0
    groups: int = 0

    @property
    def after_bytes(self) -> int:
        return max(0, self.before_bytes - self.freed_bytes)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "HistoryEntry":
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in (data or {}).items() if k in known})


class HistoryStore:
    """Load/append the operation history (newest-first), capped to ``MAX_ENTRIES``."""

    def __init__(self, path: Path | None = None) -> None:
        self._path = path or _history_path()

    def load(self) -> list[HistoryEntry]:
        try:
            data = json.loads(self._path.read_text())
        except (OSError, ValueError):
            return []
        items = data.get("entries", []) if isinstance(data, dict) else data
        out = [HistoryEntry.from_dict(d) for d in items if isinstance(d, dict)]
        out.sort(key=lambda e: e.when, reverse=True)      # newest first
        return out

    def add(self, entry: HistoryEntry) -> None:
        entries = self.load()
        entries.insert(0, entry)
        entries = entries[:MAX_ENTRIES]
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(json.dumps(
                {"entries": [e.to_dict() for e in entries]}, indent=2))
        except OSError:
            pass

    def latest(self) -> HistoryEntry | None:
        entries = self.load()
        return entries[0] if entries else None
