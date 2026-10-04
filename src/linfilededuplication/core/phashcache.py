"""Perceptual-hash cache for images: reuse pHash/dHash (and pixel size) for an image unchanged
since the last scan, so repeat image scans don't re-open and re-hash every photo. Pure (stdlib
json only); same remount-tolerant screening as the content hash cache — match on size + mtime.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from linfilededuplication import APP_ID

MAX_ENTRIES = 200_000


def _cache_path() -> Path:
    base = os.environ.get("XDG_STATE_HOME") or str(Path.home() / ".local" / "state")
    return Path(base) / APP_ID / "phashcache.json"


class PHashCache:
    """``path -> [size, mtime, phash_hex, dhash_hex, [w, h]]``."""

    def __init__(self, path: Path | None = None) -> None:
        self._path = path or _cache_path()
        self._data: dict[str, list] = {}
        self._dirty = False
        try:
            raw = json.loads(self._path.read_text())
            if isinstance(raw, dict):
                self._data = {k: v for k, v in raw.get("images", {}).items()
                              if isinstance(v, list) and len(v) == 5}
        except (OSError, ValueError):
            self._data = {}

    def get(self, e):
        """Return ``(phash_hex, dhash_hex, (w, h))`` when unchanged (size + mtime), else None."""
        rec = self._data.get(e.path)
        if rec and rec[0] == e.size and rec[1] == e.mtime:
            wh = rec[4]
            return rec[2], rec[3], (wh[0], wh[1]) if isinstance(wh, (list, tuple)) and len(wh) == 2 else (0, 0)
        return None

    def put(self, e, phash_hex: str, dhash_hex: str, size_wh) -> None:
        w, h = (size_wh or (0, 0))[:2] if size_wh else (0, 0)
        self._data[e.path] = [e.size, e.mtime, phash_hex, dhash_hex, [w, h]]
        self._dirty = True

    def save(self, force: bool = False) -> None:
        if not (self._dirty or force):
            return
        data = self._data
        if len(data) > MAX_ENTRIES:
            data = dict(list(data.items())[-MAX_ENTRIES:])
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(json.dumps({"images": data}))
            self._dirty = False
        except OSError:
            pass

    def __len__(self) -> int:
        return len(self._data)
