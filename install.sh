#!/usr/bin/env bash
# LangSwitcher — universal installer (Linux).
# One-liner:
#   curl -fsSL https://raw.githubusercontent.com/Samuel-Ku/langswitcher-linux/main/install.sh | bash
# Env overrides:
#   LANGSWITCHER_REPO=...  LANGSWITCHER_BRANCH=...  LANGSWITCHER_SRC=/local/dir (skip download)
#   LANGSWITCHER_COMPONENT=auto|omarchy-plugin|linux|fedora-kde   (default: auto)
# Flags: --print-plan (detect + report only), --component <name>
set -u

REPO="${LANGSWITCHER_REPO:-Samuel-Ku/langswitcher-linux}"
BRANCH="${LANGSWITCHER_BRANCH:-main}"
OS_RELEASE="${OS_RELEASE:-/etc/os-release}"
WANT="auto"
SRC_OVERRIDE="${LANGSWITCHER_SRC:-}"

for arg in "$@"; do
  case "$arg" in
    --print-plan) PRINT_PLAN=1 ;;
    --component) shift_next=1 ;;
    *)
      if [[ "${shift_next:-}" == "1" ]]; then WANT="$arg"; shift_next=0;
      elif [[ "$arg" == --component=* ]]; then WANT="${arg#--component=}"; fi ;;
  esac
done
WANT="${LANGSWITCHER_COMPONENT:-$WANT}"

have() { command -v "$1" >/dev/null 2>&1; }

# --- Windows-in-bash (Git Bash / MSYS / Cygwin): point to the Windows installer
if [[ "${OS:-}" == "Windows_NT" ]] || uname -s 2>/dev/null | grep -qiE "mingw|msys|cygwin"; then
  echo "Windows detected. Install in PowerShell with one line:"
  echo "  irm https://raw.githubusercontent.com/$REPO/$BRANCH/windows/install.ps1 | iex"
  echo "or double-click windows/install.bat from the repo."
  exit 0
fi

# --- Detect distro
ID="unknown"; ID_LIKE=""
if [[ -f "$OS_RELEASE" ]]; then
  # shellcheck disable=SC1090
  . "$OS_RELEASE"
fi
DESKTOP="${XDG_CURRENT_DESKTOP:-}"

pick_component() {
  if [[ "$WANT" != "auto" ]]; then echo "$WANT"; return; fi
  if have omarchy-shell && [[ "$DESKTOP" == *"Hyprland"* ]]; then echo "omarchy-plugin"; return; fi
  if [[ "$ID" == "omarchy" ]]; then echo "omarchy-plugin"; return; fi
  # Fedora KDE gets its own worker: Plasma needs ydotool (wtype does nothing on
  # KWin) and switches layouts through org.kde.keyboard instead of hyprctl.
  if [[ "$ID" == "fedora" ]] && [[ "$DESKTOP" == *"KDE"* || "$DESKTOP" == *"Plasma"* ]]; then
    echo "fedora-kde"; return
  fi
  echo "linux"
}

COMPONENT="$(pick_component)"

if [[ "${PRINT_PLAN:-}" == "1" ]]; then
  echo "distro=$ID (like: ${ID_LIKE:-none}) desktop=${DESKTOP:-none} session=${XDG_SESSION_TYPE:-unknown}"
  echo "component=$COMPONENT"
  case "$COMPONENT" in
    omarchy-plugin) echo "would: install Quattro plugin stealth.langswitcher + SUPER+GRAVE binds" ;;
    fedora-kde) echo "would: install kde-convert (ydotool + org.kde.keyboard) + Meta+GRAVE shortcuts" ;;
    linux) echo "would: install linux worker (Ubuntu GNOME/Mint Cinnamon auto-detect) + shortcuts" ;;
    *) echo "unknown component: $COMPONENT" >&2; exit 1 ;;
  esac
  exit 0
fi

# --- Fetch sources
if [[ -n "$SRC_OVERRIDE" ]]; then
  SRC="$SRC_OVERRIDE"
else
  TMP="$(mktemp -d)"
  trap 'rm -rf "$TMP"' EXIT
  TARBALL="https://github.com/$REPO/archive/refs/heads/$BRANCH.tar.gz"
  echo "downloading $TARBALL ..."
  if have curl; then
    curl -fsSL "$TARBALL" -o "$TMP/repo.tar.gz" || { echo "download failed" >&2; exit 1; }
  elif have wget; then
    wget -qO "$TMP/repo.tar.gz" "$TARBALL" || { echo "download failed" >&2; exit 1; }
  else
    echo "need curl or wget" >&2; exit 1
  fi
  tar -xzf "$TMP/repo.tar.gz" -C "$TMP"
  SRC="$(echo "$TMP"/*/)"
fi

case "$COMPONENT" in
  omarchy-plugin) bash "$SRC/omarchy-plugin/install-plugin.sh" ;;
  fedora-kde) bash "$SRC/fedora-kde/install.sh" ;;
  linux) bash "$SRC/linux/install.sh" ;;
  *) echo "unknown component: $COMPONENT" >&2; exit 1 ;;
esac
