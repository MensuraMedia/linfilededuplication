"""The scan pipeline: walk -> size pre-filter -> progressive -> full hash -> verify,
then an optional image near-duplicate pass. Pure (stdlib + optional Pillow/imagehash).

Emits ``core.events`` objects through a callback; a worker thread wraps it so the UI
never blocks. Nothing here imports GTK.
"""
from __future__ import annotations

import os
import queue
import threading
import time
from collections import defaultdict
from typing import Callable

from linfilededuplication.core import backup_detect, events, exclusions, hashers, image_perceptual, policy
from linfilededuplication.core.model import KIND_EXACT, DuplicateGroup, FileEntry
from linfilededuplication.core.options import ScanOptions

Emit = Callable[[events.ScanEvent], None]
_IMAGE_EXT = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".tif", ".webp"}


def _is_hidden(name: str) -> bool:
    return name.startswith(".")


def walk(opts: ScanOptions, cancel: threading.Event | None = None) -> list[FileEntry]:
    """Collect files under ``opts.root`` honouring hidden/min-size/symlink options."""
    out: list[FileEntry] = []
    matcher = exclusions.compile(opts.exclusions, opts.exclude)
    stack = [opts.root]
    while stack:
        if cancel is not None and cancel.is_set():
            break
        current = stack.pop()
        try:
            with os.scandir(current) as it:
                for de in it:
                    name = de.name
                    if not opts.include_hidden and _is_hidden(name):
                        continue
                    try:
                        if de.is_dir(follow_symlinks=opts.follow_symlinks):
                            if not matcher.excludes(de.path, True):
                                stack.append(de.path)
                        elif de.is_file(follow_symlinks=opts.follow_symlinks):
                            if matcher.excludes(de.path, False):
                                continue
                            st = de.stat(follow_symlinks=opts.follow_symlinks)
                            if st.st_size < opts.min_size:
                                continue
                            ext = os.path.splitext(name)[1].lower()
                            out.append(FileEntry(
                                path=de.path, size=st.st_size, mtime=st.st_mtime,
                                is_image=ext in _IMAGE_EXT))
                    except OSError:
                        continue
        except OSError:
            continue
    return out


def find_exact_groups(entries: list[FileEntry], opts: ScanOptions, emit: Emit,
                      cancel: threading.Event | None = None) -> list[DuplicateGroup]:
    """Size bucket -> prefix hash -> full SHA-256 -> optional byte verify."""
    by_size: dict[int, list[FileEntry]] = defaultdict(list)
    for e in entries:
        by_size[e.size].append(e)
    candidates = [grp for grp in by_size.values() if len(grp) > 1]

    groups: list[DuplicateGroup] = []
    to_hash = sum(len(g) for g in candidates)
    done = 0
    for same_size in candidates:
        if cancel is not None and cancel.is_set():
            break
        # progressive prefix hash splits the size bucket cheaply
        by_prefix: dict[str, list[FileEntry]] = defaultdict(list)
        for e in same_size:
            try:
                by_prefix[hashers.prefix_hash(e.path)].append(e)
            except OSError as exc:
                emit(events.ScanError(f"Could not read {e.name}", "Check file permissions.", e.path))
            done += 1
            if done % 64 == 0:
                emit(events.Progress(done, to_hash, "hash", "Hashing candidates"))
        for same_prefix in by_prefix.values():
            if len(same_prefix) < 2:
                continue
            by_full: dict[str, list[FileEntry]] = defaultdict(list)
            for e in same_prefix:
                try:
                    e.full_hash = hashers.full_hash(e.path)
                    by_full[e.full_hash].append(e)
                except OSError:
                    emit(events.ScanError(f"Could not read {e.name}", "Check file permissions.", e.path))
            for digest, members in by_full.items():
                if len(members) < 2:
                    continue
                if opts.verify_bytes and not hashers.bytes_equal([m.path for m in members]):
                    continue
                grp = DuplicateGroup(kind=KIND_EXACT, key=digest, files=list(members))
                if opts.detect_backups:
                    backup_detect.analyze_group(grp)
                policy.rank(grp, keep_newest=opts.keep_newest_backup)
                groups.append(grp)
                emit(events.GroupFound(grp))
    emit(events.Progress(to_hash, to_hash, "hash", "Exact matching done"))
    return groups


def scan(opts: ScanOptions, emit: Emit, cancel: threading.Event | None = None) -> events.Finished:
    """Full run. Emits ScanStarted, Progress, GroupFound*, Finished."""
    start = time.time()
    emit(events.ScanStarted(opts.root))
    entries = walk(opts, cancel)
    emit(events.Progress(len(entries), len(entries), "walk", f"Found {len(entries):,} files"))

    groups = find_exact_groups(entries, opts, emit, cancel)

    notes: list[str] = []
    if opts.find_images:
        images = [e for e in entries if e.is_image]
        if not image_perceptual.HAVE_IMAGEHASH:
            notes.append("Install python3-imagehash to find image near-duplicates.")
        elif images:
            emit(events.Progress(0, len(images), "image", "Perceptual hashing images"))
            img_groups = image_perceptual.find_similar_groups(
                images, opts.hamming, emit, cancel)
            for grp in img_groups:
                if opts.detect_backups:
                    backup_detect.analyze_group(grp)
                policy.rank(grp, keep_newest=opts.keep_newest_backup)
                emit(events.GroupFound(grp))
            groups = groups + img_groups

    cancelled = cancel is not None and cancel.is_set()
    fin = events.Finished(
        cancelled=cancelled,
        files_scanned=len(entries),
        groups=len(groups),
        reclaimable=sum(g.reclaimable for g in groups),
        seconds=time.time() - start,
        notes=notes,
    )
    emit(fin)
    return fin


class ScanThread(threading.Thread):
    """Runs ``scan`` on a worker thread, pushing events onto a queue.

    The controller drains ``self.queue`` on the GTK main loop. ``cancel()`` is honoured
    between files; a terminal Finished is always queued, even on error.
    """

    def __init__(self, opts: ScanOptions, out_queue: "queue.SimpleQueue[events.ScanEvent]") -> None:
        super().__init__(name="dedupe-scan", daemon=True)
        self.opts = opts
        self.queue = out_queue
        self._cancel = threading.Event()

    def cancel(self) -> None:
        self._cancel.set()

    def is_cancelled(self) -> bool:
        return self._cancel.is_set()

    def run(self) -> None:
        try:
            scan(self.opts, self.queue.put, self._cancel)
        except Exception as exc:                       # never leave the UI waiting
            self.queue.put(events.ScanError(f"Scan failed: {exc}", "See the log for details."))
            self.queue.put(events.Finished(cancelled=True))
