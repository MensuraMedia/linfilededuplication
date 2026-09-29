#!/usr/bin/env bash
# Remove a checkout install. --user (default) or --system.
set -euo pipefail
PKG=linfilededuplication
APPID=com.mensuramedia.linfilededuplication

MODE="user"
[ "${1:-}" = "--system" ] && MODE="system"
if [ "$MODE" = "system" ]; then PREFIX=/usr/local; SUDO=sudo; else PREFIX="$HOME/.local"; SUDO=""; fi

$SUDO rm -rf "$PREFIX/share/$PKG"
$SUDO rm -f "$PREFIX/bin/$PKG"
$SUDO rm -f "$PREFIX/share/applications/$APPID.desktop"
$SUDO rm -f "$PREFIX/share/metainfo/$APPID.metainfo.xml"
$SUDO find "$PREFIX/share/icons/hicolor" -name "$APPID*" -delete 2>/dev/null || true
echo "Removed DedupeDash from $PREFIX."
