from __future__ import annotations

from linfilededuplication.core import hashers


def test_full_hash_matches_for_identical(tmp_path):
    a = tmp_path / "a.bin"
    b = tmp_path / "b.bin"
    data = b"dedupe" * 5000
    a.write_bytes(data)
    b.write_bytes(data)
    assert hashers.full_hash(str(a)) == hashers.full_hash(str(b))


def test_full_hash_differs_for_different(tmp_path):
    a = tmp_path / "a.bin"
    b = tmp_path / "b.bin"
    a.write_bytes(b"x" * 100)
    b.write_bytes(b"y" * 100)
    assert hashers.full_hash(str(a)) != hashers.full_hash(str(b))


def test_bytes_equal(tmp_path):
    data = b"the same bytes" * 1000
    paths = []
    for name in ("1", "2", "3"):
        p = tmp_path / name
        p.write_bytes(data)
        paths.append(str(p))
    assert hashers.bytes_equal(paths) is True
    other = tmp_path / "4"
    other.write_bytes(data + b"!")
    assert hashers.bytes_equal([paths[0], str(other)]) is False


def test_prefix_hash_stable(tmp_path):
    p = tmp_path / "f"
    p.write_bytes(b"z" * 200000)
    assert hashers.prefix_hash(str(p)) == hashers.prefix_hash(str(p))
