"""Overview: a summary of the last scan and a starting point for a new one."""
from __future__ import annotations

from gi.repository import Gtk

from linfilededuplication.core.units import human_bytes, human_count
from linfilededuplication.i18n import _
from linfilededuplication.ui.pages.base import BasePage
from linfilededuplication.ui.widgets.common import icon, kpi_tile, section_title


class OverviewPage(BasePage):
    page_id = "overview"
    title = _("Overview")

    def build_content(self) -> None:
        head = Gtk.Box(spacing=14)
        titles = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2, hexpand=True)
        h = Gtk.Label(label=_("Overview"), xalign=0.0)
        h.add_css_class("app-page-title")
        sub = Gtk.Label(label=_("Find and safely remove duplicate and near-duplicate files."), xalign=0.0)
        sub.add_css_class("app-dim")
        titles.append(h)
        titles.append(sub)
        new_btn = Gtk.Button()
        new_btn.add_css_class("suggested-action")
        nb = Gtk.Box(spacing=8)
        nb.append(icon("app-nav-scan-symbolic"))
        nb.append(Gtk.Label(label=_("New scan")))
        new_btn.set_child(nb)
        new_btn.set_valign(Gtk.Align.CENTER)
        new_btn.connect("clicked", lambda _b: self.window.show_page("scan"))
        head.append(titles)
        head.append(new_btn)
        self.add(head)

        grid = Gtk.Grid(column_spacing=14, row_spacing=14, column_homogeneous=True)
        t1, self.k_groups = kpi_tile("app-nav-results-symbolic", "0", _("Duplicate groups"))
        t2, self.k_space = kpi_tile("app-stat-space-symbolic", "0 B", _("Reclaimable"))
        t3, self.k_files = kpi_tile("app-stat-items-symbolic", "0", _("Files scanned"))
        t4, self.k_last = kpi_tile("app-nav-history-symbolic", "—", _("Last scan"))
        for i, t in enumerate((t1, t2, t3, t4)):
            grid.attach(t, i, 0, 1, 1)
        self.add(grid)

        self.add(section_title(_("Getting started")))
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        card.add_css_class("app-card")
        line1 = Gtk.Label(xalign=0.0, wrap=True,
                          label=_("Open Scan, choose a folder, and run a Simple Scan to find exact "
                                  "duplicates and image near-duplicates."))
        line2 = Gtk.Label(xalign=0.0, wrap=True)
        line2.add_css_class("app-dim")
        line2.set_label(_("Nothing is changed until you review the results and confirm. "
                          "Removals move to Trash by default."))
        card.append(line1)
        card.append(line2)
        self.add(card)

        self.window.controller.connect("scan-finished", self._on_finished)

    def _on_finished(self, _c, fin) -> None:
        if fin.cancelled:
            return
        self.k_groups.set_text(human_count(fin.groups))
        self.k_space.set_text(human_bytes(fin.reclaimable))
        self.k_files.set_text(human_count(fin.files_scanned))
        self.k_last.set_text(_("just now"))
