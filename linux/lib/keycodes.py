#!/usr/bin/env python3
"""Decode X11 keycodes into characters, for the automatic (Punto-style) mode.

Hyprland's Lua API reports every key as an X11 keycode (``input.keyboard.key``),
and a keycode only means something once the layout that maps it is known:
38 is "a" under us and "ф" under ua. This module makes that mapping explicit.

The physical-key order below is the *same* order ``langswitcher.QWERTY`` is
written in, so the decoder and the converter can never disagree about which
character sits on which key: a keycode is decoded to its US character first and
then pushed through the converter's own layout maps. That is also why layouts
the converter treats as identity (pl) decode to plain ASCII.

X11 keycode = evdev code + 8 (evdev 30 = "a" = X11 38), which is the numbering
Hyprland hands to ``input.keyboard.key``.

This file is intentionally duplicated in the omarchy-plugin and linux bundles;
keep both copies byte-identical.

No dependencies, stdlib only.
"""

from langswitcher import MAPS, QWERTY

# ` 1 2 3 4 5 6 7 8 9 0 - = q w e r t y u i o p [ ] \ a s d f g h j k l ; '
# z x c v b n m , . /   — the 47 main-block keys, in QWERTY's own order.
KEYCODE_ORDER = (
    (49,)                      # `~
    + tuple(range(10, 20))     # 1..0
    + (20, 21)                 # -=
    + tuple(range(24, 36))     # qwertyuiop[]
    + (51,)                    # backslash
    + tuple(range(38, 49))     # asdfghjkl;'
    + tuple(range(52, 62))     # zxcvbnm,./
)

_HALF = len(KEYCODE_ORDER)    # 47: the shift layer repeats the same key order

# keycode -> (unshifted, shifted)
US_KEYCODES = {kc: (QWERTY[i], QWERTY[i + _HALF])
               for i, kc in enumerate(KEYCODE_ORDER)}
# The extra ISO key left of Z (evdev 86): xkeyboard-config gives it </> in the
# US layout, which is what the plain-US table has to say about it.
US_KEYCODES[94] = ("<", ">")

# Three positions the layouts do not agree about beyond the plain positional
# map, spelled out because the converter's own map is not the same thing as
# what the keyboard produces. Verified against the keymaps the compositor
# compiles (xkbcli), which is the authority for "what did the app receive":
#   us:  ` ~    \ |    < >
#   ua:  ' ʼ    ґ Ґ    / |
KEYCODE_SPECIAL = {
    49: {"uk": ("'", "ʼ"), "ua": ("'", "ʼ")},
    51: {"uk": ("ґ", "Ґ"), "ua": ("ґ", "Ґ")},
    94: {"uk": ("/", "|"), "ua": ("/", "|")},
}

# A handful of keys the buffer must never treat as text, for callers that want
# to classify keycodes without decoding them.
SPACE = 65
RETURN = 36
TAB = 23
BACKSPACE = 22
ESCAPE = 9


def us_char(keycode: int, shifted: bool = False) -> str | None:
    """The character the keycode produces under a plain US layout."""
    pair = US_KEYCODES.get(keycode)
    if pair is None:
        return None
    return pair[1 if shifted else 0]


def char_in(keycode: int, layout: str, shifted: bool = False) -> str | None:
    """The character the keycode produces under `layout` (en/us, uk/ua, pl).

    Unknown keycodes (navigation keys, multimedia keys, a layout we have no map
    for) return None: the caller decides whether that makes the whole run
    untrustworthy, and the automatic fixer refuses to act when it does.
    """
    special = KEYCODE_SPECIAL.get(keycode, {}).get(layout)
    if special:
        return special[1 if shifted else 0]
    char = us_char(keycode, shifted)
    if char is None:
        return None
    return MAPS.get(layout, {}).get(char, char)


def parse_tokens(tokens) -> list[tuple[int, bool]]:
    """Parse the wire format the Lua module sends.

    ``"38,s54,60"`` -> [(38, False), (54, True), (60, False)]: a bare number is
    an unshifted key, an ``s`` prefix means Shift was held (Lua sees the
    modifier; nothing else downstream does).
    """
    parsed: list[tuple[int, bool]] = []
    for token in str(tokens).replace(" ", "").split(","):
        if not token:
            continue
        shifted = token[0] in "sS"
        number = token[1:] if shifted else token
        parsed.append((int(number), shifted))
    return parsed


def decode(tokens, layout: str) -> tuple[str, list[int]]:
    """Decode keycodes into the text the app received under `layout`.

    Returns the text and the keycodes that could not be decoded. An empty text
    with unknown keys means "do not trust this buffer".
    """
    text = []
    unknown = []
    for keycode, shifted in parse_tokens(tokens):
        char = char_in(keycode, layout, shifted)
        if char is None:
            unknown.append(keycode)
        else:
            text.append(char)
    return "".join(text), unknown
