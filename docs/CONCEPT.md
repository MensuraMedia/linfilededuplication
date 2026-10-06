# LinFileDedup — Concept & Technical Design

**Project:** linfilededuplication (LinFileDedup)
**Status:** P0–P6b in place — exact + image + advanced engine, multi-source, fingerprint cache +
scan-performance history (fast index-first repeat scans), SpotCheck, full desktop integration
**Target platform:** Debian 12/13 + Linux Mint
**Foundation:** MensuraMedia `gtk4-dashboard-template`, ported to GTK 4 + libadwaita
**Governance:** universal-instruction-set v2026.04
**Visual system:** Adwaita, accent `#3584e4`, 212px sidebar, Cantarell / monospace

This file is the in-tree source of truth for the **technical** design and roadmap. The **UI/UX
design reference** — the ten UX laws, the ten 2026 design principles, the WCAG 2.2 AA baseline,
the visual system, component library, page specs, voice and the acceptance checklist, adapted for
LinFileDedup from the Lin\* house guide — is
[`docs/design/GUI-GUIDE-AND-DESIGN-REFERENCE.md`](design/GUI-GUIDE-AND-DESIGN-REFERENCE.md); it
drives the design work in the roadmap (§8, P8). HTML mockups are in `docs/mockups/`; the original
brief is `docs/original-brief.txt`.

## 1. Vision

Find and safely remove duplicate and near-duplicate files, with first-class support for
images, on the GNOME/Cinnamon desktop.

**Design pillars**

| Pillar | Meaning |
| --- | --- |
| Safe by default | Read-only scans; nothing removed without confirmation; Trash, not delete |
| Exact first | Cheap-to-expensive pipeline; byte-verify before trust |
| Images matter | Perceptual near-duplicates; always keep the highest resolution |
| Reusable core | Pure engine, no GTK; usable from a future CLI/daemon |

**Non-goals (v1):** cloud/remote sources, audio/video fingerprinting, inline (write-time)
dedup, cross-volume global indexing. These fit the architecture and are deferred.

## 2. Scope & feature set

Two tiers. **Simple Scan** — exact duplicates + image near-duplicates, sensible defaults,
thumbnails, safe actions. **Advanced Scan** — adds content-defined chunking, fuzzy hashing,
metadata/filename signals, a weighted keep policy, per-type thresholds, and an optional
off-by-default deep-embedding pass.

The 20 ranked comparison features map to modules: exact (1,2,3,6) → `core/hashers.py` +
`core/scanner.py`; perceptual images (7,8) → `core/image_perceptual.py`; policy/links
(18,19) → `core/policy.py` + `services/actions.py`; chunking/fuzzy/metadata/index
(4,5,10,11,12,20) → Advanced-tier modules; embeddings/audio/video/inline/global/delta
(9,13,14,15,16,17) → deferred.

## 3. Architecture

Strict layering, one-way dependencies (UI → services → core; nothing points back up).

```
src/linfilededuplication/
  core/      pure Python (no gi): scanner, hashers, image_perceptual, policy, model, events
  services/  scan_controller (queue drain), actions (trash/hard-link)   [may import GLib/Gio]
  models/    Gio.ListStore adapters
  ui/        window, sidebar, theme_loader, pages/, widgets/            [main thread only]
  config/    settings (tolerant JSON), layout
```

**Runtime flow.** A worker `ScanThread` runs the pure pipeline and emits `core.events`
onto a `queue.SimpleQueue`. `ScanController` drains it on the GTK main loop via
`GLib.timeout_add` (16 ms tick, 8 ms budget) and re-emits GObject signals; pages render from
those. Intent flows down as a scan request; data flows up as drained events.

**Core purity** is enforced by `tests/core/test_purity.py`, which imports every `core`
module in a subprocess with `sys.modules["gi"] = None`.

## 4. The exact pipeline

1. **Size pre-filter** — group by exact byte size; singletons cannot be exact duplicates.
2. **Progressive hash** — xxHash (or BLAKE2b) of the first 64 KB splits each size bucket.
3. **Full SHA-256** — only for prefix-matched candidates; equal digests form a group.
4. **Byte-for-byte verify** — final confirmation before a group is trusted. On a repeat scan it
   runs only on groups containing a file **read this run** (new/changed); a group whose members
   were all **unchanged since indexed** is trusted from the hash cache with no re-read (Trash-by-
   default keeps the rare size+mtime-preserving-edit case recoverable). See FEATURES §4b.

