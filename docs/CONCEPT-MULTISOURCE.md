# Concept — Multi-Source Scanning, Per-Source Progress & Scan History

**Status:** proposed (design for review)
**Scope:** three connected features for LinFileDedup
**Author:** MensuraMedia · 2026-10-03

This document specifies three features and how they fit the existing strict-layered architecture
(`core/` pure → `services/` bridge → `ui/`). It is the technical companion to the Scan-page
mockup.

---

## 1. Motivation

Today a scan targets **one** folder, and the **History** page is empty. Two gaps:

1. **People keep duplicates across drives.** The same photos live on an internal disk, a USB
   backup, and an external drive. The real win is finding duplicates **across** those sources, not
   one at a time. LinFileDedup should scan **several mountpoints/folders at once** and treat them
   as one pool so a copy on the USB stick and the original on `/home` form one group.
2. **No record of what was reclaimed.** After a dedup operation there's nothing to look back on.
   History should show the **last operation** clearly: when, what was scanned, and how much space
   it saved (before → after, as bars).

A third, supporting UX change makes multi-source legible:

3. **Per-source progress.** While scanning, show a **percentage ring per source** so the user sees
   each drive advance independently, not one combined bar.

---

## 2. Feature A — Multi-source scanning

### 2.1 Model

- `ScanOptions` gains **`roots: list[str]`** (the sources to scan). `root: str` is kept for
  backward compatibility and is treated as `roots = [root]` when `roots` is empty; `roots` wins
  when both are set. A convenience `all_roots()` returns the effective list.
- A file's **source** is the root that is a path-prefix of its path. No new per-file field is
  required for correctness; `source_of(path, roots)` resolves it (longest matching root wins, so
  nested roots are attributed to the most specific). For progress attribution this is computed
  once per file and cached in the walk.

### 2.2 Engine (`core/scanner.py`)

- `walk()` iterates **each root** in `opts.all_roots()`, applying the same exclusions, file-type
  filter, ignore lists, hidden/min-size rules per root, and returns one combined
  `list[FileEntry]`. The live caption/progress tags which source is being walked.
- `find_exact_groups` is unchanged in spirit: it pools **all** entries, so identical content on
  different drives groups together. Cross-device files have different `(dev, ino)`, so the
  inode-collapse step correctly keeps them as distinct physical files (a USB copy and an internal
  copy are two real files, one reclaimable).
- Perceptual/advanced passes also operate on the combined pool.
- **Keeper policy across sources:** add an optional *preferred source* tiebreak — when two copies
  are otherwise equal, keep the one on the **first-listed source** (usually the primary/internal
  drive), so the copy removed is the one on the backup/removable drive. This slots into
  `policy.rank` after the existing name/folder tiebreaks and before mtime.

### 2.3 Safety notes

- Cross-filesystem **hard-link is impossible** (different `st_dev`); `actions.hard_link` already
  refuses it and the UI already routes those to Trash. Multi-source makes this common, so the
  per-group action copy makes it explicit.
- Removable drives can disappear mid-scan; `walk()` already swallows `OSError` per entry, so a
  vanished mount degrades to "no files found there" rather than crashing.

### 2.4 UI (`ui/pages/scan.py`)

- The single "Folder to scan" row becomes a **Sources** list: each row shows the path, a
  type/όicon (folder vs mounted drive), its free/size if a mount, and a **Remove**. An **Add
  source…** button opens the folder chooser; **Add drive…** lists detected mountpoints
  (`Gio.VolumeMonitor` / `/proc/mounts`) for one-tap adding.
- At least one source is required to start. Sources persist in settings (`roots`).

---

## 3. Feature B — Per-source progress

### 3.1 Events (`core/events.py`)

`Progress` gains **`source: str = ""`** and keeps its existing `done/total/phase/detail`. The
scanner emits, per source, the **true files-scanned ratio for that source** (same accurate model
as today, scoped per source): a source's non-candidate files count as done once walked; each
hashed candidate / perceptually-hashed image on that source advances its count; its total work =
its files (+ its image pass). Global progress is still available as the sum.

Attribution during hashing: the scanner keeps `processed[source]` and `total[source]` maps; when a
candidate file is hashed, it credits the file's source. Emits are throttled per source.

### 3.2 Scan page rings

- While scanning, the Scan page shows **one `RingLoader` per source** (reusing the existing widget
  and its `set_progress`), labelled with the source path and the live file beneath. Sources not yet
  reached read "Queued"; the active source's ring climbs; finished sources sit at 100%.
- The rings live in a responsive grid (wrap to the window width). The existing single ring on the
  **Results** page remains as the **overall** progress and still gates the reveal-on-complete.
