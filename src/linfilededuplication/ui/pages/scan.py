"""Scan: choose a folder and tier, set options, run, watch progress."""
from __future__ import annotations

from gi.repository import Adw, Gtk

from linfilededuplication.core import filetypes
from linfilededuplication.core.options import TIER_ADVANCED, TIER_SIMPLE, ScanOptions
from linfilededuplication.i18n import _
from linfilededuplication.ui.pages.base import BasePage
from linfilededuplication.ui.widgets.info_hint import InfoHint


class ScanPage(BasePage):
    page_id = "scan"
    title = _("Scan")

    def build_content(self) -> None:
        s = self.app.settings
        self.tier = s.tier
        self.root = s.last_root

        self.add_heading(_("Scan"), _("Read-only — nothing is changed until you confirm."))

        # tier toggle
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
        self.add(toggle_box)

        # folder + options
        grp = Adw.PreferencesGroup()
        self.folder_row = Adw.ActionRow(title=_("Folder to scan"),
                                        subtitle=self.root or _("No folder chosen"))
        choose = Gtk.Button(label=_("Choose…"), valign=Gtk.Align.CENTER)
        choose.connect("clicked", self._choose_folder)
        self.folder_row.add_suffix(choose)
        grp.add(self.folder_row)

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
        self.add(grp)

        # file-type filter (columns of popular types, each with an "All")
        self.add(self._filetypes_section(list(getattr(s, "file_types", []))))

        # run + progress
        self.run_btn = Gtk.Button(label=_("Start scan"))
        self.run_btn.add_css_class("suggested-action")
        self.run_btn.add_css_class("pill")
        self.run_btn.set_halign(Gtk.Align.START)
        self.run_btn.connect("clicked", self._on_run_clicked)
        self.add(self.run_btn)

        self.progress = Gtk.ProgressBar()
        self.progress.add_css_class("app-progress")
        self.progress.set_visible(False)
        self.add(self.progress)
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

        flow = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE, homogeneous=True,
                           min_children_per_line=1, max_children_per_line=4,
                           column_spacing=20, row_spacing=14)
        for cat in filetypes.CATEGORIES:
            flow.append(self._category_column(cat, saved_set))
        card.append(flow)
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
            cb.connect("toggled", lambda _c, k=cat["key"]: self._sync_cat(k))
            cbs.append(cb)
            col.append(cb)
        all_cb.connect("toggled", lambda c, cbs=cbs: self._toggle_all(c, cbs))
        self._cat_groups[cat["key"]] = (all_cb, cbs)
        self._sync_cat(cat["key"])                     # set All's initial (checked/mixed)
        return col

    def _toggle_all(self, all_cb: Gtk.CheckButton, cbs: list[Gtk.CheckButton]) -> None:
        if self._syncing:
            return
        self._syncing = True
        if all_cb.get_inconsistent():                  # a click on a mixed box -> select all
            all_cb.set_inconsistent(False)
            all_cb.set_active(True)
        for cb in cbs:
            cb.set_active(all_cb.get_active())
        self._syncing = False

    def _sync_cat(self, key: str) -> None:
        if self._syncing:
            return
        all_cb, cbs = self._cat_groups[key]
        n = sum(cb.get_active() for cb in cbs)
        self._syncing = True
        all_cb.set_inconsistent(0 < n < len(cbs))
        all_cb.set_active(n == len(cbs))
        self._syncing = False

    def _selected_file_types(self) -> list[str]:
        """Selected extensions, or [] when everything is checked (= scan all types)."""
        selected: list[str] = []
        all_checked = True
        for cb, exts in self._type_checks.items():
            if cb.get_active():
                selected += exts
            else:
                all_checked = False
        if all_checked or not selected:                # all or (defensively) none -> no filter
            return []
        return filetypes.normalize(selected)

    # --- controls --------------------------------------------------------
    def _on_tier(self, btn: Gtk.ToggleButton) -> None:
        if btn.get_active():
            self.tier = TIER_SIMPLE if btn is self.btn_simple else TIER_ADVANCED

    def _choose_folder(self, _btn) -> None:
        dialog = Gtk.FileDialog(title=_("Choose a folder to scan"))
        dialog.select_folder(self.window, None, self._folder_chosen)

    def _folder_chosen(self, dialog, result) -> None:
        try:
            folder = dialog.select_folder_finish(result)
        except Exception:
            return
        if folder is not None:
            self.root = folder.get_path()
            self.folder_row.set_subtitle(self.root)

    def _options(self) -> ScanOptions:
        s = self.app.settings
        return ScanOptions(
            root=self.root,
            tier=self.tier,
            find_images=self.sw_images.get_active(),
            include_hidden=self.sw_hidden.get_active(),
            min_size=max(1, int(self.min_row.get_value()) * 1_000_000),
            hamming=s.hamming,
            detect_backups=s.detect_backups,
            keep_newest_backup=s.keep_newest_backup,
            exclusions=list(s.exclusions),
            exclude=list(getattr(s, "custom_excludes", [])),
            file_types=self._selected_file_types(),
            advanced_similar=(self.tier == TIER_ADVANCED),
            similar_threshold=s.similar_threshold,
        )

    def _on_run_clicked(self, _btn) -> None:
        if self.window.controller.running:
            self.window.controller.cancel()
            return
        if not self.root:
            self.window.toast(_("Choose a folder to scan first."))
            self._choose_folder(None)
            return
        # persist choices
        s = self.app.settings
        s.tier, s.last_root = self.tier, self.root
        s.find_images = self.sw_images.get_active()
        s.include_hidden = self.sw_hidden.get_active()
        s.min_size_mb = max(1, int(self.min_row.get_value()))
        s.file_types = self._selected_file_types()
        s.save()
        self.window.start_scan(self._options())

    # --- controller signals ---------------------------------------------
    def _on_started(self, _c, root: str) -> None:
        self.run_btn.set_label(_("Stop"))
        self.run_btn.remove_css_class("suggested-action")
        self.run_btn.add_css_class("destructive-action")
        self.progress.set_visible(True)
        self.progress.set_fraction(0.0)
        self.status.set_text(_("Scanning {root}…").format(root=root))

    def _on_progress(self, _c, fraction: float, phase: str, detail: str) -> None:
        self.progress.set_fraction(min(1.0, max(0.0, fraction)))
        if detail:
            self.status.set_text(detail)

    def _on_finished(self, _c, fin) -> None:
        self.run_btn.set_label(_("Start scan"))
        self.run_btn.remove_css_class("destructive-action")
        self.run_btn.add_css_class("suggested-action")
        self.progress.set_visible(False)
        if fin.cancelled:
            self.status.set_text(_("Scan cancelled."))
        else:
            self.status.set_text(
                _("Found {g} groups · {n} files scanned").format(g=fin.groups, n=fin.files_scanned))

    def _on_error(self, _c, message: str, fix: str, path: str) -> None:
        self.status.set_text(f"{message} {fix}".strip())
