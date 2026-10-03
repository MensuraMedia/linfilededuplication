"""Hashing strategies for the exact-match pipeline. Pure (stdlib + optional xxhash)."""
from __future__ import annotations

import hashlib
import threading
from typing import Iterable

try:                                    # optional, faster non-crypto pre-hash
    import xxhash
    HAVE_XXHASH = True
except ImportError:                     # pragma: no cover - environment dependent
    HAVE_XXHASH = False

PREFIX_BYTES = 64 * 1024                 # progressive-hash window
_CHUNK = 1024 * 1024                     # read chunk for full hashing / verification


class Cancelled(Exception):
    """Raised when a long read is aborted because the scan was cancelled."""


def prefix_hash(path: str, nbytes: int = PREFIX_BYTES) -> str:
    """Cheap hash of the first ``nbytes`` bytes. xxHash if available, else BLAKE2b."""
    with open(path, "rb") as fh:
        head = fh.read(nbytes)
    if HAVE_XXHASH:
        return "x" + xxhash.xxh64(head).hexdigest()
    return "b" + hashlib.blake2b(head, digest_size=16).hexdigest()


def full_hash(path: str, algo: str = "sha256",
              cancel: "threading.Event | None" = None) -> str:
    """Cryptographic hash of the whole file, read in chunks.

    Checks ``cancel`` every chunk so a Stop during a huge file (e.g. a multi-GB .vdi) aborts
    promptly instead of reading the whole file first; raises ``Cancelled`` when it does.
    """
    h = hashlib.new(algo)
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(_CHUNK), b""):
            if cancel is not None and cancel.is_set():
                raise Cancelled
            h.update(chunk)
    return h.hexdigest()


def bytes_equal(paths: Iterable[str], cancel: "threading.Event | None" = None) -> bool:
    """Byte-for-byte confirm that every path has identical content.

    The final safety check before an exact group is trusted: rules out the
    astronomically rare hash collision. Streams in lock-step, stops at first difference.
    Aborts promptly on ``cancel`` (raising ``Cancelled``) so a Stop during a huge file is honoured.
    """
    handles = []
    try:
        handles = [open(p, "rb") for p in paths]
        if len(handles) < 2:
            return True
        while True:
            if cancel is not None and cancel.is_set():
                raise Cancelled
            chunks = [fh.read(_CHUNK) for fh in handles]
            first = chunks[0]
            if any(c != first for c in chunks[1:]):
                return False
            if not first:               # all reached EOF together
                return True
    finally:
        for fh in handles:
            fh.close()
