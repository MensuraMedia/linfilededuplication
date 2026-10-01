"""SpaceChart: a before/after bar chart of disk space for a scan result.

Two horizontal bars: "Now" (the total footprint of every duplicate) and "After cleanup"
(the keepers that remain), with the freed portion highlighted on the second bar. Drawn with
Cairo + Pango so it is crisp at any width and follows the theme's accent/success/text colours.
"""
from __future__ import annotations

import cairo
from gi.repository import Gtk, Pango, PangoCairo

from linfilededuplication.core.units import human_bytes
from linfilededuplication.i18n import _

_ACCENT = (0.208, 0.518, 0.894)       # #3584e4
_SUCCESS = (0.180, 0.700, 0.380)      # green
_TRACK = (0.5, 0.5, 0.55)


class SpaceChart(Gtk.DrawingArea):
    def __init__(self) -> None:
        super().__init__()
        self._occupied = 0
        self._freed = 0
        self.set_content_height(120)
        self.set_hexpand(True)
        self.set_draw_func(self._draw)

    def set_values(self, occupied_bytes: int, freed_bytes: int) -> None:
        """occupied = all duplicate copies; freed = reclaimable (non-keepers)."""
        self._occupied = max(0, int(occupied_bytes))
        self._freed = max(0, min(int(freed_bytes), self._occupied))
        self.queue_draw()

    # --- theme colours ---------------------------------------------------
    def _color(self, *names, fallback):
        ctx = self.get_style_context()
        for name in names:
            found, rgba = ctx.lookup_color(name)
            if found:
                return (rgba.red, rgba.green, rgba.blue)
        return fallback

    def _draw(self, _area, cr, w: int, h: int) -> None:
        accent = self._color("accent_bg_color", "accent_color", fallback=_ACCENT)
        success = self._color("success_color", "app-success", fallback=_SUCCESS)
        fg = self._color("window_fg_color", "theme_fg_color", fallback=(0.9, 0.9, 0.92))
        track = self._color("headerbar_shade_color", fallback=_TRACK)

        if self._occupied <= 0:
            return
        after = self._occupied - self._freed

        pad = 8.0
        label_w = 118.0                        # space for the row label on the left
        value_w = 96.0                         # space for the byte value on the right
        bar_x = pad + label_w
        bar_w = max(40.0, w - bar_x - value_w - pad)
        bar_h = 26.0
        gap = 26.0
        top = 14.0

        def rrect(x, y, width, height, r):
            r = min(r, height / 2, width / 2)
            cr.new_sub_path()
            cr.arc(x + width - r, y + r, r, -1.5708, 0)
            cr.arc(x + width - r, y + height - r, r, 0, 1.5708)
            cr.arc(x + r, y + height - r, r, 1.5708, 3.1416)
            cr.arc(x + r, y + r, r, 3.1416, 4.7124)
            cr.close_path()

        def text(s, x, y, color, *, bold=False, size=10.5, align_right_to=None, dim=False):
            layout = PangoCairo.create_layout(cr)
            desc = Pango.FontDescription()
            desc.set_family("Sans")
            desc.set_size(int(size * Pango.SCALE))
            desc.set_weight(Pango.Weight.BOLD if bold else Pango.Weight.NORMAL)
            layout.set_font_description(desc)
            layout.set_text(s, -1)
            _ink, logical = layout.get_pixel_extents()
            ty = y - logical.height / 2
            tx = x if align_right_to is None else align_right_to - logical.width
            cr.save()
            cr.set_source_rgba(color[0], color[1], color[2], 0.6 if dim else 1.0)
            cr.move_to(tx, ty)
            PangoCairo.show_layout(cr, layout)
            cr.restore()

        def bar_row(y, label, fill_frac, fill_rgb, value_str, *, freed_frac=0.0):
            text(label, pad, y + bar_h / 2, fg)
            # track
            cr.set_source_rgba(track[0], track[1], track[2], 0.22)
            rrect(bar_x, y, bar_w, bar_h, 6); cr.fill()
            # filled portion (kept / now)
            fw = max(0.0, bar_w * fill_frac)
            if fw > 1:
                cr.set_source_rgba(fill_rgb[0], fill_rgb[1], fill_rgb[2], 0.95)
                rrect(bar_x, y, fw, bar_h, 6); cr.fill()
            # freed portion (hatched-light accent) sitting after the kept portion
            if freed_frac > 0:
                fx = bar_x + bar_w * (fill_frac)
                ww = bar_w * freed_frac
                cr.set_source_rgba(accent[0], accent[1], accent[2], 0.28)
                rrect(fx, y, ww, bar_h, 6); cr.fill()
            text(value_str, 0, y + bar_h / 2, fg, align_right_to=w - pad, bold=True)

        occ = float(self._occupied)
        # Row 1 — Now: the full current footprint (scaled to the full bar).
        bar_row(top, _("Now"), 1.0, accent, human_bytes(self._occupied))
        # Row 2 — After cleanup: keepers remain (green); the freed slice is highlighted.
        bar_row(top + bar_h + gap, _("After cleanup"), after / occ, success,
                human_bytes(after), freed_frac=self._freed / occ)
