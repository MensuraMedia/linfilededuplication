"""Results: duplicate groups with previews, selection, and safe actions."""
from __future__ import annotations

import time

from gi.repository import Adw, Gdk, GdkPixbuf, GLib, Gtk

from linfilededuplication.core.model import KIND_IMAGE, KIND_SIMILAR, DuplicateGroup, FileEntry
from linfilededuplication.core.units import human_bytes
from linfilededuplication.i18n import _
from linfilededuplication.services import actions
from linfilededuplication.ui.pages.base import BasePage
from linfilededuplication.ui.widgets.common import badge, icon
from linfilededuplication.ui.widgets.info_hint import InfoHint
from linfilededuplication.ui.widgets.scan_spinner import RadarSpinner
from linfilededuplication.ui.widgets.space_chart import SpaceChart


class ResultsPage(BasePage):
    page_id = "results"
    title = _("Results")
    clamp_max = 0           # fill the window for the spreadsheet-like file list
    MIN_SPIN = 1.6          # keep the radar visible at least this long
    MAX_CARDS = 400         # cap rendered group cards; a comprehensive scan can find
                            # tens of thousands, and a widget per group would exhaust memory

    def build_content(self) -> None:
        self._groups: list[dict] = []       # {group, keeper, checks:[(CheckButton, FileEntry)], widget}

        self.add_heading(_("Results"))
        spin_box = Gtk.Box(halign=Gtk.Align.CENTER)
        spin_box.set_margin_top(4)
        spin_box.set_margin_bottom(4)
        self.spinner = RadarSpinner(100)        # shown below the title while scanning
        spin_box.append(self.spinner)
        self.add(spin_box)

        # live scan caption under the radar: the root/mountpoint, then the file going by
        cap = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1, halign=Gtk.Align.CENTER)
        cap.set_margin_bottom(6)
        self.scan_root = Gtk.Label(xalign=0.5)
        self.scan_root.add_css_class("app-small")
        self.scan_root.set_ellipsize(2)         # middle: keep the mountpoint and the tail
        self.scan_root.set_max_width_chars(64)
        self.scan_activity = Gtk.Label(xalign=0.5)
        self.scan_activity.add_css_class("app-small")
        self.scan_activity.add_css_class("app-dim")
        self.scan_activity.add_css_class("app-mono")
        self.scan_activity.set_ellipsize(2)
        self.scan_activity.set_max_width_chars(68)
        cap.append(self.scan_root)
        cap.append(self.scan_activity)
        self.scan_caption = cap
        cap.set_visible(False)
        self.add(cap)

        # space-savings panel: a headline sentiment + a before/after bar chart
        panel = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        panel.add_css_class("app-card")
        panel.add_css_class("app-savings")
        self.savings_head = Gtk.Label(xalign=0.0, use_markup=True, wrap=True)
        self.savings_head.add_css_class("app-savings-head")
        self.savings_sub = Gtk.Label(xalign=0.0, wrap=True)
        self.savings_sub.add_css_class("app-dim")
        self.savings_sub.add_css_class("app-small")
        self.space_chart = SpaceChart()
        panel.append(self.savings_head)
        panel.append(self.savings_sub)
        panel.append(self.space_chart)
        self.savings_panel = panel
        panel.set_visible(False)
        self.add(panel)

        self.formula_card = self._build_formula_card()
        self.formula_card.set_visible(False)
        self.add(self.formula_card)

        # action bar — above the findings, below the information card
        bar = Gtk.Box(spacing=12)
        bar.add_css_class("app-card")
        self.sel_label = Gtk.Label(label=_("Nothing selected"), xalign=0.0, hexpand=True)
        self.sel_label.add_css_class("app-small")
        self.btn_link = Gtk.Button(label=_("Hard-link"))
        self.btn_trash = Gtk.Button(label=_("Delete All Duplicates"))
        self.btn_trash.add_css_class("destructive-action")
        self.btn_trash.get_child().set_ellipsize(0)      # never truncate — expand the button
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

        self.summary = Gtk.Label(label="", xalign=0.0)
        self.summary.add_css_class("app-dim")
        self.add(self.summary)

        self.groups_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        self.add(self.groups_box)

        c = self.window.controller
        c.connect("scan-started", self._on_started)
        c.connect("progress", self._on_progress)
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
        self.savings_panel.set_visible(False)
        self.formula_card.set_visible(False)
        self.scan_root.set_text(_("Scanning {p}").format(p=_root))
        self.scan_activity.set_text("")
        self.scan_caption.set_visible(True)
        self.spinner.start()

    def _on_progress(self, _c, _fraction: float, phase: str, detail: str) -> None:
        if detail:                              # a path (walk/hash/image) or a short phase note
            self.scan_activity.set_text(detail)

    def _end_spin(self) -> None:
        self.spinner.stop()
        self.scan_caption.set_visible(False)

    def _on_group(self, _c, group: DuplicateGroup) -> None:
        if len(self._groups) >= self.MAX_CARDS:
            # keep the scan running and the totals accurate (from Finished), but stop
            # building widgets so a huge result set can't exhaust memory.
            return
        record = {"group": group, "keeper": group.keeper, "checks": [], "ignored_files": set()}
        card = self._build_card(group, record)
        record["widget"] = card
        self._groups.append(record)
        self.groups_box.append(card)
        self._refresh_selection()

    def _on_finished(self, _c, fin) -> None:
        elapsed = time.monotonic() - getattr(self, "_scan_start", 0.0)
        remaining = self.MIN_SPIN - elapsed
        if remaining > 0:
            GLib.timeout_add(int(remaining * 1000), lambda: (self._end_spin(), False)[1])
        else:
            self._end_spin()
        if not self._groups:
            self.summary.set_text(_("No duplicates found."))
            return
        summary = _("{g} groups · up to {b} reclaimable").format(
            g=fin.groups, b=human_bytes(fin.reclaimable))
        if fin.groups > len(self._groups):      # some groups weren't rendered (card cap)
            summary += _(" · showing the first {n} — narrow the scan to act on the rest").format(
                n=len(self._groups))
        self.summary.set_text(summary)
        self._show_savings(fin)
        self.action_bar.set_visible(True)

    def _build_formula_card(self) -> Gtk.Widget:
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        card.add_css_class("app-card")
        card.add_css_class("app-savings")
        title = Gtk.Label(label=_("How LinFileDedup decides what to keep"), xalign=0.0)
        title.add_css_class("app-group-title")
        sub = Gtk.Label(xalign=0.0, wrap=True, label=_(
            "One file in every group is always kept — only the extra copies are ever removed."))
        sub.add_css_class("app-dim")
        sub.add_css_class("app-small")
        card.append(title)
        card.append(sub)
        g, r = "#2ec27e", "#e2564b"
        rules = [
            _("<b>Same size and type.</b> The <span foreground=\"{g}\">newest</span> copy is kept; "
              "the <span foreground=\"{r}\">older</span> copies are marked for deletion."),
            _("<b>Same type, different size.</b> The <span foreground=\"{g}\">largest</span> "
              "(highest-quality) copy is kept; the <span foreground=\"{r}\">smaller</span> copies "
              "are marked for deletion."),
            _("<b>Backups detected.</b> The <span foreground=\"{g}\">newest</span> backup is kept; "
              "<span foreground=\"{r}\">older</span> backups are marked for deletion."),
            _("<b>Name tells.</b> An original is kept over a <span foreground=\"{r}\">“copy”, “(1)”, "
              "or “resized”</span> version of the same content."),
            _("<b>Already hard-linked.</b> Files that share one physical copy are "
              "<span foreground=\"{g}\">left alone</span> — there is nothing to reclaim."),
        ]
        grid = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=9)
        grid.set_margin_top(6)
        for i, rule in enumerate(rules, 1):
            rowb = Gtk.Box(spacing=11)
            num = Gtk.Label(label=str(i))
            num.add_css_class("app-rule-num")
            num.set_size_request(22, 22)
            num.set_valign(Gtk.Align.START)
            body = Gtk.Label(xalign=0.0, wrap=True, use_markup=True, hexpand=True,
                             label=rule.format(g=g, r=r))
            rowb.append(num)
            rowb.append(body)
            grid.append(rowb)
        card.append(grid)
        return card

    def _show_savings(self, fin) -> None:
        self.formula_card.set_visible(fin.groups > 0 and not fin.cancelled)
        if fin.reclaimable <= 0 or fin.occupied_bytes <= 0:
            self.savings_panel.set_visible(False)
            return
        freed = human_bytes(fin.reclaimable)
        after = human_bytes(max(0, fin.occupied_bytes - fin.reclaimable))
        now = human_bytes(fin.occupied_bytes)
        self.savings_head.set_markup(
            _("You can free up <span foreground=\"#2ec27e\">{b}</span>").format(b=freed))
        self.savings_sub.set_text(
            _("Across {g} duplicate groups · {now} now → {after} after cleanup").format(
                g=fin.groups, now=now, after=after))
        self.space_chart.set_values(fin.occupied_bytes, fin.reclaimable)
        self.savings_panel.set_visible(True)
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
            label=_("{n} files · reclaim {b}").format(n=group.count, b=human_bytes(group.reclaimable)),
            xalign=0.0, hexpand=True)           # takes the slack so SpotCheck sits at the right
        meta.add_css_class("app-dim")
        meta.add_css_class("app-small")
        del_all = Gtk.ToggleButton(label=_("Delete All"))
        del_all.set_valign(Gtk.Align.CENTER)
        del_all.add_css_class("app-delall")
        del_all.set_tooltip_text(_("Remove every copy in this group — keep none"))
        del_all.connect("toggled", lambda b, rec=record: self._on_delete_all(rec, b))
        record["delete_all"] = del_all
        ignore = Gtk.ToggleButton(label=_("Ignore Files"))
        ignore.set_valign(Gtk.Align.CENTER)
        ignore.add_css_class("app-ignore")
        ignore.set_tooltip_text(_("Take no action; skip these files in future scans"))
        ignore.connect("toggled", lambda b, rec=record: self._on_ignore(rec, b))
        record["ignore"] = ignore
        ihint = InfoHint(self.window, "ignore-files")
        ihint.set_valign(Gtk.Align.CENTER)
        ignore_folder = Gtk.Button(label=_("Ignore Folder"))
        ignore_folder.set_valign(Gtk.Align.CENTER)
        ignore_folder.add_css_class("app-ignore")
        ignore_folder.set_tooltip_text(_("Skip the folders these files live in, in future scans"))
        ignore_folder.connect("clicked", lambda _b, g=group: self._ignore_group_folders(g))
        fhint = InfoHint(self.window, "ignore-folder")
        fhint.set_valign(Gtk.Align.CENTER)
        spot = Gtk.Button(label=_("SpotCheck"))
        spot.set_valign(Gtk.Align.CENTER)      # a normal raised button, not flat text
        spot.connect("clicked", lambda _b, g=group: self.window.open_spotcheck(g, self._on_spotcheck_applied))
        header.append(meta)
        header.append(del_all)
        header.append(ignore)
        header.append(ihint)
        header.append(ignore_folder)
        header.append(fhint)
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

        guard = Gtk.Label(xalign=0.0, wrap=True, label=_(
            "⚠  No copy will remain in this group. These files move to Trash (recoverable); "
            "Hard-link is unavailable when nothing is kept."))
        guard.add_css_class("app-guard")
        guard.add_css_class("app-small")
        guard.set_visible(False)
        record["guard"] = guard
        card.append(guard)
        return card

    def _on_delete_all(self, record: dict, toggle: Gtk.ToggleButton) -> None:
        on = toggle.get_active()
        kr = record.get("keeper_row")
        if kr:
            kr["label"].set_text(_("Delete") if on else _("Keep"))
            kr["label"].remove_css_class("app-keep-text" if on else "app-del-text")
            kr["label"].add_css_class("app-del-text" if on else "app-keep-text")
            if on:
                kr["name"].add_css_class("app-del-name")
                kr["marker"].remove_css_class("app-keep-check")
                kr["marker"].add_css_class("app-del-static")
            else:
                kr["name"].remove_css_class("app-del-name")
                kr["marker"].remove_css_class("app-del-static")
                kr["marker"].add_css_class("app-keep-check")
        if record.get("guard"):
            record["guard"].set_visible(on)
        if on:
            toggle.add_css_class("destructive-action")
        else:
            toggle.remove_css_class("destructive-action")
        self._refresh_selection()

    def _on_ignore(self, record: dict, toggle: Gtk.ToggleButton) -> None:
        on = toggle.get_active()
        record["ignored"] = on
        for row in record.get("rows", {}).values():
            row.set_sensitive(not on)                 # grey out: no action will be taken
        if record.get("delete_all"):                  # can't delete-all an ignored group
            record["delete_all"].set_sensitive(not on)
        # persist so future scans skip these files
        s = self.app.settings
        paths = [f.path for f in record["group"].files]
        cur = set(getattr(s, "ignored_paths", []))
        cur.update(paths) if on else cur.difference_update(paths)
        s.ignored_paths = sorted(cur)
        s.save()
        self._refresh_selection()
        if on:
            self.window.toast(
                _("Ignoring {n} files — they will be skipped in future scans").format(n=len(paths)))

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
            # remember the keeper row so "Delete all copies" can flip it to red
            record["keeper_row"] = {"label": lbl, "marker": marker, "name": name}
        else:
            # a red check-circle marker (not an orange system checkbox): active = will delete
            marker = Gtk.ToggleButton()
            marker.add_css_class("flat")
            marker.add_css_class("app-del-marker")
            marker.set_child(icon("app-status-success-symbolic", 18))
            marker.set_active(True)
            marker.set_tooltip_text(_("Marked for removal — click to keep this copy"))
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
                # Decode SCALED, never full-resolution: new_from_file would hold a full
                # bitmap per row (tens of MB each), which OOMs a large image result set.
                pb = GdkPixbuf.Pixbuf.new_from_file_at_scale(f.path, 48, 48, True)
                img = Gtk.Image.new_from_pixbuf(pb)
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
            if rec.get("ignored"):                    # whole group ignored -> no action
                continue
            ig = rec.get("ignored_files") or set()    # individually ignored (via Ignore Folder)
            for check, f in rec["checks"]:
                if id(f) not in ig and check.get_active():
                    out.append((rec, f))
            da = rec.get("delete_all")
            keeper = rec.get("keeper")
            if (da is not None and da.get_active() and keeper is not None
                    and id(keeper) not in ig):
                out.append((rec, keeper))             # delete-all also removes the keeper
        return out

    def _ignore_group_folders(self, group: DuplicateGroup) -> None:
        """Ignore the folders this group's files live in: persist them and grey the matching rows
        everywhere in the current results."""
        folders = sorted({f.parent for f in group.files})
        s = self.app.settings
        cur = set(getattr(s, "ignored_folders", []))
        cur.update(folders)
        s.ignored_folders = sorted(cur)
        s.save()
        self.apply_ignored_folders(folders)
        self.window.toast(_("Ignoring {n} folder(s) — skipped in future scans").format(
            n=len(folders)))

    def apply_ignored_folders(self, folders: list[str]) -> None:
        """Grey out (and drop from the selection) any current result rows whose file lives under
        a now-ignored folder. Called when a folder is ignored after a scan has produced results."""
        import os
        dirs = [f.rstrip("/") for f in folders if f]
        if not dirs:
            return
        changed = False
        for rec in self._groups:
            ig = rec.setdefault("ignored_files", set())
            for f in rec["group"].files:
                if any(f.path == d or f.path.startswith(d + os.sep) for d in dirs):
                    if id(f) not in ig:
                        ig.add(id(f))
                        changed = True
                        row = rec.get("rows", {}).get(id(f))
                        if row is not None:
                            row.set_sensitive(False)   # grey: no action will be taken
        if changed:
            self._refresh_selection()

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
        nuke = sum(1 for rec, _f in sel
                   if rec.get("delete_all") is not None and rec["delete_all"].get_active())
        if nuke:                                       # some groups keep no copy at all
            body = _("The selected files move to Trash and can be restored from your file "
                     "manager.\n\n⚠ {n} group(s) are set to “Delete all copies” — every copy "
                     "in those groups will be removed, leaving nothing behind.").format(n=nuke)
        else:
            keepers = {rec["keeper"].name for rec, _f in sel if rec["keeper"]}
            body = _("The selected copies move to Trash and can be restored from your file "
                     "manager. Kept originals: {k}.").format(k=", ".join(sorted(keepers))[:200])
        dialog = Adw.AlertDialog(
            heading=_("Move {n} files to Trash?").format(n=len(sel)), body=body)
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
        skipped_delete_all = False
        by_group: dict[int, list[FileEntry]] = {}
        keepers: dict[int, FileEntry] = {}
        for rec, f in sel:
            da = rec.get("delete_all")
            if da is not None and da.get_active():
                skipped_delete_all = True             # no keeper to link to — can't hard-link
                continue
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
        # only remove the rows that were actually hard-linked
        linked = {id(f) for gid, extras in by_group.items() if keepers[gid] is not None
                  for f in extras}
        self._remove_by_ids(linked)
        self.window.toast(_("Hard-linked {n} files · {b} reclaimed").format(n=done, b=human_bytes(freed)))
        if skipped_delete_all:
            self.window.toast(_("Groups set to “Delete all copies” were skipped — use Move to Trash."))
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
