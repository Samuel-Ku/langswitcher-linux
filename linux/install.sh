#!/usr/bin/env bash
# install.sh — LangSwitcher for generic Linux (Ubuntu GNOME + Mint Cinnamon).
# Deps -> copy to ~/.local/share/langswitcher -> symlink ~/.local/bin/linux-convert
# -> register SUPER+GRAVE shortcuts (GNOME/Cinnamon via gsettings, else manual).
set -u

SRC_DIR="$(cd "$(dirname "$0")" && pwd)"
DEST="$HOME/.local/share/langswitcher"
BINLINK="$HOME/.local/bin/linux-convert"

echo "== 1/3 deps =="
if command -v apt-get >/dev/null 2>&1; then
  sudo apt-get update \
  && sudo apt-get install -y python3 wl-clipboard wtype xclip xdotool libnotify-bin
elif command -v dnf >/dev/null 2>&1; then
  sudo dnf install -y python3 wl-clipboard wtype xclip xdotool libnotify
elif command -v pacman >/dev/null 2>&1; then
  sudo pacman -S --needed --noconfirm python3 wl-clipboard wtype xclip xdotool libnotify
else
  echo "(!) невідомий пакетний менеджер — встанови вручну:"
  echo "    python3 + (wl-clipboard, wtype) для Wayland та/або (xclip, xdotool) для X11 + notify-send"
fi

echo "== 2/3 files =="
mkdir -p "$HOME/.local/bin"
rm -rf "$DEST"
mkdir -p "$DEST"
cp -r "$SRC_DIR/bin" "$SRC_DIR/lib" "$DEST/"
chmod +x "$DEST/bin/linux-convert"
ln -sf "$DEST/bin/linux-convert" "$BINLINK"
echo "встановлено: $BINLINK -> $DEST/bin/linux-convert"
"$BINLINK" --check || echo "(!) --check не пройшов — дивись missing вище"

echo "== 3/3 shortcuts =="
DESKTOP="${XDG_CURRENT_DESKTOP:-}"
if [[ "$DESKTOP" == *"GNOME"* ]] && command -v gsettings >/dev/null 2>&1; then
  python3 - "$BINLINK" <<'EOF'
import subprocess, sys
worker = sys.argv[1]
SCHEMA = "org.gnome.settings-daemon.plugins.media-keys"
def get(k):
    return subprocess.run(["gsettings", "get", SCHEMA, k],
                          capture_output=True, text=True).stdout.strip()
def cur_list():
    raw = get("custom-keybindings")
    if raw in ("@as []", "[]", ""):
        return []
    try:
        return [x for x in __import__("ast").literal_eval(raw) if isinstance(x, str)]
    except Exception:
        return []
def entry(path):
    base = ["gsettings", "get", f"{SCHEMA}.custom-keybinding:{path}"]
    vals = {}
    for k in ("name", "command", "binding"):
        r = subprocess.run(base + [k], capture_output=True, text=True)
        vals[k] = r.stdout.strip()
    return vals
def add(name, command, binding):
    paths = cur_list()
    for p in paths:  # idempotent: не дублюємо свою команду
        if worker in entry(p).get("command", "") and binding in entry(p).get("binding", ""):
            print(f"  вже є: {name} ({binding})")
            return
    i = 0
    while f"/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/custom{i}/" in paths:
        i += 1
    path = f"/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/custom{i}/"
    sub = f"{SCHEMA}.custom-keybinding:{path}"
    subprocess.run(["gsettings", "set", sub, "name", name], check=True)
    subprocess.run(["gsettings", "set", sub, "command", command], check=True)
    subprocess.run(["gsettings", "set", sub, "binding", binding], check=True)
    subprocess.run(["gsettings", "set", SCHEMA, "custom-keybindings",
                    str(paths + [path])], check=True)
    print(f"  додано: {name} ({binding})")
add("LangSwitcher: конвертувати виділення", f"{worker} selection", "<Super>grave")
add("LangSwitcher: конвертувати рядок", f"{worker} greedy", "<Super><Shift>grave")
EOF
elif [[ "$DESKTOP" == *"Cinnamon"* ]] && command -v gsettings >/dev/null 2>&1; then
  python3 - "$BINLINK" <<'EOF'
import ast, subprocess, sys
worker = sys.argv[1]
SCHEMA = "org.cinnamon.desktop.keybindings"
def get(key):
    return subprocess.run(["gsettings", "get", SCHEMA, key],
                          capture_output=True, text=True).stdout.strip()
def cur_list():
    raw = get("custom-list")
    if raw in ("@as []", "[]", ""):
        return []
    try:
        return [x for x in ast.literal_eval(raw) if isinstance(x, str)]
    except Exception:
        return []
def entry(name):
    base = ["gsettings", "get",
            f"org.cinnamon.desktop.keybindings.custom-keybinding:/org/cinnamon/desktop/keybindings/custom-keybindings/{name}/"]
    return {k: subprocess.run(base + [k], capture_output=True, text=True).stdout.strip()
            for k in ("name", "command", "binding")}
def add(name, command, binding):
    names = cur_list()
    for n in names:  # idempotent
        e = entry(n)
        if worker in e.get("command", "") and binding in e.get("binding", ""):
            print(f"  вже є: {name} ({binding})")
            return
    i = 0
    while f"custom{i}" in names:
        i += 1
    slot = f"custom{i}"
    sub = f"org.cinnamon.desktop.keybindings.custom-keybinding:/org/cinnamon/desktop/keybindings/custom-keybindings/{slot}/"
    subprocess.run(["gsettings", "set", sub, "name", name], check=True)
    subprocess.run(["gsettings", "set", sub, "command", command], check=True)
    subprocess.run(["gsettings", "set", sub, "binding", f"['{binding}']"], check=True)
    subprocess.run(["gsettings", "set", SCHEMA, "custom-list", str(names + [slot])], check=True)
    print(f"  додано: {name} ({binding})")
add("LangSwitcher: конвертувати виділення", f"{worker} selection", "<Super>grave")
add("LangSwitcher: конвертувати рядок", f"{worker} greedy", "<Super><Shift>grave")
EOF
else
  echo "DE '$DESKTOP' — додай шорткати вручну:"
  echo "  команда 1: $BINLINK selection           (клавіша: Super+`)"
  echo "  команда 2: $BINLINK greedy              (клавіша: Super+Shift+`)"
  echo "  GNOME: Параметри -> Клавіатура -> Спеціальні комбінації"
  echo "  Cinnamon: Параметри системи -> Клавіатура -> Комбінації -> Власні"
  echo "  KDE: Параметри -> Комбінації клавіш -> Додати команду"
fi

echo ""
echo "Готово. Перевірка: $BINLINK --check"
echo "Видалення: rm -rf $DEST $BINLINK (+ прибери шорткати)"
