"""Drive / hardware info for scan sources. Pure (stdlib + optional ``lsblk``).

For a given path we resolve the mount point (``/proc/mounts``), then enrich it with the backing
device's model, media kind (SSD/HDD), transport (usb/sata/nvme) and filesystem using ``lsblk``
when it is present. Everything degrades gracefully: with no ``lsblk`` we still report the mount
point, device, filesystem and total size from ``statvfs``. Local-first and GTK-free.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from dataclasses import asdict, dataclass, field

_LSBLK_TTL = 10.0                      # seconds; one lsblk call serves a whole scan
_lsblk_cache: dict = {"when": 0.0, "data": None}


@dataclass
class DriveInfo:
    mountpoint: str = ""
    device: str = ""        # e.g. /dev/sdb1
    model: str = ""         # e.g. "Samsung SSD 870 EVO"
    kind: str = ""          # "SSD" | "HDD" | ""
    transport: str = ""     # usb | sata | nvme | mmc | ...
    fstype: str = ""        # ext4 | ntfs | vfat | ...
    size_bytes: int = 0     # size of the backing device/partition (lsblk)
    total_bytes: int = 0    # filesystem total (statvfs) — always available

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "DriveInfo":
        known = set(cls.__dataclass_fields__)
        return cls(**{k: v for k, v in (data or {}).items() if k in known})


def _statvfs_total(path: str) -> int:
    try:
        st = os.statvfs(path)
        return st.f_blocks * st.f_frsize
    except OSError:
        return 0


def _find_mount(path: str) -> tuple[str, str, str]:
    """Longest mount-point prefix of ``path`` → (mountpoint, device, fstype)."""
    try:
        real = os.path.realpath(path)
    except OSError:
        real = path
    best = ("", "", "")
    try:
        with open("/proc/mounts", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                parts = line.split()
                if len(parts) < 3:
                    continue
                dev, mp, fstype = parts[0], parts[1].replace("\\040", " "), parts[2]
                if (real == mp or real.startswith(mp.rstrip("/") + "/")) and len(mp) >= len(best[0]):
                    best = (mp, dev, fstype)
    except OSError:
        pass
    return best


def _as_bool(v) -> bool | None:
    if v is None:
        return None
    return str(v).strip().lower() in ("1", "true", "yes")


def _lsblk(force: bool = False) -> dict:
    """Return a flattened lsblk view {mountpoint: node, nodes: [...]}; {} when unavailable.

    Memoised for ``_LSBLK_TTL`` so probing several sources in one scan runs lsblk once.
    """
    now = time.time()
    if not force and _lsblk_cache["data"] is not None and now - _lsblk_cache["when"] < _LSBLK_TTL:
        return _lsblk_cache["data"]
    result: dict = {}
    if shutil.which("lsblk"):
        try:
            out = subprocess.run(
                ["lsblk", "-J", "-b", "-o", "NAME,PATH,MODEL,ROTA,TRAN,FSTYPE,SIZE,MOUNTPOINT"],
                capture_output=True, text=True, timeout=5, check=False)
            data = json.loads(out.stdout or "{}")
            by_mp: dict = {}
            nodes: list = []

            def walk(node: dict, parent: dict | None) -> None:
                node["_parent"] = parent
                nodes.append(node)
                mp = node.get("mountpoint")              # older lsblk: single string
                if not mp:                               # newer lsblk: a "mountpoints" list
                    mps = node.get("mountpoints")
                    if isinstance(mps, list):
                        mp = next((m for m in mps if m), None)
                if mp:
                    by_mp[mp] = node
                for child in node.get("children") or []:
                    walk(child, node)

            for top in data.get("blockdevices") or []:
                walk(top, None)
            result = {"by_mp": by_mp, "nodes": nodes}
        except (OSError, ValueError, subprocess.SubprocessError):
            result = {}
    _lsblk_cache["when"] = now
    _lsblk_cache["data"] = result
    return result


def probe(path: str) -> DriveInfo:
    """Best-effort hardware description of the drive that holds ``path``."""
    mp, dev, fstype = _find_mount(path)
    di = DriveInfo(mountpoint=mp or path, device=dev, fstype=fstype,
                   total_bytes=_statvfs_total(path))
    lb = _lsblk()
    node = None
    if lb:
        node = (lb.get("by_mp") or {}).get(mp)
        if node is None and dev:
            for n in lb.get("nodes") or []:
                if n.get("path") == dev or "/dev/" + (n.get("name") or "") == dev:
                    node = n
                    break
    if node is not None:
        try:
            di.size_bytes = int(node.get("size") or 0)
        except (TypeError, ValueError):
            di.size_bytes = 0
        top = node
        while top.get("_parent"):
            top = top["_parent"]
        di.model = (node.get("model") or top.get("model") or "").strip()
        di.transport = (node.get("tran") or top.get("tran") or "").strip()
        rota = node.get("rota")
        if rota is None:
            rota = top.get("rota")
        b = _as_bool(rota)
        if b is not None:
            di.kind = "HDD" if b else "SSD"
        if not di.fstype:
            di.fstype = (node.get("fstype") or "").strip()
    return di


def describe(di: DriveInfo) -> str:
    """Short human label, e.g. 'Samsung SSD 870 · SSD · USB · ext4'."""
    bits = [di.model, di.kind, di.transport.upper() if di.transport else "", di.fstype]
    return " · ".join(b for b in bits if b)
