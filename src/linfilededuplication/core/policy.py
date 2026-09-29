"""Keep/delete policy: choose which file in a group to keep. Pure.

Default order (re-orderable in Advanced Scan):
  1. Highest resolution (width x height) -- images only
  2. Largest file size
  3. Non-derived filename (no copy / -1 / resized / thumb)
  4. Inside a preferred folder
  5. Oldest modification time
  6. Shallowest path depth (tie-break)
So a full-resolution original always outranks a resized or re-compressed copy.
"""
from __future__ import annotations

import re

from linfilededuplication.core.model import KIND_IMAGE, DuplicateGroup, FileEntry

# A derived copy adds a duplicate marker to an otherwise complete name. Match those markers
# only -- never a bare "name_1234" (camera files like IMG_2381 are not derived).
_DERIVED = re.compile(
    r"(copy of|\bcopy\b|\(\s*\d+\s*\)|[-_ ](?:resized|small|thumb|thumbnail|edited?|dup(?:licate)?)\b)",
    re.IGNORECASE)


def _is_derived(name: str) -> bool:
    return bool(_DERIVED.search(name))


def _score(f: FileEntry, is_image: bool, preferred: list[str]) -> tuple:
    """Higher tuple sorts first (the keeper). Mirrors the documented order."""
    in_preferred = any(f.path.startswith(p) for p in preferred)
    return (
        f.pixels if is_image else 0,        # 1. resolution (images)
        f.size,                             # 2. size
        0 if _is_derived(f.name) else 1,    # 3. original name beats derived
        1 if in_preferred else 0,           # 4. preferred folder
        -f.mtime,                           # 5. oldest wins
        -f.path.count("/"),                 # 6. shallower wins
    )


def rank(group: DuplicateGroup, preferred: list[str] | None = None) -> DuplicateGroup:
    """Mark exactly one file as the keeper; leave the rest as removal candidates."""
    preferred = preferred or []
    is_image = group.kind == KIND_IMAGE
    for f in group.files:
        f.keeper = False
    if not group.files:
        return group
    winner = max(group.files, key=lambda f: _score(f, is_image, preferred))
    winner.keeper = True
    # keeper first, then extras largest-first, for stable display
    group.files.sort(key=lambda f: (not f.keeper, -f.size))
    return group
