"""Results: duplicate groups with previews, selection, and safe actions."""
from __future__ import annotations

import time

from gi.repository import Adw, Gdk, GLib, Gtk

from linfilededuplication.core.model import KIND_IMAGE, KIND_SIMILAR, DuplicateGroup, FileEntry
from linfilededuplication.core.units import human_bytes
from linfilededuplication.i18n import _
from linfilededuplication.services import actions
from linfilededuplication.ui.pages.base import BasePage
from linfilededuplication.ui.widgets.common import badge, icon
from linfilededuplication.ui.widgets.info_hint import InfoHint
from linfilededuplication.ui.widgets.scan_spinner import RadarSpinner


class ResultsPage(BasePage):
    page_id = "results"
    title = _("Results")
    clamp_max = 0           # fill the window for the spreadsheet-like file list
    MIN_SPIN = 1.6          # keep the radar visible at least this long

    def build_content(self) -> None:
        self._groups: list[dict] = []       # {group, keeper, checks:[(CheckButton, FileEntry)], widget}

        self.add_heading(_("Results"))
        spin_box = Gtk.Box(halign=Gtk.Align.CENTER)
        spin_box.set_margin_top(4)
        spin_box.set_margin_bottom(4)
        self.spinner = RadarSpinner(100)        # shown below the title while scanning
        spin_box.append(self.spinner)
        self.add(spin_box)
        self.summary = Gtk.Label(label="", xalign=0.0)
        self.summary.add_css_class("app-dim")
        self.add(self.summary)

        self.groups_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        self.add(self.groups_box)

        # action bar
        bar = Gtk.Box(spacing=12)
        bar.add_css_class("app-card")
        self.sel_label = Gtk.Label(label=_("Nothing selected"), xalign=0.0, hexpand=True)
        self.sel_label.add_css_class("app-small")
        self.btn_link = Gtk.Button(label=_("Hard-link"))
        self.btn_trash = Gtk.Button(label=_("Move to Trash"))
        self.btn_trash.add_css_class("destructive-action")
        self.btn_link.set_sensitive(False)
        self.btn_trash.set_sensitive(False)
        self.btn_trash.connect("clicked", self._trash_selected)
        self.btn_link.connect("clicked", self._link_selected)
        bar.append(self.sel_label)
        bar.append(InfoHint(self.window, "hard-link"))
        bar.append(self.btn_link)
        bar.append(self.btn_trash)
        self.action_bar = bar
        self.action_bar.set_visible(False)
        self.add(bar)

        c = self.window.controller
        c.connect("scan-started", self._on_started)
        c.connect("group-found", self._on_group)
        c.connect("scan-finished", self._on_finished)

    # --- lifecycle -------------------------------------------------------
    def _on_started(self, _c, _root: str) -> None:
        child = self.groups_box.get_first_child()
        while child is not None:
            nxt = child.get_next_sibling()
            self.groups_box.remove(child)
            child = nxt
        self._groups.clear()
        self.summary.set_text("")               # the radar shows scanning; no text needed
        self.action_bar.set_visible(False)
        self._scan_start = time.monotonic()
        self.spinner.start()

    def _on_group(self, _c, group: DuplicateGroup) -> None:
        record = {"group": group, "keeper": group.keeper, "checks": []}
        card = self._build_card(group, record)
        record["widget"] = card
        self._groups.append(record)
        self.groups_box.append(card)
        self._refresh_selection()

    def _on_finished(self, _c, fin) -> None:
        elapsed = time.monotonic() - getattr(self, "_scan_start", 0.0)
        remaining = self.MIN_SPIN - elapsed
        if remaining > 0:
            GLib.timeout_add(int(remaining * 1000), lambda: (self.spinner.stop(), False)[1])
        else:
            self.spinner.stop()
        if not self._groups:
            self.summary.set_text(_("No duplicates found."))
            return
        self.summary.set_text(
            _("{g} groups · up to {b} reclaimable").format(g=fin.groups, b=human_bytes(fin.reclaimable)))
        self.action_bar.set_visible(True)
        for note in fin.notes:
            self.window.toast(note)

    # --- card building ---------------------------------------------------
    def _build_card(self, group: DuplicateGroup, record: dict) -> Gtk.Box:
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        card.add_css_class("app-group")

        header = Gtk.Box(spacing=11)
        header.add_css_class("app-group-header")
        if group.kind == KIND_IMAGE:
            header.append(badge(_("IMAGES · Δ{d}").format(d=group.distance), "app-kind-image"))
        elif group.kind == KIND_SIMILAR:
            header.append(badge(_("SIMILAR · {d}%").format(d=group.distance), "app-kind-similar"))
        else:
            header.append(badge(_("EXACT · SHA-256"), "app-kind-exact"))
        header.append(InfoHint(self.window, "match-kind"))
        if group.has_backups:
            header.append(badge(_("Backups"), "app-kind-image"))
            header.append(InfoHint(self.window, "backup-file"))
        title = Gtk.Label(label=group.title, xalign=0.0, hexpand=True)
        title.add_css_class("app-group-title")
        title.set_ellipsize(3)  # PANGO_ELLIPSIZE_END
        meta = Gtk.Label(
            label=_("{n} files · reclaim {b}").format(n=group.count, b=human_bytes(group.reclaimable)))
        meta.add_css_class("app-dim")
        meta.add_css_class("app-small")
        spot = Gtk.Button(label=_("SpotCheck"))
        spot.set_valign(Gtk.Align.CENTER)      # a normal raised button, not flat text
        spot.connect("clicked", lambda _b, g=group: self.window.open_spotcheck(g, self._on_spotcheck_applied))
        header.append(meta)
        header.append(spot)
        card.append(header)

        # size groups align the Name and Size columns across rows (spreadsheet style)
        name_sg = Gtk.SizeGroup(mode=Gtk.SizeGroupMode.HORIZONTAL)
        size_sg = Gtk.SizeGroup(mode=Gtk.SizeGroupMode.HORIZONTAL)
        sel_sg = Gtk.SizeGroup(mode=Gtk.SizeGroupMode.HORIZONTAL)
        record["rows"] = {}
        for f in group.files:
            row = self._file_row(f, group, record, name_sg, size_sg, sel_sg)
            record["rows"][id(f)] = row
            card.append(row)
        return card

    def _file_row(self, f: FileEntry, group: DuplicateGroup, record: dict,
                  name_sg: Gtk.SizeGroup, size_sg: Gtk.SizeGroup, sel_sg: Gtk.SizeGroup) -> Gtk.Box:
        row = Gtk.Box(spacing=18)
        row.add_css_class("app-file-row")
        if f.keeper:
            row.add_css_class("app-keep")

        # column 1: type icon + name (aligned across rows)
        namecell = Gtk.Box(spacing=10)
        namecell.append(self._thumb(f))
        name = Gtk.Label(label=f.name, xalign=0.0)
        name.set_ellipsize(3)                # PANGO_ELLIPSIZE_END
        name.set_max_width_chars(46)
        if not f.keeper:
            name.add_css_class("app-del-name")   # the file marked for deletion reads red
        namecell.append(name)
        if f.is_backup:
            namecell.append(badge(_("Newest") if f.is_newest else _("Older"), "app-keepbadge"))
        name_sg.add_widget(namecell)
        row.append(namecell)

        # column 2: size (right-aligned numbers)
        size = Gtk.Label(label=human_bytes(f.size), xalign=1.0)
        size.add_css_class("app-mono")
        size_sg.add_widget(size)
        row.append(size)

        # column 3: path (fills remaining width, truncates with a trailing ellipsis)
        path = Gtk.Label(label=f.parent, xalign=0.0, hexpand=True)
        path.add_css_class("app-mono")
        path.add_css_class("app-dim")
        path.add_css_class("app-small")
        path.set_ellipsize(3)
        path.set_tooltip_text(_("{p}\nRight-click the row for options").format(p=f.path))
        row.append(path)

        # column 4: "Keep" + green circle, or "Delete" + red check.
        # The label is right-aligned and the marker sits in an equal fixed slot, so the
        # markers line up across rows and are never clipped at the card edge.
        sel = Gtk.Box(spacing=10)
        sel.set_valign(Gtk.Align.CENTER)
        sel.set_margin_end(6)
        lbl = Gtk.Label(label=_("Keep") if f.keeper else _("Delete"), xalign=1.0, hexpand=True)
        lbl.add_css_class("app-keep-text" if f.keeper else "app-del-text")
        sel.append(lbl)
        if f.keeper:
            marker = icon("app-status-success-symbolic", 18)
            marker.add_css_class("app-keep-check")
            marker.set_tooltip_text(_("Kept"))
        else:
            marker = Gtk.CheckButton()
            marker.add_css_class("app-del-check")
            marker.set_active(True)
            marker.set_tooltip_text(_("Marked for removal"))
            marker.connect("toggled", lambda _c: self._refresh_selection())
            record["checks"].append((marker, f))
        marker.set_size_request(26, 26)
        marker.set_halign(Gtk.Align.CENTER)
        marker.set_valign(Gtk.Align.CENTER)
        sel.append(marker)
        sel_sg.add_widget(sel)
        row.append(sel)
        # right-click anywhere on the row -> Explore here / Open file / Copy path for THIS file
        gesture = Gtk.GestureClick(button=3)
        gesture.connect("pressed", lambda _g, _n, x, y, ff=f: self._show_path_menu(row, ff, x, y))
        row.add_controller(gesture)
        return row

    def _thumb(self, f: FileEntry) -> Gtk.Widget:
        if f.is_image:
            try:
                img = Gtk.Image.new_from_file(f.path)
                img.set_pixel_size(24)
                img.add_css_class("app-thumb")
                return img
            except Exception:
                pass
        img = icon("app-stat-items-symbolic", 20)
        img.add_css_class("app-dim")
        return img

    # --- path context menu ----------------------------------------------
    def _show_path_menu(self, anchor, f: FileEntry, x: float, y: float) -> None:
        pop = Gtk.Popover()
        pop.set_parent(anchor)
        pop.set_pointing_to(Gdk.Rectangle(int(x), int(y), 1, 1))
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        box.set_margin_top(4)
        box.set_margin_bottom(4)
        box.set_margin_start(4)
        box.set_margin_end(4)

        def item(label: str, cb) -> None:
            lbl = Gtk.Label(label=label, xalign=0.0)
            b = Gtk.Button()
            b.set_child(lbl)
            b.add_css_class("flat")
            b.set_hexpand(True)
            b.connect("clicked", lambda _b: (pop.popdown(), cb()))
            box.append(b)

        item(_("Explore here"), lambda: actions.show_in_file_manager(f.path))
        item(_("Open file"), lambda: actions.open_file(f.path))
        item(_("Copy path"), lambda: self._copy_path(f.path))
        pop.set_child(box)
        pop.connect("closed", lambda p: p.unparent())
        pop.popup()

    def _copy_path(self, path: str) -> None:
        try:
            self.get_clipboard().set(path)
            self.window.toast(_("Path copied"))
        except Exception:
            pass

    # --- selection + actions --------------------------------------------
    def _selected(self) -> list[tuple[dict, FileEntry]]:
        out = []
        for rec in self._groups:
            for check, f in rec["checks"]:
                if check.get_active():
                    out.append((rec, f))
        return out

    def _refresh_selection(self) -> None:
        sel = self._selected()
        n = len(sel)
        freed = sum(f.size for _r, f in sel)
        self.sel_label.set_text(
            _("{n} files selected · reclaim {b}").format(n=n, b=human_bytes(freed)) if n
            else _("Nothing selected"))
        self.btn_trash.set_sensitive(n > 0)
        self.btn_link.set_sensitive(n > 0)

    def _trash_selected(self, _btn) -> None:
        sel = self._selected()
        if not sel:
            return
        keepers = {rec["keeper"].name for rec, _f in sel if rec["keeper"]}
        dialog = Adw.AlertDialog(
            heading=_("Move {n} files to Trash?").format(n=len(sel)),
            body=_("The selected copies move to Trash and can be restored from your file manager. "
                   "Kept originals: {k}.").format(k=", ".join(sorted(keepers))[:200]))
        dialog.add_response("cancel", _("Cancel"))
        dialog.add_response("ok", _("Move to Trash"))
        dialog.set_response_appearance("ok", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.set_default_response("cancel")
        dialog.choose(self.window, None, lambda d, r: self._do_trash(d, r, sel))

    def _do_trash(self, dialog, result, sel) -> None:
        if dialog.choose_finish(result) != "ok":
            return
        res = actions.move_to_trash([f for _r, f in sel])
        self._apply_removed(sel)
        self.window.toast(_("Moved {n} files to Trash · {b} reclaimed").format(
            n=res.done, b=human_bytes(res.freed)))
        for err in res.errors[:1]:
            self.window.toast(err)

    def _link_selected(self, _btn) -> None:
        sel = self._selected()
        if not sel:
            return
        done = freed = 0
        errors: list[str] = []
        by_group: dict[int, list[FileEntry]] = {}
        keepers: dict[int, FileEntry] = {}
        for rec, f in sel:
            gid = id(rec)
            by_group.setdefault(gid, []).append(f)
            keepers[gid] = rec["keeper"]
        for gid, extras in by_group.items():
            if keepers[gid] is None:
                continue
            res = actions.hard_link(keepers[gid], extras)
            done += res.done
            freed += res.freed
            errors += res.errors
        self._apply_removed(sel)
        self.window.toast(_("Hard-linked {n} files · {b} reclaimed").format(n=done, b=human_bytes(freed)))
        for err in errors[:1]:
            self.window.toast(err)

    def _apply_removed(self, sel) -> None:
        self._remove_by_ids({id(f) for _r, f in sel})

    def _on_spotcheck_applied(self, files) -> None:
        """SpotCheck removed these files; reflect it in the Results list."""
        self._remove_by_ids({id(f) for f in files})

    def _remove_by_ids(self, removed) -> None:
        """Remove the acted-on rows; when a group has no candidates left, drop the whole card."""
        for rec in list(self._groups):
            rows = rec.get("rows", {})
            for fid in list(rows.keys()):
                if fid in removed:
                    row = rows.pop(fid)
                    if row.get_parent() is rec["widget"]:
                        rec["widget"].remove(row)
            rec["checks"] = [(c, f) for (c, f) in rec["checks"] if id(f) not in removed]
            if not rec["checks"]:            # every candidate handled -> group resolved
                if rec["widget"].get_parent() is self.groups_box:
                    self.groups_box.remove(rec["widget"])
                self._groups.remove(rec)
        self._refresh_selection()
        self._update_summary()

    def _update_summary(self) -> None:
        n = len(self._groups)
        reclaim = sum(f.size for rec in self._groups for (_c, f) in rec["checks"])
        self.window.sidebar.set_count("results", n)
        if n == 0:
            self.summary.set_text(_("All groups resolved."))
            self.action_bar.set_visible(False)
        else:
            self.summary.set_text(
                _("{g} groups · up to {b} reclaimable").format(g=n, b=human_bytes(reclaim)))
