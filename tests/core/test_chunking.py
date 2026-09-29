from __future__ import annotations

import random

from linfilededuplication.core import chunking, events
from linfilededuplication.core.model import KIND_SIMILAR
from linfilededuplication.core.options import ScanOptions
from linfilededuplication.core.scanner import scan


def _varied(seed: int, n: int) -> bytes:
    """Realistic, non-repetitive content (like a real document)."""
    r = random.Random(seed)
    return bytes(r.getrandbits(8) for _ in range(n))


def test_jaccard_high_after_insertion(tmp_path):
    base = _varied(1, 60000)
    a = tmp_path / "a.bin"
    b = tmp_path / "b.bin"
    a.write_bytes(base)
    b.write_bytes(base[:30000] + b"INSERTED EDIT BLOCK" * 8 + base[30000:])   # small insertion
    sa = chunking.chunk_signatures(str(a))
    sb = chunking.chunk_signatures(str(b))
    assert sa and sb
    assert chunking.jaccard(sa, sb) > 0.6           # mostly shared content survives a shift
    assert chunking.jaccard(sa, frozenset()) == 0.0


def test_unrelated_files_do_not_match(tmp_path):
    a = tmp_path / "a.bin"
    b = tmp_path / "b.bin"
    a.write_bytes(_varied(1, 60000))
    b.write_bytes(_varied(2, 60000))
    assert chunking.jaccard(chunking.chunk_signatures(str(a)),
                            chunking.chunk_signatures(str(b))) < 0.2


def test_advanced_scan_finds_similar(tmp_path):
    base = _varied(7, 50000)
    (tmp_path / "doc1.bin").write_bytes(base)
    (tmp_path / "doc2.bin").write_bytes(base + b"one extra trailing block\n" * 20)
    (tmp_path / "unrelated.bin").write_bytes(_varied(99, 50000))

    opts = ScanOptions(root=str(tmp_path), tier="advanced", advanced_similar=True,
                       find_images=False, fuzzy=False, similar_threshold=0.5, min_size=1)
    evs: list = []
    scan(opts, evs.append)
    similar = [e.group for e in evs if isinstance(e, events.GroupFound)
               and e.group.kind == KIND_SIMILAR]
    assert similar, "expected a similar group for the two near-identical docs"
    paths = {f.name for g in similar for f in g.files}
    assert "doc1.bin" in paths and "doc2.bin" in paths
    assert "unrelated.bin" not in paths
