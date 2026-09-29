#!/usr/bin/env bash
# Build a .deb with dpkg-deb (no dh/pybuild). Stages into build/deb, emits dist/*.deb.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PKG=linfilededuplication
APPID=com.mensuramedia.linfilededuplication
VERSION="$(sed -n 's/^__version__ = "\(.*\)"/\1/p' src/$PKG/__init__.py)"
BUILD="build/deb"
DEST="$BUILD/usr"

rm -rf "$BUILD"
mkdir -p "$DEST/lib/$PKG" "$DEST/share/$PKG" "$DEST/bin" \
         "$DEST/share/applications" "$DEST/share/metainfo" \
         "$DEST/share/doc/$PKG" "$BUILD/DEBIAN"

# Python package + data
cp -r src "$DEST/lib/$PKG/src"
cp -r data/css data/icons data/glossary "$DEST/share/$PKG/"
cp data/$APPID.desktop  "$DEST/share/applications/"
cp data/$APPID.metainfo.xml "$DEST/share/metainfo/"

# Icons into the hicolor theme (already laid out under data/icons/hicolor)
cp -r data/icons/hicolor "$DEST/share/icons/hicolor" 2>/dev/null || \
  { mkdir -p "$DEST/share/icons"; cp -r data/icons/hicolor "$DEST/share/icons/"; }

# Launcher (rewrite __ROOT__)
sed "s|__ROOT__|/usr/lib/$PKG|" bin/$PKG > "$DEST/bin/$PKG"
sed -i "s|/usr/share/linfilededuplication|/usr/share/$PKG|" "$DEST/bin/$PKG"
chmod 755 "$DEST/bin/$PKG"

cp README.md "$DEST/share/doc/$PKG/" 2>/dev/null || true
cp LICENSE.md "$DEST/share/doc/$PKG/copyright"
gzip -9 -c changelog.md > "$DEST/share/doc/$PKG/changelog.gz"

INSTALLED_SIZE="$(du -sk "$DEST" | cut -f1)"

cat > "$BUILD/DEBIAN/control" <<EOF
Package: $PKG
Version: $VERSION
Section: utils
Priority: optional
Architecture: all
Maintainer: MensuraMedia <artisanstock@gmail.com>
Installed-Size: $INSTALLED_SIZE
Depends: python3 (>= 3.11), python3-gi, python3-gi-cairo, gir1.2-gtk-4.0, gir1.2-adw-1
Recommends: python3-pil, python3-imagehash, python3-xxhash, fonts-cantarell, hicolor-icon-theme, gir1.2-xapp-1.0
Suggests: python3-tlsh, poppler-utils
Homepage: https://github.com/MensuraMedia/linfilededuplication
Description: Find and safely remove duplicate and near-duplicate files
 DedupeDash is a GTK 4 dashboard that finds exact duplicate files and visually
 similar images, then removes the extras safely with Trash or hard-links after a
 dry-run preview and confirmation.
EOF

cat > "$BUILD/DEBIAN/postinst" <<'EOF'
#!/bin/sh
set -e
if which update-desktop-database >/dev/null 2>&1; then update-desktop-database -q || true; fi
if which gtk-update-icon-cache >/dev/null 2>&1; then gtk-update-icon-cache -q /usr/share/icons/hicolor || true; fi
EOF
cp "$BUILD/DEBIAN/postinst" "$BUILD/DEBIAN/postrm"
chmod 755 "$BUILD/DEBIAN/postinst" "$BUILD/DEBIAN/postrm"

mkdir -p dist
dpkg-deb --root-owner-group --build "$BUILD" "dist/${PKG}_${VERSION}_all.deb"
echo "Built dist/${PKG}_${VERSION}_all.deb"
