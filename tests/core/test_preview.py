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


def test_video_is_classified_as_video():
    from linfilededuplication.core import preview as pv
    p = pv.preview("/does/not/exist/clip.mp4")
    assert p.kind == pv.KIND_VIDEO
    assert p.image_path.endswith("clip.mp4")


def test_unknown_video_ext_not_video():
    from linfilededuplication.core import preview as pv
    assert pv.preview("/x/readme.txt").kind != pv.KIND_VIDEO


def test_audio_preview_is_audio_kind(tmp_path):
    for name in ("song.mp3", "track.flac", "clip.opus", "voice.m4a", "tune.wav"):
        p = tmp_path / name
        p.write_bytes(b"\x00" * 64)
        pv = preview.preview(str(p))
        assert pv.kind == preview.KIND_AUDIO, name
        assert pv.image_path == str(p)          # the player needs the real path


def test_broad_image_formats_are_image_kind(tmp_path):
    # HEIC / AVIF / SVG / camera-RAW are classified as images; the UI decodes or falls back.
    for name in ("photo.heic", "shot.avif", "vector.svg", "raw.cr2", "raw.nef", "raw.dng"):
        p = tmp_path / name
        p.write_bytes(b"\x00" * 64)
        assert preview.preview(str(p)).kind == preview.KIND_IMAGE, name
