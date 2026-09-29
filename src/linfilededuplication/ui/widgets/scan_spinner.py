"""RadarSpinner: a rotating 'radar sweep' shown while a scan runs.

A Cairo DrawingArea that draws a faint ring, a rotating beam with a soft trailing wedge, and a
centre dot, in the current accent colour. Rendered live (crisp at any size, transparent, theme-
aware) and rotated with the frame clock, so it reads as an active scan.
"""
from __future__ import annotations

import math

import cairo
from gi.repository import Gtk

_ACCENT_FALLBACK = (0.208, 0.518, 0.894)      # #3584e4
_TURN_SECONDS = 1.4                            # one full rotation


class RadarSpinner(Gtk.DrawingArea):
    def __init__(self, size: int = 60) -> None:
        super().__init__()
        self.set_content_width(size)
        self.set_content_height(size)
        self._angle = 0.0
        self._tick = 0
        self._last = 0
        self.set_draw_func(self._draw)
        self.set_visible(False)

    def start(self) -> None:
        self.set_visible(True)
        self._last = 0
        if not self._tick:
            self._tick = self.add_tick_callback(self._on_tick)

    def stop(self) -> None:
        self.set_visible(False)
        if self._tick:
            self.remove_tick_callback(self._tick)
            self._tick = 0

    def _on_tick(self, _widget, clock) -> bool:
        t = clock.get_frame_time()             # microseconds
        if self._last:
            dt = (t - self._last) / 1_000_000
            self._angle = (self._angle + dt * (360.0 / _TURN_SECONDS)) % 360.0
        self._last = t
        self.queue_draw()
        return True

    def _accent(self) -> tuple[float, float, float]:
        ctx = self.get_style_context()
        for name in ("accent_color", "accent_bg_color"):
            found, rgba = ctx.lookup_color(name)
            if found:
                return (rgba.red, rgba.green, rgba.blue)
        return _ACCENT_FALLBACK

    def _draw(self, _area, cr, w: int, h: int) -> None:
        cx, cy = w / 2, h / 2
        lw = max(2.0, w * 0.075)
        r = min(w, h) / 2 - lw
        ar, ag, ab = self._accent()
        ang = math.radians(self._angle)

        cr.set_line_width(lw * 0.8)            # faint ring
        cr.set_source_rgba(ar, ag, ab, 0.28)
        cr.arc(cx, cy, r, 0, 2 * math.pi)
        cr.stroke()

        cr.set_source_rgba(ar, ag, ab, 0.16)   # trailing wedge
        cr.move_to(cx, cy)
        cr.arc(cx, cy, r, ang - math.radians(72), ang)
        cr.close_path()
        cr.fill()

        cr.set_line_width(lw * 0.6)            # sweep beam
        cr.set_line_cap(cairo.LINE_CAP_ROUND)
        cr.set_source_rgba(ar, ag, ab, 0.95)
        cr.move_to(cx, cy)
        cr.line_to(cx + r * math.cos(ang), cy + r * math.sin(ang))
        cr.stroke()

        for (px, py) in ((cx + r * math.cos(ang), cy + r * math.sin(ang)), (cx, cy)):
            cr.arc(px, py, lw * 0.55, 0, 2 * math.pi)
            cr.fill()
