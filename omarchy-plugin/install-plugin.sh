#!/usr/bin/env bash
# Installs the Omarchy Quattro plugin component.
# Usable standalone (./install-plugin.sh) or via the repo-root universal installer.
set -u

SRC_DIR="$(cd "$(dirname "$0")" && pwd)"
PLUGIN_ID="stealth.langswitcher"
DEST="$HOME/.config/omarchy/plugins/$PLUGIN_ID"
BIND_FILE="$HOME/.config/hypr/bindings.lua"

command -v omarchy >/dev/null 2>&1 || { echo "(!) omarchy CLI not found — is this Omarchy?" >&2; exit 1; }

echo "== plugin files -> $DEST =="
rm -rf "$DEST"
mkdir -p "$DEST"
cp "$SRC_DIR/manifest.json" "$SRC_DIR/Service.qml" "$SRC_DIR/BarWidget.qml" "$SRC_DIR/Panel.qml" \
   "$SRC_DIR/LICENSE" "$SRC_DIR/README.md" "$SRC_DIR/bindings.snippet.lua" "$DEST/" 2>/dev/null || true
cp -r "$SRC_DIR/bin" "$SRC_DIR/lib" "$DEST/"
chmod +x "$DEST/bin/langswitcher-convert"

omarchy-shell shell rescanPlugins >/dev/null 2>&1 || true
omarchy plugin enable "$PLUGIN_ID"

echo "== hotkeys -> $BIND_FILE =="
if [[ -f "$BIND_FILE" ]]; then
  grep -q "langswitcher-convert selection" "$BIND_FILE" || cat "$SRC_DIR/bindings.snippet.lua" >> "$BIND_FILE"
  echo "binds ensured (SUPER+GRAVE / SUPER+SHIFT+GRAVE)"
else
  echo "(!) $BIND_FILE not found — add binds manually:"
  cat "$SRC_DIR/bindings.snippet.lua"
fi

command -v hyprctl >/dev/null 2>&1 && hyprctl reload >/dev/null 2>&1 || true
"$DEST/bin/langswitcher-convert" --check || echo "(!) --check failed — see missing above"
echo "Done. Select text -> SUPER+GRAVE."
