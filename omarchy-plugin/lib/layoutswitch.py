#!/usr/bin/env python3
"""Layout Switch mode — switch the OS active layout after a conversion.

macOS parity: LangSwitcher's `LayoutSwitchMode` (always / ifLastWordConverted /
ifAnyWordConverted, default always) calls TISSelectInputSource so the next word
is typed in the just-converted language. This module ports the decision and the
Linux (Hyprland) action; the pure parts are unit-tested in test_layoutswitch.py.

Only Hyprland is implemented; other compositors return False (no-op) rather than
guess. Windows does its own switch in LangSwitcher.ahk.
"""
import json
import shutil
import subprocess

# Our layout ids -> xkb layout codes as they appear in `hyprctl devices`.
LANG_TO_XKB = {"en": "us", "uk": "ua", "pl": "pl"}

_MODE_ALWAYS = "always"
_MODE_IF_CONVERTED = "if-converted"


def should_switch(mode: str, converted: bool) -> bool:
    """macOS maps all three modes to the same outcome (conversionOccurred is
    always true at the call sites); we keep `always` and `if-converted` plus an
    explicit `never`."""
    if mode == _MODE_ALWAYS:
        return True
    if mode == _MODE_IF_CONVERTED:
        return bool(converted)
    return False


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


def switch_to(lang: str, devices: dict | None = None, runner=subprocess.run) -> bool:
    """Switch the active layout to `lang`. Returns True if a switch was made.

    `devices` and `runner` are injectable for tests. Unknown/absent layouts are
    a no-op, not an error.
    """
    if devices is None:
        devices = _hyprctl_devices()
    keyboard = choose_keyboard(devices)
    index = index_for_lang(keyboard, lang)
    if not keyboard or index is None:
        return False
    try:
        runner(["hyprctl", "switchxkblayout", keyboard["name"], str(index)],
               capture_output=True, text=True, timeout=3)
        return True
    except Exception:
        return False
