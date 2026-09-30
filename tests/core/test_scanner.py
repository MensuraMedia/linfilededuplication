from __future__ import annotations

from linfilededuplication.core import events
from linfilededuplication.core.model import KIND_EXACT
from linfilededuplication.core.options import ScanOptions
from linfilededuplication.core.scanner import scan, walk


def _collect(opts):
    out: list[events.ScanEvent] = []
    scan(opts, out.append)
    return out


def test_walk_respects_min_size_and_hidden(tmp_path):
    (tmp_path / "big.txt").write_bytes(b"x" * 5000)
    (tmp_path / "tiny.txt").write_bytes(b"x")
    (tmp_path / ".hidden.txt").write_bytes(b"x" * 5000)
    opts = ScanOptions(root=str(tmp_path), min_size=100, include_hidden=False)
    names = {e.name for e in walk(opts)}
    assert "big.txt" in names
    assert "tiny.txt" not in names          # below min_size
    assert ".hidden.txt" not in names       # hidden excluded


def test_finds_exact_duplicate_group(tmp_path):
    data = b"identical content" * 2000
    (tmp_path / "a.dat").write_bytes(data)
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "b.dat").write_bytes(data)
    (tmp_path / "unique.dat").write_bytes(b"different" * 2000)

    opts = ScanOptions(root=str(tmp_path), find_images=False, min_size=1)
    evs = _collect(opts)
    groups = [e.group for e in evs if isinstance(e, events.GroupFound)]
    finished = [e for e in evs if isinstance(e, events.Finished)][-1]

    assert len(groups) == 1
    g = groups[0]
    assert g.kind == KIND_EXACT
    assert g.count == 2
    assert sum(1 for f in g.files if f.keeper) == 1     # exactly one keeper
    assert g.reclaimable == len(data)                    # one copy freed
    assert finished.groups == 1


def test_hardlinked_files_not_reported(tmp_path):
    import os
    data = b"already linked content" * 2000
    a = tmp_path / "a.dat"
    a.write_bytes(data)
    os.link(str(a), str(tmp_path / "b.dat"))     # hard link -> same inode
    opts = ScanOptions(root=str(tmp_path), find_images=False, min_size=1)
    groups = [e.group for e in _collect(opts) if isinstance(e, events.GroupFound)]
    assert not groups                            # one physical file -> nothing to reclaim


def test_no_duplicates(tmp_path):
    (tmp_path / "a").write_bytes(b"a" * 3000)
    (tmp_path / "b").write_bytes(b"b" * 3000)
    opts = ScanOptions(root=str(tmp_path), find_images=False)
    evs = _collect(opts)
    assert not [e for e in evs if isinstance(e, events.GroupFound)]
