"""Persisted user settings: a tolerant JSON file under the XDG config dir. GTK-free."""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path

from linfilededuplication import APP_ID
from linfilededuplication.core.exclusions import DEFAULT_ON

SCHEMA = 1


def _config_path() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / APP_ID / "settings.json"


@dataclass
class Settings:
    schema: int = SCHEMA
    style: str = "system"           # system | light | dark
    last_root: str = ""
    tier: str = "simple"
    find_images: bool = True
    include_hidden: bool = False
    min_size_mb: int = 1
    hamming: int = 8
    default_action: str = "trash"   # trash | hardlink
    dry_run: bool = True
    detect_backups: bool = True
    keep_newest_backup: bool = True
    similar_threshold: float = 0.55
    exclusions: list[str] = field(default_factory=lambda: list(DEFAULT_ON))
    file_types: list[str] = field(default_factory=list)   # [] = all types

    @classmethod
    def load(cls) -> "Settings":
        path = _config_path()
        try:
            data = json.loads(path.read_text())
        except (OSError, ValueError):
            return cls()
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in data.items() if k in known})

    def save(self) -> None:
        path = _config_path()
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(asdict(self), indent=2))
        except OSError:
            pass
