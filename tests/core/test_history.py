from __future__ import annotations

from linfilededuplication.config.history import HistoryEntry, HistoryStore


def test_entry_after_and_roundtrip(tmp_path):
    e = HistoryEntry(sources=["/home/user"], action="trash", before_bytes=1000, freed_bytes=400,
                     files_removed=3, groups=2)
    assert e.after_bytes == 600
    assert HistoryEntry.from_dict(e.to_dict()).freed_bytes == 400


def test_store_appends_newest_first_and_caps(tmp_path):
    store = HistoryStore(tmp_path / "history.json")
    assert store.load() == []
    for i in range(3):
        store.add(HistoryEntry(when=float(i), sources=[f"/s{i}"], freed_bytes=i * 100))
    entries = store.load()
    assert [e.when for e in entries] == [2.0, 1.0, 0.0]        # newest first
    assert store.latest().when == 2.0


def test_store_caps_to_max(tmp_path, monkeypatch):
    import linfilededuplication.config.history as h
    monkeypatch.setattr(h, "MAX_ENTRIES", 5)
    store = h.HistoryStore(tmp_path / "history.json")
    for i in range(12):
        store.add(h.HistoryEntry(when=float(i)))
    assert len(store.load()) == 5


def test_store_tolerates_garbage(tmp_path):
    p = tmp_path / "history.json"
    p.write_text("{ not valid json")
    assert HistoryStore(p).load() == []
