# CLAUDE.md — linfilededuplication (DedupeDash)

Native Linux desktop app that finds and safely removes duplicate and near-duplicate files.
GTK 4 + libadwaita, Python / PyGObject. Built from the MensuraMedia `gtk4-dashboard-template`
house pattern (ported to GTK 4 per its `docs/12-gtk4-porting.md`).

## Commands

```bash
./run.sh                      # run from the checkout (uses .venv if present)
./run.sh --debug              # verbose logging
python3 -m linfilededuplication --smoke   # build every page headless and exit
pytest -q                     # tests (pure-core runs anywhere; UI smoke needs xvfb)
ruff check src tests          # lint
scripts/build-deb.sh          # build dist/linfilededuplication_<ver>_all.deb
```

Dev setup: `python3 -m venv --system-site-packages .venv && .venv/bin/pip install xxhash imagehash`.
System deps: `python3-gi python3-gi-cairo gir1.2-gtk-4.0 gir1.2-adw-1` (+ `python3-pil` for images).

## Architecture (strict layering, one-way dependencies)

- `core/` — **pure Python, no gi/Gtk imports** (enforced by `tests/core/test_purity.py`).
  The scan pipeline (size → progressive → SHA-256 → verify, plus perceptual images) and the
  keep/delete policy. Emits `core.events` objects; a `ScanThread` wraps it.
- `services/` — GTK ↔ core bridge. `ScanController` drains the worker's `queue.SimpleQueue`
  on the main loop via `GLib.timeout_add(16 ms, 8 ms budget)` (never `idle_add`) and re-emits
  GObject signals. `actions.py` does Trash / hard-link with guards.
- `models/` — Gio.ListStore adapters (thin; results currently render as widgets).
- `ui/` — `window.py` (Adw shell), `sidebar.py`, `theme_loader.py`, `pages/` (registered in
  `pages/__init__.py` via `PageSpec`), `widgets/`. Main thread only.
- `config/` — `settings.py` (tolerant JSON), `layout.py`, theme handled by libadwaita.

Rules of the house:
1. Local-first: embedded icons, system fonts, stdlib + PyGObject. Optional libs (Pillow,
   imagehash, xxhash) are runtime-detected and degrade gracefully when absent.
2. Never block the main loop; all scanning is on a worker thread.
3. Safety first: scans are read-only; nothing is removed without an `Adw.AlertDialog`
   confirmation; Trash by default (recoverable); protected paths refused.
4. Every rule is a test (purity, hashers, scanner, policy, headless smoke).

## Conventions

- App id `com.mensuramedia.linfilededuplication`; package `linfilededuplication`; visible
  name **DedupeDash**; GObject prefix `Lfd`.
- Icons: embedded Phosphor `-symbolic` SVGs under `data/icons/`, named `app-<id>-symbolic`
  (+ `-active` for nav). Never rely on the system icon theme.
- Wrap user-visible strings in `_()` (`i18n.py`).
- Window controls (min/max/close) sit at the **top-right** (desktop decoration layout).

## Memory & docs

- Design: `docs/CONCEPT.md`; mockups: `docs/mockups/`; changelog: `changelog.md`.
- `.claude/memory/` holds decisions and change manifests; `.claude/rules/` holds the
  path-scoped core-purity and python-gtk rules.

## SpotCheck & guidance (see docs/SPOTCHECK.md)

- `core/exclusions.py` — scan-scope presets + custom globs (used in `walk()`).
- `core/backup_detect.py` — Probable-backup signals + keep-newest ranking.
- `core/preview.py` — read-only, budgeted content previews for SpotCheck.
- `core/glossary.py` + `data/glossary/en.json` — terms/FAQ for the Knowledge page and InfoHint.
- `ui/widgets/info_hint.py`, `ui/pages/knowledge.py`, `ui/pages/spotcheck.py`.

## Status

P0 foundation + exact engine + image near-duplicates + Simple Scan UI + safe actions, plus
SpotCheck, backup awareness, scan exclusions, info icons and the Knowledge page. 25 tests
passing. Roadmap in `docs/CONCEPT.md`; feature notes in `docs/SPOTCHECK.md`.
