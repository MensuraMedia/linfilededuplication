"""ScanController: runs a scan on a worker thread and drains its events on the main loop.

Drains a queue.SimpleQueue with GLib.timeout_add on a 16 ms tick and an 8 ms budget per
tick, so the UI stays responsive under a fast scan. Not GLib.idle_add (which would flood
the loop). Re-emits engine events as GObject signals the UI subscribes to.
"""
from __future__ import annotations

import queue

from gi.repository import GLib, GObject

from linfilededuplication.core import events
from linfilededuplication.core.options import ScanOptions
from linfilededuplication.core.scanner import ScanThread

TICK_MS = 16
BUDGET_US = 8000        # 8 ms


class ScanController(GObject.GObject):
    __gtype_name__ = "LfdScanController"
    __gsignals__ = {
        "scan-started": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
        "progress": (GObject.SignalFlags.RUN_FIRST, None, (float, str, str, str)),
        "group-found": (GObject.SignalFlags.RUN_FIRST, None, (object,)),
        "scan-error": (GObject.SignalFlags.RUN_FIRST, None, (str, str, str)),
        "scan-finished": (GObject.SignalFlags.RUN_FIRST, None, (object,)),
    }

    def __init__(self) -> None:
        super().__init__()
        self._thread: ScanThread | None = None
        self._queue: "queue.SimpleQueue[events.ScanEvent]" | None = None
        self._timer: int = 0

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self, opts: ScanOptions) -> None:
        self.cancel()
        self._queue = queue.SimpleQueue()
        self._thread = ScanThread(opts, self._queue)
        self._thread.start()
        self._timer = GLib.timeout_add(TICK_MS, self._drain)

    def cancel(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            self._thread.cancel()

    def _stop_timer(self) -> None:
        if self._timer:
            GLib.source_remove(self._timer)
            self._timer = 0

    def _drain(self) -> bool:
        if self._queue is None:
            return False
        deadline = GLib.get_monotonic_time() + BUDGET_US
        handled = 0
        while True:
            try:
                ev = self._queue.get_nowait()
            except queue.Empty:
                break
            self._dispatch(ev)
            if isinstance(ev, events.Finished):
                self._stop_timer()
                return False
            handled += 1
            if handled & 0x3F == 0 and GLib.get_monotonic_time() > deadline:
                break               # yield; resume next tick
        return True

    def _dispatch(self, ev: events.ScanEvent) -> None:
        if isinstance(ev, events.ScanStarted):
            self.emit("scan-started", ev.root)
        elif isinstance(ev, events.Progress):
            self.emit("progress", ev.fraction, ev.phase, ev.detail, ev.source)
        elif isinstance(ev, events.GroupFound):
            self.emit("group-found", ev.group)
        elif isinstance(ev, events.ScanError):
            self.emit("scan-error", ev.message, ev.fix, ev.path)
        elif isinstance(ev, events.Finished):
            self.emit("scan-finished", ev)
