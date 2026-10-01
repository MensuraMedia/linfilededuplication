"""Popular file-type categories for the Scan page filter. Pure (stdlib only).

Each category (Images / Video / Music / Documents) lists a few popular *types*; a type is a
label mapped to one or more extensions (e.g. JPG -> .jpg/.jpeg). The Scan page renders these
as checkboxes with an "All" per column; the chosen extensions go into ``ScanOptions.file_types``
and the walk keeps only matching files. An empty selection means "all types" (no filter).
"""
from __future__ import annotations

CATEGORIES: list[dict] = [
    {"key": "image", "label": "Images", "types": [
        {"label": "JPG", "exts": [".jpg", ".jpeg"]},
        {"label": "PNG", "exts": [".png"]},
        {"label": "HEIC", "exts": [".heic", ".heif"]},
        {"label": "WEBP", "exts": [".webp"]},
        {"label": "GIF", "exts": [".gif"]},
        {"label": "TIFF", "exts": [".tiff", ".tif"]},
        {"label": "BMP", "exts": [".bmp"]},
        {"label": "RAW", "exts": [".raw", ".cr2", ".nef", ".arw", ".dng", ".orf", ".rw2"]},
        {"label": "SVG", "exts": [".svg"]},
    ]},
    {"key": "video", "label": "Video", "types": [
        {"label": "MP4", "exts": [".mp4", ".m4v"]},
        {"label": "MOV", "exts": [".mov"]},
        {"label": "MKV", "exts": [".mkv"]},
        {"label": "AVI", "exts": [".avi"]},
        {"label": "WEBM", "exts": [".webm"]},
        {"label": "WMV", "exts": [".wmv"]},
        {"label": "FLV", "exts": [".flv"]},
        {"label": "MPG", "exts": [".mpg", ".mpeg"]},
        {"label": "3GP", "exts": [".3gp"]},
    ]},
    {"key": "music", "label": "Music", "types": [
        {"label": "MP3", "exts": [".mp3"]},
        {"label": "FLAC", "exts": [".flac"]},
        {"label": "WAV", "exts": [".wav"]},
        {"label": "AAC", "exts": [".aac"]},
        {"label": "M4A", "exts": [".m4a"]},
        {"label": "OGG", "exts": [".ogg", ".oga"]},
        {"label": "OPUS", "exts": [".opus"]},
        {"label": "WMA", "exts": [".wma"]},
        {"label": "AIFF", "exts": [".aiff", ".aif"]},
    ]},
    {"key": "document", "label": "Documents", "types": [
        {"label": "PDF", "exts": [".pdf"]},
        {"label": "Word", "exts": [".doc", ".docx", ".odt", ".rtf"]},
        {"label": "Excel", "exts": [".xls", ".xlsx", ".ods", ".csv"]},
        {"label": "PowerPoint", "exts": [".ppt", ".pptx", ".odp"]},
        {"label": "Text", "exts": [".txt", ".md"]},
        {"label": "EPUB", "exts": [".epub"]},
    ]},
]


def all_extensions() -> set[str]:
    """Every extension known to the categories (lowercase, with the leading dot)."""
    out: set[str] = set()
    for cat in CATEGORIES:
        for t in cat["types"]:
            out.update(t["exts"])
    return out


def category_extensions(key: str) -> set[str]:
    out: set[str] = set()
    for cat in CATEGORIES:
        if cat["key"] == key:
            for t in cat["types"]:
                out.update(t["exts"])
    return out


def normalize(exts) -> list[str]:
    """Lowercase, dot-prefixed, de-duplicated, sorted — safe to store in ScanOptions."""
    seen: set[str] = set()
    for e in exts or ():
        e = e.strip().lower()
        if not e:
            continue
        if not e.startswith("."):
            e = "." + e
        seen.add(e)
    return sorted(seen)
