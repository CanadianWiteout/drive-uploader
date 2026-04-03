#!/usr/bin/env bash
# Build a fully standalone Drive Uploader.app using PyInstaller
# No Python installation required to run the output app.

set -e

APP_NAME="Drive Uploader"
BUNDLE_ID="com.kootenaycolor.drive-uploader"
PYTHON="/Library/Frameworks/Python.framework/Versions/3.14/bin/python3"
PYINSTALLER="/Library/Frameworks/Python.framework/Versions/3.14/bin/pyinstaller"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "▶ Building standalone $APP_NAME.app…"
echo ""

# ── Install / upgrade PyInstaller ──────────────────────────────────────────
if ! "$PYINSTALLER" --version &>/dev/null; then
    echo "Installing PyInstaller…"
    "$PYTHON" -m pip install --quiet pyinstaller
fi

# ── Clean previous build ───────────────────────────────────────────────────
rm -rf "$SCRIPT_DIR/dist" "$SCRIPT_DIR/build" "$SCRIPT_DIR"/*.spec

# ── Run PyInstaller ────────────────────────────────────────────────────────
cd "$SCRIPT_DIR"

# Build hidden-import list for Google API client (it uses dynamic imports)
HIDDEN=(
    "googleapiclient.discovery"
    "googleapiclient.http"
    "google.auth.transport.requests"
    "google.oauth2.credentials"
    "google_auth_oauthlib.flow"
    "customtkinter"
)

HIDDEN_ARGS=""
for h in "${HIDDEN[@]}"; do
    HIDDEN_ARGS="$HIDDEN_ARGS --hidden-import=$h"
done

# Bundle credentials.json if it exists
ADD_DATA_ARGS=""
[ -f "$SCRIPT_DIR/credentials.json" ] && ADD_DATA_ARGS="--add-data credentials.json:."
[ -f "$SCRIPT_DIR/token.json"       ] && ADD_DATA_ARGS="$ADD_DATA_ARGS --add-data token.json:."

"$PYINSTALLER" \
    --windowed \
    --noconfirm \
    --name "$APP_NAME" \
    --osx-bundle-identifier "$BUNDLE_ID" \
    $HIDDEN_ARGS \
    $ADD_DATA_ARGS \
    main.py

echo ""
echo "✓ Done!  →  dist/$APP_NAME.app"
echo ""
echo "To install:  cp -r \"dist/$APP_NAME.app\" /Applications/"
echo "To update:   re-run this script"
