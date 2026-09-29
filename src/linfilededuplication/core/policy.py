"""Keep/delete policy: choose which file in a group to keep. Pure.

Default order (re-orderable in Advanced Scan):
  0. In a backup group: newest generation, but a non-backup original beats a
     marginally newer .bak (within BACKUP_CLOSE_SECONDS)
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

# Backup files whose effective dates fall within this window count as the same generation,
# so the non-backup original is kept rather than a marginally newer .bak.
BACKUP_CLOSE_SECONDS = 300

# A derived copy adds a duplicate marker to an otherwise complete name. Match those markers
# only -- never a bare "name_1234" (camera files like IMG_2381 are not derived).
_DERIVED = re.compile(
    r"(copy of|\bcopy\b|\(\s*\d+\s*\)|[-_ ](?:resized|small|thumb|thumbnail|edited?|dup(?:licate)?)\b)",
    re.IGNORECASE)


def _is_derived(name: str) -> bool:
    return bool(_DERIVED.search(name))


def _score(f: FileEntry, is_image: bool, preferred: list[str], backup_mode: bool) -> tuple:
    """Higher tuple sorts first (the keeper). Mirrors the documented order."""
    in_preferred = any(f.path.startswith(p) for p in preferred)
    date_bucket = int(f.effective_date // BACKUP_CLOSE_SECONDS) if backup_mode else 0
    non_backup = (0 if f.is_backup else 1) if backup_mode else 0
    return (
        date_bucket,                        # 0a. newer backup generation wins...
        non_backup,                         # 0b. ...but within a close window keep the original
        f.pixels if is_image else 0,        # 1. resolution (images)
        f.size,                             # 2. size
        0 if _is_derived(f.name) else 1,    # 3. original name beats derived
        1 if in_preferred else 0,           # 4. preferred folder
        -f.mtime,                           # 5. oldest wins
        -f.path.count("/"),                 # 6. shallower wins
    )


def rank(group: DuplicateGroup, preferred: list[str] | None = None,
         keep_newest: bool = True) -> DuplicateGroup:
    """Mark exactly one file as the keeper; leave the rest as removal candidates.

    In a group flagged as backups, ``keep_newest`` puts the most recent copy on top.
    """
    preferred = preferred or []
    is_image = group.kind == KIND_IMAGE
    backup_mode = group.has_backups and keep_newest
    for f in group.files:
        f.keeper = False
    if not group.files:
        return group
    winner = max(group.files, key=lambda f: _score(f, is_image, preferred, backup_mode))
    winner.keeper = True
    # keeper first, then extras largest-first, for stable display
    group.files.sort(key=lambda f: (not f.keeper, -f.size))
    return group
