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
        shown = runs[:12]
        for i, run in enumerate(shown):
            prev = self._previous_same_sources(run, runs[i + 1:])
            lst.append(self._run_row(run, prev))
        wrap.append(lst)
        return wrap

    @staticmethod
    def _sig(run) -> frozenset:
        return frozenset(s.path.rstrip("/") for s in run.sources)

    def _previous_same_sources(self, run, older):
        """The most recent earlier run over the SAME set of sources (for a like-for-like compare)."""
        sig = self._sig(run)
        for r in older:
            if not r.cancelled and r.tier == run.tier and self._sig(r) == sig:
                return r                            # same sources AND same tier = caching compare
        return None

    def _run_row(self, run, prev=None) -> Gtk.Widget:
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
        when = Gtk.Label(label=_when(run.when), xalign=0.0, hexpand=True)
        when.add_css_class("app-small")
        # duration, emphasised, on the right of the header — the headline comparison metric
        dur = Gtk.Label(label=self._fmt_duration(run.duration), xalign=1.0)
        dur.add_css_class("app-group-title")
        dur.add_css_class("app-keep-text")
        dur.set_tooltip_text(_("Scan duration"))
        head.append(chip)
        head.append(when)
        head.append(dur)
        box.append(head)

        cmp = self._compare_text(run, prev)
        if cmp is not None:
            text, css = cmp
            cl = Gtk.Label(label=text, xalign=0.0, wrap=True)
            cl.add_css_class("app-small")
            cl.add_css_class(css)
            box.append(cl)

        # scope & size: file-type filter · files · data scanned · reclaimable · groups
        sp = [self._filter_label(run.file_types), _("{n:,} files").format(n=run.total_files)]
        if run.bytes_scanned:
            sp.append(_("{b} scanned").format(b=human_bytes(run.bytes_scanned)))
        if run.reclaimable_bytes:
            sp.append(_("{b} reclaimable").format(b=human_bytes(run.reclaimable_bytes)))
        sp.append(_("{g} groups").format(g=run.groups))
        scope = Gtk.Label(label=" · ".join(sp), xalign=0.0, wrap=True)
        scope.add_css_class("app-small")
        if run.file_types:
            scope.set_tooltip_text(_("File types: {x}").format(x=", ".join(run.file_types)))
        box.append(scope)

        # one line per source — the drive, folder and mountpoint, kept terse (full detail in tooltip)
        for s in run.sources:
            d = driveinfo.DriveInfo.from_dict(s.drive) if s.drive else None
            tags = [t for t in ((d.kind if d else ""), (d.transport.upper() if d and d.transport else ""),
                                (d.fstype if d else "")) if t]
            dsize = human_bytes(d.size_bytes or d.total_bytes) if d and (d.size_bytes or d.total_bytes) else ""
            right = _("{n:,} files").format(n=s.files_scanned)
            if tags:
                right += " · " + "·".join(tags)
            if dsize:
                right += " · " + dsize
            srow = Gtk.Box(spacing=10)
            pl = Gtk.Label(label=s.path, xalign=0.0, hexpand=True)   # full path = mountpoint + folder
            pl.add_css_class("app-small"); pl.add_css_class("app-dim"); pl.add_css_class("app-mono")
            pl.set_ellipsize(2)                                      # middle: keep root and tail
            pl.set_tooltip_text((d.model + "\n" if d and d.model else "") + s.path)
            mr = Gtk.Label(label=right, xalign=1.0)
            mr.add_css_class("app-small"); mr.add_css_class("app-dim")
            srow.append(pl); srow.append(mr)
            box.append(srow)
        return box

    @staticmethod
    def _filter_label(file_types) -> str:
        """'All Files' when no include filter, else a compact list of the chosen extensions."""
        fts = list(file_types or [])
        if not fts:
            return _("All Files")
        if len(fts) <= 5:
            return ", ".join(fts)
        return _("{head} +{n} more").format(head=", ".join(fts[:4]), n=len(fts) - 4)

    def _compare_text(self, run, prev):
        """Like-for-like duration comparison against the previous scan of the same sources — the
        line that makes the index/cache speed-up visible. Returns (text, css-class) or None."""
        if prev is None or run.cancelled or run.duration <= 0 or prev.duration <= 0:
            return None
        cur, old = run.duration, prev.duration
        reused = ""
        tot = run.total_reused + run.total_hashed
        if run.used_cache and tot:
            reused = _(" · {pct}% of files reused from the index").format(
                pct=round(100 * run.total_reused / tot))
        span = _("{old} → {new}").format(old=self._fmt_duration(old), new=self._fmt_duration(cur))
        if cur <= old / 1.15:                       # meaningfully faster
            return (_("⚡ {f:.1f}× faster than the previous scan of these sources  ({span}){r}")
                    .format(f=old / cur, span=span, r=reused), "app-keep-text")
        if cur >= old * 1.15:                        # meaningfully slower
            return (_("{f:.1f}× slower than the previous scan  ({span})")
                    .format(f=cur / old, span=span), "app-del-text")
        return (_("about the same as the previous scan  ({span}){r}").format(span=span, r=reused),
                "app-dim")

    @staticmethod
    def _fmt_duration(sec: float) -> str:
        if sec < 1:
            return _("<1s")
        if sec < 60:
            return _("{s:.1f}s").format(s=sec)
        m, s = divmod(int(sec), 60)
        return _("{m}m {s}s").format(m=m, s=s)
