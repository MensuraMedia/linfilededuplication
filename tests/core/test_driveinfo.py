"""Drive info: probing degrades gracefully and round-trips."""
from linfilededuplication.core import driveinfo


def test_probe_returns_mountpoint_and_total(tmp_path):
    di = driveinfo.probe(str(tmp_path))
    assert di.mountpoint                      # some mount point always resolves
    assert di.total_bytes > 0                 # statvfs total is always available


def test_probe_without_lsblk(tmp_path, monkeypatch):
    # Force the lsblk path to be unavailable and bypass the TTL cache.
    monkeypatch.setattr(driveinfo.shutil, "which", lambda _n: None)
    monkeypatch.setattr(driveinfo, "_lsblk_cache", {"when": 0.0, "data": None})
    di = driveinfo.probe(str(tmp_path))
    assert di.total_bytes > 0                 # still works with no lsblk
    assert di.model == "" and di.kind == ""   # hardware specs simply absent


def test_describe_formats_known_fields():
    di = driveinfo.DriveInfo(model="Samsung SSD 870", kind="SSD", transport="usb", fstype="ext4")
    assert driveinfo.describe(di) == "Samsung SSD 870 · SSD · USB · ext4"
    assert driveinfo.describe(driveinfo.DriveInfo()) == ""   # nothing known → empty


def test_round_trip():
    di = driveinfo.DriveInfo(device="/dev/sdb1", model="X", kind="HDD", size_bytes=123)
    assert driveinfo.DriveInfo.from_dict(di.to_dict()) == di
    assert driveinfo.DriveInfo.from_dict({"model": "Y", "bogus": 1}).model == "Y"  # tolerant
