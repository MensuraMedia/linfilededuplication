"""Page registry: one place that lists the app's pages and how to build them."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from linfilededuplication.i18n import _


@dataclass(frozen=True)
class PageSpec:
    id: str
    label: str
    icon: str                       # base icon id: "app-nav-<x>" (has -symbolic + -active-symbolic)
    factory: Callable               # (MainWindow) -> BasePage
    bottom: bool = False            # pinned to the bottom of the sidebar


def _overview(window):
    from linfilededuplication.ui.pages.overview import OverviewPage
    return OverviewPage(window)


def _scan(window):
    from linfilededuplication.ui.pages.scan import ScanPage
    return ScanPage(window)


def _results(window):
    from linfilededuplication.ui.pages.results import ResultsPage
    return ResultsPage(window)


def _history(window):
    from linfilededuplication.ui.pages.history import HistoryPage
    return HistoryPage(window)


def _knowledge(window):
    from linfilededuplication.ui.pages.knowledge import KnowledgePage
    return KnowledgePage(window)


def _settings(window):
    from linfilededuplication.ui.pages.settings import SettingsPage
    return SettingsPage(window)


PAGES: list[PageSpec] = [
    PageSpec("overview", _("Overview"), "app-nav-home", _overview),
    PageSpec("scan", _("Scan"), "app-nav-scan", _scan),
    PageSpec("results", _("Results"), "app-nav-results", _results),
    PageSpec("history", _("History"), "app-nav-history", _history),
    PageSpec("knowledge", _("Knowledge"), "app-nav-knowledge", _knowledge),
    PageSpec("settings", _("Settings"), "app-nav-settings", _settings, bottom=True),
]
DEFAULT_PAGE = "overview"
