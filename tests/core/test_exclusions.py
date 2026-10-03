from __future__ import annotations

from linfilededuplication.core import exclusions
from linfilededuplication.core.options import ScanOptions
from linfilededuplication.core.scanner import walk


def test_matcher_excludes_dirs_and_globs():
    m = exclusions.compile(["build", "vcs", "stubs"])
    assert m.excludes("/home/u/proj/node_modules", True)
    assert m.excludes("/home/u/proj/.git", True)
    assert m.excludes("/home/u/proj/.DS_Store", False)
    assert not m.excludes("/home/u/proj/src", True)


def test_empty_presets_exclude_nothing():
    m = exclusions.compile([])
    assert not m.excludes("/home/u/proj/.git", True)


def test_walk_skips_excluded_dirs(tmp_path):
    (tmp_path / "keep.txt").write_bytes(b"x" * 5000)
    ng = tmp_path / "node_modules"
    ng.mkdir()
    (ng / "dep.js").write_bytes(b"y" * 5000)
    opts = ScanOptions(root=str(tmp_path), min_size=1, exclusions=["build"])
    names = {e.name for e in walk(opts)}
    assert "keep.txt" in names
    assert "dep.js" not in names            # node_modules pruned


def test_windows_recycle_and_system_dirs_excluded():
    from linfilededuplication.core import exclusions
    m = exclusions.compile(None)                         # all presets on
    for d in ("$RECYCLE.BIN", "$Recycle.Bin", "RECYCLER", "System Volume Information"):
        assert m.excludes(f"/media/user/USB/{d}", True), d
    # a normal folder is NOT excluded
    assert not m.excludes("/media/user/USB/Photos", True)


def test_recycle_dir_contents_not_walked(tmp_path):
    from linfilededuplication.core.options import ScanOptions
    from linfilededuplication.core.scanner import walk
    (tmp_path / "keep.jpg").write_bytes(b"x" * 4000)
    rec = tmp_path / "$RECYCLE.BIN"; rec.mkdir()
    (rec / "deleted.jpg").write_bytes(b"x" * 4000)
    names = {e.name for e in walk(ScanOptions(root=str(tmp_path), min_size=1, exclusions=["trash"]))}
    assert names == {"keep.jpg"}                         # recycle-bin contents skipped
