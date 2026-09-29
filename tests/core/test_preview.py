from __future__ import annotations

import zipfile

from linfilededuplication.core import preview


def test_text_preview(tmp_path):
    p = tmp_path / "notes.txt"
    p.write_text("line one\nline two\nline three\n")
    pv = preview.preview(str(p))
    assert pv.kind == preview.KIND_TEXT
    assert "line one" in pv.text


def test_image_preview_points_at_file(tmp_path):
    p = tmp_path / "pic.png"
    p.write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 100)
    pv = preview.preview(str(p))
    assert pv.kind == preview.KIND_IMAGE
    assert pv.image_path == str(p)


def test_archive_preview_lists_entries(tmp_path):
    z = tmp_path / "bundle.zip"
    with zipfile.ZipFile(z, "w") as zf:
        zf.writestr("a.txt", "a")
        zf.writestr("b/c.txt", "c")
    pv = preview.preview(str(z))
    assert pv.kind == preview.KIND_TEXT
    assert "a.txt" in pv.text


def test_binary_falls_back_to_meta(tmp_path):
    p = tmp_path / "blob.dat"
    p.write_bytes(b"\x00\x01\x02\x03" * 50)
    pv = preview.preview(str(p))
    assert pv.kind == preview.KIND_META
