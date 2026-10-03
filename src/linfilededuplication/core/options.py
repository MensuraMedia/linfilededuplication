"""ScanOptions: everything the user configures for one scan. Pure, JSON-friendly."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any

TIER_SIMPLE = "simple"
TIER_ADVANCED = "advanced"


@dataclass
class ScanOptions:
    root: str = ""                    # single source (legacy); see roots
    roots: list[str] = field(default_factory=list)  # multiple sources; takes precedence
    tier: str = TIER_SIMPLE
    find_images: bool = True          # image near-duplicates via perceptual hash
    include_hidden: bool = False      # dotfiles / dot-folders
    follow_symlinks: bool = False
    min_size: int = 1                 # bytes; skip empty and tiny files
    hamming: int = 8                  # max perceptual Hamming distance (0-64)
    verify_bytes: bool = True         # byte-for-byte confirm before an exact group is final
    use_hash_cache: bool = True       # reuse cached hashes for unchanged files (fast re-scans)
    detect_backups: bool = True       # flag probable backup copies
    keep_newest_backup: bool = True   # in a backup group, keep the newest
    exclusions: list[str] = field(default_factory=list)   # exclusion preset keys
    exclude: list[str] = field(default_factory=list)      # custom glob patterns
    file_types: list[str] = field(default_factory=list)   # extensions to include; [] = all
    ignore_paths: list[str] = field(default_factory=list)  # exact files to skip (user "Ignore")
    ignore_dirs: list[str] = field(default_factory=list)   # folders to skip entirely (+ contents)
    # Advanced-tier signals:
    advanced_similar: bool = False    # find near-identical content (chunking + fuzzy)
    similar_threshold: float = 0.55   # min chunk-overlap (0..1) for a similar group
    fuzzy: bool = True                # use fuzzy hashing when available
    fuzzy_distance: int = 80          # max fuzzy distance for a similar group

    def all_roots(self) -> list[str]:
        """The effective list of sources to scan (roots wins; falls back to root)."""
        if self.roots:
            seen, out = set(), []
            for r in self.roots:
                r = r.rstrip("/") or "/"
                if r and r not in seen:
                    seen.add(r)
                    out.append(r)
            return out
        return [self.root.rstrip("/") or "/"] if self.root else []

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ScanOptions":
        """Tolerant: ignore unknown keys, default missing ones."""
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in (data or {}).items() if k in known})
