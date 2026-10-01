from __future__ import annotations

import pytest

from linfilededuplication.core.model import FileEntry


def test_fileentry_uses_slots_to_bound_memory():
    # A comprehensive scan holds one FileEntry per file (millions on a home tree), so the
    # object must stay slotted: no per-instance __dict__, and no undeclared attributes.
    e = FileEntry(path="/a/b.jpg", size=10, mtime=1.0)
    assert not hasattr(e, "__dict__")
    with pytest.raises((AttributeError, TypeError)):
        e.not_a_field = 1            # slots must reject stray attributes


def test_fileentry_properties_still_work():
    e = FileEntry(path="/a/b/photo.jpg", size=10, mtime=1.0, width=4, height=5)
    assert e.name == "photo.jpg"
    assert e.parent == "/a/b"
    assert e.pixels == 20
    assert e.resolution == "4x5"
