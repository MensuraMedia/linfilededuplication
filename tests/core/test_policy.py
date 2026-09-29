from __future__ import annotations

from linfilededuplication.core import policy
from linfilededuplication.core.model import KIND_IMAGE, DuplicateGroup, FileEntry


def test_image_group_keeps_highest_resolution():
    hi = FileEntry(path="/pics/original.png", size=8_900_000, mtime=100, is_image=True, width=5120, height=2880)
    mid = FileEntry(path="/dl/resized.jpg", size=1_200_000, mtime=200, is_image=True, width=1920, height=1080)
    lo = FileEntry(path="/cache/thumb.jpg", size=96_000, mtime=300, is_image=True, width=640, height=360)
    g = DuplicateGroup(kind=KIND_IMAGE, key="k", files=[mid, lo, hi])
    policy.rank(g)
    assert g.keeper is hi                    # highest resolution wins, not newest or first
    assert g.reclaimable == mid.size + lo.size


def test_exact_group_prefers_original_name_over_copy():
    a = FileEntry(path="/a/photo.jpg", size=1000, mtime=100)
    b = FileEntry(path="/b/photo (1).jpg", size=1000, mtime=50)
    g = DuplicateGroup(kind="exact", key="k", files=[b, a])
    policy.rank(g)
    assert g.keeper is a                     # non-derived name beats the "(1)" copy


def test_camera_filename_is_not_treated_as_derived():
    # IMG_2381.jpg must beat "copy of IMG_2381.jpg" even though it ends in _digits.
    original = FileEntry(path="/pics/IMG_2381.jpg", size=6_000_000, mtime=300)
    copy = FileEntry(path="/desk/copy of IMG_2381.jpg", size=6_000_000, mtime=100)
    numbered = FileEntry(path="/dl/IMG_2381 (1).jpg", size=6_000_000, mtime=200)
    g = DuplicateGroup(kind="exact", key="k", files=[copy, original, numbered])
    policy.rank(g)
    assert g.keeper is original
