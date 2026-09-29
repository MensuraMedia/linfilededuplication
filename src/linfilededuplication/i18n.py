"""gettext: wrap every user-visible string in _() from the start.

Falls back to the identity function when no compiled translations are present, so the app
runs untranslated without error.
"""
from __future__ import annotations

import gettext
from pathlib import Path

from linfilededuplication import APP_ID

_localedir = str(Path(__file__).resolve().parent / "data" / "locale")
_t = gettext.translation(APP_ID, localedir=_localedir, fallback=True)
_ = _t.gettext
ngettext = _t.ngettext
