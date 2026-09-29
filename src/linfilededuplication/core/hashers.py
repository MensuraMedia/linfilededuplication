"""Hashing strategies for the exact-match pipeline. Pure (stdlib + optional xxhash)."""
from __future__ import annotations

import hashlib
from typing import Iterable

try:                                    # optional, faster non-crypto pre-hash
    import xxhash
    HAVE_XXHASH = True
except ImportError:                     # pragma: no cover - environment dependent
    HAVE_XXHASH = False

PREFIX_BYTES = 64 * 1024                 # progressive-hash window
_CHUNK = 1024 * 1024                     # read chunk for full hashing / verification


def prefix_hash(path: str, nbytes: int = PREFIX_BYTES) -> str:
    """Cheap hash of the first ``nbytes`` bytes. xxHash if available, else BLAKE2b."""
    with open(path, "rb") as fh:
        head = fh.read(nbytes)
    if HAVE_XXHASH:
        return "x" + xxhash.xxh64(head).hexdigest()
    return "b" + hashlib.blake2b(head, digest_size=16).hexdigest()


def full_hash(path: str, algo: str = "sha256") -> str:
    """Cryptographic hash of the whole file, read in chunks."""
    h = hashlib.new(algo)
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(_CHUNK), b""):
            h.update(chunk)
    return h.hexdigest()


def bytes_equal(paths: Iterable[str]) -> bool:
    """Byte-for-byte confirm that every path has identical content.

    The final safety check before an exact group is trusted: rules out the
    astronomically rare hash collision. Streams in lock-step, stops at first difference.
    """
    handles = []
    try:
        handles = [open(p, "rb") for p in paths]
        if len(handles) < 2:
            return True
        while True:
            chunks = [fh.read(_CHUNK) for fh in handles]
            first = chunks[0]
            if any(c != first for c in chunks[1:]):
                return False
            if not first:               # all reached EOF together
                return True
    finally:
        for fh in handles:
            fh.close()
