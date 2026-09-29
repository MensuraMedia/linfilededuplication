"""Loads the app stylesheet and drives light/dark through libadwaita."""
from __future__ import annotations

from gi.repository import Adw, Gdk, Gtk

_SCHEMES = {
    "system": Adw.ColorScheme.DEFAULT,
    "light": Adw.ColorScheme.FORCE_LIGHT,
    "dark": Adw.ColorScheme.FORCE_DARK,
}


class ThemeLoader:
    def __init__(self, css_path: str) -> None:
        self._provider = Gtk.CssProvider()
        try:
            self._provider.load_from_path(css_path)
        except Exception:
            pass
        display = Gdk.Display.get_default()
        if display is not None:
            Gtk.StyleContext.add_provider_for_display(
                display, self._provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

    def apply(self, style: str) -> None:
        Adw.StyleManager.get_default().set_color_scheme(_SCHEMES.get(style, Adw.ColorScheme.DEFAULT))
