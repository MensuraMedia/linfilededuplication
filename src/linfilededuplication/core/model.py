"""Result data model: FileEntry and DuplicateGroup. Pure dataclasses."""
from __future__ import annotations

import os
from dataclasses import dataclass, field

KIND_EXACT = "exact"
KIND_IMAGE = "image"
KIND_SIMILAR = "similar"        # advanced: near-identical content (chunking / fuzzy)


@dataclass(slots=True)
class FileEntry:
    # slots: no per-instance __dict__ — critical for comprehensive scans, where the walk
    # holds one FileEntry per file and a home tree can have millions of them.
    path: str
    size: int
    mtime: float
    is_image: bool = False
    width: int = 0
    height: int = 0
    full_hash: str = ""
    keeper: bool = False        # policy decided this is the file to keep
    is_backup: bool = False     # looks like a backup copy
    backup_confidence: float = 0.0
    effective_date: float = 0.0  # embedded date in name, else mtime
    is_newest: bool = False     # the most recent file in a backup group
    dev: int = 0                # filesystem id
    ino: int = 0                # inode; files sharing (dev, ino) are already hard-linked
    source: str = ""            # the scan source (root) this file was found under

    @property
    def name(self) -> str:
        return os.path.basename(self.path)

    @property
    def parent(self) -> str:
        return os.path.dirname(self.path)

    @property
    def pixels(self) -> int:
        return self.width * self.height

    @property
    def resolution(self) -> str:
        return f"{self.width}x{self.height}" if self.width and self.height else ""


@dataclass
class DuplicateGroup:
    kind: str                       # KIND_EXACT | KIND_IMAGE
    key: str                        # hash digest, or a perceptual cluster id
    files: list[FileEntry] = field(default_factory=list)
    distance: int = 0               # max perceptual Hamming distance within the group
    has_backups: bool = False       # at least one member looks like a backup

    @property
    def count(self) -> int:
        return len(self.files)

    @property
    def keeper(self) -> FileEntry | None:
        for f in self.files:
            if f.keeper:
                return f
        return self.files[0] if self.files else None

    @property
    def extras(self) -> list[FileEntry]:
        return [f for f in self.files if not f.keeper]

    @property
    def reclaimable(self) -> int:
        """Bytes freed by removing every non-keeper."""
        return sum(f.size for f in self.extras)

    @property
    def title(self) -> str:
        k = self.keeper
        return k.name if k else self.key[:12]
