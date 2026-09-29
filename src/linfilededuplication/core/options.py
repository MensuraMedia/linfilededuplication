"""ScanOptions: everything the user configures for one scan. Pure, JSON-friendly."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any

TIER_SIMPLE = "simple"
TIER_ADVANCED = "advanced"


@dataclass
class ScanOptions:
    root: str = ""
    tier: str = TIER_SIMPLE
    find_images: bool = True          # image near-duplicates via perceptual hash
    include_hidden: bool = False      # dotfiles / dot-folders
    follow_symlinks: bool = False
    min_size: int = 1                 # bytes; skip empty and tiny files
    hamming: int = 8                  # max perceptual Hamming distance (0-64)
    verify_bytes: bool = True         # byte-for-byte confirm before an exact group is final
    detect_backups: bool = True       # flag probable backup copies
    keep_newest_backup: bool = True   # in a backup group, keep the newest
    exclusions: list[str] = field(default_factory=list)   # exclusion preset keys
    exclude: list[str] = field(default_factory=list)      # custom glob patterns
    # Advanced-only signals (wired in later phases):
    fuzzy: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ScanOptions":
        """Tolerant: ignore unknown keys, default missing ones."""
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in (data or {}).items() if k in known})