Images additionally get a perceptual hash (`imagehash.phash`); files within the configured
Hamming distance are clustered by union-find and reported as near-duplicate groups.

## 5. Keep/delete policy

For each group the engine marks one keeper; the rest are candidates. Order: highest
resolution (images) → largest size → non-derived filename → preferred folder → oldest mtime →
shallowest path. So a full-resolution original always outranks a resized or re-compressed copy.

## 6. Safety

Dry-run by default; `Adw.AlertDialog` confirmation naming counts and kept originals; Trash
(recoverable) by default with hard-link/permanent as options; protected paths refused;
never delete a group's keeper; unreadable groups are skipped, never treated as removable.

## 7. Packaging

App-id `com.mensuramedia.linfilededuplication`. `scripts/build-deb.sh` builds a `.deb` with
`dpkg-deb`; Depends on `python3-gi python3-gi-cairo gir1.2-gtk-4.0 gir1.2-adw-1`, Recommends
the optional hashing libraries. Flatpak is a follow-up.

## 8. Roadmap

| Phase | Deliverable | Exit criteria |
| --- | --- | --- |
| P0 | Shell, paths, logging, icons, CSS, engine skeleton | Launches; `test_purity` green |
| P1 | Data model + tolerant settings | Round-trip tests |
| P2 | Exact core (size→progressive→SHA-256→verify) | Golden tests on temp trees |
| P3 | Threaded runner + drain, cancel | End-to-end scan |
| P4 | Simple Scan UI (scan + results, trash/hard-link) | A scan runs end to end |
| P5 | Image depth (perceptual + keep-highest-res) | A test per image signal |
| P6 | Advanced Scan (chunking, fuzzy, metadata, policy) | A test per signal |
| **P6b** | **Fingerprint cache + scan-performance history** (index-first fast repeat scans, remount-tolerant cache, perceptual cache, per-scan/per-source metrics + drive specs in History) | Repeat scan of unchanged files does **zero** content reads (measured); caches + log persist across restarts. **Delivered.** |
| P7 | CLI reusing core; scheduled scans | CLI records history |
| P8 | **Accessibility & design-reference pass** (both themes, keyboard, voice) | The [GUI guide](design/GUI-GUIDE-AND-DESIGN-REFERENCE.md) §14 checklist passes |
| P9 | Packaging: desktop, metainfo, .deb, Flatpak skeleton | Validators pass |

P0–P6b are substantially in place in this foundation; P7+ follow. The cache/history rules are
specified in [`CACHE-AND-HISTORY.md`](CACHE-AND-HISTORY.md).

**Candidate enhancement (backlog):** a secondary `(volume-UUID, inode)` cache key with path
fallback, to make ext4/btrfs/xfs drives mountpoint-independent and reuse fingerprints across
moves/renames — without writing to files (exFAT/NTFS keep the path key, since they lack stable
inodes). See `docs/HANDOFF.md §6` and `CACHE-AND-HISTORY.md` §3–4.

**P8 is specified by the [GUI Guide & Design Reference](design/GUI-GUIDE-AND-DESIGN-REFERENCE.md)**
(§15, *Roadmap hooks*). Concretely: Keep/Delete shown as an icon **and** a word (not colour alone);
a contrast audit in **both** light and dark; a full keyboard flow for selection and SpotCheck;
focus rings; a 32 px target floor; 640 px / 200% reflow; screen-reader names and status
announcements; a High-Contrast pass; a copy/voice pass to the three-part pattern; and a component
sheet drawn with all states. Reviewers judge screens and mockups against the guide's §4–6 and §14.

## 9. Risks

ssdeep/TLSH packaging varies (treat as optional capability); embedding model weight (keep
off by default); libadwaita 1.2 baseline on Bookworm (feature-detect newer widgets);
hard-link edge cases (same-inode/cross-filesystem — fall back to Trash); perceptual false
positives (conservative default; near-duplicates never auto-deleted).
