"""Scan events: the one-way channel from the engine to the UI. Pure dataclasses.

A worker emits these onto a queue; the UI drains the queue on the GTK main loop.
Frozen contract: add fields with defaults, never remove them.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from linfilededuplication.core.model import DuplicateGroup


class ScanEvent:
    """Base class for everything the scanner emits."""


@dataclass
class ScanStarted(ScanEvent):
    root: str


@dataclass
class Progress(ScanEvent):
    done: int
    total: int
    phase: str          # "walk" | "size" | "hash" | "verify" | "image"
    detail: str = ""
    source: str = ""    # which scan source this progress is for ("" = overall)

    @property
    def fraction(self) -> float:
        return self.done / self.total if self.total else 0.0


@dataclass
class GroupFound(ScanEvent):
    group: "DuplicateGroup"


@dataclass
class ScanError(ScanEvent):
    message: str
    fix: str = ""
    path: str = ""


@dataclass
class Finished(ScanEvent):
    cancelled: bool = False
    files_scanned: int = 0
    groups: int = 0
    reclaimable: int = 0            # bytes freed if every duplicate is removed (non-keepers)
    occupied_bytes: int = 0         # total bytes held by all duplicate-group files (before)
    seconds: float = 0.0
    notes: list[str] = field(default_factory=list)
