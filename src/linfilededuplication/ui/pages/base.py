"""BasePage: a scrolled vertical content box. Subclasses implement build_content()."""
from __future__ import annotations

from gi.repository import Gtk


class BasePage(Gtk.ScrolledWindow):
    page_id = ""
    title = ""

    def __init__(self, window) -> None:
        super().__init__(hexpand=True, vexpand=True)
        self.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        self.window = window
        self.app = window.app
        self.box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        self.box.add_css_class("page")
        self.box.add_css_class("page-padded")
        clamp_child = self._wrap(self.box)
        self.set_child(clamp_child)
        self.build_content()

    def _wrap(self, child):
        """Keep content to a comfortable width on wide windows (Adw.Clamp)."""
        try:
            from gi.repository import Adw
            clamp = Adw.Clamp(maximum_size=1100, tightening_threshold=800)
            clamp.set_child(child)
            return clamp
        except Exception:
            return child

    def add(self, widget) -> None:
        self.box.append(widget)

    def build_content(self) -> None:
        raise NotImplementedError

    def on_shown(self) -> None:
        pass

    def on_hidden(self) -> None:
        pass

    def add_heading(self, text: str, subtitle: str = "") -> None:
        h = Gtk.Label(label=text, xalign=0.0)
        h.add_css_class("app-page-title")
        self.add(h)
        if subtitle:
            s = Gtk.Label(label=subtitle, xalign=0.0, wrap=True)
            s.add_css_class("app-dim")
            self.add(s)
