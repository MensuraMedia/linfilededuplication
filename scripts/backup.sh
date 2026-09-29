#!/usr/bin/env bash
# Local backup: a timestamped tarball of the project source, excluding build/venv/git.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PKG=linfilededuplication
STAMP="$(date +%Y%m%d-%H%M%S)"
DEST="${BACKUP_DIR:-$HOME/backups/$PKG}"
mkdir -p "$DEST"
OUT="$DEST/${PKG}_${STAMP}.tar.gz"

tar -czf "$OUT" -C "$(dirname "$ROOT")" \
  --exclude="$PKG/.venv" \
  --exclude="$PKG/.git" \
  --exclude="$PKG/build" \
  --exclude="$PKG/dist" \
  --exclude="$PKG/__pycache__" \
  --exclude="*.pyc" \
  "$PKG"

echo "Backup written: $OUT ($(du -h "$OUT" | cut -f1))"
# keep the 10 most recent
ls -1t "$DEST"/${PKG}_*.tar.gz 2>/dev/null | tail -n +11 | xargs -r rm -f
