"""Settings: appearance, matching thresholds, safety."""
from __future__ import annotations

from gi.repository import Adw, Gtk

from linfilededuplication.i18n import _
from linfilededuplication.ui.pages.base import BasePage

_STYLES = ["system", "light", "dark"]
_ACTIONS = ["trash", "hardlink"]


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
