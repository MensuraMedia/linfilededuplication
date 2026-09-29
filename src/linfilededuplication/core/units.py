"""Human-readable sizes and counts. Pure."""
from __future__ import annotations

_UNITS = ("B", "KB", "MB", "GB", "TB", "PB")


def human_bytes(n: float) -> str:
    """1234567 -> '1.2 MB'. Uses 1000-based units to match file managers."""
    n = float(n)
    for unit in _UNITS:
        if abs(n) < 1000 or unit == _UNITS[-1]:
            if unit == "B":
                return f"{int(n)} {unit}"
            return f"{n:.1f} {unit}"
        n /= 1000.0
    return f"{n:.1f} PB"


def human_count(n: int) -> str:
    """4200 -> '4,200'."""
    return f"{n:,}"
