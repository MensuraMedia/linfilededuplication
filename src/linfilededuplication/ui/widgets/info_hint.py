"""InfoHint: a small (i) icon whose popover explains a term, sourced from the glossary.

Keyboard-focusable and screen-reader-labelled (a MenuButton, never hover-only). When the term
has a fuller entry, a Learn more link opens the Knowledge page at it.
"""
from __future__ import annotations

from gi.repository import Gtk

from linfilededuplication.i18n import _


class InfoHint(Gtk.MenuButton):
    def __init__(self, window, term_key: str) -> None:
        super().__init__()
        self.window = window
        self.term_key = term_key
        self.set_icon_name("app-misc-info-symbolic")
        self.add_css_class("flat")
        self.add_css_class("app-info-hint")
        self.set_valign(Gtk.Align.CENTER)

        entry = window.app.glossary.get(term_key)
        term = entry.term if entry else term_key
        short = entry.short if entry else ""
        self.set_tooltip_text(short or term)
        self.update_property([Gtk.AccessibleProperty.LABEL], [_("About {t}").format(t=term)])

        pop = Gtk.Popover()
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.set_margin_top(12)
        box.set_margin_bottom(12)
        box.set_margin_start(12)
        box.set_margin_end(12)
        box.set_size_request(280, -1)
        title = Gtk.Label(label=term, xalign=0.0)
        title.add_css_class("heading")
        body = Gtk.Label(label=short, xalign=0.0, wrap=True)
        body.set_max_width_chars(38)
        box.append(title)
        box.append(body)
        if entry and entry.body:
            more = Gtk.Button(label=_("Learn more"))
            more.add_css_class("flat")
            more.set_halign(Gtk.Align.START)
            more.connect("clicked", self._learn_more)
            box.append(more)
        pop.set_child(box)
        self.set_popover(pop)

    def _learn_more(self, _btn) -> None:
        self.get_popover().popdown()
        self.window.open_knowledge(self.term_key)
