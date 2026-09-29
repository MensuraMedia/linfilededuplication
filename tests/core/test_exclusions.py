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
