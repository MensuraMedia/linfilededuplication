"""History: the last deduplicate operation (with before/after bars and the space saved) and the
operations before it. Reads the JSON history store written when a removal is confirmed."""
from __future__ import annotations

import os
import time

from gi.repository import Adw, Gtk

from linfilededuplication.config.history import HistoryStore
from linfilededuplication.core.units import human_bytes
from linfilededuplication.i18n import _
from linfilededuplication.ui.pages.base import BasePage
from linfilededuplication.ui.widgets.space_chart import SpaceChart

_ACTION = {"trash": _("Move to Trash"), "hardlink": _("Hard-link")}


def _when(ts: float) -> str:
    try:
        return time.strftime("%d %b %Y, %I:%M %p", time.localtime(ts)).lstrip("0")
    except Exception:
        return ""


def _sources(srcs: list[str]) -> str:
    return " · ".join(srcs) if srcs else _("(unknown)")


class HistoryPage(BasePage):
    page_id = "history"
    title = _("History")

    def build_content(self) -> None:
        self.add_heading(_("History"), _("Your most recent cleanup, and the ones before it."))
        self._body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        self.add(self._body)

    def on_shown(self) -> None:
        self._refresh()

    def _clear(self) -> None:
        child = self._body.get_first_child()
        while child is not None:
            nxt = child.get_next_sibling()
            self._body.remove(child)
            child = nxt

    def _refresh(self) -> None:
        self._clear()
        entries = HistoryStore().load()
        if not entries:
            status = Adw.StatusPage(
                title=_("No history yet"),
                description=_("After you Move to Trash, Delete All Duplicates, or Hard-link a "
                             "scan's results, that operation will be recorded here."),
                icon_name="app-nav-history-symbolic")
            status.set_vexpand(True)
            self._body.append(status)
            return
        self._body.append(self._latest_card(entries[0]))
        if len(entries) > 1:
            self._body.append(self._earlier_list(entries[1:]))

    # --- the last operation, prominently ---------------------------------
    def _latest_card(self, e) -> Gtk.Widget:
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        card.add_css_class("app-card")
        card.add_css_class("app-savings")

        head = Gtk.Box(spacing=10)
        chip = Gtk.Label(label=(_("✓ Success") if e.ok else _("✕ Failed")))
        chip.add_css_class("app-small")
        chip.add_css_class("app-chip-ok" if e.ok else "app-chip-fail")
        when = Gtk.Label(xalign=0.0, hexpand=True, label=_("{w} · {a} · {n} files · {g} groups").format(
            w=_when(e.when), a=_ACTION.get(e.action, e.action), n=e.files_removed, g=e.groups))
        when.add_css_class("app-dim")
        when.add_css_class("app-small")
        head.append(chip)
        head.append(when)
        card.append(head)

        headline = Gtk.Label(xalign=0.0, use_markup=True)
        headline.add_css_class("app-savings-head")
        verb = _("You saved") if e.ok else _("Attempted to free")
        headline.set_markup("{v} <span foreground=\"#2ec27e\">{b}</span>".format(
            v=verb, b=human_bytes(e.freed_bytes)))
        card.append(headline)

        srcs = Gtk.Label(xalign=0.0, wrap=True, label=_sources(e.sources))
        srcs.add_css_class("app-dim")
        srcs.add_css_class("app-small")
        srcs.add_css_class("app-mono")
        card.append(srcs)

        if e.exclusions:
            exc = Gtk.Label(xalign=0.0, wrap=True, label=_("Exclusion: {x}").format(
                x=", ".join(e.exclusions)))
            exc.add_css_class("app-dim")
            exc.add_css_class("app-small")
            exc.add_css_class("app-mono")
            card.append(exc)

        if e.before_bytes > 0:
            chart = SpaceChart()
            chart.set_values(e.before_bytes, e.freed_bytes)   # Now = before, After = after cleanup
            card.append(chart)
        if not e.ok and e.error:
            err = Gtk.Label(xalign=0.0, wrap=True, label=e.error)
            err.add_css_class("app-small")
            err.add_css_class("app-del-text")
            card.append(err)
        return card

    # --- earlier operations ---------------------------------------------
    def _earlier_list(self, entries) -> Gtk.Widget:
        wrap = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        title = Gtk.Label(label=_("Earlier operations"), xalign=0.0)
        title.add_css_class("app-group-title")
        wrap.append(title)
        lst = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        lst.add_css_class("app-card")
        for e in entries:
            lst.append(self._earlier_row(e))
        wrap.append(lst)
        return wrap

    def _earlier_row(self, e) -> Gtk.Widget:
        row = Gtk.Box(spacing=12)
        row.add_css_class("app-file-row")
        when = Gtk.Label(label=_when(e.when), xalign=0.0)
        when.add_css_class("app-small")
        when.set_width_chars(22)
        src = Gtk.Label(label=_sources([os.path.basename(s) or s for s in e.sources]),
                        xalign=0.0, hexpand=True)
        src.add_css_class("app-mono")
        src.add_css_class("app-small")
        src.add_css_class("app-dim")
        src.set_ellipsize(3)
        saved = Gtk.Label(label=human_bytes(e.freed_bytes), xalign=1.0)
        saved.add_css_class("app-small")
        saved.add_css_class("app-keep-text" if e.ok else "app-del-text")
        mark = Gtk.Label(label=("✓" if e.ok else "✕"))
        mark.add_css_class("app-small")
        mark.add_css_class("app-chip-ok" if e.ok else "app-chip-fail")
        row.append(when)
        row.append(src)
        row.append(saved)
        row.append(mark)
        return row
