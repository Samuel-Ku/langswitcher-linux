#!/usr/bin/env python3
"""LangSwitcher core — Python port of the macOS Swift logic.

Original: https://github.com/Samuel-Ku/langSwitcher (fork of reg2005/langSwitcher)
Ported 1:1 from:
  - LayoutCharacterMap (KeyboardLayout.swift)
  - LayoutMapper.convert / detectSourceLayout (LayoutMapper.swift)
  - TextConverter.convertSelectedText / looksLikeWrongLayout /
    findWrongLayoutBoundary / convertLineGreedy (TextConverter.swift)

No dependencies, stdlib only.
"""

QWERTY = "`1234567890-=qwertyuiop[]\\asdfghjkl;'zxcvbnm,./~!@#$%^&*()_+QWERTYUIOP{}|ASDFGHJKL:\"ZXCVBNM<>?"

_RUSSIAN = "ё1234567890-=йцукенгшщзхъ\\фывапролджэячсмитьбю.Ё!\"№;%:?*()_+ЙЦУКЕНГШЩЗХЪ/ФЫВАПРОЛДЖЭЯЧСМИТЬБЮ,"
_UKRAINIAN = "'1234567890-=йцукенгшщзхї\\фівапролджєячсмитьбю.₴!\"№;%:?*()_+ЙЦУКЕНГШЩЗХЇ/ФІВАПРОЛДЖЄЯЧСМИТЬБЮ,"
_GERMAN = "^1234567890ß´qwertzuiopü+#asdfghjklöäyxcvbnm,.-°!\"§$%&/()=?`QWERTZUIOPÜ*'ASDFGHJKLÖÄYXCVBNM;:_"
_FRENCH = "²&é\"'(-è_çà)=azertyuiop^$*qsdfghjklmùwxcvbn,;:!³1234567890°+AZERTYUIOP¨£µQSDFGHJKLM%WXCVBN?./§"
_SPANISH = "º1234567890'¡qwertyuiop`+çasdfghjklñ´zxcvbnm,.-ª!\"·$%&/()=?¿QWERTYUIOP^*ÇASDFGHJKLÑ¨ZXCVBNM;:_"


def _build_map(target: str) -> dict:
    q = list(QWERTY)
    t = list(target)
    return {q[i]: t[i] for i in range(min(len(q), len(t)))}


def _identity_map() -> dict:
    return {c: c for c in QWERTY}


# NOTE про польську:
# Польська programisty фізично збігається з US QWERTY (діакритика через AltGr),
# тому базова мапа — identity, як і в оригіналі для "british"/"abc".
# Конвертація en<->pl для звичайного ASCII — no-op (і це правильно).
# Реальні кейси "не та розкладка" покриваються парами en<->uk, en<->ru.
MAPS: dict[str, dict] = {
    "en": _identity_map(),
    "us": _identity_map(),
    "uk": _build_map(_UKRAINIAN),
    "ua": _build_map(_UKRAINIAN),
    "ru": _build_map(_RUSSIAN),
    "pl": _identity_map(),  # див. NOTE вище
    "de": _build_map(_GERMAN),
    "fr": _build_map(_FRENCH),
    "es": _build_map(_SPANISH),
}

# Польська діакритика -> базова латинська (для детекту/евристик).
PL_FOLD = str.maketrans({
    "ą": "a", "ć": "c", "ę": "e", "ł": "l", "ń": "n",
    "ó": "o", "ś": "s", "ź": "z", "ż": "z",
    "Ą": "A", "Ć": "C", "Ę": "E", "Ł": "L", "Ń": "N",
    "Ó": "O", "Ś": "S", "Ź": "Z", "Ż": "Z",
})

DEFAULT_LAYOUTS = ["en", "uk", "pl"]

# Польська діакритика, якої нема в жодній іншій мапі (ą ć ę ł ń ś ź ż).
# Польська programisty фізично = US QWERTY, тому кейсу "не та розкладка"
# en<->pl для ASCII не існує; а текст з діакритикою — точно польський
# намір, і конвертувати його не можна.
_PL_UNIQUE = set("ąćęłńśźżĄĆĘŁŃŚŹŻ")
# ó/Ó є і в іспанській/французькій, тому вважаємо польським
# лише коли es/fr не серед кандидатів.
_PL_O = set("óÓ")


def _is_polish_text(text: str, layouts: list[str]) -> bool:
    if any(c in _PL_UNIQUE for c in text):
        return True
    if any(c in _PL_O for c in text) and "es" not in layouts and "fr" not in layouts:
        return True
    return False


def _is_ascii(c: str) -> bool:
    return ord(c) < 128


