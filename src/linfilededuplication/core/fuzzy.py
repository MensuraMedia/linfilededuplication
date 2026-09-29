"""Fuzzy (similarity) hashing via TLSH or ssdeep. Pure, optional, runtime-detected.

Catches near-identical binaries, documents, and text that differ by small edits. When neither
library is present the pass is skipped and the caller shows an install hint.
"""
from __future__ import annotations

import os
import threading
from collections import defaultdict
from typing import Callable

from linfilededuplication.core import events
from linfilededuplication.core.model import KIND_SIMILAR, DuplicateGroup, FileEntry

try:
    import tlsh
    HAVE_TLSH = True
except ImportError:                     # pragma: no cover
    HAVE_TLSH = False

try:
    import ssdeep
    HAVE_SSDEEP = True
except ImportError:                     # pragma: no cover
    HAVE_SSDEEP = False

HAVE_FUZZY = HAVE_TLSH or HAVE_SSDEEP
_MIN_BYTES = 256                        # TLSH needs at least this much data
_MAX_FILE = 64 * 1024 * 1024
_MAX_CANDIDATES = 600

Emit = Callable[[events.ScanEvent], None]


def digest(path: str) -> str | None:
    try:
        if not (_MIN_BYTES <= os.path.getsize(path) <= _MAX_FILE):
            return None
        with open(path, "rb") as fh:
            data = fh.read(_MAX_FILE)
    except OSError:
        return None
    if HAVE_TLSH:
        try:
            h = tlsh.hash(data)
            return h if h and h != "TNULL" else None
        except Exception:
            return None
    if HAVE_SSDEEP:
        try:
            return ssdeep.hash(data)
        except Exception:
            return None
    return None


def _distance(a: str, b: str) -> int:
    """A small distance = very similar. TLSH: 0..>300; ssdeep: 0..100 similarity inverted."""
    if HAVE_TLSH:
        try:
            return tlsh.diff(a, b)
        except Exception:
            return 10_000
    if HAVE_SSDEEP:
        try:
            return 100 - ssdeep.compare(a, b)
        except Exception:
            return 10_000
    return 10_000


def find_fuzzy_groups(entries: list[FileEntry], max_distance: int, emit: Emit,
                      cancel: threading.Event | None = None) -> list[DuplicateGroup]:
    if not HAVE_FUZZY:
        return []
    candidates = [e for e in entries if _MIN_BYTES <= e.size <= _MAX_FILE][:_MAX_CANDIDATES]
    digs: list[tuple[FileEntry, str]] = []
    for i, e in enumerate(candidates):
        if cancel is not None and cancel.is_set():
            break
        d = digest(e.path)
        if d:
            digs.append((e, d))
        if i % 16 == 0:
            emit(events.Progress(i, len(candidates), "similar", "Fuzzy hashing"))

    parent = list(range(len(digs)))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for a in range(len(digs)):
        for b in range(a + 1, len(digs)):
            if _distance(digs[a][1], digs[b][1]) <= max_distance:
                parent[find(a)] = find(b)

    clusters: dict[int, list[int]] = defaultdict(list)
    for idx in range(len(digs)):
        clusters[find(idx)].append(idx)

    groups: list[DuplicateGroup] = []
    for members in clusters.values():
        if len(members) < 2:
            continue
        files = [digs[m][0] for m in members]
        worst = 0
        for a in range(len(members)):
            for b in range(a + 1, len(members)):
                worst = max(worst, _distance(digs[members[a]][1], digs[members[b]][1]))
        groups.append(DuplicateGroup(kind=KIND_SIMILAR, key=files[0].path,
                                     files=files, distance=int(worst)))
    return groups
