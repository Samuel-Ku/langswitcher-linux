#!/usr/bin/env python3
"""Layout Switch mode — switch the active layout after a conversion.

Once the text is converted, the next word should already be typed in the layout
that was just converted to, so this module decides whether to switch (always /
if-converted / never) and performs the switch. Two desktops are implemented:

* **Hyprland** via ``hyprctl switchxkblayout`` — what the Omarchy plugin uses;
* **KDE Plasma** via the ``org.kde.keyboard`` D-Bus interface (object
  ``/Layouts``, interface ``org.kde.KeyboardLayouts``). That interface is served
  by KWin on Wayland and by the kded keyboard module on X11, so a KDE port needs
  no session branching. This module shells out to ``gdbus``: it is always present
  on Fedora (``glib2``), while ``qdbus6`` does not exist there at all and bare
  ``qdbus`` is Qt4.

Anything else returns False (a no-op) rather than guessing. The pure parts are
unit-tested in test_layoutswitch.py.

Two things worth knowing about the KDE path:

* ``getLayoutsList()`` answers ``a(sss)`` — ``(shortName, displayName,
  longName)`` per layout — and only ``shortName`` is machine-readable: it is the
  xkb layout code (``us``, ``ua``), which is exactly what ``LANG_TO_XKB`` holds.
  The variant is not exposed.
* ``setLayout(uint)`` answers a bool, so a refused switch is visible instead of
  being assumed to have worked.
"""
import ast
import json
import os
import re
import shutil
import subprocess

# Our layout ids -> xkb layout codes, as `hyprctl devices` and KDE's
# `getLayoutsList()` both spell them.
LANG_TO_XKB = {"en": "us", "uk": "ua", "pl": "pl"}

KDE_SERVICE = "org.kde.keyboard"
KDE_PATH = "/Layouts"
KDE_IFACE = "org.kde.KeyboardLayouts"

_MODE_ALWAYS = "always"
_MODE_IF_CONVERTED = "if-converted"


def should_switch(mode: str, converted: bool) -> bool:
    """`always` switches unconditionally, `if-converted` only when a conversion
    happened, anything else never."""
    if mode == _MODE_ALWAYS:
        return True
    if mode == _MODE_IF_CONVERTED:
        return bool(converted)
    return False


# ---- which desktop to talk to ----------------------------------------------

def detect_backend(env=None, which=shutil.which) -> str:
    """``"hyprland"``, ``"kde"`` or ``""`` (neither).

    Hyprland is recognised first, by its own signature variable or its desktop
    name, so the Omarchy plugin keeps the path it has always used even if
    something KDE-ish is also installed; KDE is recognised by the desktop name
    *and* ``gdbus``, which is what the call needs. The mere presence of
    ``hyprctl`` is deliberately *not* evidence: a KDE user can have it installed
    without a running Hyprland, and guessing wrong here is a switch that silently
    does nothing.
    """
    env = os.environ if env is None else env
    forced = (env.get("LANGSWITCHER_LAYOUT_BACKEND") or "").strip().lower()
    if forced in ("hyprland", "kde", "none"):
        # An escape hatch for a port that cannot be tested on the machine it is
        # written on: name the API instead of hoping the desktop name matches.
        return "" if forced == "none" else forced
    desktop = (env.get("XDG_CURRENT_DESKTOP") or "").upper()
    if (env.get("HYPRLAND_INSTANCE_SIGNATURE") or "HYPRLAND" in desktop) and which("hyprctl"):
        return "hyprland"
    if ("KDE" in desktop or "PLASMA" in desktop) and which("gdbus"):
        return "kde"
    return ""


# ---- KDE Plasma (org.kde.keyboard) -----------------------------------------

def _gdbus(method: str, *args: str, runner=subprocess.run):
    return runner(["gdbus", "call", "--session", "--dest", KDE_SERVICE,
                   "--object-path", KDE_PATH, "--method",
                   f"{KDE_IFACE}.{method}", *args],
                  capture_output=True, text=True, timeout=5)


def parse_kde_layouts(text: str) -> list[str]:
    """The xkb codes out of ``getLayoutsList()``, in KDE's own order.

    gdbus prints ``a(sss)`` as ``([('us', '', 'English (US)'), ('ua', '', …)],)``.
    That is valid Python, so ``ast.literal_eval`` is tried first; the regex is the
    fallback for output it cannot read (a gdbus build that escapes a translated
    name differently, or a hand-written fixture). Only the first string of each
    triple is taken: it is the xkb code, and an empty display name is normal.
    """
    text = (text or "").strip()
    try:
        parsed = ast.literal_eval(text)
        entries = parsed[0] if isinstance(parsed, tuple) and len(parsed) == 1 else parsed
        if not isinstance(entries, (list, tuple)):
            raise ValueError("not a list of layouts")
        codes = []
        for entry in entries:
            if not isinstance(entry, (tuple, list)) or not entry:
                raise ValueError("not a (shortName, displayName, longName) triple")
            if not isinstance(entry[0], str):
                raise ValueError("shortName is not a string")
            codes.append(entry[0])
        if codes:
            return codes
    except (ValueError, SyntaxError, TypeError, IndexError):
        pass
    return re.findall(r"\(\s*'((?:\\.|[^'\\])*)'", text)


