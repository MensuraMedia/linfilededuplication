"""Content-defined anchor sampling and chunk-set similarity. Pure (stdlib).

A gear rolling hash scans a shift-resistant window across the file; positions whose hash hits
a sampling mask become "anchors", and the set of anchor hashes fingerprints the file's content.
Two files that share most content share most anchors even after an edit or insertion, so their
anchor-set overlap (Jaccard) measures near-identical content for Advanced Scan.
"""
from __future__ import annotations

import hashlib
import os
import random
import threading
from collections import defaultdict
from typing import Callable

from linfilededuplication.core import events
from linfilededuplication.core.model import KIND_SIMILAR, DuplicateGroup, FileEntry

# Deterministic gear table (fixed seed -> identical every run).
_GEAR = random.Random(0xC0FFEE).sample(range(2**32), 256)
_WINDOW = 32                     # rolling window (bytes)
_MASK = 0x1F                     # sample ~1 anchor in 32 positions
_MIN_SIZE = 64
_MAX_FILE = 2 * 1024 * 1024      # cap: content similarity is for smallish files
_MAX_SIGS = 4000
_MAX_CANDIDATES = 400

Emit = Callable[[events.ScanEvent], None]


def chunk_signatures(path: str) -> frozenset[bytes]:
    """The set of content-defined anchor fingerprints for a file."""
    try:
        with open(path, "rb") as fh:
            data = fh.read(_MAX_FILE)
    except OSError:
        return frozenset()
    n = len(data)
    if n == 0:
        return frozenset()
    sigs: set[bytes] = set()
    h = 0
    for i in range(n):
        h = ((h << 1) + _GEAR[data[i]]) & 0xFFFFFFFF
        if i >= _WINDOW - 1 and (h & _MASK) == 0:
            sigs.add(h.to_bytes(4, "big"))
            if len(sigs) >= _MAX_SIGS:
                break
    if not sigs:                                # no anchor hit (tiny/uniform file)
        sigs.add(hashlib.blake2b(data, digest_size=8).digest())
    return frozenset(sigs)


def jaccard(a: frozenset[bytes], b: frozenset[bytes]) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    union = len(a | b)
    return len(a & b) / union if union else 0.0


def find_similar_groups(entries: list[FileEntry], threshold: float, emit: Emit,
                        cancel: threading.Event | None = None) -> list[DuplicateGroup]:
    """Cluster files whose anchor sets overlap by at least ``threshold`` (0..1)."""
    candidates = [e for e in entries if _MIN_SIZE <= e.size <= _MAX_FILE][:_MAX_CANDIDATES]
    sigs: list[tuple[FileEntry, frozenset[bytes]]] = []
    for i, e in enumerate(candidates):
        if cancel is not None and cancel.is_set():
            break
        s = chunk_signatures(e.path)
        if s:
            sigs.append((e, s))
        if i % 16 == 0:
            emit(events.Progress(i, len(candidates), "similar", "Comparing content"))

    parent = list(range(len(sigs)))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for a in range(len(sigs)):
        for b in range(a + 1, len(sigs)):
            if jaccard(sigs[a][1], sigs[b][1]) >= threshold:
                parent[find(a)] = find(b)

    clusters: dict[int, list[int]] = defaultdict(list)
    for idx in range(len(sigs)):
        clusters[find(idx)].append(idx)

    groups: list[DuplicateGroup] = []
    for members in clusters.values():
        if len(members) < 2:
            continue
        files = [sigs[m][0] for m in members]
        worst = 1.0
        for a in range(len(members)):
            for b in range(a + 1, len(members)):
                worst = min(worst, jaccard(sigs[members[a]][1], sigs[members[b]][1]))
        grp = DuplicateGroup(kind=KIND_SIMILAR, key=files[0].path,
                             files=files, distance=int(worst * 100))
        groups.append(grp)
    return groups
