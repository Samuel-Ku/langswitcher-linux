#!/usr/bin/env bash
# Installs the Omarchy Quattro plugin component.
# Usable standalone (./install-plugin.sh [--auto]) or via the repo-root installer.
#
# --auto also turns on the automatic (Punto-style) mode: it copies the Hyprland
# Lua module to ~/.config/hypr/ and adds its require() to hyprland.lua. Without
# the flag the module is installed but not enabled — auto mode rewrites text
# while you type, so it is opt-in.
#
# The decision data (lib/words.py) is not in the repository: it is derived from
# CC BY-SA 4.0 content while this project is MIT, so it ships as a release asset
# pinned by hash below.  Offline: unpack that asset yourself and pass
# LANGSWITCHER_DATA_DIR=/path/to/unpacked.
set -u

SRC_DIR="$(cd "$(dirname "$0")" && pwd)"
PLUGIN_ID="stealth.langswitcher"
REPO="${LANGSWITCHER_REPO:-Samuel-Ku/langswitcher-linux}"
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

# The data pin.  Bump both together when tools/build_words.py emits a new
# DATA_VERSION; the release job verifies that the published asset hashes to
# DATA_SHA256, so a mismatch fails the build instead of shipping silently.
DATA_VERSION="2026.09.15"
DATA_FILE="langswitcher-data-$DATA_VERSION.tar.gz"
DATA_SHA256="ac9776dbe5a97d68cb038b3e61316f7bed7b7990232aa87cd8129000ae90feb7"
DATA_URL="https://github.com/$REPO/releases/download/data-$DATA_VERSION/$DATA_FILE"
# Env overrides, applied after the plain constants so the CI tag job can grep
# them verbatim and check the published asset against the same numbers.
DATA_URL="${LANGSWITCHER_DATA_URL:-$DATA_URL}"
DATA_SHA256="${LANGSWITCHER_DATA_SHA256:-$DATA_SHA256}"

have() { command -v "$1" >/dev/null 2>&1; }

command -v omarchy >/dev/null 2>&1 || { echo "(!) omarchy CLI not found — is this Omarchy?" >&2; exit 1; }

# Fetch words.py into $1.  Either the local override (offline installs) or the
# pinned release asset, whose hash must match before anything is unpacked.
fetch_data() {
  local out="$1"
  if [[ -n "${LANGSWITCHER_DATA_DIR:-}" ]]; then
    if [[ -f "$LANGSWITCHER_DATA_DIR/words.py" ]]; then
      cp "$LANGSWITCHER_DATA_DIR/words.py" "$out"
      echo "== data $DATA_VERSION <- $LANGSWITCHER_DATA_DIR (offline) =="
      return 0
    fi
    echo "(!) $LANGSWITCHER_DATA_DIR/words.py not found" >&2
    return 1
  fi
  local tmp
  tmp="$(mktemp -d)"
  echo "== data $DATA_VERSION =="
  if have curl; then
    curl -fsSL "$DATA_URL" -o "$tmp/$DATA_FILE" || { rm -rf "$tmp"; return 1; }
  elif have wget; then
    wget -qO "$tmp/$DATA_FILE" "$DATA_URL" || { rm -rf "$tmp"; return 1; }
  else
    echo "(!) need curl or wget to fetch the data artifact" >&2
    rm -rf "$tmp"
    return 1
  fi
  local got
  got="$(sha256sum "$tmp/$DATA_FILE" | cut -d' ' -f1)"
  if [[ "$got" != "$DATA_SHA256" ]]; then
    echo "(!) data checksum mismatch: got $got, want $DATA_SHA256" >&2
    rm -rf "$tmp"
    return 1
  fi
  tar -xzf "$tmp/$DATA_FILE" -C "$tmp" words.py || { rm -rf "$tmp"; return 1; }
  cp "$tmp/words.py" "$out"
  rm -rf "$tmp"
}

# Build the new plugin tree next to the live one and swap only once the data is
# verified: a failed download must not leave a plugin that used to work broken.
# Staging inside the same parent directory keeps the rename atomic.
PLUGIN_DIR="$(dirname "$DEST")"
mkdir -p "$PLUGIN_DIR"
STAGE="$(mktemp -d "$PLUGIN_DIR/.langswitcher-stage.XXXXXX" 2>/dev/null)" || STAGE="$(mktemp -d)"
mkdir -p "$STAGE/plugin"
echo "== plugin files -> $STAGE/plugin =="
cp "$SRC_DIR/manifest.json" "$SRC_DIR/Service.qml" "$SRC_DIR/BarWidget.qml" "$SRC_DIR/Panel.qml" \
   "$SRC_DIR/LICENSE" "$SRC_DIR/README.md" "$SRC_DIR/bindings.snippet.lua" "$STAGE/plugin/" 2>/dev/null || true
cp -r "$SRC_DIR/bin" "$SRC_DIR/lib" "$SRC_DIR/hypr" "$STAGE/plugin/"
chmod +x "$STAGE/plugin/bin/langswitcher-convert" "$STAGE/plugin/bin/langswitcher-auto"

if ! fetch_data "$STAGE/plugin/lib/words.py"; then
  echo "(!) no decision data — the installed plugin was left untouched" >&2
  echo "    Offline: download $DATA_FILE from the release, unpack it, and rerun with" >&2
  echo "    LANGSWITCHER_DATA_DIR=<dir> $0 $*" >&2
  rm -rf "$STAGE"
  exit 1
fi

# Automatic mode starts a Python process per finished word, and compiling the
# core on every one of them is a cost the user feels. Precompile now.
command -v python3 >/dev/null 2>&1 && python3 -m compileall -q "$STAGE/plugin/lib" >/dev/null 2>&1 || true

rm -rf "$DEST"
mkdir -p "$(dirname "$DEST")"
mv "$STAGE/plugin" "$DEST"
rm -rf "$STAGE"

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
