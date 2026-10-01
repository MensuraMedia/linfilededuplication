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

        if self._occupied <= 0:
            return
        after = self._occupied - self._freed

        pad = 8.0
        label_w = 118.0                        # row label on the left
        value_w = 92.0                         # byte value on the right
        bar_x = pad + label_w
        bar_w = max(40.0, w - bar_x - value_w - pad)
        bar_h = 22.0
        gap = 30.0
        top = 16.0

        def text(s, x, y, color, *, bold=False, size=10.5, align_right_to=None):
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
            cr.set_source_rgb(*color)
            cr.move_to(tx, ty)
            PangoCairo.show_layout(cr, layout)
            cr.restore()

        def meter(y, label, frac, fill_rgb, value_str):
            text(label, pad, y + bar_h / 2, (fg[0] * 0.78, fg[1] * 0.78, fg[2] * 0.82))
            # recessed track: dark well, square corners (no rounding, no gridlines)
            cr.set_source_rgb(0.082, 0.090, 0.106)
            cr.rectangle(bar_x, y, bar_w, bar_h); cr.fill()
            # filled portion
            fw = max(0.0, bar_w * max(0.0, min(1.0, frac)))
            if fw > 1:
                cr.set_source_rgb(*fill_rgb)
                cr.rectangle(bar_x, y, fw, bar_h); cr.fill()
            # inset border
            cr.set_source_rgba(1, 1, 1, 0.14); cr.set_line_width(1.0)
            cr.rectangle(bar_x + 0.5, y + 0.5, bar_w - 1, bar_h - 1); cr.stroke()
            text(value_str, 0, y + bar_h / 2, fg, align_right_to=w - pad, bold=True)

        occ = float(self._occupied)
        meter(top, _("Now"), 1.0, accent, human_bytes(self._occupied))
        meter(top + bar_h + gap, _("After cleanup"), after / occ, success, human_bytes(after))
