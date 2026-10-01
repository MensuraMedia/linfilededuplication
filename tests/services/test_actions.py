"""Thorough tests for the hard-link action — the operation that deletes a duplicate and
replaces it with a link to the keeper. Filesystem-level assertions (inode, link count,
content) so the safety-critical behaviour is pinned, not assumed.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from linfilededuplication.core.model import FileEntry
from linfilededuplication.services import actions


def _entry(p: Path) -> FileEntry:
    st = p.stat()
    return FileEntry(path=str(p), size=st.st_size, mtime=st.st_mtime,
                     dev=st.st_dev, ino=st.st_ino)


def test_hard_link_replaces_extra_with_link_to_keeper(tmp_path):
    data = b"same content" * 1000
    keep = tmp_path / "keep.bin"; keep.write_bytes(data)
    dup = tmp_path / "dup.bin"; dup.write_bytes(data)
    assert keep.stat().st_ino != dup.stat().st_ino        # start: two physical files

    res = actions.hard_link(_entry(keep), [_entry(dup)])

    assert res.done == 1 and not res.errors
    assert res.freed == len(data)
    assert dup.exists() and keep.exists()                 # both paths survive
    assert keep.stat().st_ino == dup.stat().st_ino        # now one physical file
    assert os.stat(keep).st_nlink == 2                    # keeper gained a link
    assert dup.read_bytes() == data                       # content intact


def test_hard_link_collapses_any_number_of_duplicates(tmp_path):
    data = b"triplets" * 500
    keep = tmp_path / "a.bin"; keep.write_bytes(data)
    d1 = tmp_path / "b.bin"; d1.write_bytes(data)
    d2 = tmp_path / "c.bin"; d2.write_bytes(data)

    res = actions.hard_link(_entry(keep), [_entry(d1), _entry(d2)])

    assert res.done == 2 and not res.errors
    ino = keep.stat().st_ino
    assert d1.stat().st_ino == ino and d2.stat().st_ino == ino   # all one inode
    assert os.stat(keep).st_nlink == 3


def test_hard_link_skips_already_linked(tmp_path):
    data = b"already" * 500
    keep = tmp_path / "k.bin"; keep.write_bytes(data)
    linked = tmp_path / "l.bin"
    os.link(keep, linked)                                 # already the same inode

    res = actions.hard_link(_entry(keep), [_entry(linked)])

    assert res.done == 0 and not res.errors               # nothing to do, no error
    assert keep.stat().st_ino == linked.stat().st_ino


def test_hard_link_edit_through_one_path_visible_through_other(tmp_path):
    data = b"original" * 100
    keep = tmp_path / "k.bin"; keep.write_bytes(data)
    dup = tmp_path / "d.bin"; dup.write_bytes(data)
    actions.hard_link(_entry(keep), [_entry(dup)])

    # in-place edit through the keeper path is seen through the duplicate's path:
    # they are literally the same file (same inode), which is the feature's promise.
    with open(keep, "r+b") as fh:
        fh.seek(0); fh.write(b"EDITED!!")
    assert dup.read_bytes()[:8] == b"EDITED!!"


def test_hard_link_refuses_protected_path(tmp_path):
    data = b"x" * 100
    keep = tmp_path / "k.bin"; keep.write_bytes(data)
    # Target whose realpath is the home root itself -> must be refused, untouched.
    home = FileEntry(path=str(Path.home()), size=0, mtime=0.0)
    res = actions.hard_link(_entry(keep), [home])
    assert res.done == 0
    assert res.errors and "protected" in res.errors[0].lower()


def test_hard_link_cross_filesystem_reports_error(tmp_path, monkeypatch):
    data = b"y" * 100
    keep = tmp_path / "k.bin"; keep.write_bytes(data)
    dup = tmp_path / "d.bin"; dup.write_bytes(data)
    real_stat = os.stat

    def fake_stat(path, *a, **k):
        st = real_stat(path, *a, **k)
        if os.fspath(path) == str(dup):                   # pretend dup is on another device
            return os.stat_result(tuple(st)[:2] + (st.st_dev + 1,) + tuple(st)[3:])
        return st

    monkeypatch.setattr(actions.os, "stat", fake_stat)
    res = actions.hard_link(_entry(keep), [_entry(dup)])
    assert res.done == 0
    assert res.errors and "filesystem" in res.errors[0].lower()
    assert dup.stat().st_ino != keep.stat().st_ino        # left untouched


def test_is_protected_guards_system_and_home_roots(tmp_path):
    assert actions._is_protected(str(Path.home())) is True
    assert actions._is_protected("/usr") is True
    assert actions._is_protected(str(tmp_path / "ordinary.txt")) is False
