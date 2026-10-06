# LinFileDedup — Handoff

**Last updated:** 2026-10-05
**Repo:** https://github.com/MensuraMedia/linfilededuplication (default branch `main`)
**Status:** P0–P6 complete and installed. Fingerprint cache + scan-performance history now
deliver genuinely fast repeat scans (unchanged files skipped entirely); SpotCheck covers audio +
all image types; the Lin\* UI/UX design reference is in-tree. Actively iterating on
Scan/Results/History/SpotCheck UX.
**Owner:** MensuraMedia (`lin-*` desktop app series).

This is the practical "pick it up and keep going" document. Design rationale is in
`docs/CONCEPT.md`; the full feature/function reference is `docs/FEATURES.md`; dated history is
`changelog.md`; invariants are in `CLAUDE.md` and `.claude/rules/`.

---

## 1. What it is

A native Linux (Debian/Mint) GTK 4 + libadwaita (PyGObject) desktop app that finds and safely
removes duplicate and near-duplicate files, with first-class image support. Built on the
MensuraMedia `gtk4-dashboard-template` house pattern.

---

## 2. Run / build / test

```bash
# from the checkout
./run.sh                        # or: PYTHONPATH=src .venv/bin/python -m linfilededuplication
./run.sh --debug                # verbose logging
python3 -m linfilededuplication --smoke   # build every page headless and exit (CI-safe)
pytest -q                       # 95 tests; pure-core runs anywhere, UI smoke needs a display
ruff check src tests            # lint (ruff not always installed in the venv)
scripts/build-deb.sh            # -> dist/linfilededuplication_<ver>_all.deb
scripts/install.sh              # install to ~/.local (writes launcher, icons, index.theme)
scripts/backup.sh               # timestamped tarball -> ~/backups/linfilededuplication/
```

**Dev venv:** `python3 -m venv --system-site-packages .venv && .venv/bin/pip install xxhash
imagehash`. System deps: `python3-gi python3-gi-cairo gir1.2-gtk-4.0 gir1.2-adw-1`
(+ `python3-pil`, `poppler-utils` for PDF pages, GStreamer plugins for SpotCheck video).

**Installed app** runs on **system** `python3` (not the venv). Optional libs must be importable
there: `imagehash` was installed into the user site
(`pip install --user --break-system-packages imagehash`) — that's why image near-dup works in the
installed build. There is no apt `python3-imagehash` on this box.

**Restarting the installed app safely** (avoid pkill matching its own command):
```bash
pkill -f "python3 -m [l]infilededuplication"; DISPLAY=:0 nohup ~/.local/bin/linfilededuplication &
```

---

## 3. Architecture (one-way layering)

`core/` (pure, no gi) → `services/` (GTK bridge) → `ui/`. See `docs/FEATURES.md §0` and the
path-scoped rules in `.claude/rules/core-purity.md` and `.claude/rules/python-gtk.md`.
`tests/core/test_purity.py` fails the build if any `core/` module imports GTK.

**Scan event flow:** `scanner.scan()` (worker thread) emits `core.events` →
`services/scan_controller.py` drains the queue on the main loop (16 ms / 8 ms budget) → re-emits
GObject signals `scan-started / progress / group-found / scan-error / scan-finished` → pages react.

---

## 4. Where things live (quick map)

| Area | File |
| --- | --- |
| Scan pipeline, walk (exclusions, file-type & ignore filters, inode collapse) | `core/scanner.py` |
| Hashers (xxhash/blake2b/sha256/byte-verify) | `core/hashers.py` |
| Perceptual images (dual pHash+dHash) | `core/image_perceptual.py` |
| Advanced similarity | `core/chunking.py`, `core/fuzzy.py`, `core/metadata.py` |
| Keep/delete policy, backups | `core/policy.py`, `core/backup_detect.py` |
| Scan options / exclusions / file types | `core/options.py`, `core/exclusions.py`, `core/filetypes.py` |
| Previews (image/pdf/video/text/office/archive) | `core/preview.py` |
| Events / model (`FileEntry` slots, `DuplicateGroup`) | `core/events.py`, `core/model.py` |
| Trash / hard-link / explore | `services/actions.py` |
| Queue drain / signals | `services/scan_controller.py` |
| Window shell / pages registry | `ui/window.py`, `ui/pages/__init__.py` |
| Scan page (tiers, **multi-source list**, options, file-type filter, **per-source ring rows**) | `ui/pages/scan.py` |
| Removal history store / History page (+ **Recent scans** performance list, duration compare) | `config/history.py`, `ui/pages/history.py` |
| **Content hash cache** (size+mtime match, remount-tolerant; fast repeat/cross-source scans) | `core/hashcache.py` |
| **Perceptual image cache** (pHash/dHash reuse for unchanged images) | `core/phashcache.py` |
| **Scan performance log** (per-scan ScanRun/SourceStat → `scanruns.json`) | `core/scanstats.py` |
| **Source drive specs** (lsblk model/SSD-HDD/transport/fstype/size; degrades w/o lsblk) | `core/driveinfo.py` |
| Results (chart, formula card, action bar, rows, Delete All, Ignore, `_invalidate_cache`) | `ui/pages/results.py` |
| SpotCheck (image/**audio**/pdf/video players + graceful fallbacks) | `ui/pages/spotcheck.py` |
| Space-savings bars / percentage ring / info hint | `ui/widgets/space_chart.py`, `ui/widgets/ring_loader.py`, `ui/widgets/info_hint.py` |
| Theme palette | `ui/theme_loader.py` · styles `data/css/app.css` |
| Settings (tolerant JSON) | `config/settings.py` |
| Glossary data | `data/glossary/en.json` |
| Logging | `src/linfilededuplication/logsetup.py` |