- A source whose drive vanished shows a muted "unavailable" state rather than spinning forever.

---

## 4. Feature C — Scan / dedup History

### 4.1 Store (`config/history.py`)

A small, tolerant JSON store at `~/.local/state/<app-id>/history.json`, mirroring `settings.py`:

```
HistoryEntry:
  when: float            # epoch seconds (converted to local datetime for display)
  sources: list[str]     # the roots scanned
  action: str            # "trash" | "hardlink"
  ok: bool               # the operation succeeded (or failed)
  error: str = ""        # short message when ok is False
  before_bytes: int      # footprint of the duplicate set at scan time (Finished.occupied_bytes)
  freed_bytes: int       # bytes actually reclaimed by this operation
  files_removed: int
  groups: int
```

`after_bytes = before_bytes - freed_bytes`. The store appends on each operation, caps to the most
recent N (e.g. 100), and is read by the History page. Pure stdlib (`json`, `dataclasses`), so it
stays test-friendly.

### 4.2 When an entry is recorded

A **deduplicate operation** is a removal the user confirmed — not merely a scan. On completion of
**Move to Trash / Delete All Duplicates** or **Hard-link** (in `ui/pages/results.py`), record one
entry using the current scan's `sources` + `before_bytes` (from the last `Finished`) and the
`freed_bytes`/`files_removed` the action reports. A failed action records `ok=False` with the
error.

### 4.3 History page (`ui/pages/history.py`)

- **The last operation, prominently:** date & time, the source(s) scanned, a **before/after bar
  pair** (space before vs after — reusing `SpaceChart`), and a bold **"Saved N GB"** headline.
  A success/failure chip. This is the primary content, as requested.
- **Earlier operations:** a compact list below (date · sources · saved · ok), newest first, so the
  page is a genuine history without burying the latest.
- **Empty state:** a friendly explainer (what will appear here after the first cleanup).

---

## 4b. Feature D — Hash cache (fast repeat / incremental scans)

Scans spend most time **reading whole files for SHA-256**. A persistent cache lets a re-scan
skip that work for files that have not changed — which is exactly what makes "scan again,
comparing against another source" fast.

### Design (`config/hashcache.py`)

A tolerant JSON store at `~/.local/state/<app-id>/hashcache.json`, mapping **path → fingerprint**:

```
path: { dev, ino, size, mtime, sha256 }
```

- **Lookup** (`get`): return the cached `sha256` only when the file's current `(size, mtime, dev,
  ino)` all match the stored values — i.e. the file is unchanged. Any difference (edited, replaced,
  moved onto a different inode) is a **cache miss → re-hash**. This is the fast boolean the user
  described: unchanged ⇒ reuse, changed ⇒ rescan that file.
- **Update** (`put`): store the fingerprint whenever a full hash is computed.
- **Maintenance:** prune entries whose path no longer exists; drop entries for files removed by a
  dedup operation (so the cache stays truthful after deletion); hard-linking updates the inode.
- **Scope:** only files that reach the full-hash step (prefix-collision candidates) are cached, so
  the file stays small. Enabled by default; a Settings toggle can clear/disable it.

### Integration

`find_exact_groups` consults the cache before `hashers.full_hash`: on a hit it reuses the digest
(no file read); on a miss it hashes and `put`s. The cache is saved at the end of a scan. The
byte-for-byte verification remains the final safety net, so a stale/mtime-preserving edit can never
cause a wrong removal. **Caveat:** mtime is a heuristic; a tool that preserves mtime after editing
is the one case the fast path would miss, which verification still catches.

### Correctness

mtime/size matching is the same heuristic rsync and backup tools rely on. Combined with the
inode check and the retained byte-verify, it is safe: the cache only ever *avoids recomputing a
hash we would have computed identically*, never changes which files are judged equal.

---

## 5. Backward compatibility & tests

- `root`→`roots` is additive; existing callers and tests keep working (`root` still honoured).
- New core tests: walk over multiple roots combines + finds cross-source duplicates; `source_of`
  longest-prefix resolution; per-source progress sums to the global ratio; `HistoryStore`
  round-trips and caps; preferred-source keeper tiebreak.
- UI stays behind the smoke test; the History page and multi-ring Scan page build headless.

---

## 6. Rollout

1. Core: `roots`/`all_roots`, `source_of`, walk-per-root, `Progress.source`, per-source attribution,
   preferred-source policy. Tests.
2. `config/history.py` + tests.
3. Scan page: Sources list + Add source/drive + per-source rings.
4. Results page: record a `HistoryEntry` on each action.
5. History page: last-operation card with before/after bars + earlier list.
6. README (standard features), HANDOFF, changelog, backup, commit, push.
