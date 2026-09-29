"""Result data model: FileEntry and DuplicateGroup. Pure dataclasses."""
from __future__ import annotations

import os
from dataclasses import dataclass, field

KIND_EXACT = "exact"
KIND_IMAGE = "image"


@dataclass
class FileEntry:
    path: str
    size: int
    mtime: float
    is_image: bool = False
    width: int = 0
    height: int = 0
    full_hash: str = ""
    keeper: bool = False        # policy decided this is the file to keep

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
