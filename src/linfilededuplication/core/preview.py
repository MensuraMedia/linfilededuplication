"""Read-only content previews for SpotCheck. Pure (stdlib + optional external tools).

A provider opens a file to read a snippet and NEVER executes it, follows a link out, or
touches the network. Each is bounded by byte/line budgets. Missing optional tools fall back
to a metadata card. Returns plain ``Preview`` data so the UI just renders it.
"""
from __future__ import annotations

import os
import re
import subprocess
import zipfile
from dataclasses import dataclass

from linfilededuplication.core.units import human_bytes

KIND_IMAGE = "image"
KIND_TEXT = "text"
KIND_META = "meta"
KIND_PDF = "pdf"        # render the actual pages (UI), with text as a fallback
KIND_VIDEO = "video"    # inline player (UI); metadata card as a fallback
KIND_AUDIO = "audio"    # inline player (UI); metadata card as a fallback

MAX_BYTES = 64 * 1024
MAX_LINES = 200

# Images: the GdkPixbuf-native set, plus modern/raw formats. Formats that need an extra pixbuf
# loader (HEIC/AVIF/JXL) or a raw decoder (CR2/NEF/…) are still offered as images; the SpotCheck
# viewer tries to render them and falls back gracefully (open-in-viewer) when a loader is absent.
_IMAGE_EXT = {".jpg", ".jpeg", ".jfif", ".png", ".gif", ".bmp", ".tiff", ".tif", ".webp",
              ".svg", ".svgz", ".ico", ".xpm", ".pnm", ".ppm", ".pgm", ".pbm", ".tga", ".qoi",
              ".heic", ".heif", ".avif", ".jxl",
              ".cr2", ".cr3", ".nef", ".nrw", ".arw", ".srf", ".sr2", ".dng", ".orf", ".rw2",
              ".raf", ".pef", ".raw", ".rwl", ".x3f"}
_AUDIO_EXT = {".mp3", ".flac", ".wav", ".wave", ".aac", ".m4a", ".m4b", ".ogg", ".oga", ".opus",
              ".wma", ".aiff", ".aif", ".aifc", ".alac", ".ape", ".wv", ".mka", ".mpc", ".ra"}
_VIDEO_EXT = {".mp4", ".m4v", ".mov", ".mkv", ".webm", ".avi", ".wmv", ".flv",
              ".mpg", ".mpeg", ".3gp", ".ogv"}
_TEXT_EXT = {".txt", ".md", ".rst", ".log", ".csv", ".tsv", ".json", ".yaml", ".yml", ".toml",
             ".ini", ".cfg", ".conf", ".xml", ".html", ".css", ".js", ".ts", ".py", ".c", ".h",
             ".cpp", ".rs", ".go", ".java", ".sh", ".rb", ".php", ".sql"}
_ARCHIVE_EXT = {".zip", ".jar", ".whl", ".tar", ".gz", ".tgz", ".bz2", ".xz", ".7z"}
_OFFICE_EXT = {".docx", ".odt", ".pptx", ".odp", ".xlsx", ".ods"}


@dataclass
class Preview:
    kind: str                   # image | text | meta
    title: str
    text: str = ""
    image_path: str = ""
    note: str = ""


def _meta(path: str, note: str = "") -> Preview:
    try:
        size = os.path.getsize(path)
    except OSError:
        size = 0
    ext = os.path.splitext(path)[1].lower().lstrip(".") or "file"
    return Preview(KIND_META, os.path.basename(path),
                   text=f"{ext.upper()} · {human_bytes(size)}", note=note)


def _text_snippet(path: str) -> Preview:
    try:
        with open(path, "rb") as fh:
            raw = fh.read(MAX_BYTES)
        body = raw.decode("utf-8", errors="replace")
        lines = body.splitlines()[:MAX_LINES]
        return Preview(KIND_TEXT, os.path.basename(path), text="\n".join(lines))
    except OSError as exc:
        return _meta(path, f"Could not read: {exc}")


def _strip_xml(xml: str) -> str:
    text = re.sub(r"<[^>]+>", " ", xml)
    return re.sub(r"\s+", " ", text).strip()


