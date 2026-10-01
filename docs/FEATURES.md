# LinFileDedup — Features & Functions Reference

**Project:** `linfilededuplication` (visible name **LinFileDedup**)
**App ID:** `com.mensuramedia.linfilededuplication` · **GObject prefix:** `Lfd`
**Platform:** Debian 12/13 + Linux Mint · GTK 4 + libadwaita (PyGObject)
**Repo:** https://github.com/MensuraMedia/linfilededuplication

This document describes every user-facing feature and the functions/modules behind it, with
purpose and behaviour. It is the comprehensive counterpart to `CONCEPT.md` (design rationale)
and `changelog.md` (dated history). Architecture rules live in `CLAUDE.md` and `.claude/rules/`.

---

## 0. Architecture at a glance

Strict one-way layering, enforced by tests:

| Layer | Path | Rule |
| --- | --- | --- |
| Engine | `core/` | **Pure Python** — no `gi`/GTK. Stdlib + optional runtime-detected libs only. Enforced by `tests/core/test_purity.py` (imports every core module with `gi` blocked). |
| Bridge | `services/` | GTK ↔ core. `ScanController` drains the worker queue on the main loop; `actions.py` does Trash/hard-link. |
| Models | `models/` | Thin Gio.ListStore adapters. |
| UI | `ui/` | `window.py` shell, `sidebar.py`, `theme_loader.py`, `pages/`, `widgets/`. Main thread only. |
| Config | `config/` | `settings.py` (tolerant JSON), `layout.py`. |

**Threading:** a worker thread runs the scan and pushes `core.events` dataclasses onto a
`queue.SimpleQueue`; `ScanController` drains it on the GTK main loop via
`GLib.timeout_add(16 ms, 8 ms budget)` (never `idle_add`). The UI never blocks.

**Safety model:** scans are read-only; nothing is removed without an `Adw.AlertDialog`
confirmation; removals go to Trash by default (recoverable); protected paths are refused.

---

## 1. The scan pipeline (`core/scanner.py`)

Cheap-to-expensive, so most files are rejected before any hashing:

1. **Walk** (`walk()`) — recursive `os.scandir` honouring hidden/min-size/symlink options,
   **scan exclusions**, the **file-type filter**, and the **ignore list**. Captures each file's
   `(size, mtime, dev, ino)`. Streams the current folder/file back as throttled `Progress`
   events (~15/sec) for the live scan caption.
2. **Size pre-filter** — only sizes shared by ≥2 files continue.
3. **Progressive prefix hash** (`hashers.prefix_hash`) — cheaply splits same-size buckets
   (xxHash when available, else BLAKE2b).
4. **Full hash** (`hashers.full_hash`, SHA-256) — confirms identical content.
5. **Byte-for-byte verify** (optional, on by default) — rules out hash coincidence.
6. **Inode collapse** — files sharing `(dev, ino)` are one physical file (already hard-linked),
   collapsed so they are never reported and never "reappear" on the next scan.

A **DuplicateGroup** holds *any number* of identical files (2, 3, 50 …), not just pairs. One is
the **keeper** (by policy); the rest are removal candidates.

**Memory:** `FileEntry` is `__slots__`-based (no per-instance `__dict__`) because the walk holds
one per file — millions on a home tree (~265 bytes/entry). Validated: a full `/home` scan with
image hashing peaks at ~326 MB.

---

## 2. Image near-duplicates (`core/image_perceptual.py`)

Finds pictures that *look* alike though their bytes differ (resized, re-saved, re-compressed).

- **Dual-hash agreement:** two images are joined only when **both** their pHash **and** dHash
  are within the Hamming threshold (default 8). pHash alone collides on large smooth, low-detail
  regions (a plain wall vs a ceiling); requiring dHash agreement — which encodes edge/gradient
  structure — rejects those false positives while keeping true near-duplicates (which match on
  both). Discovered by testing on a real 437-photo set; it removed the lone false positive with
  no recall loss.
- **Clustering:** union-find over the pairwise check, bucketed by a pHash prefix to bound the
  comparison count; a group may contain more than two members.
- **Optional dependency:** needs Pillow + `imagehash`. Absent → the image pass is skipped and a
  one-line install hint is shown. Keeper for an image group is the **highest resolution**.

---

## 3. Advanced scan (`core/chunking.py`, `core/fuzzy.py`, `core/metadata.py`)

The Advanced tier adds **SIMILAR** groups for near-identical *content* (edited documents, etc.):

- **Content-defined chunking** — gear rolling-hash anchor sampling + Jaccard overlap.
- **Fuzzy hashing** — TLSH/ssdeep when installed (optional, detected).
- **Metadata/filename** — EXIF + filename-similarity signals.

---

## 4. Keep / delete policy (`core/policy.py`, `core/backup_detect.py`)

How the keeper is chosen in every group — surfaced to the user in the **"How LinFileDedup
decides what to keep"** card on Results:

1. **Same size & type** → keep the **newest**; mark the older copies for deletion.
2. **Same type, different size** → keep the **largest** (highest-quality / highest-resolution);
   mark the smaller copies.
