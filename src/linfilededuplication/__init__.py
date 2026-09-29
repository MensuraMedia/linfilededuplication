"""linfilededuplication (DedupeDash) — a GTK 4 + libadwaita file-deduplication dashboard.

Identity constants only; no imports, so every layer (including the pure core) can read them.
"""
from __future__ import annotations

APP_ID = "com.mensuramedia.linfilededuplication"
APP_NAME = "DedupeDash"          # visible product name
ICON_PREFIX = "app"              # embedded icons are named "app-<id>-symbolic"
__version__ = "0.1.0"
