"""Main window: Adw shell (HeaderBar + 212px sidebar + Gtk.Stack) with a toast overlay.

Window controls (minimise / maximise / close) sit at the top-right, following the desktop's
decoration layout (the default on GNOME and Cinnamon).
"""
from __future__ import annotations

from gi.repository import Adw, Gio, Gtk

from linfilededuplication import APP_NAME
from linfilededuplication.config.layout import (
    WINDOW_HEIGHT, WINDOW_MIN_HEIGHT, WINDOW_MIN_WIDTH, WINDOW_WIDTH)
from linfilededuplication.i18n import _
from linfilededuplication.services.scan_controller import ScanController
from linfilededuplication.ui.pages import DEFAULT_PAGE, PAGES
from linfilededuplication.ui.sidebar import Sidebar


class MainWindow(Adw.ApplicationWindow):
    def __init__(self, app) -> None:
        super().__init__(application=app)
        self.app = app
        self.set_title(APP_NAME)
        self.set_default_size(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.set_size_request(WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT)
        self.add_css_class("lfd-window")

        self.controller = ScanController()
        self._group_count = 0
        self.current: str | None = None

        # header
        header = Adw.HeaderBar()
        self.title_widget = Adw.WindowTitle(title=APP_NAME, subtitle="")
        header.set_title_widget(self.title_widget)
        menu = Gio.Menu()
        menu.append(_("About DedupeDash"), "app.about")
        menu.append(_("Quit"), "app.quit")
        menu_btn = Gtk.MenuButton(icon_name="app-app-menu-symbolic", menu_model=menu,
                                  tooltip_text=_("Main menu"))
        header.pack_end(menu_btn)

        # sidebar + stack
        self.sidebar = Sidebar(PAGES)
        self.sidebar.connect("page-changed", lambda _s, pid: self.show_page(pid))
        self.stack = Gtk.Stack(hexpand=True, vexpand=True)
        self.stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self.stack.set_transition_duration(120)

        self.pages = {}
        for spec in PAGES:
            page = spec.factory(self)
            self.pages[spec.id] = page
            self.stack.add_named(page, spec.id)

        body = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        body.append(self.sidebar)
        body.append(self.stack)

        self.toasts = Adw.ToastOverlay()
        self.toasts.set_child(body)

        toolbar = Adw.ToolbarView()
        toolbar.add_top_bar(header)
        toolbar.set_content(self.toasts)
        self.set_content(toolbar)

        self.controller.connect("scan-started", self._on_scan_started)
        self.controller.connect("group-found", self._on_group_found)
        self.controller.connect("scan-finished", self._on_scan_finished)

        self.show_page(DEFAULT_PAGE)

    # --- navigation ------------------------------------------------------
    def show_page(self, page_id: str) -> None:
        if page_id == self.current or page_id not in self.pages:
            return
        if self.current is not None:
            self.pages[self.current].on_hidden()
        self.current = page_id
        self.stack.set_visible_child_name(page_id)
        self.sidebar.select(page_id)
        page = self.pages[page_id]
        self.title_widget.set_subtitle(page.title)
        page.on_shown()

    def show_page_index(self, i: int) -> None:
        if 0 <= i < len(PAGES):
            self.show_page(PAGES[i].id)

    # --- scan glue -------------------------------------------------------
    def start_scan(self, opts) -> None:
        self.show_page("results")
        self.controller.start(opts)

    def request_scan(self, path: str | None) -> None:
        if not path:
            return
        scan_page = self.pages["scan"]
        scan_page.root = path
        scan_page.folder_row.set_subtitle(path)
        self.show_page("scan")

    def toast(self, text: str) -> None:
        self.toasts.add_toast(Adw.Toast.new(text))

    def _on_scan_started(self, _c, _root: str) -> None:
        self._group_count = 0
        self.sidebar.set_count("results", 0)
        self.sidebar.set_running("scan", True)

    def _on_group_found(self, _c, _group) -> None:
        self._group_count += 1
        self.sidebar.set_count("results", self._group_count)

    def _on_scan_finished(self, _c, fin) -> None:
        self.sidebar.set_running("scan", False)
        if not fin.cancelled and fin.groups:
            self.toast(_("Found {n} duplicate groups").format(n=fin.groups))
