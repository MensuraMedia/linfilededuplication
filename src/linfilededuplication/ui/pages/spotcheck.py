"""SpotCheck: a large side-by-side confirmation view for one duplicate group.

Shows each file at a readable size (image previews or document snippets) so the user can
confirm the copies before acting. A gate, not an actor: closing it changes nothing.
"""
from __future__ import annotations

from gi.repository import Adw, Gdk, Gtk

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
        self._tmp_dirs: list[str] = []
        self._pdf_pagers: list = []         # per-PDF page setters, driven together for A/B compare
        self.connect("closed", self._cleanup)
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
        elif pv.kind == previewmod.KIND_VIDEO and pv.image_path:
            view = self._video_view(pv.image_path)
            frame.set_child(view if view is not None else self._text_view(pv))
        elif pv.kind == previewmod.KIND_PDF and pv.image_path:
            view = self._pdf_view(pv.image_path)
            frame.set_child(view if view is not None else self._text_view(pv))
        else:
            frame.set_child(self._text_view(pv))
        return frame

    def _video_view(self, path: str) -> Gtk.Widget | None:
        """Show a video thumbnail and play it. Uses GtkVideo (inline, with controls) when GTK's
        media backend is installed; otherwise shows the poster frame with a Play-in-default-player
        button and the one-line install hint, so videos are at least visible and playable."""
        poster = self._video_thumbnail(path)
        try:
            mf = Gtk.MediaFile.new_for_filename(path)
            backend_ok = mf.__gtype__.name != "GtkNoMediaFile"
        except Exception:
            mf, backend_ok = None, False
        if backend_ok and mf is not None:
            video = Gtk.Video()
            video.set_media_stream(mf)
            video.set_autoplay(False)
            video.set_hexpand(True)
            video.set_vexpand(True)
            return video
        return self._video_fallback(path, poster)

    def _video_thumbnail(self, path: str) -> str | None:
        """Grab a poster frame (~10% in) with ffmpegthumbnailer, if available. Read-only."""
        import os
        import subprocess
        import tempfile
        outdir = tempfile.mkdtemp(prefix="lfd-vid-")
        self._tmp_dirs.append(outdir)
        out = os.path.join(outdir, "poster.png")
        try:
            subprocess.run(["ffmpegthumbnailer", "-i", path, "-o", out, "-s", "640", "-t", "10%"],
                           capture_output=True, timeout=20)
            if os.path.exists(out) and os.path.getsize(out) > 0:
                return out
        except Exception:
            pass
        return None

    def _video_fallback(self, path: str, poster: str | None) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10, hexpand=True, vexpand=True)
        if poster:
            pic = Gtk.Picture.new_for_filename(poster)
            pic.set_content_fit(Gtk.ContentFit.CONTAIN)
            pic.set_can_shrink(True)
            pic.set_hexpand(True)
            pic.set_vexpand(True)
            pic.add_css_class("app-thumb")
            box.append(pic)
        else:
            ph = Gtk.Label(label=_("Video"), vexpand=True)
            ph.add_css_class("app-dim")
            box.append(ph)
        play = Gtk.Button(label=_("▶  Play in default player"))
        play.set_halign(Gtk.Align.CENTER)
        play.add_css_class("pill")
        play.connect("clicked", lambda _b, p=path: actions.open_file(p))
        box.append(play)
        note = Gtk.Label(xalign=0.5, justify=Gtk.Justification.CENTER, wrap=True, label=_(
            "Play videos inside SpotCheck by installing the GTK media backend:\n"
            "sudo apt install libgtk-4-media-gstreamer"))
        note.add_css_class("app-small")
        note.add_css_class("app-dim")
        box.append(note)
        return box

    def _text_view(self, pv) -> Gtk.Widget:
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
        return sw

    def _pdf_view(self, path: str) -> Gtk.Widget | None:
        """A one-page-at-a-time PDF viewer for side-by-side comparison.

        Shows a single rendered page (via pdftoppm) that fills the panel, with Previous/Next
        and an actual-size zoom toggle. Paging is synced across every PDF panel by
        ``_set_all_pages``, so page N sits beside page N for a true A/B check.
        """
        pages = self._render_pdf_pages(path)
        if not pages:
            return None
        n = len(pages)
        cache: dict[int, Gdk.Texture] = {}

        def tex(i: int):
            if i not in cache:
                try:
                    cache[i] = Gdk.Texture.new_from_filename(pages[i])
                except Exception:
                    cache[i] = None
            return cache[i]

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6, hexpand=True, vexpand=True)
        pic = Gtk.Picture(hexpand=True, vexpand=True)
        pic.set_content_fit(Gtk.ContentFit.CONTAIN)
        pic.set_can_shrink(True)
        pic.add_css_class("app-thumb")
        scroll = Gtk.ScrolledWindow(hexpand=True, vexpand=True)
        scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scroll.set_child(pic)
        outer.append(scroll)

        nav = Gtk.Box(spacing=6, halign=Gtk.Align.CENTER)
        nav.add_css_class("app-pdf-nav")
        prev = Gtk.Button(label=_("‹ Prev"))
        prev.add_css_class("flat")
        indicator = Gtk.Label()
        indicator.add_css_class("app-small")
        indicator.add_css_class("app-dim")
        indicator.set_width_chars(12)
        nxt = Gtk.Button(label=_("Next ›"))
        nxt.add_css_class("flat")
        zoom = Gtk.ToggleButton(label=_("Actual size"))
        zoom.add_css_class("flat")
        zoom.add_css_class("app-small")
        nav.append(prev)
        nav.append(indicator)
        nav.append(nxt)
        nav.append(zoom)
        outer.append(nav)

        state = {"i": 0}

        def apply_zoom() -> None:
            t = tex(state["i"])
            if zoom.get_active() and t is not None:
                pic.set_can_shrink(False)
                pic.set_content_fit(Gtk.ContentFit.FILL)
                pic.set_size_request(t.get_width(), t.get_height())
            else:
                pic.set_can_shrink(True)
                pic.set_content_fit(Gtk.ContentFit.CONTAIN)
                pic.set_size_request(-1, -1)

        def render() -> None:
            t = tex(state["i"])
            if t is not None:
                pic.set_paintable(t)
            indicator.set_text(_("Page {a} / {b}").format(a=state["i"] + 1, b=n))
            prev.set_sensitive(state["i"] > 0)
            nxt.set_sensitive(state["i"] < n - 1)
            apply_zoom()

        def goto(i: int) -> None:                 # clamp to THIS file's page count, then draw
            state["i"] = max(0, min(n - 1, i))
            render()

        prev.connect("clicked", lambda _b: self._set_all_pages(state["i"] - 1))
        nxt.connect("clicked", lambda _b: self._set_all_pages(state["i"] + 1))
        zoom.connect("toggled", lambda _b: apply_zoom())
        self._pdf_pagers.append(goto)
        render()
        return outer

    def _set_all_pages(self, i: int) -> None:
        """Move every PDF panel to page ``i`` (each clamps to its own length)."""
        for goto in self._pdf_pagers:
            goto(i)

    def _render_pdf_pages(self, path: str, max_pages: int = 15, dpi: int = 120) -> list[str]:
        import glob
        import subprocess
        import tempfile
        outdir = tempfile.mkdtemp(prefix="lfd-pdf-")
        self._tmp_dirs.append(outdir)
        prefix = f"{outdir}/p"
        try:
            subprocess.run(["pdftoppm", "-png", "-f", "1", "-l", str(max_pages), "-r", str(dpi),
                            path, prefix], capture_output=True, timeout=25)
        except Exception:
            return []
        return sorted(glob.glob(prefix + "*.png"))

    def _cleanup(self, *_a) -> None:
        import shutil
        for d in self._tmp_dirs:
            shutil.rmtree(d, ignore_errors=True)
        self._tmp_dirs = []

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
