from __future__ import annotations

from linfilededuplication.core import hashers, scanner
from linfilededuplication.core.hashcache import HashCache
from linfilededuplication.core.model import FileEntry
from linfilededuplication.core.options import ScanOptions


def _entry(path, dev=1, ino=2, size=10, mtime=100.0):
    return FileEntry(path=path, size=size, mtime=mtime, dev=dev, ino=ino)


def test_hit_only_when_unchanged(tmp_path):
    c = HashCache(tmp_path / "hc.json")
    e = _entry("/a/b.dat")
    assert c.get(e) is None                       # empty
    c.put(e, "deadbeef")
    assert c.get(e) == "deadbeef"                 # unchanged -> hit
    assert c.get(_entry("/a/b.dat", mtime=200.0)) is None    # mtime changed -> miss (re-hash)
    assert c.get(_entry("/a/b.dat", size=11)) is None        # size changed -> miss (re-hash)
    # dev/inode are NOT part of the match: a removable drive remounted with a new device id or
    # non-stable inodes must still hit, so repeat scans of USB/external drives stay fast.
    assert c.get(_entry("/a/b.dat", dev=99, ino=9)) == "deadbeef"   # remount-tolerant -> hit


def test_roundtrip_and_remove(tmp_path):
    p = tmp_path / "hc.json"
    c = HashCache(p)
    c.put(_entry("/x"), "h1")
    c.save()
    assert HashCache(p).get(_entry("/x")) == "h1"             # persisted
    c2 = HashCache(p)
    c2.remove(["/x"])
    assert HashCache(p).get(_entry("/x")) is None             # removed + saved


def test_second_scan_reuses_cache_and_skips_hashing(tmp_path, monkeypatch):
    data = b"same content here" * 400
    (tmp_path / "a.dat").write_bytes(data)
    (tmp_path / "b.dat").write_bytes(data)        # a duplicate pair -> both get full-hashed
    opts = ScanOptions(root=str(tmp_path), find_images=False, min_size=1)
    entries = scanner.walk(opts)
    cache = HashCache(tmp_path / "hc.json")

    # first pass populates the cache
    scanner.find_exact_groups(list(entries), opts, lambda e: None, cache=cache)
    assert len(cache) >= 2

    # second pass: full_hash must NOT be called (every candidate is an unchanged cache hit)
    calls = {"n": 0}
    real = hashers.full_hash
    def spy(path, **kw):
        calls["n"] += 1
        return real(path)
    monkeypatch.setattr(hashers, "full_hash", spy)
    groups = scanner.find_exact_groups(list(scanner.walk(opts)), opts, lambda e: None, cache=cache)
    assert calls["n"] == 0                        # reused the cache entirely
    assert len(groups) == 1 and groups[0].count == 2


def test_new_files_hashed_and_changed_files_update_the_cache(tmp_path, monkeypatch):
    import os
    data = b"shared bytes " * 400
    a = tmp_path / "a.dat"; a.write_bytes(data)
    b = tmp_path / "b.dat"; b.write_bytes(data)          # a + b identical -> a candidate pair
    opts = ScanOptions(root=str(tmp_path), find_images=False, min_size=1)
    cache = HashCache(tmp_path / "hc.json")

    n = {"h": 0}
    real = hashers.full_hash
    def spy(p, **kw):
        n["h"] += 1
        return real(p)
    monkeypatch.setattr(hashers, "full_hash", spy)

    # pass 1 — a, b have NO history: both are hashed and recorded
    scanner.find_exact_groups(scanner.walk(opts), opts, lambda e: None, cache=cache)
    assert n["h"] == 2 and len(cache) == 2

    # b's mtime changes (edited), and c is a brand-new identical file
    os.utime(b, (1_000_000_000, 1_000_000_000))
    (tmp_path / "c.dat").write_bytes(data)
    n["h"] = 0
    scanner.find_exact_groups(scanner.walk(opts), opts, lambda e: None, cache=cache)
    assert n["h"] == 2            # b (changed) + c (new) re-hashed; a (unchanged) reused
    assert len(cache) == 3        # history updated: b's entry refreshed, c added

    # pass 3 — everything is now unchanged: nothing is hashed
    n["h"] = 0
    scanner.find_exact_groups(scanner.walk(opts), opts, lambda e: None, cache=cache)
    assert n["h"] == 0
