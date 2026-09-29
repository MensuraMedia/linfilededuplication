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
$SUDO cp -r "$ROOT/src" "$SHARE/src"
$SUDO cp -r "$ROOT/data/css" "$ROOT/data/icons" "$SHARE/"
$SUDO cp "$ROOT/data/$APPID.desktop" "$PREFIX/share/applications/"
$SUDO cp "$ROOT/data/$APPID.metainfo.xml" "$PREFIX/share/metainfo/"
$SUDO cp -r "$ROOT/data/icons/hicolor" "$PREFIX/share/icons/"

$SUDO sed "s|__ROOT__|$SHARE|" "$ROOT/bin/$PKG" | \
  $SUDO tee "$PREFIX/bin/$PKG" >/dev/null
$SUDO sed -i "s|/usr/share/linfilededuplication|$SHARE|" "$PREFIX/bin/$PKG"
$SUDO chmod 755 "$PREFIX/bin/$PKG"

which update-desktop-database >/dev/null 2>&1 && $SUDO update-desktop-database -q "$PREFIX/share/applications" || true
which gtk-update-icon-cache >/dev/null 2>&1 && $SUDO gtk-update-icon-cache -q "$PREFIX/share/icons/hicolor" || true
echo "Installed to $PREFIX. Run: $PKG"
