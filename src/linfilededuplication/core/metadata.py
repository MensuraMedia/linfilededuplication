"""Metadata and filename signals for Advanced Scan. Pure (stdlib + optional Pillow)."""
from __future__ import annotations

import difflib
import os

try:
    from PIL import Image
    from PIL.ExifTags import TAGS
    HAVE_PIL = True
except ImportError:                     # pragma: no cover
    HAVE_PIL = False


def filename_similarity(a: str, b: str) -> float:
    """0..1 similarity of two file basenames (ignoring extension)."""
    na = os.path.splitext(os.path.basename(a))[0].lower()
    nb = os.path.splitext(os.path.basename(b))[0].lower()
    return difflib.SequenceMatcher(None, na, nb).ratio()


def exif_datetime(path: str) -> str | None:
    """The EXIF capture timestamp of an image, or None."""
    if not HAVE_PIL:
        return None
    try:
        with Image.open(path) as im:
            exif = im.getexif()
            for tag_id, value in exif.items():
                if TAGS.get(tag_id) in ("DateTimeOriginal", "DateTime"):
                    return str(value)
    except Exception:
        return None
    return None


def exif_camera(path: str) -> str | None:
    if not HAVE_PIL:
        return None
    try:
        with Image.open(path) as im:
            exif = im.getexif()
            model = None
            for tag_id, value in exif.items():
                if TAGS.get(tag_id) == "Model":
                    model = str(value).strip()
            return model or None
    except Exception:
        return None
