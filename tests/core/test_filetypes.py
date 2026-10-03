from __future__ import annotations

from linfilededuplication.core import events, filetypes
from linfilededuplication.core.model import KIND_EXACT
from linfilededuplication.core.options import ScanOptions
from linfilededuplication.core.scanner import scan, walk


def test_categories_cover_expected_kinds():
    keys = {c["key"] for c in filetypes.CATEGORIES}
    assert {"image", "video", "music", "document"} <= keys
    assert ".jpg" in filetypes.category_extensions("image")
    assert ".mp3" in filetypes.category_extensions("music")
    assert ".jpg" not in filetypes.category_extensions("music")


def test_normalize_dedups_and_dot_prefixes():
    assert filetypes.normalize(["JPG", ".jpeg", "png", ".png", ""]) == [".jpeg", ".jpg", ".png"]


def test_all_extensions_is_union():
    allx = filetypes.all_extensions()
    assert filetypes.category_extensions("video") <= allx
    assert ".pdf" in allx


def test_walk_file_type_filter_keeps_only_selected(tmp_path):
    (tmp_path / "a.jpg").write_bytes(b"x" * 4000)
    (tmp_path / "b.mp3").write_bytes(b"y" * 4000)
    (tmp_path / "c.txt").write_bytes(b"z" * 4000)
    opts = ScanOptions(root=str(tmp_path), min_size=1, file_types=[".jpg", ".png"])
    names = {e.name for e in walk(opts)}
    assert names == {"a.jpg"}                       # only the selected type survives


def test_empty_file_types_keeps_everything(tmp_path):
    (tmp_path / "a.jpg").write_bytes(b"x" * 4000)
    (tmp_path / "b.mp3").write_bytes(b"y" * 4000)
    opts = ScanOptions(root=str(tmp_path), min_size=1, file_types=[])
    names = {e.name for e in walk(opts)}
    assert names == {"a.jpg", "b.mp3"}              # no filter


def test_finished_reports_occupied_bytes(tmp_path):
    data = b"same" * 2000
    (tmp_path / "a.dat").write_bytes(data)
    (tmp_path / "b.dat").write_bytes(data)          # one duplicate pair
    out = []
    scan(ScanOptions(root=str(tmp_path), find_images=False, min_size=1), out.append)
    fin = [e for e in out if isinstance(e, events.Finished)][-1]
    assert fin.groups == 1
    assert fin.occupied_bytes == 2 * len(data)      # both copies counted (before cleanup)
    assert fin.reclaimable == len(data)             # one copy freed (after cleanup)


def test_walk_skips_ignored_paths(tmp_path):
    keep = tmp_path / "keep.dat"; keep.write_bytes(b"x" * 4000)
    skip = tmp_path / "skip.dat"; skip.write_bytes(b"y" * 4000)
    opts = ScanOptions(root=str(tmp_path), min_size=1, ignore_paths=[str(skip)])
    names = {e.name for e in walk(opts)}
    assert names == {"keep.dat"}            # ignored file is not walked


def test_walk_skips_ignored_folder_and_contents(tmp_path):
    (tmp_path / "keep.dat").write_bytes(b"x" * 4000)
    sub = tmp_path / "archive"; sub.mkdir()
    (sub / "a.dat").write_bytes(b"y" * 4000)
    (sub / "b.dat").write_bytes(b"z" * 4000)
    opts = ScanOptions(root=str(tmp_path), min_size=1, ignore_dirs=[str(sub)])
    names = {e.name for e in walk(opts)}
    assert names == {"keep.dat"}            # the ignored folder and all its files are skipped


def test_walk_excludes_excluded_extensions(tmp_path):
    (tmp_path / "a.jpg").write_bytes(b"x" * 4000)
    (tmp_path / "big.vdi").write_bytes(b"y" * 4000)
    (tmp_path / "disk.iso").write_bytes(b"z" * 4000)
    opts = ScanOptions(root=str(tmp_path), min_size=1, exclude_types=[".vdi", ".iso"])
    names = {e.name for e in walk(opts)}
    assert names == {"a.jpg"}            # excluded large types are skipped


def test_large_types_defined():
    labels = {t["label"] for t in filetypes.LARGE_TYPES}
    assert {"VDI", "ISO", "BIN"} <= labels
