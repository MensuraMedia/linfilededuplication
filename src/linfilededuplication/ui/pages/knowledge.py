"""Knowledge: a searchable local glossary and FAQ (no network)."""
from __future__ import annotations

from gi.repository import GLib, Gtk

from linfilededuplication.i18n import _
from linfilededuplication.ui.pages.base import BasePage
from linfilededuplication.ui.widgets.common import section_title


class KnowledgePage(BasePage):
    page_id = "knowledge"
    title = _("Knowledge")

    def build_content(self) -> None:
        self.glossary = self.app.glossary
        self._rows: dict = {}
        self._highlight_key: str | None = None

        self.add_heading(_("Knowledge"), _("Definitions and answers for the terms you meet."))
        self.search = Gtk.SearchEntry()
        self.search.set_placeholder_text(_("Search terms, file kinds, actions, FAQ…"))
        self.search.connect("search-changed", lambda _e: self._rebuild())
        self.add(self.search)

        self.results = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        self.add(self.results)
        self._rebuild()

    def _clear(self) -> None:
        child = self.results.get_first_child()
        while child is not None:
            nxt = child.get_next_sibling()
            self.results.remove(child)
            child = nxt
        self._rows.clear()

    def _rebuild(self) -> None:
        self._clear()
        query = self.search.get_text()
        entries = self.glossary.search(query)
        if not entries:
            self.results.append(Gtk.Label(label=_("No matches."), xalign=0.0))
            return
        by_cat: dict[str, list] = {}
        for e in entries:
            by_cat.setdefault(e.category, []).append(e)
        for cat in self.glossary.categories():
            if cat not in by_cat:
                continue
            self.results.append(section_title(cat.upper()))
            group = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
            group.add_css_class("app-group")
            for e in by_cat[cat]:
                group.append(self._entry_row(e))
            self.results.append(group)

    def _entry_row(self, e) -> Gtk.Widget:
        row = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
        row.add_css_class("app-file-row")
        if e.key == self._highlight_key:
            row.add_css_class("app-keep")
        term = Gtk.Label(label=e.term, xalign=0.0)
        term.add_css_class("app-group-title")
        body = Gtk.Label(label=e.body or e.short, xalign=0.0, wrap=True)
        body.add_css_class("app-dim")
        body.set_max_width_chars(80)
        row.append(term)
        row.append(body)
        self._rows[e.key] = row
        return row

    def focus(self, key: str) -> None:
        """Open the page at a specific entry (called from Learn more)."""
        self.search.set_text("")
        self._highlight_key = key
        self._rebuild()
        row = self._rows.get(key)
        if row is not None:
            GLib.idle_add(self._scroll_to, row)

    def _scroll_to(self, row) -> bool:
        adj = self.get_vadjustment()
        if adj is not None:
            adj.set_value(max(0, row.get_allocation().y - 12))
        return False
