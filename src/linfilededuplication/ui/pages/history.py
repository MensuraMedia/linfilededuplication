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
        runs = self._load_runs()
        if not entries and not runs:
            status = Adw.StatusPage(
                title=_("No history yet"),
                description=_("Run a scan to see its performance here; after you Move to Trash, "
                             "Delete All Duplicates, or Hard-link results, that cleanup is "
                             "recorded too."),
                icon_name="app-nav-history-symbolic")
            status.set_vexpand(True)
            self._body.append(status)
            return
        if entries:
            self._body.append(self._latest_card(entries[0]))
            if len(entries) > 1:
                self._body.append(self._earlier_list(entries[1:]))
        if runs:
            self._body.append(self._scan_runs_section(runs))

    @staticmethod
    def _load_runs():
        try:
            from linfilededuplication.core.scanstats import ScanStatsStore
            return ScanStatsStore().load()
        except Exception:
            return []

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

    # --- scan performance log -------------------------------------------
    def _scan_runs_section(self, runs) -> Gtk.Widget:
        wrap = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        title = Gtk.Label(label=_("Recent scans"), xalign=0.0)
        title.add_css_class("app-group-title")
        sub = Gtk.Label(xalign=0.0, wrap=True, label=_(
            "Every scan's performance — when it ran, how long it took, files scanned, how many "
            "fingerprints were reused from the cache, and the drive each source lives on."))
        sub.add_css_class("app-dim")
        sub.add_css_class("app-small")
        wrap.append(title)
        wrap.append(sub)
        lst = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        lst.add_css_class("app-card")
        for run in runs[:12]:
            lst.append(self._run_row(run))
        wrap.append(lst)
        return wrap

    def _run_row(self, run) -> Gtk.Widget:
        from linfilededuplication.core import driveinfo
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
        box.add_css_class("app-file-row")

        head = Gtk.Box(spacing=10)
        tier = _("Advanced") if run.tier == "advanced" else _("Simple")
        state = _("Stopped") if run.cancelled else tier
        chip = Gtk.Label(label=state)
        chip.add_css_class("app-small")
        chip.add_css_class("app-chip-fail" if run.cancelled else "app-chip-ok")
        chip.set_valign(Gtk.Align.CENTER)
        when = Gtk.Label(label=_when(run.when), xalign=0.0)
        when.add_css_class("app-small")
        head.append(chip)
        head.append(when)
        box.append(head)

        # headline metrics: files · duration · throughput · groups · reuse
        parts = [_("{n:,} files").format(n=run.total_files),
                 self._fmt_duration(run.duration)]
        if run.throughput:
            parts.append(_("{n:,.0f}/s").format(n=run.throughput))
        parts.append(_("{g} groups").format(g=run.groups))
        if run.used_cache and (run.total_reused or run.total_hashed):
            tot = run.total_reused + run.total_hashed
            pct = round(100 * run.total_reused / tot) if tot else 0
            parts.append(_("{pct}% reused").format(pct=pct))
        metrics = Gtk.Label(label=" · ".join(parts), xalign=0.0)
        metrics.add_css_class("app-small")
        box.append(metrics)

        for s in run.sources:
            label = driveinfo.describe(driveinfo.DriveInfo.from_dict(s.drive)) if s.drive else ""
            size = human_bytes(s.drive.get("size_bytes") or s.drive.get("total_bytes") or 0) \
                if s.drive else ""
            bits = [os.path.basename(s.path.rstrip("/")) or s.path,
                    _("{n:,} files").format(n=s.files_scanned)]
            if label:
                bits.append(label)
            if size:
                bits.append(size)
            sl = Gtk.Label(label=" · ".join(bits), xalign=0.0)
            sl.add_css_class("app-small")
            sl.add_css_class("app-dim")
            sl.add_css_class("app-mono")
            sl.set_ellipsize(3)
            sl.set_tooltip_text(s.path)
            box.append(sl)
        return box

    @staticmethod
    def _fmt_duration(sec: float) -> str:
        if sec < 1:
            return _("<1s")
        if sec < 60:
            return _("{s:.1f}s").format(s=sec)
        m, s = divmod(int(sec), 60)
        return _("{m}m {s}s").format(m=m, s=s)