3. **Backups detected** → keep the **newest** backup; mark older backups. Within a close time
   window (`BACKUP_CLOSE_SECONDS`), a non-backup original wins over a marginally newer `.bak`.
4. **Name tells** → an original beats a `copy`/`(1)`/`resized`/`thumb` derivative of the same
   content. (Camera names like `IMG_2381` are **not** treated as derived.)
5. **Already hard-linked** → files sharing one physical copy are left alone (nothing to reclaim).

**Backup detection** (`core/backup_detect.py`) flags probable backups from name/date/sibling
signals and marks each group member **Newest** or **Older**.

---

## 5. Scan scope controls (Scan page)

### 5.1 Tiers
**Simple Scan** (exact + image near-duplicates) vs **Advanced Scan** (adds similarity signals).

### 5.2 Options
Folder chooser, **Find image near-duplicates** toggle, **Include hidden files**, **Minimum file
size (MB)** — each with an InfoHint where useful.

### 5.3 Scan exclusions (`core/exclusions.py`)
Named presets (system, cache, build artifacts, VCS) + custom globs, all **on by default**, so a
`/home` scan skips `.cache`, `node_modules`, `.git`, `/usr`, etc. Wired into `walk()` and
Settings.

### 5.4 File-type filter (`core/filetypes.py`, Scan page)
Columns of popular types in four categories — **Images / Video / Music / Documents** — each a
label mapped to one or more extensions (e.g. JPG → `.jpg`/`.jpeg`, RAW → `.cr2`/`.nef`/…).

- **Per-type checkbox** — include just that type.
- **Column "All"** — a tri-state checkbox (checked / mixed / empty) selecting the whole column.
- **"All Files"** (master, above the columns) — a tri-state that selects **every** type and means
  *scan all files, including extensions not listed here*. This is the default.
- **Semantics:** the selection becomes `ScanOptions.file_types` (a list of extensions); the walk
  keeps only matching files. An empty list = no filter = scan everything. The chosen set persists
  in Settings between runs.

### 5.5 Ignore list (`ScanOptions.ignore_paths`, `settings.ignored_paths`)
Exact file paths the user chose to **Ignore** (see §6.5) are skipped by `walk()` in **all future
scans**, so deliberately-kept duplicates never get re-flagged. Clearable from Settings.

---

## 6. Results page (`ui/pages/results.py`)

### 6.1 Space-savings panel (`ui/widgets/space_chart.py`)
At the top of a finished scan: a headline sentiment **"You can free up N GB"** (phrased as
*potential*, since nothing is deleted at scan time) plus two **capacity-style bar meters** —
**Now** (total footprint of every duplicate) and **After cleanup** (the keepers that remain).
Bars are square-cornered recessed meters (no rounding, no gridlines). Backed by a new
`Finished.occupied_bytes`.

### 6.2 "How LinFileDedup decides what to keep" card
A persistent explainer listing the §4 keep/delete rules, with keep words in green and delete
words in red. Makes the automatic decisions transparent.

### 6.3 Action bar (above the findings, below the info card)
- **Nothing selected / N files selected · reclaim X** — live summary.
- **Hard-link** — replace each selected duplicate with a link to its group's keeper (see §7.2).
  Skips groups set to **Delete All** (nothing to link to).
- **Delete All Duplicates** — move every selected duplicate to Trash. The label never truncates;
  the button expands to fit.

### 6.4 Group cards & file rows
Spreadsheet-aligned rows (**Name | Size | Path | marker**) via `Gtk.SizeGroup`. The path column
ellipsizes with a tooltip.
- **Keeper** row: green **Keep** label + green check-circle.
- **Candidate** row: red **Delete** label + a **red check-circle** marker (a toggle — bright red
  = will delete, faint = spared). This replaced the old system-accent (orange) checkbox.
- **Right-click any row** → **Explore here** (opens the default file manager with the file
  highlighted, via FileManager1 `ShowItems`), **Open file**, **Copy path** — always for the
  clicked row's file.
- **Thumbnails** decode *scaled* (48 px via `GdkPixbuf.new_from_file_at_scale`), never full-res,
  so a large image result set can't exhaust memory. Rendered group cards are **capped at 400**
  (the summary still reports true totals and notes when more exist).

