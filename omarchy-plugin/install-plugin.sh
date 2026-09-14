#!/usr/bin/env bash
# Installs the Omarchy Quattro plugin component.
# Usable standalone (./install-plugin.sh [--auto]) or via the repo-root installer.
#
# --auto also turns on the automatic (Punto-style) mode: it copies the Hyprland
# Lua module to ~/.config/hypr/ and adds its require() to hyprland.lua. Without
# the flag the module is installed but not enabled — auto mode rewrites text
# while you type, so it is opt-in.
set -u

SRC_DIR="$(cd "$(dirname "$0")" && pwd)"
PLUGIN_ID="stealth.langswitcher"
DEST="$HOME/.config/omarchy/plugins/$PLUGIN_ID"
BIND_FILE="$HOME/.config/hypr/bindings.lua"
HYPR_DIR="$HOME/.config/hypr"
HYPR_MAIN="$HYPR_DIR/hyprland.lua"
AUTO=0
for arg in "$@"; do
  case "$arg" in
    --auto) AUTO=1 ;;
    *) echo "(!) unknown argument: $arg" >&2; exit 2 ;;
  esac
done

command -v omarchy >/dev/null 2>&1 || { echo "(!) omarchy CLI not found — is this Omarchy?" >&2; exit 1; }

echo "== plugin files -> $DEST =="
rm -rf "$DEST"
mkdir -p "$DEST"
cp "$SRC_DIR/manifest.json" "$SRC_DIR/Service.qml" "$SRC_DIR/BarWidget.qml" "$SRC_DIR/Panel.qml" \
   "$SRC_DIR/LICENSE" "$SRC_DIR/README.md" "$SRC_DIR/bindings.snippet.lua" "$DEST/" 2>/dev/null || true
cp -r "$SRC_DIR/bin" "$SRC_DIR/lib" "$SRC_DIR/hypr" "$DEST/"
chmod +x "$DEST/bin/langswitcher-convert" "$DEST/bin/langswitcher-auto"
# Automatic mode starts a Python process per finished word, and compiling the
# core on every one of them is a cost the user feels. Precompile now.
command -v python3 >/dev/null 2>&1 && python3 -m compileall -q "$DEST/lib" >/dev/null 2>&1 || true

omarchy-shell shell rescanPlugins >/dev/null 2>&1 || true
omarchy plugin enable "$PLUGIN_ID"

echo "== hotkeys -> $BIND_FILE =="
# Each bind is checked on its own, by its exact line: an existing install keeps
# its binds and only gains the ones it is missing (the undo bind arrived later),
# and a fresh install gets all of them once.
if [[ -f "$BIND_FILE" ]]; then
  added=0
  while IFS= read -r line; do
    [[ "$line" == o.bind* ]] || continue
    if ! grep -qF -- "$line" "$BIND_FILE"; then
      printf '%s\n' "$line" >> "$BIND_FILE"
      added=$((added + 1))
    fi
  done < "$SRC_DIR/bindings.snippet.lua"
  echo "binds ensured ($added added): SUPER+GRAVE / SUPER+SHIFT+GRAVE / SUPER+BACKSPACE"
else
  echo "(!) $BIND_FILE not found — add binds manually:"
  cat "$SRC_DIR/bindings.snippet.lua"
fi

if [[ "$AUTO" == 1 ]]; then
  echo "== automatic mode -> $HYPR_DIR/langswitcher-auto.lua =="
  install -m644 "$SRC_DIR/hypr/langswitcher-auto.lua" "$HYPR_DIR/langswitcher-auto.lua"
  if [[ -f "$HYPR_MAIN" ]]; then
    if grep -q 'require("hypr.langswitcher-auto")' "$HYPR_MAIN"; then
      echo "require() already present in $HYPR_MAIN"
    else
      {
        echo ""
        echo "-- LangSwitcher automatic mode (Punto-style). See"
        echo "-- ~/.config/omarchy/plugins/$PLUGIN_ID/README.md; disable it with"
        echo "-- {\"enabled\": false} in ~/.config/omarchy/langswitcher-auto.json."
        echo 'require("hypr.langswitcher-auto")'
      } >> "$HYPR_MAIN"
      echo "require() appended to $HYPR_MAIN"
    fi
  else
    echo "(!) $HYPR_MAIN not found — enable it with: require(\"hypr.langswitcher-auto\")"
  fi
else
  echo "== automatic mode is installed but off =="
  echo "Enable with: ./install-plugin.sh --auto   (or add require(\"hypr.langswitcher-auto\") to $HYPR_MAIN)"
fi

command -v hyprctl >/dev/null 2>&1 && hyprctl reload >/dev/null 2>&1 || true
"$DEST/bin/langswitcher-convert" --check || echo "(!) --check failed — see missing above"
[[ -x "$DEST/bin/langswitcher-auto" ]] && "$DEST/bin/langswitcher-auto" --check \
  || echo "(!) auto --check failed — automatic mode will stay out of the way"
echo "Done. Select text -> SUPER+GRAVE."
