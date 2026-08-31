#!/usr/bin/env bash
# Packages the PyInstaller .app bundle (build/dist/PaceChart.app) into a
# drag-to-Applications .dmg installer. Expects the .app to already exist
# (see pacechart.spec's BUNDLE step). Run from the repo root:
#
#   packaging/macos/build-dmg.sh <version>
set -euo pipefail

VERSION="${1:?usage: build-dmg.sh <version>}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
APP="$ROOT/build/dist/PaceChart.app"
STAGE="$ROOT/build/dmg-stage"
OUT_DIR="$ROOT/build/installer"
DMG="$OUT_DIR/PaceChartSetup.dmg"

rm -rf "$STAGE" "$DMG"
mkdir -p "$STAGE" "$OUT_DIR"
cp -R "$APP" "$STAGE/"
ln -s /Applications "$STAGE/Applications"

hdiutil create -volname "PaceChart $VERSION" -srcfolder "$STAGE" -ov -format UDZO "$DMG"
