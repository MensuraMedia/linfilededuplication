"""SpotCheck: a large side-by-side confirmation view for one duplicate group.

Shows each file at a readable size (image previews or document snippets) so the user can
confirm the copies before acting. A gate, not an actor: closing it changes nothing.
"""
from __future__ import annotations

from gi.repository import Adw, Gtk

from linfilededuplication.core import preview as previewmod
from linfilededuplication.core.model import KIND_IMAGE, DuplicateGroup, FileEntry
from linfilededuplication.core.units import human_bytes
from linfilededuplication.i18n import _
from linfilededuplication.services import actions
from linfilededuplication.ui.widgets.common import badge, icon
from linfilededuplication.ui.widgets.info_hint import InfoHint


class SpotCheckDialog(Adw.Dialog):
    def __init__(self, window, group: DuplicateGroup, on_applied) -> None:
        super().__init__()
        self.window = window
        self.group = group
        self.on_applied = on_applied
        self._checks: list[tuple[Gtk.CheckButton, FileEntry]] = []
        self.set_title(_("SpotCheck"))
        self.set_content_width(920)
        self.set_content_height(640)

        toolbar = Adw.ToolbarView()
        header = Adw.HeaderBar()
        header.set_title_widget(Adw.WindowTitle(title=_("SpotCheck"), subtitle=group.title))
        toolbar.add_top_bar(header)

        count = len(group.files)
        panels = Gtk.Box(spacing=14, hexpand=True, vexpand=True, homogeneous=count <= 4)
        panels.set_margin_top(16)
        panels.set_margin_bottom(16)
        panels.set_margin_start(16)
        panels.set_margin_end(16)
        for f in group.files:
            panels.append(self._panel(f, count))
        if count <= 4:                          # few files: fill the modal width
            toolbar.set_content(panels)
        else:                                   # many files: scroll horizontally
            scroller = Gtk.ScrolledWindow(hexpand=True, vexpand=True)
            scroller.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.NEVER)
            scroller.set_child(panels)
            toolbar.set_content(scroller)

        bottom = Gtk.Box(spacing=12)
        bottom.add_css_class("toolbar")
        bottom.set_margin_top(8)
        bottom.set_margin_bottom(8)
        bottom.set_margin_start(12)
        bottom.set_margin_end(12)
        self.decision = Gtk.Label(xalign=0.0, hexpand=True)
        self.decision.add_css_class("app-small")
        btn_link = Gtk.Button(label=_("Hard-link"))
        btn_trash = Gtk.Button(label=_("Move to Trash"))
        btn_trash.add_css_class("destructive-action")
        btn_link.connect("clicked", self._link)
        btn_trash.connect("clicked", self._trash)
        bottom.append(self.decision)
        bottom.append(btn_link)
        bottom.append(btn_trash)
        toolbar.add_bottom_bar(bottom)

        self.set_child(toolbar)
        self._refresh()

    def _panel(self, f: FileEntry, count: int) -> Gtk.Widget:
        panel = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8, hexpand=True, vexpand=True)
        panel.add_css_class("app-card")
        if count > 4:
            panel.set_size_request(300, -1)     # min width when the row scrolls
        if f.keeper:
            panel.add_css_class("app-keep")

        panel.append(self._preview_widget(f))

        name = Gtk.Label(label=f.name, xalign=0.0, wrap=True)
        name.add_css_class("app-group-title")
        panel.append(name)
        meta = Gtk.Label(label=self._meta_text(f), xalign=0.0)
        meta.add_css_class("app-dim")
        meta.add_css_class("app-small")
        panel.append(meta)

        if f.is_backup:
            brow = Gtk.Box(spacing=6)
            brow.append(badge(_("Probable backup"), "app-kind-image"))
            brow.append(InfoHint(self.window, "backup-file"))
            panel.append(brow)
            age = badge(_("Newest") if f.is_newest else _("Older"), "app-keepbadge")
            panel.append(age)

        if f.keeper:
            krow = Gtk.Box(spacing=6)
            krow.append(badge(_("Keep"), "app-keepbadge"))
            krow.append(InfoHint(self.window, "keeper"))
            panel.append(krow)
        else:
            check = Gtk.CheckButton(label=_("Confirm duplicate"))
            check.set_active(True)
            check.connect("toggled", lambda _c: self._refresh())
            self._checks.append((check, f))
            panel.append(check)
        return panel

    def _meta_text(self, f: FileEntry) -> str:
        parts = []
        if f.resolution:
            parts.append(f.resolution)
        parts.append(human_bytes(f.size))
        return " · ".join(parts)

    def _preview_widget(self, f: FileEntry) -> Gtk.Widget:
        pv = previewmod.preview(f.path)
        frame = Gtk.Frame(hexpand=True, vexpand=True)
        frame.set_size_request(-1, 200)         # minimum height; grows to fill
        if pv.kind == previewmod.KIND_IMAGE and pv.image_path:
            pic = Gtk.Picture.new_for_filename(pv.image_path)
            pic.set_content_fit(Gtk.ContentFit.CONTAIN)
            pic.set_hexpand(True)
            pic.set_vexpand(True)
            frame.set_child(pic)
        else:
            sw = Gtk.ScrolledWindow(hexpand=True, vexpand=True)
            sw.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
            lbl = Gtk.Label(label=pv.text or pv.note or _("No preview"), xalign=0.0, yalign=0.0,
                            wrap=True, hexpand=True)
            lbl.add_css_class("app-mono")
            lbl.add_css_class("app-small")
            lbl.set_margin_top(8)
            lbl.set_margin_bottom(8)
            lbl.set_margin_start(8)
            lbl.set_margin_end(8)
            sw.set_child(lbl)
            frame.set_child(sw)
        return frame

    def _selected(self) -> list[FileEntry]:
        return [f for c, f in self._checks if c.get_active()]

    def _refresh(self) -> None:
        sel = self._selected()
        freed = sum(f.size for f in sel)
        self.decision.set_text(
            _("{n} of {t} confirmed · reclaim {b}").format(
                n=len(sel), t=len(self._checks), b=human_bytes(freed)))

    def _trash(self, _btn) -> None:
        sel = self._selected()
        if not sel:
            return
        res = actions.move_to_trash(sel)
        self._done(res, sel)

    def _link(self, _btn) -> None:
        sel = self._selected()
        if not sel or self.group.keeper is None:
            return
        res = actions.hard_link(self.group.keeper, sel)
        self._done(res, sel)

    def _done(self, res, sel) -> None:
        self.window.toast(_("{n} files · {b} reclaimed").format(n=res.done, b=human_bytes(res.freed)))
        for err in res.errors[:1]:
            self.window.toast(err)
        if self.on_applied:
            self.on_applied(sel)
        self.close()
