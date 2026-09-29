# Changelog

Append-only. Format: `| ISO-8601 datetime | description |`.

| Datetime | Description |
| --- | --- |
| 2026-09-29 | P0 foundation: GTK 4 + libadwaita shell (window, 212px sidebar, page registry, toast overlay), ported from the gtk4-dashboard-template house pattern. |
| 2026-09-29 | Pure core engine: size pre-filter → progressive (xxHash/BLAKE2b) → SHA-256 → byte-verify exact matching; perceptual image near-duplicates; keep/delete policy (highest-resolution first). Enforced by `test_purity`. |
| 2026-09-29 | Services: `ScanController` queue-drain (16ms/8ms), `actions` Trash/hard-link with protected-path guards. |
| 2026-09-29 | UI: Overview, Scan (Simple/Advanced tiers, folder chooser, options, live progress), Results (duplicate groups, selection, confirmed Trash/hard-link), History, Settings. |
| 2026-09-29 | Packaging: desktop entry, AppStream metainfo, `build-deb.sh`, install/uninstall scripts; CC BY-NC 4.0 license; README with mockup screenshots; CONCEPT design doc and HTML mockups under docs/. |
