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

from linfilededuplication.core import (
    backup_detect, chunking, events, exclusions, fuzzy, hashers, image_perceptual, policy)
from linfilededuplication.core.model import KIND_EXACT, DuplicateGroup, FileEntry
from linfilededuplication.core.options import ScanOptions

Emit = Callable[[events.ScanEvent], None]
_IMAGE_EXT = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".tif", ".webp"}


def _is_hidden(name: str) -> bool:
    return name.startswith(".")


def source_of(path: str, roots: list[str]) -> str:
    """The scan source (root) a path belongs to — the longest matching root prefix."""
    best = ""
    for r in roots:
        rr = r.rstrip("/")
        if path == r or path == rr or path.startswith(rr + "/") or rr == "":
            if len(rr) >= len(best):
                best = rr
    return best or (roots[0].rstrip("/") if roots else "")


def walk(opts: ScanOptions, cancel: threading.Event | None = None,
         emit: Emit | None = None) -> list[FileEntry]:
    """Collect files under every source in ``opts.all_roots()``, honouring hidden/min-size/
    symlink/exclusion/file-type/ignore options. Returns one combined list so duplicates are
    found ACROSS sources. Each ``FileEntry.source`` is tagged with its root.

    When ``emit`` is given, reports the folder/file currently being scanned (tagged with its
    source), throttled so the live caption stays readable instead of flooding the UI.
    """
    out: list[FileEntry] = []
    matcher = exclusions.compile(opts.exclusions, opts.exclude)
    type_filter = {e.lower() for e in opts.file_types}   # empty = keep all types
    ignored = set(opts.ignore_paths)                     # files the user chose to ignore
    ignored_dirs = set(opts.ignore_dirs)                 # folders to skip entirely (+ contents)
    roots = opts.all_roots()
    found_by_source: dict[str, int] = {r: 0 for r in roots}
    last_tick = 0.0

    def tick(path: str, source: str) -> None:
        nonlocal last_tick
        if emit is None:
            return
        now = time.monotonic()
        if now - last_tick >= 0.06:          # ~15 updates/sec, enough to read
            emit(events.Progress(len(out), 0, "walk", path))                       # overall caption
            emit(events.Progress(found_by_source.get(source, 0), 0, "walk", path,  # per-source
                                 source=source))
            last_tick = now

    # process each source subtree; files are attributed to their source
    for root in roots:
        stack = [root]
        while stack:
            if cancel is not None and cancel.is_set():
                break
            current = stack.pop()
            if current in ignored_dirs:       # user ignored this whole folder — skip it + contents
                continue
            tick(current, root)              # folder being scanned
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
                                if type_filter and ext not in type_filter:
                                    continue             # file-type filter active, ext not wanted
                                if de.path in ignored:
                                    continue             # user chose to ignore this file
                                out.append(FileEntry(
                                    path=de.path, size=st.st_size, mtime=st.st_mtime,
                                    is_image=ext in _IMAGE_EXT, dev=st.st_dev, ino=st.st_ino,
                                    source=root))
                                found_by_source[root] = found_by_source.get(root, 0) + 1
                                tick(de.path, root)  # file going by
                        except OSError:
                            continue
            except OSError:
                continue
    return out


def find_exact_groups(entries: list[FileEntry], opts: ScanOptions, emit: Emit,
                      cancel: threading.Event | None = None,
                      total_work: int = 0, files_by_source: dict | None = None,
                      preferred: list[str] | None = None, cache=None) -> list[DuplicateGroup]:
    """Size bucket -> prefix hash -> full SHA-256 -> optional byte verify.

    When ``total_work`` is given (total files + any later passes), overall progress is reported as
    the TRUE ratio: files that need no hashing are already "done", and each hashed candidate
    advances the count. When ``files_by_source`` is given, a PER-SOURCE progress event is also
    emitted (files processed in that source / its file count), driving the per-source rings.
    ``preferred`` folders/sources bias the keeper (the primary source is kept across drives).
    """
    preferred = preferred or []
    by_size: dict[int, list[FileEntry]] = defaultdict(list)
    for e in entries:
        by_size[e.size].append(e)
    candidates = [grp for grp in by_size.values() if len(grp) > 1]

    groups: list[DuplicateGroup] = []
    to_hash = sum(len(g) for g in candidates)
    if total_work:
        base = len(entries) - to_hash      # non-candidate files require no hashing: already done
        total = total_work
    else:
        base, total = 0, to_hash           # legacy: progress over candidates only

    # per-source accounting: non-candidate files of a source are done immediately
    per_total = dict(files_by_source or {})
    cand_by_src: dict[str, int] = defaultdict(int)
    for g in candidates:
        for e in g:
            cand_by_src[e.source] += 1
    per_done = {s: per_total[s] - cand_by_src.get(s, 0) for s in per_total}
    last_src_tick = 0.0

    def tick_source(e: FileEntry) -> None:
        nonlocal last_src_tick
        if not per_total:
            return
        now = time.monotonic()
        if now - last_src_tick >= 0.06:
            s = e.source
            emit(events.Progress(per_done.get(s, 0), per_total.get(s, 0), "hash", e.path, source=s))
            last_src_tick = now

    done = 0
    for same_size in candidates:
        if cancel is not None and cancel.is_set():
            break
        # progressive prefix hash splits the size bucket cheaply
        by_prefix: dict[str, list[FileEntry]] = defaultdict(list)
        for e in same_size:
            try:
                by_prefix[hashers.prefix_hash(e.path)].append(e)
            except OSError:
                emit(events.ScanError(f"Could not read {e.name}", "Check file permissions.", e.path))
            done += 1
            per_done[e.source] = per_done.get(e.source, 0) + 1
            tick_source(e)
            if done % 32 == 0:
                emit(events.Progress(base + done, total, "hash", e.path))
        for same_prefix in by_prefix.values():
            if len(same_prefix) < 2:
                continue
            by_full: dict[str, list[FileEntry]] = defaultdict(list)
            for e in same_prefix:
                try:
                    cached = cache.get(e) if cache is not None else None
                    if cached is not None:        # unchanged file: reuse the stored digest
                        e.full_hash = cached
                    else:                          # new/changed file: hash it and remember
                        e.full_hash = hashers.full_hash(e.path)
                        if cache is not None:
                            cache.put(e, e.full_hash)
                    by_full[e.full_hash].append(e)
                except OSError:
                    emit(events.ScanError(f"Could not read {e.name}", "Check file permissions.", e.path))
            for digest, members in by_full.items():
                if len(members) < 2:
                    continue
                if opts.verify_bytes and not hashers.bytes_equal([m.path for m in members]):
                    continue
                # Collapse files already hard-linked together (same inode): they are one
                # physical file, so there is nothing to reclaim and they must not reappear.
                by_inode: dict[tuple[int, int], FileEntry] = {}
                for m in members:
                    by_inode.setdefault((m.dev, m.ino), m)
                distinct = list(by_inode.values())
                if len(distinct) < 2:
                    continue
                grp = DuplicateGroup(kind=KIND_EXACT, key=digest, files=distinct)
                if opts.detect_backups:
                    backup_detect.analyze_group(grp)
                policy.rank(grp, preferred=preferred, keep_newest=opts.keep_newest_backup)
                groups.append(grp)
                emit(events.GroupFound(grp))
    emit(events.Progress(base + to_hash, total, "hash", "Exact matching done"))
    for s, tot in per_total.items():       # settle every source's ring at 100%
        emit(events.Progress(tot, tot, "hash", "", source=s))
    return groups