def _office_snippet(path: str) -> Preview:
    try:
        with zipfile.ZipFile(path) as z:
            names = set(z.namelist())
            member = None
            for candidate in ("word/document.xml", "content.xml", "ppt/slides/slide1.xml"):
                if candidate in names:
                    member = candidate
                    break
            if member is None:                       # spreadsheets: show sheet names
                sheets = [n for n in names if n.startswith("xl/worksheets/")]
                if sheets:
                    return Preview(KIND_TEXT, os.path.basename(path),
                                   text=f"Spreadsheet with {len(sheets)} sheet(s).")
                return _meta(path, "Office document")
            with z.open(member) as fh:
                text = _strip_xml(fh.read(MAX_BYTES * 4).decode("utf-8", errors="replace"))
            return Preview(KIND_TEXT, os.path.basename(path), text=text[:6000])
    except (OSError, zipfile.BadZipFile) as exc:
        return _meta(path, f"Could not read document: {exc}")


def _archive_snippet(path: str) -> Preview:
    try:
        if zipfile.is_zipfile(path):
            with zipfile.ZipFile(path) as z:
                names = z.namelist()
                head = "\n".join(names[:MAX_LINES])
                return Preview(KIND_TEXT, os.path.basename(path),
                               text=head, note=f"{len(names)} entries")
        import tarfile
        if tarfile.is_tarfile(path):
            with tarfile.open(path) as t:
                names = t.getnames()
                head = "\n".join(names[:MAX_LINES])
                return Preview(KIND_TEXT, os.path.basename(path),
                               text=head, note=f"{len(names)} entries")
    except (OSError, Exception):
        pass
    return _meta(path, "Archive")


def _pdf_snippet(path: str) -> Preview:
    # poppler's pdftotext, first several pages so there's a real sample (argv only, no shell).
    try:
        out = subprocess.run(["pdftotext", "-f", "1", "-l", "8", "-q", path, "-"],
                             capture_output=True, timeout=12, text=True)
        text = (out.stdout or "").strip()
        if text:
            return Preview(KIND_TEXT, os.path.basename(path), text=text[:8000], note="first pages")
    except (OSError, subprocess.SubprocessError):
        pass
    try:                                             # optional pure-python fallback
        import pypdf
        reader = pypdf.PdfReader(path)
        pages = reader.pages[:8]
        text = "\n".join((p.extract_text() or "") for p in pages).strip()
        note = f"{len(reader.pages)} pages"
        if text:
            return Preview(KIND_TEXT, os.path.basename(path), text=text[:8000], note=note)
        return _meta(path, note + " — no extractable text (likely scanned images)")
    except Exception:
        return _meta(path, "PDF — install poppler-utils (pdftotext) to preview text")


def preview(path: str) -> Preview:
    """Return a read-only snippet preview for a file, chosen by type."""
    ext = os.path.splitext(path)[1].lower()
    try:
        if ext in _IMAGE_EXT:
            return Preview(KIND_IMAGE, os.path.basename(path), image_path=path)
        if ext in _VIDEO_EXT:
            return Preview(KIND_VIDEO, os.path.basename(path), image_path=path,
                           note=ext.lstrip(".").upper() + " video")
        if ext in _AUDIO_EXT:
            return Preview(KIND_AUDIO, os.path.basename(path), image_path=path,
                           note=ext.lstrip(".").upper() + " audio")
        if ext == ".pdf":
            snip = _pdf_snippet(path)       # text fallback if page rendering is unavailable
            return Preview(KIND_PDF, os.path.basename(path), image_path=path,
                           text=snip.text, note=snip.note)
        if ext in _OFFICE_EXT:
            return _office_snippet(path)
        if ext in _ARCHIVE_EXT:
            return _archive_snippet(path)
        if ext in _TEXT_EXT:
            return _text_snippet(path)
        # sniff: if it looks like text, show it; else metadata
        with open(path, "rb") as fh:
            head = fh.read(512)
        if head and b"\x00" not in head:
            return _text_snippet(path)
        return _meta(path)
    except OSError as exc:
        return _meta(path, f"Could not open: {exc}")
