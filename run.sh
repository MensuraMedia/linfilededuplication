#!/usr/bin/env bash
# Run DedupeDash from a checkout. Prefers the project venv if present.
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if ! python3 -c 'import gi; gi.require_version("Gtk","4.0"); gi.require_version("Adw","1")' 2>/dev/null; then
  echo "Missing GTK 4 / libadwaita bindings. Install:" >&2
  echo "  sudo apt install python3-gi python3-gi-cairo gir1.2-gtk-4.0 gir1.2-adw-1" >&2
  exit 1
fi

PY=python3
[ -x "$DIR/.venv/bin/python" ] && PY="$DIR/.venv/bin/python"
export PYTHONPATH="$DIR/src${PYTHONPATH:+:$PYTHONPATH}"
export LINFILEDEDUPLICATION_DATA_DIR="$DIR/data"
exec "$PY" -m linfilededuplication "$@"
