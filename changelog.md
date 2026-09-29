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
