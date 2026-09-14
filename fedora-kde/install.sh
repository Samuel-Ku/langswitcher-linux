#!/usr/bin/env bash
# install.sh — LangSwitcher for Fedora KDE (Plasma 6, Wayland or X11).
#
# 1. deps via dnf
# 2. files -> ~/.local/share/langswitcher-kde, worker linked as ~/.local/bin/kde-convert
# 3. ydotoold: Fedora's system unit runs the daemon as root and creates the socket
#    0600, so a user's `ydotool` is refused. This hands the socket to your user
#    with a systemd drop-in instead of asking you to run the worker as root.
# 4. KDE global shortcuts: two command shortcuts in kglobalshortcutsrc.
#
# --dry-run prints every command instead of running it; --no-ydotool and
# --no-shortcuts skip step 3 and step 4 (the worker then prints what to do by
# hand). Nothing here writes outside your home except the ydotoold drop-in, and
# that one is shown before it happens.
set -u

DRY=0
DO_YDOTOOL=1
DO_SHORTCUTS=1
for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY=1 ;;
    --no-ydotool) DO_YDOTOOL=0 ;;
    --no-shortcuts) DO_SHORTCUTS=0 ;;
    *) echo "(!) unknown argument: $arg" >&2; exit 2 ;;
  esac
done

SRC_DIR="$(cd "$(dirname "$0")" && pwd)"
DEST="$HOME/.local/share/langswitcher-kde"
BINLINK="$HOME/.local/bin/kde-convert"
APPS="$HOME/.local/share/applications"
KEY_SEL='Meta+`'
KEY_LINE='Meta+Shift+`'

have() { command -v "$1" >/dev/null 2>&1; }
run() { if [[ $DRY == 1 ]]; then echo "  + $*"; else "$@"; fi; }

echo "== 1/4 deps =="
if have dnf; then
  # glib2 is for gdbus, which is what talks to org.kde.keyboard; kglobalacceld is
  # what actually runs a command shortcut on Plasma 6 (khotkeys is gone).
  run sudo dnf install -y python3 wl-clipboard ydotool glib2 libnotify kf6-kconfig
  have xclip || echo "  (X11 session? also: sudo dnf install xclip xdotool)"
else
  echo "(!) dnf not found — this installer is for Fedora. Install by hand:"
  echo "    python3 wl-clipboard ydotool glib2 libnotify kf6-kconfig"
fi

echo "== 2/4 files =="
run rm -rf "$DEST"
run mkdir -p "$DEST" "$HOME/.local/bin"
if [[ $DRY == 1 ]]; then
  echo "  + cp -r $SRC_DIR/bin $SRC_DIR/lib $DEST/"
  echo "  + ln -sf $DEST/bin/kde-convert $BINLINK"
else
  cp -r "$SRC_DIR/bin" "$SRC_DIR/lib" "$DEST/"
  chmod +x "$DEST/bin/kde-convert"
  ln -sf "$DEST/bin/kde-convert" "$BINLINK"
  echo "  installed: $BINLINK -> $DEST/bin/kde-convert"
fi

