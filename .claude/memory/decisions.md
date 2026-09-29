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
