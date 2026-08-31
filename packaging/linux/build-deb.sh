#!/usr/bin/env bash
# Packages the PyInstaller onedir build (build/dist/PaceChart) into a .deb
# for Debian-based Linux -- including the Debian container Chromebooks run
# under "Linux (Beta)" (Crostini). Expects the onedir build to already
# exist (see pacechart.spec). Run from the repo root:
#
#   packaging/linux/build-deb.sh <version>
set -euo pipefail

VERSION="${1:?usage: build-deb.sh <version>}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
STAGE="$ROOT/build/deb-stage"
OUT_DIR="$ROOT/build/installer"

rm -rf "$STAGE"
mkdir -p "$STAGE/DEBIAN" \
         "$STAGE/opt/pacechart" \
         "$STAGE/usr/bin" \
         "$STAGE/usr/share/applications" \
         "$STAGE/usr/share/pixmaps"

cp -r "$ROOT/build/dist/PaceChart/"* "$STAGE/opt/pacechart/"
cp "$ROOT/src/pacechart/assets/logo.png" "$STAGE/usr/share/pixmaps/pacechart.png"
cp "$ROOT/packaging/linux/pacechart.desktop" "$STAGE/usr/share/applications/pacechart.desktop"
ln -s /opt/pacechart/PaceChart "$STAGE/usr/bin/pacechart"

cat > "$STAGE/DEBIAN/control" <<EOF
Package: pacechart
Version: $VERSION
Section: utils
Priority: optional
Architecture: amd64
Maintainer: Simon Griggs
Description: Training-pace chart generator for XC/track meet results
 Scrapes meet roster/results, converts marks to a 5k- or 3k-equivalent,
 and generates a training-pace PDF. Works in a Chromebook's Linux
 (Crostini) environment as well as Debian/Ubuntu desktops.
EOF

chmod -R go=rX,u=rwX "$STAGE"
chmod 0755 "$STAGE/DEBIAN"

mkdir -p "$OUT_DIR"
dpkg-deb --build --root-owner-group "$STAGE" "$OUT_DIR/pacechart_${VERSION}_amd64.deb"
