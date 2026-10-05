"""Scan performance log: round-trip, store, lookups, cap."""
from linfilededuplication.core.scanstats import ScanRun, ScanStatsStore, SourceStat


def _run(when, path="/data", reused=80, hashed=20, files=100):
    return ScanRun(when=when, duration=10.0, tier="simple", total_files=files,
                   total_hashed=hashed, total_reused=reused, groups=3,
                   sources=[SourceStat(path=path, files_scanned=files, files_hashed=hashed,
                                       files_reused=reused, bytes_scanned=5000,
                                       drive={"model": "Disk X", "kind": "SSD"})])


def test_source_stat_derived():
    s = SourceStat(files_hashed=20, files_reused=80)
    assert s.fingerprinted == 100
    assert s.cache_hit_pct == 80
    assert SourceStat().cache_hit_pct == 0        # no divide-by-zero


def test_run_throughput_and_round_trip():
    r = _run(1000.0)
    assert r.throughput == 10.0                   # 100 files / 10s
    back = ScanRun.from_dict(r.to_dict())
    assert back.total_reused == 80
    assert back.sources[0].drive["model"] == "Disk X"
    assert back.sources[0].cache_hit_pct == 80    # survives the round trip


def test_store_add_load_newest_first(tmp_path):
    store = ScanStatsStore(path=tmp_path / "scanruns.json")
    store.add(_run(1000.0))
    store.add(_run(2000.0))
    runs = store.load()
    assert len(runs) == 2
    assert runs[0].when == 2000.0                 # newest first


def test_last_for_source(tmp_path):
    store = ScanStatsStore(path=tmp_path / "scanruns.json")
    store.add(_run(1000.0, path="/old"))
    store.add(_run(2000.0, path="/data"))
    assert store.last_for_source("/missing") is None
    hit = store.last_for_source("/data/")         # trailing slash tolerated
    assert hit is not None and hit[1].files_scanned == 100


def test_cap(tmp_path):
    from linfilededuplication.core import scanstats
    store = scanstats.ScanStatsStore(path=tmp_path / "scanruns.json")
    for i in range(scanstats.MAX_ENTRIES + 10):
        store.add(_run(float(i)))
    assert len(store.load()) == scanstats.MAX_ENTRIES


def test_file_types_and_bytes_scanned_round_trip():
    r = ScanRun(file_types=[".jpg", ".png"],
                sources=[SourceStat(path="/a", bytes_scanned=100),
                         SourceStat(path="/b", bytes_scanned=250)])
    back = ScanRun.from_dict(r.to_dict())
    assert back.file_types == [".jpg", ".png"]
    assert back.bytes_scanned == 350                 # summed across sources
