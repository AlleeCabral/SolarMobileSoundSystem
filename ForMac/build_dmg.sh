#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# build_dmg.sh — builds Solar Sound System Simulator.app and wraps it in a .dmg
#
# Requirements (run once before building):
#   python3 -m pip install py2app
#
# Usage:
#   cd ForMac
#   chmod +x build_dmg.sh
#   ./build_dmg.sh
#
# Output:
#   ForMac/dist/SolarSoundSimulator.dmg
# ─────────────────────────────────────────────────────────────────────────────

set -e   # stop on any error

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"
BUILD_DIR="$SCRIPT_DIR/build"
DIST_DIR="$SCRIPT_DIR/dist"
APP_NAME="Solar Sound System Simulator"
DMG_NAME="SolarSoundSimulator"

echo "==> Cleaning previous builds..."
rm -rf "$BUILD_DIR" "$DIST_DIR"

echo "==> Building .app with py2app..."
cd "$SCRIPT_DIR"
python3 setup.py py2app 2>&1

APP_BUNDLE="$DIST_DIR/${APP_NAME}.app"

if [ ! -d "$APP_BUNDLE" ]; then
    echo "ERROR: .app bundle not found at expected path: $APP_BUNDLE"
    exit 1
fi

echo "==> Creating .dmg..."
DMG_PATH="$DIST_DIR/${DMG_NAME}.dmg"
STAGING="$DIST_DIR/dmg_staging"

mkdir -p "$STAGING"
cp -R "$APP_BUNDLE" "$STAGING/"

# Create a symlink to /Applications so users can drag-and-drop
ln -sf /Applications "$STAGING/Applications"

hdiutil create \
    -volname "$APP_NAME" \
    -srcfolder "$STAGING" \
    -ov \
    -format UDZO \
    "$DMG_PATH"

rm -rf "$STAGING"

echo ""
echo "✅  Done!"
echo "    DMG : $DMG_PATH"
echo ""
echo "    To install: open the .dmg and drag the app to Applications."
