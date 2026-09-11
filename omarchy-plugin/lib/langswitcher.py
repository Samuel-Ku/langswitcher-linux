#!/usr/bin/env python3
"""LangSwitcher core — Python port of the macOS Swift logic.

Original: https://github.com/Samuel-Ku/langSwitcher (fork of reg2005/langSwitcher)
Ported 1:1 from:
  - LayoutCharacterMap (KeyboardLayout.swift)
  - LayoutMapper.convert / detectSourceLayout (LayoutMapper.swift)
  - TextConverter.convertSelectedText / looksLikeWrongLayout /
    findWrongLayoutBoundary / convertLineGreedy (TextConverter.swift)

Only the layouts this project ships are kept: en, uk, pl (Russian is
deliberately absent — it was never needed).

This file is intentionally duplicated in the omarchy-plugin and linux bundles;
keep both copies byte-identical.

No dependencies, stdlib only.
"""

QWERTY = "`1234567890-=qwertyuiop[]\\asdfghjkl;'zxcvbnm,./~!@#$%^&*()_+QWERTYUIOP{}|ASDFGHJKL:\"ZXCVBNM<>?"

_UKRAINIAN = "'1234567890-=йцукенгшщзхї\\фівапролджєячсмитьбю.₴!\"№;%:?*()_+ЙЦУКЕНГШЩЗХЇ/ФІВАПРОЛДЖЄЯЧСМИТЬБЮ,"


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
# Реальний кейс "не та розкладка" покривається парою en<->uk.
MAPS: dict[str, dict] = {
    "en": _identity_map(),
    "us": _identity_map(),
    "uk": _build_map(_UKRAINIAN),
    "ua": _build_map(_UKRAINIAN),
    "pl": _identity_map(),  # див. NOTE вище
}

DEFAULT_LAYOUTS = ["en", "uk", "pl"]

# Польська діакритика: ніколи не є артефактом пари en<->uk, тож текст із нею
# завжди вважаємо навмисною польською і не конвертуємо.
_PL_DIACRITICS = set("ąćęłńśźżĄĆĘŁŃŚŹŻóÓ")


def _is_polish_text(text: str) -> bool:
    return any(c in _PL_DIACRITICS for c in text)


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


def _split_affixes(text: str) -> tuple[str, str, str]:
    """Split leading/trailing non-alphanumerics from the core.

    "ghbdsn." -> ("", "ghbdsn", "."); "(Руддщ)" -> ("(", "Руддщ", ")").
    Punctuation a user typed at a word boundary is theirs to keep — it must not
    be run through the layout map (where '.' would become 'ю', ',' -> 'б').
    """
    i, j = 0, len(text)
    while i < j and not (text[i].isalpha() or text[i].isdigit()):
        i += 1
    while j > i and not (text[j - 1].isalpha() or text[j - 1].isdigit()):
        j -= 1
    return text[:i], text[i:j], text[j:]


def convert_selected(text: str, layouts: list[str]) -> tuple[str, str] | None:
    """Порт convertSelectedTextWithInfo. Повертає (конвертований, target_layout).

    Convention applies only to the alphanumeric core; leading/trailing punctuation
    is preserved verbatim so "ghbdsn." -> "привіт.", not "привітю".
    """
    if len(layouts) < 2:
        return None
    if _is_polish_text(text):
        return None
    lead, core, trail = _split_affixes(text)
    if not core:
        return None
    src = detect_source_layout(core, layouts)
    if src is None:
        return None
    target = next((l for l in layouts if l != src), None)
    if target is None:
        target = layouts[0]
    res = convert(core, src, target)
    if res is None:
        return None
    return lead + res + trail, target


def looks_like_wrong_layout(text: str, layouts: list[str]) -> bool:
    """Порт looksLikeWrongLayout: чи переключення скрипту після конвертації."""
    trimmed = text.strip()
    if not trimmed:
        return False
    if len(layouts) < 2:
        return False
    if _is_polish_text(trimmed):
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


# Vowels per script, for the conservative auto-mode check below.
_LATIN_VOWELS = set("aeiouyAEIOUY")
_CYRILLIC_VOWELS = set("аеєиіїоуюяАЕЄИІЇОУЮЯ")


def _has_vowel(text: str, vowels: set) -> bool:
    return any(c in vowels for c in text)


def looks_like_wrong_layout_strict(text: str, layouts: list[str], min_len: int = 3) -> bool:
    """Conservative check for AUTO modes (Punto-style split-word conversion).

    ``looks_like_wrong_layout`` (the faithful macOS port) returns True for *any*
    Latin word that maps to Cyrillic, so it must only ever run on an explicit
    user action. Auto-converting after Space needs a stricter signal, or every
    ordinary English word would be rewritten.

    Rule: fire only when the word is implausible in its current script (no
    vowel) and plausible in the target script (has a vowel). "ghbdsn" has no
    Latin vowel and maps to "привіт" (has Cyrillic vowels) -> convert. "hello"
    already has vowels -> leave alone. Polish diacritics never convert.

    Leading/trailing punctuation is ignored for the test, so a sentence-ending
    "ghbdsn." still converts (and the "." is preserved).
    """
    _, core, _ = _split_affixes(text.strip())
    if len(core) < min_len or not core.isalpha():
        return False
    if _is_polish_text(text):
        return False
    resolved = convert_selected(core, layouts)
    if resolved is None:
        return False
    conv, _ = resolved
    if conv == core:
        return False
    if core.isascii():
        return not _has_vowel(core, _LATIN_VOWELS) and _has_vowel(conv, _CYRILLIC_VOWELS)
    return not _has_vowel(core, _CYRILLIC_VOWELS) and _has_vowel(conv, _LATIN_VOWELS)


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
