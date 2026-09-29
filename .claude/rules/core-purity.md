---
paths: ["src/linfilededuplication/core/**"]
---
# Core purity

Modules under `core/` MUST NOT import `gi`, `Gtk`, `Gdk`, `GLib`, `Gio`, `cairo`, or any
`linfilededuplication.ui` / `.services` / `.models` module. Standard library plus optional,
runtime-detected libraries (Pillow, imagehash, xxhash) only.

Why: the engine stays headless-testable and reusable from a future CLI. Communication to the
UI is one-way, via `core.events` dataclasses on a `queue.SimpleQueue`.

Enforced by `tests/core/test_purity.py`, which imports every core module in a subprocess with
`sys.modules["gi"] = None` so any leaked GTK import fails the build.
