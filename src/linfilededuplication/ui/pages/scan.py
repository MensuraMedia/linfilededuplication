"""Scan: choose a folder and tier, set options, run, watch progress."""
from __future__ import annotations

import os

from gi.repository import Adw, GLib, Gtk

from linfilededuplication.core import filetypes
from linfilededuplication.core.options import TIER_ADVANCED, TIER_SIMPLE, ScanOptions
from linfilededuplication.core.units import human_bytes
from linfilededuplication.i18n import _
from linfilededuplication.ui.pages.base import BasePage
from linfilededuplication.ui.widgets.common import icon
from linfilededuplication.ui.widgets.info_hint import InfoHint
from linfilededuplication.ui.widgets.ring_loader import RingLoader


class ScanPage(BasePage):
    page_id = "scan"
    title = _("Scan")

    def build_content(self) -> None:
        s = self.app.settings
        self.tier = s.tier
        self.root = s.last_root

        self.add_heading(_("Scan"), _("Read-only — nothing is changed until you confirm."))

        # tier toggle + Start scan on one line (Start scan right-aligned)
        toprow = Gtk.Box(spacing=12)
        toggle_box = Gtk.Box(spacing=0)
        toggle_box.add_css_class("linked")
        self.btn_simple = Gtk.ToggleButton(label=_("Simple Scan"))
        self.btn_adv = Gtk.ToggleButton(label=_("Advanced Scan"))
        self.btn_adv.set_group(self.btn_simple)
        (self.btn_simple if self.tier == TIER_SIMPLE else self.btn_adv).set_active(True)
        self.btn_simple.connect("toggled", self._on_tier)
        self.btn_adv.connect("toggled", self._on_tier)
        toggle_box.append(self.btn_simple)
        toggle_box.append(self.btn_adv)
        toprow.append(toggle_box)
        toprow.append(Gtk.Box(hexpand=True))        # spacer pushes Start scan to the right
        self.run_btn = Gtk.Button(label=_("Start scan"))
        self.run_btn.add_css_class("suggested-action")
        self.run_btn.set_halign(Gtk.Align.END)
        self.run_btn.set_valign(Gtk.Align.CENTER)
        self.run_btn.connect("clicked", self._on_run_clicked)
        toprow.append(self.run_btn)
        self.add(toprow)

        # effective sources: saved multi-source list, else the last single folder
        self.sources = [r for r in (list(getattr(s, "roots", [])) or
                                     ([s.last_root] if s.last_root else [])) if r]

        # config box (sources + options + file types) — hidden while a scan runs
        self.config_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        self.config_box.append(self._sources_section())

        grp = Adw.PreferencesGroup()
        self.sw_images = Adw.SwitchRow(title=_("Find image near-duplicates"),
                                       subtitle=_("Perceptual hash, within the similarity threshold"))
        self.sw_images.set_active(s.find_images)
        self.sw_images.add_prefix(InfoHint(self.window, "near-duplicate"))
        grp.add(self.sw_images)
        self.sw_hidden = Adw.SwitchRow(title=_("Include hidden files"),
                                       subtitle=_("Dotfiles and dot-folders"))
        self.sw_hidden.set_active(s.include_hidden)
        grp.add(self.sw_hidden)
        self.min_row = Adw.SpinRow.new_with_range(0, 1024, 1)
        self.min_row.set_title(_("Minimum file size (MB)"))
        self.min_row.set_value(s.min_size_mb)
        self.min_row.add_prefix(InfoHint(self.window, "min-size"))
        grp.add(self.min_row)
        self.config_box.append(grp)
        self.config_box.append(self._filetypes_section(list(getattr(s, "file_types", []))))
        self.add(self.config_box)

        # scanning view: a percentage ring per source (hidden until a scan runs)
        self.scanning_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.scan_title = Gtk.Label(xalign=0.0)
        self.scan_title.add_css_class("app-page-title")
        self.rings_list = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.scanning_box.append(self.scan_title)
        self.scanning_box.append(self.rings_list)
        self.scanning_box.set_visible(False)
        self.add(self.scanning_box)
        self._rings: dict = {}
        self._pulse_timer: int = 0

        self.status = Gtk.Label(label="", xalign=0.0)
        self.status.add_css_class("app-dim")
        self.status.add_css_class("app-small")
        self.add(self.status)

        c = self.window.controller
        c.connect("scan-started", self._on_started)
        c.connect("progress", self._on_progress)
        c.connect("scan-finished", self._on_finished)
        c.connect("scan-error", self._on_error)

    # --- file-type filter ------------------------------------------------
    def _filetypes_section(self, saved: list[str]) -> Gtk.Widget:
        self._syncing = False
        self._type_checks: dict[Gtk.CheckButton, list[str]] = {}
        self._cat_groups: dict[str, tuple[Gtk.CheckButton, list[Gtk.CheckButton]]] = {}
        saved_set = {e.lower() for e in saved}

        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        card.add_css_class("app-card")
        card.add_css_class("app-savings")              # reuse the comfortable card padding
        title = Gtk.Label(label=_("File types to scan"), xalign=0.0)
        title.add_css_class("app-group-title")
        hint = Gtk.Label(xalign=0.0, wrap=True, label=_(
            "All types are scanned by default. Tick a column's All, or pick individual "
            "types, to limit the scan to just those."))
        hint.add_css_class("app-dim")
        hint.add_css_class("app-small")
        card.append(title)
        card.append(hint)

        # master "All Files" + a custom-extension field, on one row
        toprow = Gtk.Box(spacing=18)
        self._all_files_cb = Gtk.CheckButton(label=_("All Files"))
        self._all_files_cb.add_css_class("app-cat-all")
        self._all_files_cb.set_valign(Gtk.Align.CENTER)
        self._all_files_cb.set_tooltip_text(_(
            "Scan every file, including types not listed below (default)"))
        self._all_files_cb.connect("toggled", self._toggle_all_files)
        toprow.append(self._all_files_cb)

        extbox = Gtk.Box(spacing=8, hexpand=True)
        extbox.set_valign(Gtk.Align.CENTER)
        extlbl = Gtk.Label(label=_("Enter Extension"))
        extlbl.add_css_class("app-small")
        self._ext_entry = Gtk.Entry(hexpand=True)
        self._ext_entry.set_placeholder_text(".bak, .csv, .txt, .idx")
        self._ext_entry.set_text(getattr(self.app.settings, "custom_extensions", ""))
        extbox.append(extlbl)
        extbox.append(self._ext_entry)
        extbox.append(InfoHint(self.window, "custom-extensions"))
        toprow.append(extbox)
        card.append(toprow)

        flow = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE, homogeneous=True,
                           min_children_per_line=1, max_children_per_line=4,
                           column_spacing=20, row_spacing=14)
        for cat in filetypes.CATEGORIES:
            flow.append(self._category_column(cat, saved_set))
        card.append(flow)
        self._recompute_master_states()                # set the All / All Files states
        return card

    def _category_column(self, cat: dict, saved_set: set[str]) -> Gtk.Widget:
        col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        all_cb = Gtk.CheckButton(label=_("All {c}").format(c=cat["label"]))
        all_cb.add_css_class("app-cat-all")
        col.append(all_cb)
        cbs: list[Gtk.CheckButton] = []
        for t in cat["types"]:
            cb = Gtk.CheckButton(label=t["label"])
            cb.set_margin_start(16)
            # default checked; if a saved selection exists, restore from it
            cb.set_active(all(e in saved_set for e in t["exts"]) if saved_set else True)
            self._type_checks[cb] = t["exts"]
            cb.connect("toggled", lambda _c: self._on_type_toggled())
            cbs.append(cb)
            col.append(cb)
        all_cb.connect("toggled", lambda c, k=cat["key"], cbs=cbs: self._toggle_all(k, c, cbs))
        self._cat_groups[cat["key"]] = (all_cb, cbs)
        return col

    def _toggle_all(self, key: str, all_cb: Gtk.CheckButton, cbs: list[Gtk.CheckButton]) -> None:
        if self._syncing:
            return
        self._syncing = True
        if all_cb.get_inconsistent():                  # a click on a mixed box -> select all
            all_cb.set_inconsistent(False)
            all_cb.set_active(True)
        for cb in cbs:
            cb.set_active(all_cb.get_active())
        self._syncing = False
        self._recompute_master_states()

    def _toggle_all_files(self, cb: Gtk.CheckButton) -> None:
        if self._syncing:
            return
        self._syncing = True
        if cb.get_inconsistent():                      # a click on a mixed box -> select all
            cb.set_inconsistent(False)
            cb.set_active(True)
        for tcb in self._type_checks:
            tcb.set_active(cb.get_active())
        self._syncing = False
        self._recompute_master_states()

    def _on_type_toggled(self) -> None:
        if self._syncing:
            return
        self._recompute_master_states()

    def _recompute_master_states(self) -> None:
        """Refresh every column's All and the global All Files to checked / mixed / empty."""
        self._syncing = True
        for _key, (all_cb, cbs) in self._cat_groups.items():
            n = sum(c.get_active() for c in cbs)
            all_cb.set_inconsistent(0 < n < len(cbs))
            all_cb.set_active(n == len(cbs))
        total = len(self._type_checks)
        gn = sum(c.get_active() for c in self._type_checks)
        self._all_files_cb.set_inconsistent(0 < gn < total)
        self._all_files_cb.set_active(gn == total)
        self._syncing = False

    def _custom_extensions(self) -> list[str]:
        """Parse the free-text extension field: comma/space separated, normalized."""
        import re
        text = self._ext_entry.get_text() if hasattr(self, "_ext_entry") else ""
        parts = [p for p in re.split(r"[,\s]+", text.strip()) if p]
        return filetypes.normalize(parts)

    def _selected_file_types(self) -> list[str]:
        """The extensions to scan: the checked types plus any custom extensions. [] = scan all.

        - All Files checked -> [] (everything; custom is a subset of that, so it's moot).
        - Otherwise the checked types UNION the custom field.
        - Nothing checked and nothing custom -> [] (default to all).
        """
        selected: list[str] = []
        all_checked = True
        for cb, exts in self._type_checks.items():
            if cb.get_active():
                selected += exts
            else:
                all_checked = False
        if all_checked:
            return []
        merged = filetypes.normalize(selected + self._custom_extensions())
        return merged if merged else []                # none selected + none custom -> all

    # --- sources ---------------------------------------------------------
    def _sources_section(self) -> Gtk.Widget:
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        card.add_css_class("app-card")
        card.add_css_class("app-savings")
        title = Gtk.Label(label=_("Sources to scan"), xalign=0.0)
        title.add_css_class("app-group-title")
        hint = Gtk.Label(xalign=0.0, wrap=True, label=_(
            "Duplicates are found across every source — a copy on a backup drive and the original "
            "on your disk form one group. The copy on the first-listed (primary) source is kept."))
        hint.add_css_class("app-dim")
        hint.add_css_class("app-small")
        card.append(title)
        card.append(hint)
        self.sources_list = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        card.append(self.sources_list)
        addrow = Gtk.Box(spacing=8)
        addrow.set_margin_top(10)
        add_src = Gtk.Button(label=_("＋ Add source…"))
        add_src.connect("clicked", self._add_source_dialog)
        add_drv = Gtk.Button(label=_("Add drive…"))
        add_drv.connect("clicked", self._add_drive_menu)
        addrow.append(add_src)
        addrow.append(add_drv)
        card.append(addrow)
        self._rebuild_sources()
        return card

    def _rebuild_sources(self) -> None:
        box = self.sources_list
        child = box.get_first_child()
        while child is not None:
            nxt = child.get_next_sibling()
            box.remove(child)
            child = nxt
        if not self.sources:
            empty = Gtk.Label(xalign=0.0, label=_("No sources yet — add a folder or a drive."))
            empty.add_css_class("app-dim")
            empty.add_css_class("app-small")
            empty.set_margin_top(6)
            box.append(empty)
            return
        for i, src in enumerate(self.sources):
            box.append(self._source_row(src, primary=(i == 0)))

    def _source_row(self, path: str, primary: bool) -> Gtk.Widget:
        row = Gtk.Box(spacing=12)
        row.add_css_class("app-source-row")
        ic = icon("app-stat-space-symbolic", 18)
        ic.add_css_class("app-dim")
        nm = Gtk.Label(label=path, xalign=0.0, hexpand=True)
        nm.add_css_class("app-mono")
        nm.add_css_class("app-small")
        nm.set_ellipsize(2)
        meta = Gtk.Label(label=self._source_meta(path, primary))
        meta.add_css_class("app-dim")
        meta.add_css_class("app-small")
        rm = Gtk.Button(label=_("Remove"))
        rm.add_css_class("flat")
        rm.set_valign(Gtk.Align.CENTER)
        rm.connect("clicked", lambda _b, p=path: self._remove_source(p))
        row.append(ic)
        row.append(nm)
        row.append(meta)
        row.append(rm)
        return row

    def _source_meta(self, path: str, primary: bool) -> str:
        import shutil
        parts = [_("primary")] if primary else []
        try:
            parts.append(human_bytes(shutil.disk_usage(path).total))
        except Exception:
            pass
        return " · ".join(parts)

    def _add_source(self, path: str) -> None:
        if not path:
            return
        p = path.rstrip("/") or "/"
        if p not in [s.rstrip("/") for s in self.sources]:
            self.sources.append(p)
            self._rebuild_sources()

    def _remove_source(self, path: str) -> None:
        self.sources = [s for s in self.sources if s.rstrip("/") != path.rstrip("/")]
        self._rebuild_sources()

    def _add_source_dialog(self, _btn) -> None:
        dialog = Gtk.FileDialog(title=_("Add a folder to scan"))
        dialog.select_folder(self.window, None, self._source_chosen)

    def _source_chosen(self, dialog, result) -> None:
        try:
            folder = dialog.select_folder_finish(result)
        except Exception:
            return
        if folder is not None:
            self._add_source(folder.get_path())

    def _detect_mounts(self) -> list:
        out: list = []
        seen: set = set()

        def add(label: str, path: str) -> None:
            p = (path or "").rstrip("/")
            if p and p not in seen:
                seen.add(p)
                out.append((label, p))

        try:
            from gi.repository import Gio
            for m in Gio.VolumeMonitor.get().get_mounts():
                r = m.get_root()
                p = r.get_path() if r is not None else None
                if p:
                    add(m.get_name() or os.path.basename(p) or p, p)
        except Exception:
            pass
        from pathlib import Path
        add(_("Home"), str(Path.home()))
        return out

    def _add_drive_menu(self, btn) -> None:
        pop = Gtk.Popover()
        pop.set_parent(btn)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        box.set_margin_top(4)
        box.set_margin_bottom(4)
        box.set_margin_start(4)
        box.set_margin_end(4)
        have = {s.rstrip("/") for s in self.sources}
        added = 0
        for label, path in self._detect_mounts():
            if path in have:
                continue
            b = Gtk.Button()
            b.add_css_class("flat")
            lbl = Gtk.Label(label=f"{label}  —  {path}", xalign=0.0)
            lbl.add_css_class("app-small")
            b.set_child(lbl)
            b.connect("clicked", lambda _b, p=path: (self._add_source(p), pop.popdown()))
            box.append(b)
            added += 1
        if not added:
            none = Gtk.Label(label=_("No other drives detected."), xalign=0.0)
            none.add_css_class("app-dim")
            none.add_css_class("app-small")
            none.set_margin_start(6)
            none.set_margin_end(6)
            box.append(none)
        pop.set_child(box)
        pop.connect("closed", lambda p: p.unparent())
        pop.popup()

    # --- controls --------------------------------------------------------
    def _on_tier(self, btn: Gtk.ToggleButton) -> None:
        if btn.get_active():
            self.tier = TIER_SIMPLE if btn is self.btn_simple else TIER_ADVANCED

    def _options(self) -> ScanOptions:
        s = self.app.settings
        return ScanOptions(
            roots=list(self.sources),
            root=self.sources[0] if self.sources else "",
            tier=self.tier,
            find_images=self.sw_images.get_active(),
            include_hidden=self.sw_hidden.get_active(),
            min_size=max(1, int(self.min_row.get_value()) * 1_000_000),
            hamming=s.hamming,
            use_hash_cache=getattr(s, "use_hash_cache", True),
            detect_backups=s.detect_backups,
            keep_newest_backup=s.keep_newest_backup,
            exclusions=list(s.exclusions),
            exclude=list(getattr(s, "custom_excludes", [])),
            file_types=self._selected_file_types(),
            ignore_paths=list(getattr(s, "ignored_paths", [])),
            ignore_dirs=list(getattr(s, "ignored_folders", [])),
            advanced_similar=(self.tier == TIER_ADVANCED),
            similar_threshold=s.similar_threshold,
        )

    def _on_run_clicked(self, _btn) -> None:
        if self.window.controller.running:
            self.window.controller.cancel()
            return
        if not self.sources:
            self.window.toast(_("Add at least one source to scan."))
            self._add_source_dialog(None)
            return
        s = self.app.settings
        s.tier = self.tier
        s.roots = list(self.sources)
        s.last_root = self.sources[0]
        s.find_images = self.sw_images.get_active()
        s.include_hidden = self.sw_hidden.get_active()
        s.min_size_mb = max(1, int(self.min_row.get_value()))
        s.file_types = self._selected_file_types()
        s.custom_extensions = self._ext_entry.get_text().strip()
        s.save()
        self.window.start_scan(self._options())

    # --- controller signals: per-source ring rows -----------------------
    def _scan_row(self, src: str):
        """One list row: ring (left) + full path / file name / per-file activity bar / note."""
        row = Gtk.Box(spacing=16)
        row.add_css_class("app-ring-card")
        ring = RingLoader(84)
        ring.set_valign(Gtk.Align.CENTER)
        row.append(ring)

        col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2, hexpand=True)
        col.set_valign(Gtk.Align.CENTER)
        path = Gtk.Label(label=src, xalign=0.0)
        path.add_css_class("app-mono")
        path.add_css_class("app-small")
        path.set_ellipsize(2)                       # middle-ellipsize only if it overflows
        name = Gtk.Label(label="", xalign=0.0)
        name.add_css_class("app-group-title")
        name.set_ellipsize(3)
        bar = Gtk.ProgressBar()
        bar.add_css_class("app-activity")
        bar.set_hexpand(False)                      # half width, left-aligned
        bar.set_halign(Gtk.Align.START)
        bar.set_size_request(360, -1)
        bar.set_margin_top(6)
        bar.set_margin_bottom(3)
        note = Gtk.Label(xalign=0.0, label=_("Note: large files may take several minutes to scan…"))
        note.add_css_class("app-dim")
        note.add_css_class("app-small")
        col.append(path)
        col.append(name)
        col.append(bar)
        col.append(note)
        row.append(col)
        return row, ring, path, name, bar

    def _on_started(self, _c, root: str) -> None:
        self.run_btn.set_label(_("Stop"))
        self.run_btn.remove_css_class("suggested-action")
        self.run_btn.add_css_class("destructive-action")
        self.status.set_text("")
        box = self.rings_list
        child = box.get_first_child()
        while child is not None:
            nxt = child.get_next_sibling()
            box.remove(child)
            child = nxt
        self._rings = {}
        srcs = self.sources or [root]
        self.scan_title.set_text(_("Scanning {n} source{p}…").format(
            n=len(srcs), p="" if len(srcs) == 1 else "s"))
        for src in srcs:
            row, ring, path, name, bar = self._scan_row(src)
            ring.start()
            name.set_text(_("Queued"))
            self._rings[src.rstrip("/")] = (ring, path, name, bar)
            box.append(row)
        self.config_box.set_visible(False)
        self.scanning_box.set_visible(True)
        if not self._pulse_timer:               # steady fallback pulse so bars never look frozen
            self._pulse_timer = GLib.timeout_add(250, self._pulse_bars)

    def _pulse_bars(self) -> bool:
        for _ring, _path, _name, bar in self._rings.values():
            bar.pulse()
        return True

    def _on_progress(self, _c, fraction: float, phase: str, detail: str, source: str) -> None:
        if not source:                     # overall progress is shown on Results; rows are per-source
            return
        entry = self._rings.get(source.rstrip("/"))
        if entry is None:
            return
        ring, path, name, bar = entry
        ring.set_progress(fraction, phase)
        bar.pulse()                         # a file event: quick motion for small files
        if detail:
            path.set_text(detail)
            base = os.path.basename(detail)
            if base:
                name.set_text(base)
            elif phase != "walk":
                name.set_text(_("Analyzing…"))

    def _stop_pulse(self) -> None:
        if self._pulse_timer:
            GLib.source_remove(self._pulse_timer)
            self._pulse_timer = 0

    def _on_finished(self, _c, fin) -> None:
        self.run_btn.set_label(_("Start scan"))
        self.run_btn.remove_css_class("destructive-action")
        self.run_btn.add_css_class("suggested-action")
        self._stop_pulse()
        if fin.cancelled:
            self.status.set_text(_("Scan cancelled."))
            self._restore_after_scan(go_results=False)
            return
        # Keep EVERY ring visible until the whole scan is done: settle each at 100%, mark the row
        # Done, then — after a brief hold — fade them ALL together and reveal the results.
        for ring, path, name, bar in self._rings.values():
            ring.set_progress(1.0, "done")
            name.set_text(_("Done"))
            bar.set_fraction(1.0)
        GLib.timeout_add(650, lambda: (self._fade_rings_and_show(), False)[1])

    def _fade_rings_and_show(self) -> None:
        box = self.scanning_box
        state = {"o": 1.0}

        def step() -> bool:
            state["o"] -= 0.08
            box.set_opacity(max(0.0, state["o"]))
            if state["o"] <= 0.0:
                box.set_opacity(1.0)
                self._restore_after_scan(go_results=True)
                return False
            return True
        GLib.timeout_add(25, step)

    def _restore_after_scan(self, go_results: bool) -> None:
        self._stop_pulse()
        for ring, _path, _name, _bar in self._rings.values():
            ring.hide()
        self.scanning_box.set_visible(False)
        self.config_box.set_visible(True)
        if go_results:
            self.window.show_page("results")

    def _on_error(self, _c, message: str, fix: str, path: str) -> None:
        self.status.set_text(f"{message} {fix}".strip())
