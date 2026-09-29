"""Pure deduplication engine.

RULE: nothing in this package may import ``gi``, ``Gtk``, ``Gdk``, ``GLib``, ``Gio``,
``cairo`` or any ``linfilededuplication.ui`` / ``.services`` / ``.models`` module. It is
stdlib-only plus optional, runtime-detected libraries (Pillow, imagehash, xxhash), so the
engine stays headless-testable and reusable from a future CLI. Enforced by
``tests/core/test_purity.py``. The UI receives results only as ``core.events`` objects.
"""
