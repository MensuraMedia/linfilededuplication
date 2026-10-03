"""Scan exclusions: named presets + custom globs, compiled to a fast matcher. Pure.

Excluded paths are never scanned and never become removal candidates, so this both focuses
the scan and hard-guards the user's system and app-recreatable files.
"""
from __future__ import annotations

import fnmatch
import os
from dataclasses import dataclass, field

# key -> (label, directory-name matches, absolute path prefixes, path/basename globs)
PRESETS: dict[str, dict] = {
    "system": {
        "label": "System files",
        # dir names cover Windows system folders found on mounted NTFS/USB drives
        "dirs": {"System Volume Information", "$SysReset", "Config.Msi", "Recovery"},
        "prefixes": ["/proc", "/sys", "/dev", "/run", "/boot", "/usr", "/lib", "/lib64", "/sbin", "/bin"],
        "globs": [],
    },
    "caches": {
        "label": "Caches and thumbnails",
        "dirs": {".cache", "Cache", "CachedData", ".thumbnails"},
        "prefixes": [],
        "globs": [],
    },
    "build": {
        "label": "Package and build artifacts",
        "dirs": {"node_modules", "__pycache__", ".venv", "venv", "build", "dist", "target",
                 "vendor", ".gradle", ".tox", ".mypy_cache", ".pytest_cache"},
        "prefixes": [],
        "globs": [],
    },
    "vcs": {
        "label": "Version-control internals",
        "dirs": {".git", ".svn", ".hg"},
        "prefixes": [],
        "globs": [],
    },
    "apps": {
        "label": "App and runtime files",
        "dirs": set(),
        "prefixes": ["/opt", "/var/lib/flatpak", "/snap"],
        "globs": [],
    },
    "stubs": {
        "label": "Known stubs and noise",
        "dirs": set(),
        "prefixes": [],
        "globs": ["*/.DS_Store", ".DS_Store", "*/Thumbs.db", "Thumbs.db", "*/desktop.ini", "desktop.ini"],
    },
    "trash": {
        "label": "Trash and recycle bins",
        # Linux Trash plus Windows/macOS recycle bins on mounted drives (case variants included)
        "dirs": {".Trash", "$RECYCLE.BIN", "$Recycle.Bin", "$RECYCLER", "RECYCLER", "RECYCLED",
                 ".Trashes"},
        "prefixes": [],
        "globs": ["*/.local/share/Trash/*", "*/.Trash-*/*"],
    },
}

# All presets on by default; build/vcs are easy to switch off in Settings.
DEFAULT_ON = list(PRESETS.keys())


def preset_label(key: str) -> str:
    return PRESETS.get(key, {}).get("label", key)


@dataclass
class Matcher:
    dirs: set[str] = field(default_factory=set)
    prefixes: list[str] = field(default_factory=list)
    globs: list[str] = field(default_factory=list)

    def excludes(self, path: str, is_dir: bool) -> bool:
        base = os.path.basename(path.rstrip("/"))
        if is_dir and base in self.dirs:
            return True
        for prefix in self.prefixes:
            if path == prefix or path.startswith(prefix + "/"):
                return True
        for g in self.globs:
            if fnmatch.fnmatch(path, g) or fnmatch.fnmatch(base, g):
                return True
        return False


def compile(preset_keys: list[str] | None, custom_globs: list[str] | None = None) -> Matcher:
    keys = DEFAULT_ON if preset_keys is None else preset_keys
    m = Matcher()
    for key in keys:
        preset = PRESETS.get(key)
        if not preset:
            continue
        m.dirs |= set(preset["dirs"])
        m.prefixes += list(preset["prefixes"])
        m.globs += list(preset["globs"])
    m.globs += list(custom_globs or [])
    return m
