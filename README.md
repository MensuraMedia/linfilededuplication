# LinFileDedup

**Find and safely remove duplicate and near-duplicate files — with real care for images,
backups, and your confidence before anything is deleted.**

LinFileDedup (`linfilededuplication`) is a native Linux desktop app for Debian 12/13 and Linux
Mint, built with **GTK 4 + libadwaita**. It finds exact duplicates, visually similar images,
and near-identical documents; flags probable backups; and lets you reclaim space **safely** —
nothing is changed until you review the groups and confirm, and removals go to Trash by default.

![LinFileDedup — Results](docs/screenshots/results.png)

> Part of the MensuraMedia `lin-*` family of Linux utilities, built on the house
> `gtk4-dashboard-template` pattern. Runs entirely locally — no accounts, no network, no telemetry.

---

## Table of contents

- [Feature tour](#feature-tour)
- [Everything LinFileDedup does](#everything-linfilededuplication-does)
- [Desktop integration](#desktop-integration)
- [Install](#install)
- [Usage](#usage)
- [How it works (architecture & services)](#how-it-works-architecture--services)
- [Development](#development)
- [Roadmap](#roadmap)
- [License](#license)
- [Credits](#credits)

---

## Feature tour

### SpotCheck — confirm before you remove

A large side-by-side view of a duplicate group. See each file's real content — full **image**
previews, a page-by-page **PDF** viewer (synced across panels, with zoom), an inline **video**
player (with thumbnails), or readable document snippets — keeper first, so you can be sure before
acting. It is a gate, not an actor: closing it changes nothing.

![SpotCheck](docs/screenshots/spotcheck.png)

### Backups, guidance, and scan scope

| Probable backups in Results | Knowledge (searchable glossary + FAQ) |
| --- | --- |
| ![Results with backups](docs/screenshots/results-backups.png) | ![Knowledge](docs/screenshots/knowledge.png) |

| Scan scope & backup settings | |
| --- | --- |
| ![Scan scope](docs/screenshots/settings-scope.png) | |

### Scan scope & ignored items

| Scan — tiers, file-type filter, custom extensions | Ignored — files & folders you skip |
| --- | --- |
| ![Scan](docs/screenshots/scan.png) | ![Ignored](docs/screenshots/ignored.png) |

### The basics

| Overview | Live progress — a real percentage |
| --- | --- |
| ![Overview](docs/screenshots/overview.png) | ![Scanning](docs/screenshots/scan-ring.png) |

Interactive design mockups (light and dark) live in
[`docs/mockups/dedupedash-mockups.html`](docs/mockups/dedupedash-mockups.html).

---

## Everything LinFileDedup does

### Matching engine

- **Exact duplicates** — a fast, layered pipeline: size pre-filter → progressive partial hash
  (xxHash or BLAKE2b) → full **SHA-256** → optional **byte-for-byte** verification. A match is
  a real match, never a hash coincidence.
- **Image near-duplicates** — perceptual hashing groups images that look the same after resizing,
  cropping, or re-saving, with a tunable Hamming-distance threshold. Matching requires **both
  pHash and dHash to agree**, which filters out the smooth-image false positives that a single
  hash produces — found and fixed by testing on a real 400+ photo set.
- **Near-identical content (Advanced)** — **content-defined chunking** fingerprints files by
  shift-resistant anchors and groups documents that share most content even after an edit or
  insertion.
- **Fuzzy hashing (Advanced)** — TLSH / ssdeep (when installed) catch near-identical binaries,
  documents, and text that differ by small edits.
- **Metadata & filename signals (Advanced)** — EXIF capture time and camera, plus filename
  similarity, enrich matching and display.

### Simple and Advanced tiers

- **Simple Scan** — exact duplicates + image near-duplicates, with sensible defaults. What
  most people need.
- **Advanced Scan** — adds the content-similarity, fuzzy, and metadata passes for documents
  and binaries, plus finer control.

### Keep policy — and it's transparent

Every group keeps exactly one file (the **keeper**); the rest become candidates. The order:
highest resolution (images) → largest size → original (non-derived) filename → preferred folder
→ oldest file. Nothing derived is ever kept over an original. Results shows a **"How LinFileDedup
decides what to keep"** card that spells out these rules (newest / largest / backups / name /
hard-linked), so the automatic choices are never a mystery.

### Space savings at a glance

When a scan finishes, Results leads with a headline — **"You can free up N GB"** — and a
before/after **capacity-bar chart** (space now vs. after cleanup), so the payoff is clear before
you act. Results are revealed only once the progress loader reaches 100% and fades, never
half-formed.

### Backup awareness

- **Probable Backup** marker (icon + words, colourblind-safe) on files that look like backups —
  by name (`~`, `.bak`, `.old`, `backup`, `copy`, `vN`), embedded date stamps, backup folders,
  or dated sibling sets.
- **Newest / Older** age indicators so you can keep the most recent backup and clear the stale
  ones — the keep policy prefers the newest in a backup group.
- Detection is advisory: backups are **never** removed automatically.

### SpotCheck & content previews

- Large keeper-first comparison of a group, opened from Results.
- **Images** render full; **PDFs** render as actual pages in a page-by-page viewer (Prev/Next,
  page N of M, actual-size zoom) that's **synced across panels** for a true A/B compare;
  **videos** get a thumbnail and an inline player (or "Play in default player" when the GTK media
  backend isn't installed).
- **Preview providers** show read-only snippets for everything else: first lines of
  **text/code/config**; paragraphs / sheet names of **office** documents (docx/odt/pptx/xlsx);
  entry lists of **archives**; and a metadata card as a fallback. Providers never execute a file,
  follow links out, or touch the network, and are bounded by size/time budgets.

### Choose exactly what to scan

- **File-type filter** — columns of popular types (**Images / Video / Music / Documents**), each
  with a tri-state **All**, plus a master **All Files**, and a free-text **Enter Extension** field
  for anything else (e.g. `.bak, .csv, .idx`) that's *added* to your selections.
- **Scan scope (exclusions)** — presets that skip files an app or the OS can recreate (**system
  files, caches, package/build artifacts, version-control internals, Trash**) plus custom globs.
  Excluded paths are never scanned and never removable.
- **Ignore files & folders** — on Results, **Ignore Files** or **Ignore Folder** greys out rows
  (no action taken) and skips them in **every future scan**; the dedicated **Ignored** page lists
  everything you've skipped, with **Resume scanning** on any entry.

### In-app guidance

- **Info icons** — a small `(i)` next to anything that could confuse; hover or focus it for a
  plain-language explanation, with a **Learn more** link into the Knowledge page.
- **Knowledge page** — a searchable, offline glossary and FAQ defining every term, file kind,
  and action you meet (duplicate, perceptual hash, hard link, backup file, system file, and more).

### Safety

- Read-only scans; nothing removed without an `Adw.AlertDialog` confirmation — which lists the
  affected files in a scrollable, non-wrapping list so you can review before you commit.
- **Delete All Duplicates** → **Move to Trash** (recoverable) or **Hard-link** (reclaim space,
  keep every path) instead of permanent deletion. A per-group **Delete All** can remove every
  copy when you want none kept (Trash-only, with a clear guard and confirmation).
- Protected system paths refused; a group's keeper can never be deleted by accident; unreadable
  groups are skipped, never treated as removable.

### Progress & performance

- A circular **percentage loader** shows the **true ratio of files scanned** (not a cosmetic
  spinner): every file counts, each hashed candidate and perceptually-hashed image advances it,
  and it eases to 100% before the results appear.
- **Memory-safe on huge scans** — thumbnails decode scaled (not full-resolution), rendered group
  cards are capped, and the file model is slot-based, so a full home-directory scan stays bounded
  (hundreds of MB, not gigabytes).

### Desktop-native

GTK 4 + libadwaita, automatic light/dark, your GNOME/Cinnamon accent, keyboard-navigable,
screen-reader labelled, responsive.

---

## Desktop integration

- **Application launcher & menu item** — a `.desktop` entry installs LinFileDedup into your
  applications menu; it also registers for folders (open a folder "with LinFileDedup").
- **App icon** — an original icon shipped in `hicolor` (scalable SVG + 16–256 px PNGs), used in
  the menu, the window, and **Alt-Tab** (via `StartupWMClass` / WM_CLASS matching).
- **Panel / system-tray icon** — an optional `XApp.StatusIcon` (Mint, Cinnamon, and others):
  left-click opens the window, and the tray menu offers Open, New scan, and Quit. Closing the
  window then minimises to the tray. A detected capability — the app runs fine without a tray.
- **Command line** — `linfilededuplication [folder]` launches a scan on a folder.

---

## Install

### From the `.deb`

```bash
scripts/build-deb.sh
sudo apt install ./dist/linfilededuplication_0.1.0_all.deb
```

Depends on `python3-gi`, `python3-gi-cairo`, `gir1.2-gtk-4.0`, `gir1.2-adw-1`. Recommends
`python3-pil`, `python3-imagehash`, `python3-xxhash`, `gir1.2-xapp-1.0` (tray), `poppler-utils`
(PDF pages), `libgtk-4-media-gstreamer` (SpotCheck video playback), and `ffmpegthumbnailer`
(video thumbnails). Suggests `python3-tlsh` (fuzzy). Optional pieces are detected at runtime and
degrade gracefully when absent.

### From source (development)

```bash
sudo apt install python3-gi python3-gi-cairo gir1.2-gtk-4.0 gir1.2-adw-1 python3-pil gir1.2-xapp-1.0
git clone https://github.com/MensuraMedia/linfilededuplication.git
cd linfilededuplication
python3 -m venv --system-site-packages .venv
.venv/bin/pip install xxhash imagehash py-tlsh        # optional extras
./run.sh
```

### System / user install without a package

```bash
scripts/install.sh            # ~/.local (user)
scripts/install.sh --system   # /usr/local (sudo)
scripts/uninstall.sh          # remove
```

---

## Usage

1. Open **Scan**, choose a folder, pick **Simple** or **Advanced**, optionally narrow the
   **file types**, and start (the button is top-right on the tier row).
2. A circular **percentage loader** shows the real progress as files are scanned; when it reaches
   100% and fades, **Results** appears with a **"You can free up N GB"** headline and the
   before/after chart.
3. Review each group — the keeper shows a green check, candidates a red one. Open **SpotCheck**
   to compare content, and check the **Probable backup** / **Newest / Older** markers. Right-click
   a row for **Explore here / Open / Copy path**; use **Ignore Files/Folder** to skip things.
4. Choose **Hard-link** or **Delete All Duplicates**, review the file list, confirm, and reclaim
   the space.

![Live progress](docs/screenshots/scan-ring.png)

Tune matching, backups, safety, and **Scan scope** in **Settings**; manage skipped items on the
**Ignored** page. Hover any `(i)` for help, or open **Knowledge** to search terms.

---

## How it works (architecture & services)

Strict layering, one-way dependencies (UI → services → core; nothing points back up).

```
src/linfilededuplication/
  core/       pure Python, NO GTK (enforced by tests/core/test_purity.py)
    scanner.py          the pipeline: walk -> size -> progressive -> SHA-256 -> verify
    hashers.py          size / xxHash / SHA-256 / byte-for-byte
    image_perceptual.py perceptual image hashing + Hamming clustering
    chunking.py         content-defined anchor sampling + Jaccard similarity
    fuzzy.py            TLSH / ssdeep fuzzy hashing (optional)
    metadata.py         EXIF + filename similarity
    backup_detect.py    probable-backup signals + age ranking
    exclusions.py       scan-scope presets + custom globs
    filetypes.py        popular file-type categories for the scan filter
    policy.py           keep/delete ranking (incl. keep-newest for backups)
    preview.py          read-only content previews for SpotCheck
    glossary.py         load + search the local glossary/FAQ
  services/   GTK <-> core bridge
    scan_controller.py  worker thread -> queue -> GLib drain (16 ms / 8 ms budget)
    actions.py          Trash / hard-link with protected-path guards
    tray.py             optional XApp status icon
  ui/         Adwaita shell: window, sidebar, pages/, widgets/ (main thread only)
  config/     settings (tolerant JSON), layout
```

The engine runs on a worker thread and streams results to the UI through a drained queue, so
the window never freezes and a scan can always be cancelled. The `core/` package imports no GTK
and is covered by unit and golden tests, so it can back a future CLI or daemon unchanged.

See [`docs/CONCEPT.md`](docs/CONCEPT.md) for the full technical design and
[`docs/SPOTCHECK.md`](docs/SPOTCHECK.md) for the SpotCheck / backup / guidance features.

---

## Development

```bash
pytest -q                     # tests: pure core runs anywhere; UI smoke needs a display/xvfb
python3 -m linfilededuplication --smoke   # build every page headless
ruff check src tests          # lint
scripts/build-deb.sh          # build the .deb
scripts/backup.sh             # timestamped local backup of the source
```

Core is pure and guarded: `tests/core/test_purity.py` imports every `core` module with GTK
blocked, so a stray GTK import fails the build.

---

## Roadmap

Done: the exact engine, image near-duplicates (dual pHash+dHash), Advanced Scan (content
similarity, fuzzy, metadata), backups, SpotCheck with synced PDF pages and an inline video player,
previews, exclusions, the file-type filter and custom extensions, ignore files/folders and the
Ignored page, the space-savings chart and keep-rules card, the real-progress percentage loader,
info icons, the Knowledge page, and desktop integration (launcher, menu, tray, Alt-Tab, icon,
`.deb`). Next: a persistent scan **History**, a headless CLI, a Flatpak, and a SpotCheck A/B
difference view. Details in [`docs/CONCEPT.md`](docs/CONCEPT.md).

---

## License

Released under the **Creative Commons Attribution–NonCommercial 4.0 International License
(CC BY-NC 4.0)**. You are welcome to use, copy, modify, and redistribute LinFileDedup for any
non-commercial purpose, with attribution. **Commercial use requires prior written permission** —
we're happy to talk; please reach out. Full terms in [`LICENSE.md`](LICENSE.md).

## Credits

- Icons from [Phosphor Icons](https://phosphoricons.com) (MIT); the app icon is original.
- Built by **MensuraMedia** on the `gtk4-dashboard-template` house pattern.
