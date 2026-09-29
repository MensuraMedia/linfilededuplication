"""Optional panel / system-tray icon via XApp.StatusIcon (Mint/Cinnamon and others).

A detected capability: when XApp is unavailable the app simply runs without a tray. Left-click
opens the window; the menu offers Open, New scan, and Quit.
"""
from __future__ import annotations

from linfilededuplication import APP_ID, APP_NAME
from linfilededuplication.i18n import _


def create_tray(app):
    """Return a live tray object, or None when no tray backend is available."""
    try:
        import gi
        gi.require_version("XApp", "1.0")
        from gi.repository import Gio, Gtk, XApp
    except Exception:
        return None
    try:
        icon = XApp.StatusIcon()
        icon.set_name(APP_ID)
        icon.set_icon_name(APP_ID)
        icon.set_tooltip_text(APP_NAME)

        menu = Gio.Menu()
        menu.append(_("Open LinFileDedup"), "app.present")
        menu.append(_("New scan"), "app.scan")
        menu.append(_("Quit"), "app.quit")
        popover = Gtk.PopoverMenu.new_from_model(menu)
        icon.set_secondary_menu(popover)

        icon.connect("activate", lambda _i, _b, _t: app.activate_action("present", None))
        return icon
    except Exception:
        return None
