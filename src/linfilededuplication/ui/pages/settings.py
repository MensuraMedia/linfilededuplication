"""Settings: appearance, matching thresholds, safety."""
from __future__ import annotations

from gi.repository import Adw, Gtk

from linfilededuplication.core import exclusions
from linfilededuplication.i18n import _
from linfilededuplication.ui.pages.base import BasePage
from linfilededuplication.ui.widgets.info_hint import InfoHint

_STYLES = ["system", "light", "dark"]
_ACTIONS = ["trash", "hardlink"]
_PRESET_HINT = {"system": "system-file", "caches": "cache", "build": "package-artifact",
                "vcs": "exclusions", "apps": "exclusions", "stubs": "exclusions", "trash": "trash"}


class SettingsPage(BasePage):
    page_id = "settings"
    title = _("Settings")

    def build_content(self) -> None:
        s = self.app.settings
        self.add_heading(_("Settings"))

        appearance = Adw.PreferencesGroup(title=_("Appearance"))
        self.style_row = Adw.ComboRow(title=_("Theme"))
        self.style_row.set_model(Gtk.StringList.new([_("System"), _("Light"), _("Dark")]))
        self.style_row.set_selected(_STYLES.index(s.style) if s.style in _STYLES else 0)
        self.style_row.connect("notify::selected", self._on_style)
        appearance.add(self.style_row)
        self.add(appearance)

        matching = Adw.PreferencesGroup(
            title=_("Matching"), description=_("Applied to Advanced Scan"))
        self.hamming_row = Adw.SpinRow.new_with_range(0, 64, 1)
        self.hamming_row.set_title(_("Image similarity (max Hamming distance)"))
        self.hamming_row.set_subtitle(_("Lower is stricter · 8 of 64 bits is a good default"))
        self.hamming_row.set_value(s.hamming)
        self.hamming_row.connect("notify::value", self._on_hamming)
        matching.add(self.hamming_row)
        self.add(matching)

        scanning = Adw.PreferencesGroup(
            title=_("Scanning"),
            description=_("Speed and multi-source behaviour."))
        self.cache_row = Adw.SwitchRow(
            title=_("Reuse hashes for unchanged files"),
            subtitle=_("A hash cache skips re-reading files that haven't changed, so repeat and "
                       "cross-source scans finish much faster"))
        self.cache_row.set_active(getattr(s, "use_hash_cache", True))
        self.cache_row.connect("notify::active", self._on_cache)
        scanning.add(self.cache_row)
        self.primary_row = Adw.SwitchRow(
            title=_("Keep the primary source across drives"),
            subtitle=_("When equal copies are on different sources, keep the one on the "
                       "first-listed source and remove the copy on the others"))
        self.primary_row.set_active(getattr(s, "keep_primary_source", True))
        self.primary_row.connect("notify::active", self._on_primary)
        scanning.add(self.primary_row)
        self.add(scanning)

        safety = Adw.PreferencesGroup(title=_("Safety"))
        self.action_row = Adw.ComboRow(title=_("Default action for extras"))
        self.action_row.set_model(Gtk.StringList.new([_("Move to Trash"), _("Hard-link")]))
        self.action_row.set_selected(_ACTIONS.index(s.default_action) if s.default_action in _ACTIONS else 0)
        self.action_row.connect("notify::selected", self._on_action)
        safety.add(self.action_row)
        self.dry_row = Adw.SwitchRow(title=_("Dry-run preview"),
                                     subtitle=_("Always review before applying"))
        self.dry_row.set_active(s.dry_run)
        self.dry_row.connect("notify::active", self._on_dry)
        safety.add(self.dry_row)
        self.add(safety)

        backups = Adw.PreferencesGroup(title=_("Backups"))
        self.backup_row = Adw.SwitchRow(title=_("Flag probable backups"),
                                        subtitle=_("Mark older saved copies so you can clear stale ones"))
        self.backup_row.set_active(s.detect_backups)
        self.backup_row.add_prefix(InfoHint(self.window, "backup-file"))
        self.backup_row.connect("notify::active", self._on_backup)
        backups.add(self.backup_row)
        self.newest_row = Adw.SwitchRow(title=_("For backups, keep the newest"),
                                        subtitle=_("Suggest keeping the most recent copy"))
        self.newest_row.set_active(s.keep_newest_backup)
        self.newest_row.add_prefix(InfoHint(self.window, "newest-older"))
        self.newest_row.connect("notify::active", self._on_newest)
        backups.add(self.newest_row)
        self.add(backups)

        scope = Adw.PreferencesGroup(
            title=_("Scan scope"),
            description=_("Skip files an app or the OS can recreate. Excluded paths are never removed."))
        self._preset_rows = {}
        for key in exclusions.PRESETS:
            row = Adw.SwitchRow(title=exclusions.preset_label(key))
            row.set_active(key in s.exclusions)
            row.add_prefix(InfoHint(self.window, _PRESET_HINT.get(key, "exclusions")))
            row.connect("notify::active", self._on_preset, key)
            self._preset_rows[key] = row
            scope.add(row)
        self.add(scope)

    def _save(self) -> None:
        self.app.settings.save()

    def _on_style(self, *_a) -> None:
        style = _STYLES[self.style_row.get_selected()]
        self.app.settings.style = style
        self.app.theme.apply(style)
        self._save()

    def _on_hamming(self, *_a) -> None:
        self.app.settings.hamming = int(self.hamming_row.get_value())
        self._save()

    def _on_action(self, *_a) -> None:
        self.app.settings.default_action = _ACTIONS[self.action_row.get_selected()]
        self._save()

    def _on_dry(self, *_a) -> None:
        self.app.settings.dry_run = self.dry_row.get_active()
        self._save()

    def _on_cache(self, *_a) -> None:
        self.app.settings.use_hash_cache = self.cache_row.get_active()
        self._save()

    def _on_primary(self, *_a) -> None:
        self.app.settings.keep_primary_source = self.primary_row.get_active()
        self._save()

    def _on_backup(self, *_a) -> None:
        self.app.settings.detect_backups = self.backup_row.get_active()
        self._save()

    def _on_newest(self, *_a) -> None:
        self.app.settings.keep_newest_backup = self.newest_row.get_active()
        self._save()

    def _on_preset(self, row, _p, key) -> None:
        current = set(self.app.settings.exclusions)
        if row.get_active():
            current.add(key)
        else:
            current.discard(key)
        # preserve preset order
        self.app.settings.exclusions = [k for k in exclusions.PRESETS if k in current]
        self._save()
