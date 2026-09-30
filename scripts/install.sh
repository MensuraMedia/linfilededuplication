#!/usr/bin/env bash
# Install DedupeDash from a checkout. --user (default) or --system.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PKG=linfilededuplication
APPID=com.mensuramedia.linfilededuplication

MODE="user"
[ "${1:-}" = "--system" ] && MODE="system"

if [ "$MODE" = "system" ]; then
  PREFIX=/usr/local; SUDO=sudo
else
  PREFIX="$HOME/.local"; SUDO=""
fi

SHARE="$PREFIX/share/$PKG"
$SUDO mkdir -p "$SHARE" "$PREFIX/bin" "$PREFIX/share/applications" \
              "$PREFIX/share/metainfo" "$PREFIX/share/icons"
# Clean previous payload so a reinstall never nests (cp -r into an existing dir).
$SUDO rm -rf "$SHARE/src" "$SHARE/css" "$SHARE/icons" "$SHARE/glossary"
$SUDO cp -r "$ROOT/src" "$SHARE/src"
$SUDO cp -r "$ROOT/data/css" "$ROOT/data/icons" "$ROOT/data/glossary" "$SHARE/"
$SUDO cp "$ROOT/data/$APPID.desktop" "$PREFIX/share/applications/"
$SUDO cp "$ROOT/data/$APPID.metainfo.xml" "$PREFIX/share/metainfo/"
$SUDO cp -r "$ROOT/data/icons/hicolor" "$PREFIX/share/icons/"

# hicolor needs an index.theme, or the panel/menu/tray can't resolve the icon (falls back to a gear).
if [ ! -f "$PREFIX/share/icons/hicolor/index.theme" ]; then
  if [ -f /usr/share/icons/hicolor/index.theme ]; then
    $SUDO cp /usr/share/icons/hicolor/index.theme "$PREFIX/share/icons/hicolor/index.theme"
  else
    printf '[Icon Theme]\nName=Hicolor\nComment=Fallback\nDirectories=scalable/apps,16x16/apps,22x22/apps,24x24/apps,32x32/apps,48x48/apps,64x64/apps,128x128/apps,256x256/apps\n\n[scalable/apps]\nSize=48\nMinSize=8\nMaxSize=512\nContext=Applications\nType=Scalable\n' | $SUDO tee "$PREFIX/share/icons/hicolor/index.theme" >/dev/null
  fi
fi

# Write a clean installed launcher (no sentinel to accidentally rewrite).
$SUDO tee "$PREFIX/bin/$PKG" >/dev/null <<LAUNCH
#!/bin/sh
export PYTHONPATH="$SHARE/src\${PYTHONPATH:+:\$PYTHONPATH}"
export LINFILEDEDUPLICATION_DATA_DIR="$SHARE"
exec python3 -m $PKG "\$@"
LAUNCH
$SUDO chmod 755 "$PREFIX/bin/$PKG"

which update-desktop-database >/dev/null 2>&1 && $SUDO update-desktop-database -q "$PREFIX/share/applications" || true
which gtk-update-icon-cache >/dev/null 2>&1 && $SUDO gtk-update-icon-cache -f -t "$PREFIX/share/icons/hicolor" >/dev/null 2>&1 || true
echo "Installed to $PREFIX. Run: $PKG"
