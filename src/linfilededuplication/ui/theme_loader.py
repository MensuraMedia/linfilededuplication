"""Loads the app stylesheet, drives light/dark, and injects the house colour palette.

The palette matches the approved mockup exactly (content darker than the sidebar, a lighter
top bar) by overriding libadwaita's named colours per effective theme, and re-injects when the
system theme changes.
"""
from __future__ import annotations

from gi.repository import Adw, Gdk, Gtk

_SCHEMES = {
    "system": Adw.ColorScheme.DEFAULT,
    "light": Adw.ColorScheme.FORCE_LIGHT,
    "dark": Adw.ColorScheme.FORCE_DARK,
}

# Exact mockup palette, overriding libadwaita named colours.
_DARK = {
    "window_bg_color": "#1c1f24",
    "view_bg_color": "#1c1f24",
    "sidebar_bg_color": "#262a30",
    "headerbar_bg_color": "#2a2e35",
    "card_bg_color": "#1e2126",
    "popover_bg_color": "#2a2e35",
    "dialog_bg_color": "#1c1f24",
    "window_fg_color": "#eef0f2",
    "view_fg_color": "#eef0f2",
    "accent_bg_color": "#3584e4",
    "accent_fg_color": "#ffffff",
    "accent_color": "#78aeea",
}
_LIGHT = {
    "window_bg_color": "#fafafb",
    "view_bg_color": "#fafafb",
    "sidebar_bg_color": "#f2f2f2",
    "headerbar_bg_color": "#ebebeb",
    "card_bg_color": "#ffffff",
    "popover_bg_color": "#ffffff",
    "dialog_bg_color": "#fafafb",
    "window_fg_color": "#22262a",
    "view_fg_color": "#22262a",
    "accent_bg_color": "#3584e4",
    "accent_fg_color": "#ffffff",
    "accent_color": "#1c5fb4",
}


class ThemeLoader:
    def __init__(self, css_path: str) -> None:
        self._style = "system"
        self._app = Gtk.CssProvider()
        try:
            self._app.load_from_path(css_path)
        except Exception:
            pass
        self._tokens = Gtk.CssProvider()
        display = Gdk.Display.get_default()
        if display is not None:
            Gtk.StyleContext.add_provider_for_display(
                display, self._app, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
            # token overrides sit above app.css so @define-color wins over the theme
            Gtk.StyleContext.add_provider_for_display(
                display, self._tokens, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION + 1)
        self._sm = Adw.StyleManager.get_default()
        self._sm.connect("notify::dark", lambda *_: self._reload_tokens())

    def apply(self, style: str) -> None:
        self._style = style
        self._sm.set_color_scheme(_SCHEMES.get(style, Adw.ColorScheme.DEFAULT))
        self._reload_tokens()

    def _effective_dark(self) -> bool:
        if self._style == "dark":
            return True
        if self._style == "light":
            return False
        return self._sm.get_dark()

    def _reload_tokens(self) -> None:
        palette = _DARK if self._effective_dark() else _LIGHT
        css = "".join(f"@define-color {name} {value};\n" for name, value in palette.items())
        try:
            self._tokens.load_from_data(css.encode())
        except Exception:
            pass
