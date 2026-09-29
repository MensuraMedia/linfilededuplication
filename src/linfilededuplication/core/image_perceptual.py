"""Perceptual image hashing and near-duplicate clustering. Pure.

Optional dependencies (Pillow + imagehash) are detected at runtime; when absent the
whole image pass is skipped and the caller shows an install hint. Nothing imports GTK.
"""
from __future__ import annotations

import threading
from collections import defaultdict
from typing import Callable

from linfilededuplication.core import events
from linfilededuplication.core.model import KIND_IMAGE, DuplicateGroup, FileEntry

try:
    from PIL import Image
    import imagehash
    HAVE_IMAGEHASH = True
except ImportError:                     # pragma: no cover - environment dependent
    HAVE_IMAGEHASH = False

Emit = Callable[[events.ScanEvent], None]


def read_dimensions(path: str) -> tuple[int, int]:
    if not HAVE_IMAGEHASH:
        return (0, 0)
    try:
        with Image.open(path) as im:
            return im.size
    except Exception:
        return (0, 0)


def phash(path: str):
    """Perceptual hash (64-bit) or None if the image cannot be read."""
    try:
        with Image.open(path) as im:
            return imagehash.phash(im)
    except Exception:
        return None


def find_similar_groups(images: list[FileEntry], max_distance: int, emit: Emit,
                        cancel: threading.Event | None = None) -> list[DuplicateGroup]:
    """Cluster images whose perceptual hashes are within ``max_distance`` bits.

    Union-find over pairwise Hamming distance. Bucketed by a hash prefix first to keep
    the comparison count down on large sets.
    """
    if not HAVE_IMAGEHASH:
        return []
    hashed: list[tuple[FileEntry, object]] = []
    for i, e in enumerate(images):
        if cancel is not None and cancel.is_set():
            break
        h = phash(e.path)
        if h is not None:
            e.width, e.height = read_dimensions(e.path)
            hashed.append((e, h))
        if i % 32 == 0:
            emit(events.Progress(i, len(images), "image", "Perceptual hashing images"))

    parent = list(range(len(hashed)))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: int, b: int) -> None:
        parent[find(a)] = find(b)

    # Bucket by the top 16 bits of the hash so only plausibly-close images are compared.
    buckets: dict[str, list[int]] = defaultdict(list)
    for idx, (_e, h) in enumerate(hashed):
        buckets[str(h)[:4]].append(idx)
    seen: set[int] = set()
    index_lists = list(buckets.values())
    # Also compare across adjacent buckets by falling back to an all-pairs pass when small.
    pairs_source = [range(len(hashed))] if len(hashed) <= 400 else index_lists
    for group_idx in pairs_source:
        idxs = list(group_idx)
        for a in range(len(idxs)):
            for b in range(a + 1, len(idxs)):
                ia, ib = idxs[a], idxs[b]
                if (hashed[ia][1] - hashed[ib][1]) <= max_distance:
                    union(ia, ib)

    clusters: dict[int, list[int]] = defaultdict(list)
    for idx in range(len(hashed)):
        clusters[find(idx)].append(idx)

    groups: list[DuplicateGroup] = []
    for members in clusters.values():
        if len(members) < 2:
            continue
        files = [hashed[m][0] for m in members]
        dist = 0
        for a in range(len(members)):
            for b in range(a + 1, len(members)):
                dist = max(dist, hashed[members[a]][1] - hashed[members[b]][1])
        grp = DuplicateGroup(kind=KIND_IMAGE, key=str(hashed[members[0]][1]),
                             files=files, distance=int(dist))
        groups.append(grp)
    return groups
