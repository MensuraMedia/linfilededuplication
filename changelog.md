# Changelog

Append-only. Format: `| ISO-8601 datetime | description |`.

| Datetime | Description |
| --- | --- |
| 2026-09-29 | P0 foundation: GTK 4 + libadwaita shell (window, 212px sidebar, page registry, toast overlay), ported from the gtk4-dashboard-template house pattern. |
| 2026-09-29 | Pure core engine: size pre-filter → progressive (xxHash/BLAKE2b) → SHA-256 → byte-verify exact matching; perceptual image near-duplicates; keep/delete policy (highest-resolution first). Enforced by `test_purity`. |
| 2026-09-29 | Services: `ScanController` queue-drain (16ms/8ms), `actions` Trash/hard-link with protected-path guards. |
| 2026-09-29 | UI: Overview, Scan (Simple/Advanced tiers, folder chooser, options, live progress), Results (duplicate groups, selection, confirmed Trash/hard-link), History, Settings. |
| 2026-09-29 | Packaging: desktop entry, AppStream metainfo, `build-deb.sh`, install/uninstall scripts; CC BY-NC 4.0 license; README with mockup screenshots; CONCEPT design doc and HTML mockups under docs/. |
| 2026-09-29 | Scan exclusions (`core/exclusions.py`): named presets + custom globs skip system/cache/build/VCS/app files; wired into `walk()` and Settings → Scan scope. |
| 2026-09-29 | Backup awareness (`core/backup_detect.py`): Probable-backup detection (name/date/sibling signals), Newest/Older markers, and keep-newest policy; Settings toggles. |
| 2026-09-29 | Guidance: local glossary (`core/glossary.py` + `data/glossary/en.json`), searchable Knowledge page, and a reusable `InfoHint` (i) widget peppered through pages and settings. |
| 2026-09-29 | Preview providers (`core/preview.py`): read-only, budgeted snippets for images, text, PDF, office, archives; feed SpotCheck. |
| 2026-09-29 | SpotCheck (`ui/pages/spotcheck.py`): large side-by-side confirmation view with previews, confirm, and Trash/hard-link. Fixed derived-name and ampersand-markup bugs; 25 tests passing. |
| 2026-09-29 | P6 Advanced Scan: content-defined chunking similarity (`core/chunking.py`), fuzzy hashing (`core/fuzzy.py`, TLSH/ssdeep), metadata/filename signals (`core/metadata.py`); new SIMILAR group kind wired into the Advanced tier. |
| 2026-09-29 | Desktop integration: original app icon (scalable SVG + 16–256px PNGs), window/Alt-Tab icon + WM_CLASS, optional XApp system-tray icon with close-to-tray (`services/tray.py`), present/scan app actions. |
| 2026-09-29 | Packaging & ops: `.deb` includes app icons + glossary; Recommends gir1.2-xapp-1.0, Suggests python3-tlsh/poppler-utils; `scripts/backup.sh` local backup; comprehensive README. 29 tests passing. |
| 2026-09-29 | Fix: installed launcher wrote by install.sh/build-deb.sh no longer breaks (the sed rewrote the checkout sentinel); write a clean launcher directly. Verified via user install + live scan. |
| 2026-09-29 | Backup policy tie-break: within a close time window (`BACKUP_CLOSE_SECONDS`), keep the non-backup original over a marginally newer `.bak`. 30 tests passing. |
| 2026-09-29 | Renamed visible app to LinFileDedup (uniform with the lin-* series); fixed install.sh nesting src on reinstall; re-captured screenshots. |
| 2026-09-29 | Scanning indicator: a live radar-sweep header widget (`ui/widgets/scan_spinner.py`, Cairo, accent-coloured, theme-aware) shown while a scan runs, kept visible ≥ `SCAN_MIN_SECONDS` (1.6s) even on sub-second scans. |
