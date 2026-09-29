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

MAX_BYTES = 16 * 1024
MAX_LINES = 40

_IMAGE_EXT = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".tif", ".webp"}
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
            return Preview(KIND_TEXT, os.path.basename(path), text=text[:2000])
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
    # Prefer poppler's pdftotext (argv, first page). Never a shell.
    try:
        out = subprocess.run(["pdftotext", "-f", "1", "-l", "1", "-q", path, "-"],
                             capture_output=True, timeout=8, text=True)
        text = (out.stdout or "").strip()
        if text:
            return Preview(KIND_TEXT, os.path.basename(path), text=text[:2000], note="page 1")
    except (OSError, subprocess.SubprocessError):
        pass
    try:                                             # optional pure-python fallback
        import pypdf
        reader = pypdf.PdfReader(path)
        text = (reader.pages[0].extract_text() or "").strip() if reader.pages else ""
        note = f"{len(reader.pages)} pages"
        if text:
            return Preview(KIND_TEXT, os.path.basename(path), text=text[:2000], note=note)
        return _meta(path, note)
    except Exception:
        return _meta(path, "PDF (install poppler-utils to preview text)")


def preview(path: str) -> Preview:
    """Return a read-only snippet preview for a file, chosen by type."""
    ext = os.path.splitext(path)[1].lower()
    try:
        if ext in _IMAGE_EXT:
            return Preview(KIND_IMAGE, os.path.basename(path), image_path=path)
        if ext == ".pdf":
            return _pdf_snippet(path)
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
