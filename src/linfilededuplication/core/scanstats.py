"""Scan performance log: one record per completed scan — when it ran, how long it took, how many
files were scanned / reused / re-hashed, and the drive each source lives on. GTK-free; tolerant
JSON like the rest of the state stores. Powers the Scan-page "Cached" indicator and the History
page's recent-scans list.
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

from linfilededuplication import APP_ID

MAX_ENTRIES = 50


def _path() -> Path:
    base = os.environ.get("XDG_STATE_HOME") or str(Path.home() / ".local" / "state")
    return Path(base) / APP_ID / "scanruns.json"


@dataclass
class SourceStat:
    path: str = ""
    files_scanned: int = 0          # files walked under this source
    files_hashed: int = 0           # candidates actually read & hashed this run
    files_reused: int = 0           # cache hits — fingerprints reused, file not re-read
    bytes_scanned: int = 0          # total size of files walked under this source
    drive: dict = field(default_factory=dict)   # DriveInfo.to_dict()

    @property
    def fingerprinted(self) -> int:
        return self.files_hashed + self.files_reused

    @property
    def cache_hit_pct(self) -> int:
        tot = self.fingerprinted
        return round(100 * self.files_reused / tot) if tot else 0


@dataclass
class ScanRun:
    when: float = field(default_factory=time.time)
    duration: float = 0.0
    tier: str = "simple"            # "simple" | "advanced"
    cancelled: bool = False
    used_cache: bool = True
    total_files: int = 0
    total_hashed: int = 0
    total_reused: int = 0
    groups: int = 0
    reclaimable_bytes: int = 0
    sources: list = field(default_factory=list)   # list[SourceStat]

    @property
    def throughput(self) -> float:
        """Files scanned per second (0 when duration is unknown)."""
        return self.total_files / self.duration if self.duration > 0 else 0.0

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "ScanRun":
        data = dict(data or {})
        src_fields = set(SourceStat.__dataclass_fields__)
        sources = [SourceStat(**{k: v for k, v in (s or {}).items() if k in src_fields})
                   for s in data.get("sources", []) if isinstance(s, dict)]
        known = set(cls.__dataclass_fields__)
        run = cls(**{k: v for k, v in data.items() if k in known and k != "sources"})
        run.sources = sources
        return run


class ScanStatsStore:
    """Load / append the scan-performance log (newest first), capped to ``MAX_ENTRIES``."""

    def __init__(self, path: Path | None = None) -> None:
        self._path = path or _path()

    def load(self) -> list[ScanRun]:
        try:
            data = json.loads(self._path.read_text())
        except (OSError, ValueError):
            return []
        runs = data.get("runs", []) if isinstance(data, dict) else []
        return [ScanRun.from_dict(r) for r in runs if isinstance(r, dict)]

    def add(self, run: ScanRun) -> None:
        runs = self.load()
        runs.insert(0, run)
        runs = runs[:MAX_ENTRIES]
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(json.dumps({"runs": [r.to_dict() for r in runs]}, indent=2))
        except OSError:
            pass

    def last_for_source(self, path: str) -> tuple[ScanRun, SourceStat] | None:
        """Most recent run (and its per-source stats) that scanned ``path``."""
        p = path.rstrip("/")
        for run in self.load():
            for s in run.sources:
                if s.path.rstrip("/") == p:
                    return run, s
        return None
