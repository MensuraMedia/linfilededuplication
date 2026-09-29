"""History: past scans and actions. Persistence lands in a later phase; this shows the shape."""
from __future__ import annotations

from gi.repository import Adw, Gtk

from linfilededuplication.i18n import _
from linfilededuplication.ui.pages.base import BasePage


class HistoryPage(BasePage):
    page_id = "history"
    title = _("History")

    def build_content(self) -> None:
        self.add_heading(_("History"), _("A record of past scans and the space they reclaimed."))
        status = Adw.StatusPage(
            title=_("No history yet"),
            description=_("Runs and actions will be listed here once you complete a scan."),
            icon_name="app-nav-history-symbolic",
        )
        status.set_vexpand(True)
        self.add(status)
