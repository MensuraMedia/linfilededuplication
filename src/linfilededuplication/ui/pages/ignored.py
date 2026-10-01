"""Ignored: everything the user chose to skip — ignored files and folders — with a way to
resume scanning each one. Reads/writes the ignore lists in Settings; the scanner's walk() skips
these in every scan."""
from __future__ import annotations

from gi.repository import Gtk

from linfilededuplication.i18n import _
from linfilededuplication.ui.pages.base import BasePage
from linfilededuplication.ui.widgets.common import icon
from linfilededuplication.ui.widgets.info_hint import InfoHint


class IgnoredPage(BasePage):
    page_id = "ignored"
    title = _("Ignored")

    def build_content(self) -> None:
        self.add_heading(_("Ignored"))

        # explainer card (top of the page)
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        card.add_css_class("app-card")
        card.add_css_class("app-savings")
        head = Gtk.Box(spacing=8)
        t = Gtk.Label(label=_("What this page shows"), xalign=0.0)
        t.add_css_class("app-group-title")
        head.append(t)
        head.append(InfoHint(self.window, "ignored-resume"))
        card.append(head)
        body = Gtk.Label(xalign=0.0, wrap=True, label=_(
            "A record of every file and folder you chose to Ignore. Ignored items are skipped in "
            "all scans so you don't have to review them again. Resume any item to include it in "
            "future scans — resumed files and locations are removed from this list."))
        body.add_css_class("app-dim")
        card.append(body)
        self.add(card)

        self._folders_wrap, self._folders_list = self._section(_("Ignored folders"))
        self._files_wrap, self._files_list = self._section(_("Ignored files"))

        self.empty_lbl = Gtk.Label(xalign=0.0, wrap=True, label=_(
            "Nothing is ignored yet. Use “Ignore Files” on a Results group, or “Ignore Folder” "
            "on the Scan page."))
        self.empty_lbl.add_css_class("app-dim")
        self.add(self.empty_lbl)

    def _section(self, title: str):
        wrap = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        h = Gtk.Label(label=title, xalign=0.0)
        h.add_css_class("app-group-title")
        lst = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        lst.add_css_class("app-card")
        wrap.append(h)
        wrap.append(lst)
        self.add(wrap)
        return wrap, lst

    def on_shown(self) -> None:
        self._refresh()

    def _refresh(self) -> None:
        s = self.app.settings
        folders = sorted(getattr(s, "ignored_folders", []))
        files = sorted(getattr(s, "ignored_paths", []))
        self._fill(self._folders_list, folders, is_dir=True)
        self._fill(self._files_list, files, is_dir=False)
        self._folders_wrap.set_visible(bool(folders))
        self._files_wrap.set_visible(bool(files))
        self.empty_lbl.set_visible(not folders and not files)

    def _fill(self, box: Gtk.Box, items: list[str], is_dir: bool) -> None:
        child = box.get_first_child()
        while child is not None:
            nxt = child.get_next_sibling()
            box.remove(child)
            child = nxt
        for p in items:
            box.append(self._row(p, is_dir))

    def _row(self, path: str, is_dir: bool) -> Gtk.Widget:
        row = Gtk.Box(spacing=12)
        row.add_css_class("app-file-row")
        ic = icon("app-nav-ignored-symbolic", 18)
        ic.add_css_class("app-dim")
        name = Gtk.Label(label=path, xalign=0.0, hexpand=True)
        name.add_css_class("app-mono")
        name.add_css_class("app-small")
        name.set_ellipsize(2)                        # middle: keep the root and the tail
        name.set_tooltip_text(path)
        btn = Gtk.Button(label=_("Resume scanning"))
        btn.set_valign(Gtk.Align.CENTER)
        btn.connect("clicked", lambda _b, p=path, d=is_dir: self._resume(p, d))
        row.append(ic)
        row.append(name)
        row.append(btn)
        return row

    def _resume(self, path: str, is_dir: bool) -> None:
        s = self.app.settings
        key = "ignored_folders" if is_dir else "ignored_paths"
        cur = list(getattr(s, key, []))
        if path in cur:
            cur.remove(path)
            setattr(s, key, cur)
            s.save()
        self.window.toast(_("Resumed — {p} will be scanned again").format(p=path))
        self._refresh()
