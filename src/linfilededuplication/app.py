"""Adw.Application: identity, data paths, icons, theme, actions, the window."""
from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gio, GLib, Gtk  # noqa: E402

from linfilededuplication import APP_ID, APP_NAME, __version__  # noqa: E402
from linfilededuplication import logsetup  # noqa: E402
from linfilededuplication.config.settings import Settings  # noqa: E402
from linfilededuplication.i18n import _  # noqa: E402

log = logging.getLogger("linfilededuplication.app")


def data_path(*parts: str) -> str:
    """Resolve a data file across dev checkout and installed prefixes."""
    candidates = []
    env = os.environ.get("LINFILEDEDUPLICATION_DATA_DIR")
    if env:
        candidates.append(Path(env))
    candidates.append(Path(__file__).resolve().parent.parent.parent / "data")  # repo/data
    candidates.append(Path("/usr/share/linfilededuplication"))
    candidates.append(Path("/usr/local/share/linfilededuplication"))
    for base in candidates:
        p = base.joinpath(*parts)
        if p.exists():
            return str(p)
    return str(candidates[0].joinpath(*parts))


class DedupeApp(Adw.Application):
    def __init__(self) -> None:
        flags = Gio.ApplicationFlags.HANDLES_OPEN
        if os.environ.get("APP_NON_UNIQUE"):
            flags |= Gio.ApplicationFlags.NON_UNIQUE
        super().__init__(application_id=APP_ID, flags=flags)
        GLib.set_application_name(APP_NAME)
        GLib.set_prgname(APP_ID)            # WM_CLASS for Alt-Tab / taskbar matching
        self.settings = Settings.load()
        self.window: Gtk.ApplicationWindow | None = None
        self.tray = None

    # --- lifecycle -------------------------------------------------------
    def do_startup(self) -> None:
        Adw.Application.do_startup(self)
        self._register_icons()
        from linfilededuplication.ui.theme_loader import ThemeLoader
        self.theme = ThemeLoader(data_path("css", "app.css"))
        self.theme.apply(self.settings.style)
        from linfilededuplication.core.glossary import Glossary
        self.glossary = Glossary.load(data_path("glossary", "en.json"))
        for name, cb in (("quit", lambda *_: self.quit()), ("about", self._about),
                         ("present", lambda *_: self._present()), ("scan", lambda *_: self._scan())):
            act = Gio.SimpleAction.new(name, None)
            act.connect("activate", cb)
            self.add_action(act)
        page = Gio.SimpleAction.new("page", GLib.VariantType.new("i"))
        page.connect("activate", lambda _a, v: self.window and self.window.show_page_index(v.get_int32()))
        self.add_action(page)
        self.set_accels_for_action("app.quit", ["<Control>q"])
        for i in range(9):
            self.set_accels_for_action(f"app.page({i})", [f"<Control>{i + 1}"])

        from linfilededuplication.services.tray import create_tray
        self.tray = create_tray(self)
        if self.tray is not None:
            self.hold()                         # keep running in the tray when the window closes
        log.info("startup complete: theme=%s, tray=%s, glossary=%d entries",
                 self.settings.style, "on" if self.tray else "unavailable", len(self.glossary.entries))

    def do_activate(self) -> None:
        if self.window is None:
            from linfilededuplication.ui.window import MainWindow
            self.window = MainWindow(self)
        self.window.present()
        log.info("window presented")

    def do_shutdown(self) -> None:
        log.info("shutting down cleanly")
        Adw.Application.do_shutdown(self)

    def do_open(self, files, n_files, _hint) -> None:  # noqa: N802 (GTK vfunc name)
        self.activate()
        if self.window is not None and files:
            self.window.request_scan(files[0].get_path())

    # --- helpers ---------------------------------------------------------
    def _register_icons(self) -> None:
        display = Gdk.Display.get_default()
        if display is not None:
            Gtk.IconTheme.get_for_display(display).add_search_path(data_path("icons"))
        Gtk.Window.set_default_icon_name(APP_ID)    # window / Alt-Tab icon

    def _present(self) -> None:
        if self.window is None:
            self.activate()
        else:
            self.window.set_visible(True)
            self.window.present()

    def _scan(self) -> None:
        self._present()
        if self.window is not None:
            self.window.show_page("scan")

    def _about(self, *_a: object) -> None:
        about = Adw.AboutDialog(
            application_name=APP_NAME, application_icon=APP_ID, version=__version__,
            developer_name="MensuraMedia",
            comments=_("Find and safely remove duplicate and near-duplicate files."),
            license_type=Gtk.License.CUSTOM,
            website="https://github.com/MensuraMedia/linfilededuplication",
        )
        about.present(self.window)


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = argparse.ArgumentParser(prog="linfilededuplication",
                                     description="LinFileDedup - find and remove duplicate files")
    parser.add_argument("paths", nargs="*", help="folder(s) to scan")
    parser.add_argument("--version", action="version", version=f"{APP_NAME} {__version__}")
    parser.add_argument("--debug", action="store_true", help="verbose logging")
    parser.add_argument("--smoke", action="store_true", help="build the window headless and exit")
    args = parser.parse_args(argv)
    logsetup.setup(args.debug)

    if args.smoke:
        os.environ["APP_NON_UNIQUE"] = "1"
        app = DedupeApp()
        # Build every page through the real lifecycle, then quit immediately.
        app.connect("activate", lambda a: GLib.idle_add(a.quit))
        return app.run([sys.argv[0]])

    app = DedupeApp()
    open_args = [sys.argv[0], *[p for p in args.paths]]
    return app.run(open_args if args.paths else [sys.argv[0]])
