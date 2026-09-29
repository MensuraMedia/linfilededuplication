# Decisions

| Date | Decision | Rationale |
| --- | --- | --- |
| 2026-09-29 | Target GTK 4 + libadwaita (not the template's GTK 3.24) | User choice; matches repo name and brief; ported via template `docs/12-gtk4-porting.md`. |
| 2026-09-29 | Pure `core/` enforced by a subprocess purity test | Headless-testable engine, reusable from a future CLI. |
| 2026-09-29 | Queue + `GLib.timeout_add(16ms, 8ms budget)` drain, not `idle_add` | Keeps the UI responsive under a fast scan without flooding the loop. |
| 2026-09-29 | Results render as widgets (not `Gtk.ColumnView`) in the first cut | Simpler and robust for the MVP; ColumnView factory is a later refinement. |
| 2026-09-29 | Visible name "DedupeDash"; app-id/package `linfilededuplication` | Friendly product name over the technical id; open naming decision, easily changed. |
| 2026-09-29 | License CC BY-NC 4.0 | Free use/copy/modify/redistribute; commercial use needs explicit permission. |
| 2026-09-29 | Optional libs (Pillow/imagehash/xxhash) are Recommends, runtime-detected | Local-first; app runs without them and degrades gracefully. |
| 2026-09-29 | Backup detection requires a real name/location signal, or 2+ dated siblings | Avoids mislabelling ordinary duplicates; a lone dated filename is not enough. |
| 2026-09-29 | Exclusion presets all default-on; excluded paths also hard-guard deletion | Local-first scan scope; excluded files are never scanned nor removable. |
| 2026-09-29 | Preview providers are pure, read-only, argv-only, budgeted | Never execute a file; safe snippets for SpotCheck; graceful fallback when a tool is absent. |
| 2026-09-29 | One glossary as the single source for InfoHint copy and the Knowledge page | A term is defined once; a test asserts every InfoHint key resolves. |
| 2026-09-29 | SpotCheck is an Adw.Dialog opened from Results | Keeps selection context; a gate that never deletes on its own. |
