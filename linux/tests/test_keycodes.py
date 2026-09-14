#!/usr/bin/env python3
"""Tests for the keycode decoder (auto mode). Run: python3 tests/test_keycodes.py

The decoder is what makes Punto-style behaviour possible: Hyprland reports keys
as X11 keycodes, and a keycode is only a character once the layout is known. An
off-by-one in the physical-key order would silently rewrite the wrong letters,
so the table is checked two ways here — against hand-written expectations, and,
when `xkbcli` is installed, against the real keymap the compositor uses.
"""
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "lib"))

import keycodes as kc  # noqa: E402

L = ["en", "uk", "pl"]
fails = []


def check(name, got, want):
    if got != want:
        fails.append(f"{name}: got {got!r}, want {want!r}")
    else:
        print(f"ok: {name}")


# ---- table shape -----------------------------------------------------------
check("keycode count", len(kc.KEYCODE_ORDER), 47)
check("no duplicate keycodes", len(set(kc.KEYCODE_ORDER)), 47)

# A handful of anchors a human can verify against any keyboard: the physical
# key positions of the standard X11 assignment (evdev code + 8).
check("38 is a", kc.us_char(38), "a")
check("54 is c", kc.us_char(54), "c")
check("24 is q", kc.us_char(24), "q")
check("57 is n", kc.us_char(57), "n")
check("10 is 1", kc.us_char(10), "1")
check("49 is grave", kc.us_char(49), "`")
check("20 is minus", kc.us_char(20), "-")
check("51 is backslash", kc.us_char(51), "\\")
check("shifted 38 is A", kc.us_char(38, True), "A")
check("shifted 19 is )", kc.us_char(19, True), ")")
check("iso key 94 is less/greater", kc.us_char(94, True), ">")
check("iso key 94 under uk", kc.char_in(94, "uk"), "/")
check("iso key 94 under uk, shifted", kc.char_in(94, "uk", True), "|")

# Keys that must never decode as text: the buffer classifies them separately.
for name, code in (("space", kc.SPACE), ("return", kc.RETURN), ("tab", kc.TAB),
                   ("backspace", kc.BACKSPACE), ("escape", kc.ESCAPE),
                   ("up", 111), ("left", 113)):
    check(f"{name} is not text", kc.us_char(code), None)

# ---- decoding under a layout ----------------------------------------------
check("ghbdsn decodes under us", kc.decode("42,43,56,40,39,57", "us")[0], "ghbdsn")
check("ghbdsn decodes under ua", kc.decode("42,43,56,40,39,57", "ua")[0], "привіт")
check("ua aliases uk", kc.decode("42,43,56,40,39,57", "ua"),
      kc.decode("42,43,56,40,39,57", "uk"))
check("hello's keys under ua", kc.decode("43,26,46,46,32", "uk")[0], "руддщ")
check("pl is identity", kc.decode("42", "pl")[0], "g")
check("unknown layout falls back to us", kc.decode("42", "de")[0], "g")
check("shifted decodes upper case", kc.decode("s42,s43", "us")[0], "GH")
check("shifted cyrillic", kc.decode("s42,s43", "uk")[0], "ПР")
check("unknown keycode reported", kc.decode("42,65", "us"), ("g", [65]))
check("empty buffer", kc.decode("", "us"), ("", []))

check("parse tokens", kc.parse_tokens("42,s54, 60"),
      [(42, False), (54, True), (60, False)])
check("parse ignores empties", kc.parse_tokens("42,,54"), [(42, False), (54, False)])


# ---- the real keymap, when xkbcli is available -----------------------------
# Names are converted with small tables of keysym names; single characters
# name themselves, and U+XXXX names carry their own code point.
_NAMES = {
    "exclam": "!", "at": "@", "numbersign": "#", "dollar": "$", "percent": "%",
    "asciicircum": "^", "ampersand": "&", "asterisk": "*", "parenleft": "(",
    "parenright": ")", "minus": "-", "underscore": "_", "equal": "=", "plus": "+",
    "bracketleft": "[", "bracketright": "]", "braceleft": "{", "braceright": "}",
    "backslash": "\\", "bar": "|", "semicolon": ";", "colon": ":", "apostrophe": "'",
    "quotedbl": '"', "grave": "`", "asciitilde": "~", "comma": ",", "period": ".",
    "slash": "/", "less": "<", "greater": ">", "question": "?", "space": " ",
}