echo "== 3/4 ydotoold =="
setup_ydotool() {
  local unit=/usr/lib/systemd/system/ydotool.service
  local sock="${YDOTOOL_SOCKET:-/tmp/.ydotool_socket}"
  local dropin=/etc/systemd/system/ydotool.service.d/socket-own.conf
  if ! [[ -f "$unit" ]]; then
    echo "  (!) $unit not found — is ydotool installed? Skipping."
    return 0
  fi
  if [[ -S "$sock" && -w "$sock" ]]; then
    echo "  socket is already writable by $(id -un): $sock"
    return 0
  fi
  echo "  Fedora's ydotoold runs as root with a 0600 socket, so your client cannot"
  echo "  connect. Handing $sock to $(id -un):$(id -gn) with a drop-in."
  if [[ $DRY == 1 ]]; then
    echo "  + sudo install -d /etc/systemd/system/ydotool.service.d"
    echo "  + write $dropin:"
    echo "      [Service]"
    echo "      ExecStart="
    echo "      ExecStart=/usr/bin/ydotoold --socket-path=$sock --socket-own=$(id -u):$(id -g) --socket-perm=0660"
    echo "  + sudo systemctl daemon-reload && sudo systemctl enable --now ydotool && sudo systemctl restart ydotool"
    return 0
  fi
  sudo install -d /etc/systemd/system/ydotool.service.d
  sudo tee "$dropin" >/dev/null <<EOF
[Service]
ExecStart=
ExecStart=/usr/bin/ydotoold --socket-path=$sock --socket-own=$(id -u):$(id -g) --socket-perm=0660
EOF
  sudo systemctl daemon-reload
  sudo systemctl enable --now ydotool
  sudo systemctl restart ydotool
  sleep 0.5
  if [[ -S "$sock" && -w "$sock" ]]; then
    echo "  ok: $sock is writable"
  else
    echo "  (!) $sock is still not writable — check: systemctl status ydotool"
  fi
}
if [[ $DO_YDOTOOL == 1 ]]; then setup_ydotool; else echo "  skipped (--no-ydotool)"; fi

echo "== 4/4 KDE global shortcuts =="
write_desktop() {  # id, Name, Exec
  local id="$1" name="$2" exec="$3" path="$APPS/$1"
  if [[ $DRY == 1 ]]; then echo "  + write $path (Exec=$exec)"; return 0; fi
  mkdir -p "$APPS"
  cat > "$path" <<EOF
[Desktop Entry]
Type=Application
Name=$name
Exec=$exec
NoDisplay=true
StartupNotify=false
X-KDE-GlobalAccel-CommandShortcut=true
EOF
}
if [[ $DO_SHORTCUTS == 1 ]]; then
  write_desktop net.local.langswitcher-selection.desktop \
                "LangSwitcher: конвертувати виділення" "$BINLINK selection"
  write_desktop net.local.langswitcher-line.desktop \
                "LangSwitcher: конвертувати рядок (greedy)" "$BINLINK greedy"
  if have kwriteconfig6; then
    # `--group` twice is what builds the nested [services][<id>] section Plasma 6
    # reads; the value is keys,defaultkeys,friendlyname.
    run kwriteconfig6 --file kglobalshortcutsrc --group services \
        --group net.local.langswitcher-selection.desktop --key _launch \
        "$KEY_SEL,$KEY_SEL,LangSwitcher: конвертувати виділення"
    run kwriteconfig6 --file kglobalshortcutsrc --group services \
        --group net.local.langswitcher-line.desktop --key _launch \
        "$KEY_LINE,$KEY_LINE,LangSwitcher: конвертувати рядок"
    run systemctl --user restart plasma-kglobalaccel.service 2>/dev/null || true
    echo "  shortcuts: $KEY_SEL (selection), $KEY_LINE (line)"
  else
    echo "  (!) kwriteconfig6 not found (sudo dnf install kf6-kconfig)."
  fi
  echo "  If a shortcut does not fire, bind it by hand:"
  echo "    System Settings -> Keyboard -> Shortcuts -> Custom -> Command:"
  echo "      $BINLINK selection     and     $BINLINK greedy"
else
  echo "  skipped (--no-shortcuts). Bind by hand:"
  echo "    $BINLINK selection     and     $BINLINK greedy"
fi

echo ""
if [[ $DRY == 0 ]]; then
  echo "== check =="
  if "$BINLINK" --check; then
    echo ""
    echo "Готово. Виділи текст -> $KEY_SEL."
  else
    echo ""
    echo "(!) --check не пройшов — у JSON вище є підказки (поле hints). Найчастіше це"
    echo "    ydotoold (systemctl status ydotool) або відсутні розкладки us/ua у KDE."
  fi
fi
echo "Видалення: rm -rf $DEST $BINLINK $APPS/net.local.langswitcher-*.desktop"
echo "  (+ sudo rm -f /etc/systemd/system/ydotool.service.d/socket-own.conf; sudo systemctl daemon-reload)"