---

## 5. Recent work

### 2026-10-03 → 10-05

- **Repeat scans now skip previously-scanned files entirely.** Three fixes so the index delivers
  the speed-up: (1) `hashcache.get` matches on **size+mtime only** — `dev`/`ino` stored but not
  required, so a remounted USB/exFAT/NTFS drive hits instead of missing every file; (2)
  `find_exact_groups` screens by the index **first** — an unchanged file skips the prefix read, the
  full SHA-256, **and** byte-verify (verify still runs on any group with a file read this run);
  (3) **perceptual cache** (`core/phashcache.py`) reuses image pHash/dHash. Measured: a 2nd scan of
  unchanged files does **zero** content reads. `_invalidate_cache` now clears **both** caches on
  removal. Full spec: `docs/CACHE-AND-HISTORY.md`.
- **Scan performance log** (`core/scanstats.py` → `scanruns.json`, cap 50) recorded in
  `window._on_scan_finished`; per-scan + per-source counters (reused vs hashed) measured **inside**
  the scan loop. **Source drive specs** via `core/driveinfo.py` (lsblk; `/proc/mounts`+statvfs
  fallback).
- **Scan page "✓ Cached" badge** per source with a prior scan (read-only; reads the perf log, not
  the 27 MB hash cache); tooltip = last run's metrics + drive.
- **History → Recent scans**: per-scan rows — bold **duration**, a like-for-like **speed-up
  comparison** vs the previous scan of the same sources+tier ("⚡ N× faster … · % reused"), a
  compact **scope line** (file-type filter · files · GB scanned · GB reclaimable · groups), and one
  terse line per source (full path = mountpoint+folder · drive specs). `Finished`/`ScanRun` carry
  `file_types`.
- **SpotCheck**: **audio/music** now previews with an inline player (GtkMediaControls, else
  Play-in-default + hint); **all image types** — decode to `Gdk.Texture`, with HEIC/AVIF/JXL via
  loaders and camera-RAW/loader-less formats falling back to an Open-in-viewer card.
- **UI/UX design reference** `docs/design/GUI-GUIDE-AND-DESIGN-REFERENCE.md` (adapted from the Lin\*
  house guide in `linapptemplate`); wired into the roadmap (CONCEPT §8, P8).
- **Exclusions**: System/Trash presets now skip mounted-drive junk (`$RECYCLE.BIN`, `System Volume
  Information`, …). **File types**: Documents gains full LibreOffice/ODF; new **Email** category;
  five include-columns; exclusion **All** box.
- Docs: new `docs/CACHE-AND-HISTORY.md`; uniform CC BY-NC 4.0 note. 95 tests (added driveinfo,
  scanstats, phashcache, repeat-scan, preview audio/image).

### 2026-09-30 → 2026-10-01

- SpotCheck: **PDF page-by-page viewer** (synced A/B, zoom) and **inline video player**.
- Results: **right-click Explore here / Open / Copy path** (row-scoped); fixed hard-link not
  removing files (row removal + inode collapse).
- **imagehash** installed to the user site so the installed app finds image near-duplicates.
- **Live scan caption** (root + streaming file under the radar).
- **Dual-hash (pHash+dHash)** image matching — kills smooth-image false positives (found by
  testing on a real 437-photo set).
- **Memory fix** for the OOM on big scans: `FileEntry.__slots__`, scaled thumbnails, 400-card cap
  (root cause was full-res thumbnail decode, not the engine).
- **Space-savings chart** (square capacity meters) + **"You can free up N GB"** sentiment +
  `Finished.occupied_bytes`.
- **Scan file-type filter** (Images/Video/Music/Documents, column "All", master **All Files**) +
  `ScanOptions.file_types`.
- **"How LinFileDedup decides what to keep"** formula card.
- **Red check-circle Delete marker** (replaced the orange system checkbox).
- **Delete All** (per group, keep none; Trash-only; guard + confirm) and **Ignore Files**
  (grey out + skip in future scans via `ScanOptions.ignore_paths` / `settings.ignored_paths`).
- Action bar **moved above the findings**; **Move to Trash → Delete All Duplicates** (no truncation).
- **Thorough hard-link tests** (`tests/services/test_actions.py`).
- Scan page: **Start scan** moved to the tier-toggle row (right-aligned, standard rounded button);
  removed the Scan-page "Ignored items" section; **Ignore Folder** is now a per-group button on
  **Results**; added a custom **Enter Extension** field (additive to the selected types).