def scan(opts: ScanOptions, emit: Emit, cancel: threading.Event | None = None) -> events.Finished:
    """Full run. Emits ScanStarted, Progress, GroupFound*, Finished."""
    from collections import Counter
    start = time.time()
    roots = opts.all_roots()
    emit(events.ScanStarted(roots[0] if roots else opts.root))
    entries = walk(opts, cancel, emit)
    total_files = len(entries)
    files_by_source = dict(Counter(e.source for e in entries))
    for r in roots:                            # ensure every chosen source has a ring, even if empty
        files_by_source.setdefault(r, 0)
    images = [e for e in entries if e.is_image] if opts.find_images else []
    do_images = bool(images) and image_perceptual.HAVE_IMAGEHASH
    # total units of work for an accurate percentage: every file is "scanned" once, and image
    # files get one more pass (perceptual hashing).
    total_work = max(1, total_files + (len(images) if do_images else 0))
    preferred = roots[:1] if getattr(opts, "keep_primary_source", True) else []
    emit(events.Progress(0, 0, "walk", f"Found {total_files:,} files"))   # caption only

    cache = None
    if getattr(opts, "use_hash_cache", True):
        from linfilededuplication.core.hashcache import HashCache
        cache = HashCache()
    groups = find_exact_groups(entries, opts, emit, cancel, total_work=total_work,
                               files_by_source=files_by_source, preferred=preferred, cache=cache)

    notes: list[str] = []
    if opts.find_images:
        if not image_perceptual.HAVE_IMAGEHASH:
            notes.append("Install python3-imagehash to find image near-duplicates.")
        elif images:
            emit(events.Progress(total_files, total_work, "image", "Perceptual hashing images"))
            img_groups = image_perceptual.find_similar_groups(
                images, opts.hamming, emit, cancel,
                progress_base=total_files, progress_total=total_work)
            for grp in img_groups:
                if opts.detect_backups:
                    backup_detect.analyze_group(grp)
                policy.rank(grp, preferred=preferred, keep_newest=opts.keep_newest_backup)
                emit(events.GroupFound(grp))
            groups = groups + img_groups

    if opts.advanced_similar:
        grouped = {f.path for g in groups for f in g.files}
        remaining = [e for e in entries if e.path not in grouped and not e.is_image]
        fz: list = []
        if opts.fuzzy and fuzzy.HAVE_FUZZY:
            fz = fuzzy.find_fuzzy_groups(remaining, opts.fuzzy_distance, emit, cancel)
        elif opts.fuzzy and not fuzzy.HAVE_FUZZY:
            notes.append("Install python3-tlsh for fuzzy matching of edited files.")
        for grp in fz:
            grouped.update(f.path for f in grp.files)
        remaining2 = [e for e in remaining if e.path not in grouped]
        ch = chunking.find_similar_groups(remaining2, opts.similar_threshold, emit, cancel)
        for grp in fz + ch:
            if opts.detect_backups:
                backup_detect.analyze_group(grp)
            policy.rank(grp, preferred=preferred, keep_newest=opts.keep_newest_backup)
            emit(events.GroupFound(grp))
        groups = groups + fz + ch

    if cache is not None:
        cache.save()                          # persist reused/new digests for the next scan
    cancelled = cancel is not None and cancel.is_set()
    fin = events.Finished(
        cancelled=cancelled,
        files_scanned=len(entries),
        groups=len(groups),
        reclaimable=sum(g.reclaimable for g in groups),
        occupied_bytes=sum(f.size for g in groups for f in g.files),
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
