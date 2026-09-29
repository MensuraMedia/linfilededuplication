---
paths: ["src/linfilededuplication/ui/**", "src/linfilededuplication/services/**"]
---
# Python + GTK 4 conventions

- All widget access on the main thread. Worker threads hand results back by putting
  `core.events` on a `queue.SimpleQueue` that `ScanController` drains with
  `GLib.timeout_add(16, ...)` on an 8 ms budget — never `GLib.idle_add` for the stream.
- No `shell=True`; argv lists only. Escape file names before any Pango markup.
- Icons are embedded `-symbolic` SVGs referenced by name (`app-<id>-symbolic`); never rely on
  the system icon theme.
- Wrap every user-visible string in `_()`.
- Destructive actions confirm via `Adw.AlertDialog`; default to Trash; refuse protected paths.
- GTK vfunc names (`do_activate`, `do_open`, `do_startup`) keep their names (ruff N802 ignored).
