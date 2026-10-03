# Concept — Scan-page per-source display (ring list + per-file activity)

**Status:** proposed (design for review)
**Supersedes:** the grid-of-rings layout from `CONCEPT-MULTISOURCE.md §3.2`
**Author:** MensuraMedia · 2026-10-03

## 1. Problem

The first per-source design shows a **grid of ring cards** with the file path *under* the ring.
Two issues surface in real use:

1. **Paths don't fit.** A ring card is ~190px wide; real paths (`/media/user/USB-BACKUP/DCIM/...`)
   truncate, so the user can't see what's being scanned.
2. **Large files look like a hang.** The ring's percentage barely moves while a single large file
   is hashed (one file among thousands), so a multi-minute hash on a big video reads as "frozen."

## 2. Design — a per-source **list row**

Replace the grid with a **vertical list**, one row per source. Each row:

```
┌───────────────────────────────────────────────────────────────────────────┐
│          ╭────╮   /media/user/USB-BACKUP/DCIM/Camera/PXL_20260515_1353.mp4  │  ← full path
│          │ 68%│   PXL_20260515_1353.mp4                                      │  ← file name
│          ╰────╯   ▮▮▮▮▮▯▯▯▯▯▯▯▯▯▯▯▯▯▯▯▯▯▯▯  (per-file activity)              │  ← activity bar
│                   Note: large files may take several minutes to scan…       │  ← reassurance
└───────────────────────────────────────────────────────────────────────────┘
```

- **Left — the ring**, left-aligned and **slightly smaller** (~84px). It still shows the source's
  true overall percentage (files processed ÷ files in that source). Vertically centred.
- **Right — a text column** that fills the remaining width:
  1. **Full path** of the file currently being scanned (monospace, middle-ellipsized only if it
     exceeds the full row width, which is wide). Updates rapidly.
  2. **File name** (the basename), bold, so the current item is readable even when the path churns.
  3. **A small horizontal activity bar** (see §3).
  4. A dim note: **"Note: large files may take several minutes to scan…"**.

The row is wide (full content width), so paths that truncated in a card now fit or nearly fit.

## 3. The per-file activity bar

A thin `Gtk.ProgressBar` in **pulse (indeterminate) mode** — not a percentage. Its job is to make
*activity* visible at the per-file level, which the ring cannot:

- **On every per-source progress event** (one per file processed, throttled), the bar is pulsed
  (`bar.pulse()`), so a burst of small files makes it **move quickly**.
- **A steady fallback pulse** (a ~250 ms timer while scanning) keeps it **always moving slowly**,
  so even when no file-event arrives for a while — i.e. **a single large file is being hashed** —
  the bar still ticks. The user sees: *fast motion for small files, a slow crawl on a big file,
  never frozen.*
- When a source finishes, its bar stops and the row shows **Done**.

This directly answers the confusion the note addresses: a long pause on one large file is now
visibly "busy, just slow", not "hung".

## 4. Behaviour unchanged

- The ring value, the per-source accounting, the "keep all rings visible until the whole scan
  completes, then fade them collectively and show results" rule, and cancel all behave as before —
  only the **layout** (list vs grid) and the **added activity bar + path/name/note** change.
- Rings still live in a scroll area if there are many sources; each row is fixed-height.

## 5. Implementation notes (`ui/pages/scan.py`)

- `_ring_card` → `_source_row`: a horizontal box: `RingLoader(84)` on the left; a vertical text
  box on the right with `path_label` (mono, ellipsize-middle), `name_label` (bold), the
  `Gtk.ProgressBar` (css class `app-activity`), and a static note label.
- Keep `self._rings[source] = (ring, path_label, name_label, bar)`.
- `_on_progress` (per source): `ring.set_progress(...)`; set `path_label`/`name_label` from
  `detail`; `bar.pulse()`.
- Add one `GLib.timeout_add(250, …)` while scanning that pulses every active bar; removed on
  finish/cancel.
- CSS: `.app-activity { min-height: 6px; }` (thin bar), muted trough.
