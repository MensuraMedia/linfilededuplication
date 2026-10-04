"""Perceptual-hash cache: round-trip, remount tolerance, cap."""
from linfilededuplication.core.model import FileEntry
from linfilededuplication.core.phashcache import PHashCache


def _e(path, size=10, mtime=100.0, dev=1, ino=2):
    return FileEntry(path=path, size=size, mtime=mtime, dev=dev, ino=ino)


def test_hit_and_round_trip(tmp_path):
    c = PHashCache(tmp_path / "p.json")
    e = _e("/a/img.jpg")
    assert c.get(e) is None
    c.put(e, "ff00ff00ff00ff00", "00ff00ff00ff00ff", (800, 600))
    ph, dh, size = c.get(e)
    assert ph == "ff00ff00ff00ff00" and dh == "00ff00ff00ff00ff" and size == (800, 600)
    c.save()
    assert PHashCache(tmp_path / "p.json").get(e)[2] == (800, 600)   # persisted


def test_remount_tolerant_and_change_detection(tmp_path):
    c = PHashCache(tmp_path / "p.json")
    e = _e("/a/img.jpg")
    c.put(e, "aa", "bb", (1, 1))
    assert c.get(_e("/a/img.jpg", dev=99, ino=7)) is not None   # dev/ino ignored -> hit
    assert c.get(_e("/a/img.jpg", mtime=200.0)) is None         # changed -> miss
    assert c.get(_e("/a/img.jpg", size=11)) is None             # changed -> miss


def test_cap(tmp_path):
    from linfilededuplication.core import phashcache
    c = phashcache.PHashCache(tmp_path / "p.json")
    for i in range(phashcache.MAX_ENTRIES + 5):
        c.put(_e(f"/img/{i}.jpg"), "aa", "bb", (1, 1))
    c.save(force=True)
    assert len(phashcache.PHashCache(tmp_path / "p.json")) == phashcache.MAX_ENTRIES
