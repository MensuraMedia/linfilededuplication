"""Small widget builders shared across pages."""
from __future__ import annotations

from gi.repository import Gtk


def icon(name: str, size: int = 16) -> Gtk.Image:
    img = Gtk.Image.new_from_icon_name(name)
    img.set_pixel_size(size)
    return img


def kpi_tile(icon_name: str, value: str, caption: str) -> tuple[Gtk.Box, Gtk.Label]:
    """A summary tile: icon + label on top, big number, caption. Returns (tile, value_label)."""
    tile = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6, hexpand=True)
    tile.add_css_class("app-tile")
    top = Gtk.Box(spacing=8)
    img = icon(icon_name, 15)
    img.add_css_class("app-accent")
    lbl = Gtk.Label(label=caption, xalign=0.0)
    lbl.add_css_class("app-dim")
    lbl.add_css_class("app-small")
    top.append(img)
    top.append(lbl)
    num = Gtk.Label(label=value, xalign=0.0)
    num.add_css_class("app-stat-num")
    tile.append(top)
    tile.append(num)
    return tile, num


def badge(text: str, css: str) -> Gtk.Label:
    lbl = Gtk.Label(label=text)
    lbl.add_css_class(css)
    lbl.set_valign(Gtk.Align.CENTER)
    return lbl


def section_title(text: str) -> Gtk.Label:
    lbl = Gtk.Label(label=text, xalign=0.0)
    lbl.add_css_class("app-section-title")
    return lbl