- SpotCheck **video**: poster thumbnail (ffmpegthumbnailer) + inline GtkVideo when
  `libgtk-4-media-gstreamer` is installed, else a "Play in default player" button + install hint.
- **Percentage ring loader** replaces the radar; the percentage is the real files-scanned ratio.
- **Results reveal only after** the loader completes to 100% and fades (groups buffered during the
  scan, built in `_present_results`).
- Trash confirm dialog: **scrollable, wide, non-wrapping** file list.
- **Multi-source scanning** (`ScanOptions.roots`/`all_roots`, `walk` tags `FileEntry.source`,
  cross-source grouping, primary-source keeper) + a Sources list on the Scan page.
- **Per-source progress rings** as a list (ring + path/name/activity bar/note); app stays on Scan
  during a scan, all rings stay up then fade together, then switches to Results.
- **Scan History** (`config/history.py` + History page with before/after bars & "You saved N GB").
- **Hash cache** (`core/hashcache.py`) for fast repeat / cross-source scans — `path →
  {dev,ino,size,mtime,sha256}`; miss ⇒ hash + record (new files), fingerprint change ⇒ re-hash +
  update (changed files), all match ⇒ reuse (unchanged); invalidated on removal. Full write-up in
  `docs/FEATURES.md §4b`.
- **Settings → Scanning** toggles: `use_hash_cache` and `keep_primary_source` (both default on,
  honoured by `ScanOptions`).
- Scan ring rows show the **folder** on the path line; the **file name** (extension orange) sits
  below it (no duplication).

---

## 6. Backlog / known gaps

- **Cache is path-keyed → mountpoint-change caveat.** A file whose *path* changes (a drive mounted
  at a new mountpoint, or a moved/renamed file) is seen as new and re-hashed once. The size+mtime
  match already handles dev/ino changes on remount; the remaining case is the path itself. Candidate
  fix (discussed, not built): a secondary **`(volume-UUID, inode)`** key with path fallback — stable
  across remounts *and* moves on ext4/btrfs/xfs, so those drives become mountpoint-independent and
  survive reorganisation with no re-hash. **Not** universal: exFAT/NTFS/FAT don't give stable
  inodes, and writing an ID into files (xattr/sidecar) is rejected (breaks read-only safety, and
  unsupported on those filesystems). So it's an ext4-and-friends improvement, not a cure-all. See
  `docs/CACHE-AND-HISTORY.md` §3–4.
- **Warm-scan floor = the directory walk.** Once reads are cached away, a repeat scan's time is
  dominated by `stat`-ing the tree (required to read size+mtime) — irreducible without a riskier
  directory-mtime walk cache. Expect the speed-up to track how read-heavy a scan is, not to reach
  ~100%.
- **Hard-link has no confirm dialog** (Trash does) — worth adding for consistency.
- **Perceptual default `hamming=8`** is reasonable but slightly loose for smooth high-res photos;
  the dual-hash guard mitigates it. Tunable in Settings if desired.
- `.deb` could add `python3-imagehash` / GStreamer codec packs to `Recommends:` so a normal
  install offers image near-dup and audio/video playback.

**Resolved this session:** History showing no scans (→ Recent-scans performance log); SpotCheck
music had no preview (→ inline audio player); image previews limited to a few formats (→ broad set
+ fallback); external-drive re-scans not using the cache (→ remount-tolerant size+mtime match).

---

## 7. Gotchas

- **Screenshots:** render via GTK `render_texture` offscreen (WebKit/offscreen hangs). Popovers
  render on a separate surface and won't appear in a window texture snapshot — capture the popover
  child widget directly if you need it.
- **PDF/video in headless capture:** `pdftoppm` works; GtkVideo shows a placeholder without
  GStreamer codecs (fine on a real desktop).
- **Installer:** `install.sh` writes a clean launcher directly (an earlier `sed` rewrote the
  checkout sentinel) and `rm -rf`s old `src/css/icons/glossary` before copy (avoids nesting).
- **Markup:** Adw row titles are Pango markup — escape `&` (use "and").
- **Memory:** keep `FileEntry` slotted; never decode full-res images per row.

---

## 8. Reference material

- Technical design & roadmap: `docs/CONCEPT.md` · Features: `docs/FEATURES.md` · SpotCheck notes: `docs/SPOTCHECK.md`
- **UI/UX design reference** (UX laws, 2026 principles, WCAG 2.2 AA, visual system, components, voice, checklist → roadmap P8): `docs/design/GUI-GUIDE-AND-DESIGN-REFERENCE.md`
- **Cache & scan-history rules** (what's remembered, how it affects/persists across scans, invalidation): `docs/CACHE-AND-HISTORY.md`
- Mockups: `docs/mockups/` · Screenshots: `docs/screenshots/` · Brief: `docs/original-brief.txt`
- Review mockup (proposals): published Artifact `LinFileDedup Proposals`.
- Agent memory/backlog: `.claude/memory/`.