def convert(text: str, from_layout: str, to_layout: str) -> str | None:
    """Покроковий порт LayoutMapper.convert (включно з punctuation preservation)."""
    src = MAPS.get(from_layout)
    dst = MAPS.get(to_layout)
    if src is None or dst is None:
        return None
    reverse = {}
    for k, v in src.items():
        reverse.setdefault(v, k)
    out = []
    for ch in text:
        physical = reverse.get(ch)
        target = dst.get(physical) if physical is not None else None
        if physical is not None and target is not None:
            # пунктуація: non-letter -> non-letter лишаємо як є
            if not ch.isalpha() and not target.isalpha():
                out.append(ch)
            else:
                out.append(target)
        else:
            out.append(ch)
    return "".join(out)


def detect_source_layout(text: str, candidates: list[str]) -> str | None:
    """Порт detectSourceLayout: чий набір символів покриває більше символів тексту."""
    best = None
    best_score = 0
    for lid in candidates:
        m = MAPS.get(lid)
        if m is None:
            continue
        charset = set(m.values())
        score = sum(1 for c in text if c in charset)
        if score > best_score:
            best_score = score
            best = lid
    return best


def convert_selected(text: str, layouts: list[str]) -> tuple[str, str] | None:
    """Порт convertSelectedTextWithInfo. Повертає (конвертований, target_layout)."""
    if len(layouts) < 2:
        return None
    if "pl" in layouts and _is_polish_text(text, layouts):
        return None
    src = detect_source_layout(text, layouts)
    if src is None:
        return None
    target = next((l for l in layouts if l != src), None)
    if target is None:
        target = layouts[0]
    res = convert(text, src, target)
    if res is None:
        return None
    return res, target


def looks_like_wrong_layout(text: str, layouts: list[str]) -> bool:
    """Порт looksLikeWrongLayout: чи переключення скрипту після конвертації."""
    trimmed = text.strip()
    if not trimmed:
        return False
    if len(layouts) < 2:
        return False
    if "pl" in layouts and _is_polish_text(trimmed, layouts):
        return False
    src = detect_source_layout(trimmed, layouts)
    if src is None:
        return False
    for layout in layouts:
        if layout == src:
            continue
        conv = convert(trimmed, src, layout)
        if conv is None:
            continue
        src_latin_only = all(_is_ascii(c) or not c.isalpha() for c in trimmed)
        conv_non_latin = any(not _is_ascii(c) and c.isalpha() for c in conv)
        src_non_latin = any(not _is_ascii(c) and c.isalpha() for c in trimmed)
        conv_latin_only = all(_is_ascii(c) or not c.isalpha() for c in conv)
        if src_latin_only and conv_non_latin:
            return True
        if src_non_latin and conv_latin_only:
            return True
    return False


def _tokenize(text: str) -> list[str]:
    tokens: list[str] = []
    cur = ""
    in_word = False
    for ch in text:
        is_word = ch.isalpha() or ch.isdigit()
        if is_word:
            if not in_word and cur:
                tokens.append(cur)
                cur = ""
            in_word = True
            cur += ch
        else:
            if in_word and cur:
                tokens.append(cur)
                cur = ""
            in_word = False
            cur += ch
    if cur:
        tokens.append(cur)
    return tokens


def _is_sep(tok: str) -> bool:
    return all(not c.isalpha() and not c.isdigit() for c in tok)


def find_wrong_boundary(text: str, layouts: list[str]) -> tuple[str, str] | None:
    """Порт findWrongLayoutBoundary (greedy two-pass, поріг 70%)."""
    if len(layouts) < 2:
        return None
    tokens = _tokenize(text)
    if not tokens:
        return None
    words = [t for t in tokens if not _is_sep(t)]
    if not words:
        return None

    wrong = sum(1 for w in words if looks_like_wrong_layout(w, layouts))

    if wrong == len(words):
        return "", text
    if len(words) >= 3 and wrong / len(words) >= 0.7:
        return "", text

    start = len(tokens)
    found = False
    for i in range(len(tokens) - 1, -1, -1):
        tok = tokens[i]
        if _is_sep(tok):
            continue
        if looks_like_wrong_layout(tok, layouts):
            start = i
            found = True
        else:
            break
    if not found or start >= len(tokens):
        return None
    keep = "".join(tokens[:start])
    conv = "".join(tokens[start:])
    if not conv.strip():
        return None
    return keep, conv


def convert_greedy(text: str, layouts: list[str]) -> tuple[str, str] | None:
    """Порт convertLineGreedyWithInfo."""
    b = find_wrong_boundary(text, layouts)
    if b is None:
        return None
    keep, conv_part = b
    r = convert_selected(conv_part, layouts)
    if r is None:
        return None
    converted, target = r
    return keep + converted, target
