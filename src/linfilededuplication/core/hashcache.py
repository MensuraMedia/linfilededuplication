"""Persistent hash cache for fast repeat / cross-source scans. Pure (stdlib json only).

Stores each hashed file's fingerprint ``{dev, ino, size, mtime}`` alongside its SHA-256. On a
later scan, a file whose size + mtime (and inode) are unchanged is a cache HIT — its digest is
reused and the file is not read again; any change is a MISS, so it is re-hashed. This is the
"unchanged ⇒ skip, changed ⇒ rescan" fast path. The byte-for-byte verification in the scanner
remains the safety net, so a stale (mtime-preserving) edit can never cause a wrong removal.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from linfilededuplication import APP_ID

MAX_ENTRIES = 300_000


def _cache_path() -> Path:
    base = os.environ.get("XDG_STATE_HOME") or str(Path.home() / ".local" / "state")
    return Path(base) / APP_ID / "hashcache.json"


class HashCache:
    def __init__(self, path: Path | None = None) -> None:
        self._path = path or _cache_path()
        self._data: dict[str, list] = {}      # path -> [dev, ino, size, mtime, sha256]
        self._dirty = False
        try:
            raw = json.loads(self._path.read_text())
            if isinstance(raw, dict):
                self._data = {k: v for k, v in raw.get("files", {}).items()
                              if isinstance(v, list) and len(v) == 5}
        except (OSError, ValueError):
            self._data = {}

    def get(self, e) -> str | None:
        """Return the cached digest when the file looks unchanged, else None (needs re-hashing).

        Match on **size + mtime** — the fields that reveal a content change. The device id and
        inode are deliberately *not* required: they change when a removable drive is remounted (a
        new `st_dev`, and some filesystems — exFAT/NTFS — don't preserve inodes), which would
        otherwise miss the entire drive and force a full re-hash on every repeat scan. Byte-for-
        byte verification remains the safety net before any file is removed, so a rare coincidental
        size+mtime match on different content can never cause a wrong removal.
        """
        rec = self._data.get(e.path)
        if rec and rec[2] == e.size and rec[3] == e.mtime:
            return rec[4]
        return None

    def put(self, e, sha: str) -> None:
        self._data[e.path] = [e.dev, e.ino, e.size, e.mtime, sha]
        self._dirty = True

    def remove(self, paths) -> None:
        """Drop entries for files that were removed or changed by a dedup operation."""
        changed = False
        for p in paths:
            if self._data.pop(p, None) is not None:
                changed = True
        if changed:
            self._dirty = True
            self.save(force=True)

    def save(self, force: bool = False) -> None:
        if not (self._dirty or force):
            return
        data = self._data
        if len(data) > MAX_ENTRIES:            # cap growth: keep the most-recently written
            data = dict(list(data.items())[-MAX_ENTRIES:])
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(json.dumps({"files": data}))
            self._dirty = False
        except OSError:
            pass

    def __len__(self) -> int:
        return len(self._data)