def kde_layouts(runner=subprocess.run, which=shutil.which) -> list[str]:
    """xkb codes KDE knows about, or ``[]`` when the interface is not there."""
    if not which("gdbus"):
        return []
    try:
        done = _gdbus("getLayoutsList", runner=runner)
    except Exception:
        return []
    if getattr(done, "returncode", 0) != 0:
        return []
    return parse_kde_layouts(getattr(done, "stdout", "") or "")


def switch_kde(lang: str, runner=subprocess.run, which=shutil.which) -> bool:
    """Switch KDE's active layout to `lang`. Returns True if it switched.

    An unknown layout, a missing interface or a refused ``setLayout`` is False —
    the caller reports that instead of assuming the layout moved.
    """
    code = LANG_TO_XKB.get(lang)
    if not code:
        return False
    codes = kde_layouts(runner=runner, which=which)
    if code not in codes:
        return False
    try:
        done = _gdbus("setLayout", str(codes.index(code)), runner=runner)
    except Exception:
        return False
    if getattr(done, "returncode", 0) != 0:
        return False
    # setLayout answers `(true,)` or `(false,)`; only a negative answer fails.
    return "false" not in (getattr(done, "stdout", "") or "").strip().lower()


# ---- Hyprland (hyprctl) ----------------------------------------------------

def choose_keyboard(devices: dict | None) -> dict | None:
    """Pick the keyboard to drive: the main one, else the first with a layout."""
    keyboards = (devices or {}).get("keyboards") or []
    if not keyboards:
        return None
    pool = [k for k in keyboards if k.get("main")] or keyboards
    for k in pool:
        if k.get("layout"):
            return k
    return None


def index_for_lang(keyboard: dict | None, lang: str) -> int | None:
    """Index of `lang`'s xkb code in the keyboard's layout list, or None."""
    code = LANG_TO_XKB.get(lang)
    if not code or not keyboard:
        return None
    codes = [c.strip() for c in (keyboard.get("layout") or "").split(",") if c.strip()]
    return codes.index(code) if code in codes else None


def _hyprctl_devices() -> dict | None:
    if not shutil.which("hyprctl"):
        return None
    try:
        r = subprocess.run(["hyprctl", "-j", "devices"], capture_output=True,
                           text=True, timeout=3)
        return json.loads(r.stdout or "{}") if r.returncode == 0 else None
    except Exception:
        return None


def switch_to(lang: str, devices: dict | None = None, runner=subprocess.run,
              backend: str | None = None) -> bool:
    """Switch the active layout to `lang`. Returns True if a switch was made.

    `devices`, `runner` and `backend` are injectable for tests. Unknown layouts
    and desktops we cannot drive are a no-op, not an error.
    """
    backend = detect_backend() if backend is None else backend
    if backend == "kde":
        return switch_kde(lang, runner=runner)
    if backend != "hyprland":
        return False
    if devices is None:
        devices = _hyprctl_devices()
    keyboard = choose_keyboard(devices)
    index = index_for_lang(keyboard, lang)
    if not keyboard or index is None:
        return False
    try:
        r = runner(["hyprctl", "switchxkblayout", keyboard["name"], str(index)],
                   capture_output=True, text=True, timeout=3)
        return getattr(r, "returncode", 0) == 0
    except Exception:
        return False


def switch_everywhere(lang: str, devices: dict | None = None, runner=subprocess.run,
                      backend: str | None = None) -> bool:
    """Switch *every* keyboard to `lang` — the Right-Alt binding's own call.

    ``switch_to`` drives one device (the main keyboard), which is right for an
    explicit user action but not for a background one: the device the compositor
    calls "main" changes as virtual keyboards (fcitx5, wtype) appear and vanish,
    and the keyboards are switched independently. A conversion must not leave a
    second keyboard on the old layout, so automatic mode moves them all.

    KDE has one layout for the session, so this is the same call as `switch_to`
    there.
    """
    backend = detect_backend() if backend is None else backend
    if backend == "kde":
        return switch_kde(lang, runner=runner)
    if backend != "hyprland":
        return False
    if devices is None:
        devices = _hyprctl_devices()
    index = index_for_lang(choose_keyboard(devices), lang)
    if index is None:
        return False
    try:
        r = runner(["hyprctl", "switchxkblayout", "all", str(index)],
                   capture_output=True, text=True, timeout=3)
        return getattr(r, "returncode", 0) == 0
    except Exception:
        return False