### 6.5 Per-group controls (card header)
- **Delete All** — a toggle that marks *every* copy in the group for deletion (including the
  keeper). Flips the keeper row to red, shows a guard banner (*"No copy will remain… Hard-link is
  unavailable when nothing is kept"*), counts the keeper in the selection, is **Trash-only**, and
  the Trash confirm dialog warns that nothing remains.
- **Ignore Files** (+ InfoHint) — a toggle that **greys out** the group's rows (no action taken),
  drops them from the selection, and adds their paths to the **ignore list** (§5.5) so future
  scans skip them. Reversible.
- **SpotCheck** — opens the confirmation view (§6.6).

### 6.6 Removal flow
Selected rows are removed from the UI as they're acted on; a fully-resolved group's card
collapses and the sidebar count and summary update. Every destructive action still routes through
an `Adw.AlertDialog` confirmation.

---

## 7. Safe actions (`services/actions.py`)

### 7.1 Move to Trash
`Gio.File.trash()` — recoverable from the file manager. Protected paths (home root, `/usr`,
`/etc`, mount roots, …) are refused.

### 7.2 Hard-link
Replaces each extra with a hard link to the keeper (same-filesystem only): deletes the duplicate
and repoints its path at the keeper's inode, so **anything referencing that path keeps working**
while the data is stored once and the space is reclaimed. Skips already-linked and
cross-filesystem targets. **Thoroughly tested** (`tests/services/test_actions.py`): shared inode,
incremented link count, content preserved, N-way collapse, already-linked skip,
edit-visible-through-both-paths, protected-path refusal, cross-filesystem error.

### 7.3 Explore / Open
`show_in_file_manager()` (FileManager1 `ShowItems`, with a parent-folder fallback) and
`open_file()` (default handler).

---

## 8. SpotCheck (`ui/pages/spotcheck.py`, `core/preview.py`)

A large side-by-side confirmation view — a *gate, not an actor*; closing it changes nothing. Each
panel fills the modal and renders the file by kind:

- **Images** — `Gtk.Picture`, content-fit.
- **PDF** — a **page-by-page viewer**: the actual pages rasterized with `pdftoppm`, shown one at a
  time with **Prev / Page N / M / Next** and an **Actual size** zoom. Paging is **synced across
  panels**, so page N sits beside page N for a true A/B compare. Falls back to extracted text when
  rendering is unavailable.
- **Video** — an inline **GtkVideo** player (play/pause + scrub) for supported types
  (`.mp4/.mov/.mkv/.webm/.avi/.wmv/.flv/.mpg/.3gp/.ogv`). Falls back to the metadata card when GTK
  has no media backend (missing GStreamer codecs).
- **Text / Office / Archive** — budgeted read-only snippets (`core/preview.py` providers never
  execute a file, follow a link out, or touch the network).

Previews are classified in **pure core** (`preview.py` returns a `Preview` with a `kind` + path);
the UI decides how to render, keeping `core/` GTK-free.

---

## 9. Guidance (`core/glossary.py`, `data/glossary/en.json`)

- **Knowledge page** — searchable terms, actions, file kinds, and FAQ.
- **InfoHint `(i)` widget** — a focusable popover sourced from the glossary, peppered through the
  UI (Hard-link, match kind, backups, keeper, min size, **Ignore files**, …), each with a
  *Learn more* link into the Knowledge page.

---

## 10. Live scan feedback

- **Radar sweep** (`ui/widgets/scan_spinner.py`) — a Cairo, accent-coloured, theme-aware rotating
  sweep shown below the Results title while scanning (kept visible ≥ 1.6 s even on fast scans).
- **Scan caption** — centered under the radar: a stable **Scanning `<root>`** line plus a live
  line streaming the current folder/file (middle-ellipsized, throttled ~15/sec), so a long
  comprehensive scan visibly progresses.

---

## 11. Appearance, settings, logging

- **Theme** (`ui/theme_loader.py`) — injects the approved mockup palette (content darker than
  sidebar, lighter top bar) as `@define-color` overrides for light and dark, following the system.
- **Settings** — tier, folder, image toggle, hidden, min size, hamming, default action, backups,
  exclusions, **file types**, **ignored paths**.
- **Logging** (`logsetup.py`) — rotating file log at
  `~/.local/state/com.mensuramedia.linfilededuplication/linfilededuplication.log`: startup banner,
  lifecycle, scan start/finish, destructive-action outcomes, plus GLib/GTK capture and a Python
  excepthook.

---

## 12. Desktop integration & packaging

- **App icon** — composed from local Phosphor glyphs (`copy` + `check-circle` on an accent tile);
  scalable SVG + 16–256 px PNGs; `index.theme` + forced icon-cache rebuild so it resolves in the
  menu / panel / Alt-Tab / tray.
- **Tray** (`services/tray.py`) — optional XApp status icon with close-to-tray; `present`/`scan`
  app actions.
- **Packaging** — `scripts/build-deb.sh` (dpkg-deb), `scripts/install.sh` (to `~/.local`),
  `scripts/uninstall.sh`, `scripts/backup.sh` (timestamped local tarball). The `.deb` bundles app
  icons + glossary; CC BY-NC 4.0 license.

---

## 13. Tests (`tests/`)

Pure-core tests run anywhere; UI smoke needs a display. Current suite: **56 passing**. Coverage
includes purity, hashers, scanner (incl. inode-collapse, walk streaming, file-type & ignore
filters, `occupied_bytes`), policy, backup detection, exclusions, chunking, metadata, glossary,
preview (incl. video classification), file-type categories, perceptual precision/recall + the
smooth-image dual-hash guard, `FileEntry` slots, and the full hard-link action matrix.

Run: `pytest -q` · lint: `ruff check src tests` · headless build check:
`python3 -m linfilededuplication --smoke`.