# Cyrillic keysym names follow the standard naming (Cyrillic_a = U+0430 and so
# on), which makes them an oracle that does not come from this project's maps.
_CYRILLIC = {}
for _name, _char in (("a", "а"), ("be", "б"), ("ve", "в"), ("ghe", "г"),
                     ("de", "д"), ("ie", "е"), ("io", "ё"), ("zhe", "ж"),
                     ("ze", "з"), ("i", "и"), ("shorti", "й"), ("ka", "к"),
                     ("el", "л"), ("em", "м"), ("en", "н"), ("o", "о"),
                     ("pe", "п"), ("er", "р"), ("es", "с"), ("te", "т"),
                     ("u", "у"), ("ef", "ф"), ("ha", "х"), ("tse", "ц"),
                     ("che", "ч"), ("sha", "ш"), ("shcha", "щ"),
                     ("hardsign", "ъ"), ("softsign", "ь"), ("yeru", "ы"),
                     ("yu", "ю"), ("ya", "я"), ("je", "ј"), ("lje", "љ"),
                     ("nje", "њ"), ("dzhe", "џ")):
    _CYRILLIC["Cyrillic_" + _name.lower()] = _char
    _CYRILLIC["Cyrillic_" + _name.upper()] = _char.upper()
for _name, _char in (("i", "і"), ("yi", "ї"), ("ie", "є")):
    _CYRILLIC["Ukrainian_" + _name] = _char
    _CYRILLIC["Ukrainian_" + _name.upper()] = _char.upper()
_CYRILLIC["Ukrainian_ghe_with_upturn"] = "ґ"
_CYRILLIC["Ukrainian_GHE_WITH_UPTURN"] = "Ґ"
_CYRILLIC["Byelorussian_shortu"] = "ў"
_CYRILLIC["Byelorussian_SHORTU"] = "Ў"


def _sysms(name):
    if name in _NAMES:
        return _NAMES[name]
    if name in _CYRILLIC:
        return _CYRILLIC[name]
    if len(name) == 1:
        return name
    if re.fullmatch(r"U[0-9A-F]{4,6}", name):
        return chr(int(name[1:], 16))
    return None


def check_against_xkbcli(layout, layout_id):
    """Compare the table with the keymap the compositor itself compiles."""
    if not subprocess.run(["sh", "-c", "command -v xkbcli"], capture_output=True).returncode == 0:
        print("skip: xkbcli not installed (real-keymap cross-check)")
        return
    text = subprocess.run(["xkbcli", "compile-keymap", "--layout", layout],
                          capture_output=True, text=True).stdout
    codes = {name: int(num) for name, num in
             re.findall(r"<([A-Z0-9]+)>\s*=\s*(\d+);", text)}
    checked = 0
    for name, symbols in re.findall(r"key\s+<([A-Z0-9]+)>\s*\{\s*\[([^\]]*)\]\s*\};", text):
        code = codes.get(name)
        levels = [s.strip() for s in symbols.split(",")]
        if code is None or code not in kc.US_KEYCODES or len(levels) < 2:
            continue
        want = tuple(_sysms(levels[i]) for i in range(2))
        if None in want:
            continue
        check(f"xkbcli {layout} {name} ({code})",
              (kc.char_in(code, layout_id), kc.char_in(code, layout_id, True)), want)
        checked += 1
    check(f"xkbcli {layout}: cross-checked keys", checked >= 40, True)


check_against_xkbcli("us", "en")
check_against_xkbcli("ua", "uk")

if fails:
    print("\nFAILURES:")
    for f in fails:
        print(" -", f)
    sys.exit(1)
print("\nALL-OK")
