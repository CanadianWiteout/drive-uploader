#!/usr/bin/env bash
# Build Drive Uploader.app for macOS

set -e

APP_NAME="Drive Uploader"
BUNDLE_ID="com.kootenaycolor.drive-uploader"
PYTHON="/Library/Frameworks/Python.framework/Versions/3.14/bin/python3"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DIST="$SCRIPT_DIR/dist/$APP_NAME.app"

echo "Building $APP_NAME.app…"

# Install dependencies into the project directory if needed
if [ ! -d "$SCRIPT_DIR/venv" ]; then
    echo "Installing dependencies…"
    "$PYTHON" -m pip install -r "$SCRIPT_DIR/requirements.txt" --quiet
fi

# Clean
rm -rf "$DIST"
mkdir -p "$DIST/Contents/MacOS"
mkdir -p "$DIST/Contents/Resources"

# Info.plist
cat > "$DIST/Contents/Info.plist" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key>             <string>$APP_NAME</string>
  <key>CFBundleDisplayName</key>      <string>$APP_NAME</string>
  <key>CFBundleIdentifier</key>       <string>$BUNDLE_ID</string>
  <key>CFBundleVersion</key>          <string>1.0</string>
  <key>CFBundleShortVersionString</key><string>1.0</string>
  <key>CFBundleExecutable</key>       <string>launcher</string>
  <key>CFBundlePackageType</key>      <string>APPL</string>
  <key>NSHighResolutionCapable</key>  <true/>
  <key>LSMinimumSystemVersion</key>   <string>12.0</string>
</dict>
</plist>
EOF

# Launcher script
cat > "$DIST/Contents/MacOS/launcher" << LAUNCHER
#!/bin/bash
DIR="\$(cd "\$(dirname "\$0")/../Resources" && pwd)"
cd "\$DIR"
exec "$PYTHON" main.py
LAUNCHER
chmod +x "$DIST/Contents/MacOS/launcher"

# Copy source files
for f in main.py drive.py state.py config.py requirements.txt; do
  cp "$SCRIPT_DIR/$f" "$DIST/Contents/Resources/"
done

# Copy credentials + token if they exist
for f in credentials.json token.json; do
  [ -f "$SCRIPT_DIR/$f" ] && cp "$SCRIPT_DIR/$f" "$DIST/Contents/Resources/"
done

echo ""
echo "Done!  →  dist/$APP_NAME.app"
echo ""
echo "To install:  cp -r \"dist/$APP_NAME.app\" /Applications/"
echo "To update:   re-run this script"
