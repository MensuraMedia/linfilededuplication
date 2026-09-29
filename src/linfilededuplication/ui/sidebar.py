"""Sidebar: nav rows (icon swap on selection, count badge, breathing activity dot) + footer."""
from __future__ import annotations

from gi.repository import GObject, Gtk

from linfilededuplication import APP_NAME
from linfilededuplication.config.layout import SIDEBAR_WIDTH
from linfilededuplication.i18n import _


def _icon(name: str, size: int = 18) -> Gtk.Image:
    img = Gtk.Image.new_from_icon_name(name)
    img.set_pixel_size(size)
    return img


class NavRow(Gtk.ListBoxRow):
    def __init__(self, spec, index: int) -> None:
        super().__init__()
        self.page_id = spec.id
        self._icon_base = spec.icon
        self.add_css_class("app-nav")
        box = Gtk.Box(spacing=12)
        box.set_margin_top(2)
        box.set_margin_bottom(2)
        self.image = _icon(f"{spec.icon}-symbolic")
        self.label = Gtk.Label(label=spec.label, xalign=0.0, hexpand=True)
        self.count = Gtk.Label(label="")
        self.count.add_css_class("app-count")
        self.count.set_visible(False)
        self.dot = Gtk.Box()
        self.dot.add_css_class("app-live-dot")
        self.dot.set_valign(Gtk.Align.CENTER)
        self.dot.set_visible(False)
        box.append(self.image)
        box.append(self.label)
        box.append(self.count)
        box.append(self.dot)
        self.set_child(box)
        self.set_tooltip_text(f"{spec.label} (Ctrl+{index})")
        self.update_property([Gtk.AccessibleProperty.LABEL], [spec.label])

    def set_selected_look(self, on: bool) -> None:
        self.image.set_from_icon_name(f"{self._icon_base}{'-active' if on else ''}-symbolic")
        self.image.set_pixel_size(18)


class Sidebar(Gtk.Box):
    __gsignals__ = {"page-changed": (GObject.SignalFlags.RUN_FIRST, None, (str,))}

    def __init__(self, specs) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.add_css_class("app-sidebar")
        self.set_size_request(SIDEBAR_WIDTH, -1)
        self.rows: dict[str, NavRow] = {}

        logo = Gtk.Box(spacing=10)
        logo.add_css_class("app-logo")
        mark = _icon("app-nav-results-symbolic", 20)
        mark.add_css_class("app-logo-mark")
        name = Gtk.Label(label=APP_NAME, xalign=0.0)
        name.add_css_class("app-logo-name")
        logo.append(mark)
        logo.append(name)
        self.append(logo)

        self.list = Gtk.ListBox(selection_mode=Gtk.SelectionMode.SINGLE)
        self.list.add_css_class("navigation-sidebar")
        for i, spec in enumerate(specs, start=1):
            if spec.bottom:
                continue
            row = NavRow(spec, i)
            self.rows[spec.id] = row
            self.list.append(row)
        self.list.connect("row-selected", self._on_selected)
        self.append(self.list)

        self.append(Gtk.Box(vexpand=True))          # spacer

        bottom = [s for s in specs if s.bottom]
        if bottom:
            blist = Gtk.ListBox(selection_mode=Gtk.SelectionMode.SINGLE)
            blist.add_css_class("navigation-sidebar")
            for i, spec in enumerate(bottom, start=len(self.rows) + 1):
                row = NavRow(spec, i)
                self.rows[spec.id] = row
                blist.append(row)
            blist.connect("row-selected", self._on_selected)
            self.append(blist)
            self._blist = blist

        self.footer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        self.footer.add_css_class("app-footer")
        heading = Gtk.Label(label=_("STATUS"), xalign=0.0)
        heading.add_css_class("app-sidebar-heading")
        self.status = Gtk.Label(label=_("Idle"), xalign=0.0)
        self.status.add_css_class("app-dim")
        self.footer.append(heading)
        self.footer.append(self.status)
        self.append(self.footer)

    def select(self, page_id: str) -> None:
        row = self.rows.get(page_id)
        if row is not None and row.get_parent() is not None:
            lb = row.get_parent()
            if lb.get_selected_row() is not row:
                lb.select_row(row)

    def set_count(self, page_id: str, n: int) -> None:
        row = self.rows.get(page_id)
        if row is not None:
            row.count.set_text(str(n))
            row.count.set_visible(n > 0)

    def set_running(self, page_id: str, running: bool) -> None:
        for pid, row in self.rows.items():
            active = running and pid == page_id
            row.dot.set_visible(active)
            if active:
                row.dot.add_css_class("running")
            else:
                row.dot.remove_css_class("running")
        self.status.set_text(_("Scanning…") if running else _("Idle"))

    def _on_selected(self, listbox: Gtk.ListBox, row: NavRow | None) -> None:
        if row is None:
            return
        for other in self.rows.values():           # single visual selection across both lists
            other.set_selected_look(other is row)
        # clear the other list's selection so only one row looks active
        for lb in {r.get_parent() for r in self.rows.values()}:
            if lb is not None and lb is not listbox:
                lb.unselect_all()
        self.emit("page-changed", row.page_id)
