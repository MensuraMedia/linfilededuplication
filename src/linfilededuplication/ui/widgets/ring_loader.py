"""RingLoader: a circular percentage loader shown while a scan runs.

A Cairo DrawingArea that draws a dark track ring, a red→orange progress arc sweeping from the
top, and the percentage in the centre. The scan runs in phases of unknown total size, so the
value is mapped (walk → ~0-12%, hashing → up to ~75%, images/similar → up to 100%) and eased
frame-to-frame so it animates smoothly; the walk phase creeps while files are still being found.
"""
from __future__ import annotations

import math

import cairo
from gi.repository import GLib, Gtk, Pango, PangoCairo

_RED = (0.996, 0.231, 0.306)        # #FE3B4E
_ORANGE = (1.0, 0.616, 0.173)       # #FF9E2C
_FG = (0.933, 0.941, 0.949)         # centre text


def _lerp(a, b, t):
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t)


class RingLoader(Gtk.DrawingArea):
    def __init__(self, size: int = 150) -> None:
        super().__init__()
        self.set_content_width(size)
        self.set_content_height(size)
        self._shown = 0.0              # eased, drawn value
        self._target = 0.0             # where we're heading
        self._indeterminate = True     # walk phase: creep slowly
        self._tick = 0
        self._last = 0
        self.set_draw_func(self._draw)
        self.set_visible(False)

    # --- lifecycle (same interface as the old RadarSpinner) --------------
    def start(self) -> None:
        self._shown = self._target = 0.0
        self._indeterminate = True
        self._last = 0
        self.set_opacity(1.0)
        self.set_visible(True)
        if not self._tick:
            self._tick = self.add_tick_callback(self._on_tick)

    def complete(self, on_done=None) -> None:
        """Fill to 100%, hold a beat, fade out, then call ``on_done`` — so results are shown
        only after the loader visibly completes and disappears."""
        self._indeterminate = False
        self._target = 1.0

        def wait_full() -> bool:
            if not self.get_visible():
                return False
            if self._shown >= 0.995:                 # reached 100% on screen
                GLib.timeout_add(320, lambda: (self._fade_out(on_done), False)[1])
                return False
            return True
        GLib.timeout_add(50, wait_full)

    def _fade_out(self, on_done) -> None:
        self._fade = 1.0

        def step() -> bool:
            self._fade -= 0.09
            self.set_opacity(max(0.0, self._fade))
            if self._fade <= 0.0:
                self.hide()
                self.set_opacity(1.0)                 # reset for the next scan
                if on_done:
                    on_done()
                return False
            return True
        GLib.timeout_add(25, step)

    def stop(self) -> None:
        self.hide()

    def hide(self) -> None:
        self.set_visible(False)
        if self._tick:
            self.remove_tick_callback(self._tick)
            self._tick = 0

    # --- progress --------------------------------------------------------
    def set_progress(self, fraction: float, phase: str) -> None:
        """``fraction`` is the TRUE overall ratio (files processed / total work) emitted by the
        scanner; the ring shows it directly. The walk phase has no known total, so it stays
        indeterminate (a slow creep) until real per-file progress begins."""
        fraction = max(0.0, min(1.0, float(fraction)))
        if phase == "walk" and fraction < 1.0:
            self._indeterminate = True                   # still enumerating; total unknown
        else:
            self._indeterminate = False
            self._target = max(self._target, fraction)   # accurate, monotonic

    # --- animation -------------------------------------------------------
    def _on_tick(self, _widget, clock) -> bool:
        t = clock.get_frame_time() / 1_000_000
        dt = (t - self._last) if self._last else 0.0
        self._last = t
        if self._indeterminate:                          # creep while walking (total unknown)
            self._target = min(0.08, self._target + dt * 0.04)
        self._shown += (self._target - self._shown) * min(1.0, dt * 6.0)
        self.queue_draw()
        return True

    # --- drawing ---------------------------------------------------------
    def _draw(self, _area, cr, w: int, h: int) -> None:
        cx, cy = w / 2.0, h / 2.0
        lw = max(6.0, w * 0.085)
        radius = min(w, h) / 2.0 - lw / 2.0 - 2.0
        frac = max(0.0, min(1.0, self._shown))

        cr.set_line_cap(cairo.LineCap.ROUND)
        cr.set_line_width(lw)
        # track
        cr.set_source_rgba(1, 1, 1, 0.10)
        cr.arc(cx, cy, radius, 0, 2 * math.pi)
        cr.stroke()

        # progress arc, red (top) -> orange (tail), drawn in short segments for the gradient
        if frac > 0.004:
            start = -math.pi / 2.0
            total = frac * 2 * math.pi
            segs = max(2, int(total / 0.09))
            for i in range(segs):
                a0 = start + total * (i / segs)
                a1 = start + total * ((i + 1) / segs)
                col = _lerp(_RED, _ORANGE, i / (segs - 1) if segs > 1 else 0)
                cr.set_source_rgb(*col)
                cr.arc(cx, cy, radius, a0, a1 + 0.02)    # slight overlap hides seams
                cr.stroke()

        # centre percentage
        layout = PangoCairo.create_layout(cr)
        desc = Pango.FontDescription()
        desc.set_family("Sans")
        desc.set_size(int(w * 0.17 * Pango.SCALE))
        desc.set_weight(Pango.Weight.NORMAL)
        layout.set_font_description(desc)
        layout.set_text(f"{int(round(frac * 100))} %", -1)
        _ink, logical = layout.get_pixel_extents()
        cr.set_source_rgb(*_FG)
        cr.move_to(cx - logical.width / 2.0, cy - logical.height / 2.0)
        PangoCairo.show_layout(cr, layout)
