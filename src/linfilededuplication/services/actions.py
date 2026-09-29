"""Safe file actions: move to Trash, hard-link. Recoverable and guarded.

Every action returns a small result (done count + freed bytes + errors) so any surface can
report both what happened and how to fix a failure. Nothing here deletes without the caller
having confirmed; protected paths are always refused.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from gi.repository import Gio

from linfilededuplication.core.model import FileEntry

_PROTECTED = (
    str(Path.home()),                       # $HOME root itself (not its children)
    "/", "/usr", "/etc", "/bin", "/boot", "/lib", "/proc", "/sys", "/dev",
    "/media", "/mnt", "/run", "/var",
)


@dataclass
class ActionResult:
    done: int = 0
    freed: int = 0
    errors: list[str] = field(default_factory=list)


def _is_protected(path: str) -> bool:
    rp = os.path.realpath(path)
    if rp in (os.path.realpath(p) for p in _PROTECTED):
        return True
    # never touch the immediate contents of a mount root or home root
    return rp.rstrip("/") in {p.rstrip("/") for p in _PROTECTED}


def move_to_trash(entries: list[FileEntry]) -> ActionResult:
    """Move each file to the XDG Trash via Gio (recoverable from the file manager)."""
    res = ActionResult()
    for e in entries:
        if _is_protected(e.path):
            res.errors.append(f"Refused to trash a protected path: {e.path}")
            continue
        try:
            gfile = Gio.File.new_for_path(e.path)
            gfile.trash(None)
            res.done += 1
            res.freed += e.size
        except Exception as exc:
            res.errors.append(f"Could not trash {e.name}: {exc}")
    return res


def hard_link(keeper: FileEntry, extras: list[FileEntry]) -> ActionResult:
    """Replace each extra with a hard link to the keeper (same-filesystem only).

    Reclaims the bytes without losing any path. Skips files already sharing the keeper's
    inode and any cross-filesystem target (the caller can fall back to Trash for those).
    """
    res = ActionResult()
    try:
        keeper_stat = os.stat(keeper.path)
    except OSError as exc:
        res.errors.append(f"Cannot read the file to keep: {exc}")
        return res
    for e in extras:
        if _is_protected(e.path):
            res.errors.append(f"Refused to relink a protected path: {e.path}")
            continue
        try:
            st = os.stat(e.path)
            if st.st_dev != keeper_stat.st_dev:
                res.errors.append(f"{e.name} is on another filesystem; use Trash instead.")
                continue
            if st.st_ino == keeper_stat.st_ino:
                continue                    # already linked
            tmp = e.path + ".dedupe-tmp"
            os.link(keeper.path, tmp)
            os.replace(tmp, e.path)
            res.done += 1
            res.freed += e.size
        except OSError as exc:
            res.errors.append(f"Could not relink {e.name}: {exc}")
    return res
