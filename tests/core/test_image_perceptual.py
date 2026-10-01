"""Perceptual near-duplicate tests: genuine variants must still group (recall), clearly
different images must not (precision), and a group may hold more than two members.

The engine requires pHash AND dHash agreement; these tests pin that it still detects true
near-duplicates (resize / recompress) while separating distinct images.
"""
from __future__ import annotations

import pytest

imagehash = pytest.importorskip("imagehash")
PILImage = pytest.importorskip("PIL.Image")
from PIL import Image, ImageDraw            # noqa: E402

from linfilededuplication.core import image_perceptual as ip   # noqa: E402
from linfilededuplication.core.model import FileEntry           # noqa: E402


def _structured(seed: int, w: int = 512, h: int = 384) -> Image.Image:
    """A detailed image (gradient + shapes) so pHash and dHash are both well defined."""
    im = Image.new("RGB", (w, h))
    px = im.load()
    for y in range(h):
        for x in range(w):
            px[x, y] = ((x * 2 + seed * 37) % 256, (y * 3 + seed * 11) % 256,
                        ((x + y) + seed * 73) % 256)
    d = ImageDraw.Draw(im)
    s = seed % 15                           # bounded so shape coords stay valid (x0 < x1)
    for k in range(6):
        d.rectangle([20 + k * 40 + s, 30 + k * 30, 120 + k * 40, 150 + k * 20],
                    outline=(255, 255, 255), width=3)
        d.ellipse([200 + k * 20, 40 + k * 25 + s, 300 + k * 20, 140 + k * 25],
                  outline=(0, 0, 0), width=2)
    return im


def _entry(p) -> FileEntry:
    return FileEntry(path=str(p), size=p.stat().st_size, mtime=p.stat().st_mtime, is_image=True)


def test_true_near_duplicate_variant_is_grouped(tmp_path):
    base = _structured(1)
    a = tmp_path / "a.png"; base.save(a)
    # a recompressed + slightly resized variant — a real near-duplicate
    v = base.resize((500, 375)).resize((512, 384))
    b = tmp_path / "b.jpg"; v.save(b, quality=70)

    groups = ip.find_similar_groups([_entry(a), _entry(b)], 8, lambda e: None)
    assert len(groups) == 1
    assert groups[0].count == 2


def test_distinct_images_are_not_grouped(tmp_path):
    a = tmp_path / "a.png"; _structured(1).save(a)
    b = tmp_path / "b.png"; _structured(140).save(b)     # very different content
    groups = ip.find_similar_groups([_entry(a), _entry(b)], 8, lambda e: None)
    assert groups == []


def test_group_can_hold_more_than_two(tmp_path):
    base = _structured(5)
    paths = []
    for i, q in enumerate((95, 80, 60)):                 # three near-identical variants
        p = tmp_path / f"v{i}.jpg"
        base.resize((512 - i, 384)).resize((512, 384)).save(p, quality=q)
        paths.append(p)
    groups = ip.find_similar_groups([_entry(p) for p in paths], 8, lambda e: None)
    assert len(groups) == 1
    assert groups[0].count == 3                          # all three cluster together


def test_fingerprint_returns_both_hashes(tmp_path):
    a = tmp_path / "a.png"; _structured(2).save(a)
    ph, dh, size = ip._fingerprint(str(a))
    assert ph is not None and dh is not None
    assert size == (512, 384)


def test_smooth_but_different_images_rejected_by_dual_hash(tmp_path):
    # Two nearly-flat images whose pHash can collide, but whose dHash differs: the dual-hash
    # requirement must keep them apart (the real PXL smooth-wall false positive).
    a_im = Image.new("RGB", (512, 384), (205, 212, 220))     # flat light blue-grey
    d = ImageDraw.Draw(a_im); d.line([0, 300, 512, 330], fill=(120, 120, 120), width=4)
    b_im = Image.new("RGB", (512, 384), (225, 223, 216))     # flat off-white, no edge
    a = tmp_path / "a.png"; a_im.save(a)
    b = tmp_path / "b.png"; b_im.save(b)
    groups = ip.find_similar_groups([_entry(a), _entry(b)], 8, lambda e: None)
    assert groups == []
