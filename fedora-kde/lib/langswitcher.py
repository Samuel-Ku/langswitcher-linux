#!/usr/bin/env python3
"""LangSwitcher core — layout conversion for en, uk, pl.

Maps physical key positions between layouts, auto-detects which layout a piece
of text was typed in, preserves the user's punctuation, and recovers Polish
⌥-layer artifacts. Algorithm and layout maps follow LangSwitcher (MIT) — see
LICENSE; only the layouts this project ships are kept (Russian is deliberately
absent — it was never needed).

This file is intentionally duplicated in the omarchy-plugin and linux bundles;
keep both copies byte-identical.

No dependencies, stdlib only.
"""

import math

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


# ---- Option (⌥) layer: Polish <-> Cyrillic recovery -------------------------
# Polish text typed while a Cyrillic layout is active comes out as that layout's
# own ⌥-layer characters: on Ukrainian-PC the diacritic chords are ⌥-chords, so
# ⌥+S emits "ы", ⌥+A emits "ƒ", ⌥+C emits "≠". A base-layer-only conversion
# leaves those unmapped ("mąka" would become "mƒkф"). Mapping the ⌥ characters
# by physical key closes the gap: ƒ (⌥+A on Ukrainian-PC) -> a -> ą (⌥+A on
# Polish Pro).
#
# Source-side only: a Polish diacritic folds to its physical base key; the
# reverse (plain base letter -> diacritic) is intentionally NOT synthesised.
_POLISH_DIACRITIC_BASES = {
    "ą": "a", "ć": "c", "ę": "e", "ł": "l", "ń": "n",
    "ó": "o", "ś": "s", "ź": "x", "ż": "z",
    "Ą": "A", "Ć": "C", "Ę": "E", "Ł": "L", "Ń": "N",
    "Ó": "O", "Ś": "S", "Ź": "X", "Ż": "Z",
}

# Polish Pro ⌥ layer, inverted from the fold so both share one source of truth.
_POLISH_PRO_OPTION = {
    base: diacritic
    for diacritic, base in _POLISH_DIACRITIC_BASES.items()
    if diacritic.islower()
}

# Ukrainian-PC ⌥ layer (letter keys a-z, real extraction).
_UKRAINIAN_OPTION = {
    "a": "ƒ", "b": "и", "c": "≠", "d": "ћ", "e": "ќ", "f": "÷", "g": "©",
    "h": "}", "i": "ѕ", "j": "°", "k": "љ", "l": "∆", "m": "~", "n": "™",
    "o": "ў", "p": "‘", "q": "ј", "r": "®", "s": "ы", "t": "ё", "u": "ґ",
    "v": "µ", "w": "џ", "x": "≈", "y": "њ", "z": "ђ",
}

_OPTION_MAPS = {
    "uk": _UKRAINIAN_OPTION,
    "ua": _UKRAINIAN_OPTION,
    "pl": _POLISH_PRO_OPTION,
}

# Every value any ⌥ map can emit. These are layout artifacts, not punctuation:
# the boundary splitter must never treat them as user-typed punctuation.
_OPTION_ARTIFACTS = set().union(*(m.values() for m in _OPTION_MAPS.values()))


def _option_map(layout_id: str) -> dict:
    return _OPTION_MAPS.get(layout_id, {})


def _is_ascii(c: str) -> bool:
    return ord(c) < 128


def convert(text: str, from_layout: str, to_layout: str) -> str | None:
    """Конвертація за фізпозиціями + збереження пунктуації +
    відновлення польського ⌥-шару/діакритики."""
    src = MAPS.get(from_layout)
    dst = MAPS.get(to_layout)
    if src is None or dst is None:
        return None
    reverse = {}
    for k, v in src.items():
        reverse.setdefault(v, k)
    is_polish_source = "pl" in from_layout or "polish" in from_layout
    source_option = _option_map(from_layout)
    reverse_option = {}
    for k, v in source_option.items():
        reverse_option.setdefault(v, k)
    target_option = _option_map(to_layout)

    out = []
    for ch in text:
        physical = reverse.get(ch)
        if physical is not None and physical in dst:
            target = dst[physical]
            # пунктуація: non-letter -> non-letter лишаємо як є
            out.append(ch if (not ch.isalpha() and not target.isalpha()) else target)
        elif is_polish_source and ch in _POLISH_DIACRITIC_BASES \
                and _POLISH_DIACRITIC_BASES[ch] in dst:
            out.append(dst[_POLISH_DIACRITIC_BASES[ch]])
        elif ch in reverse_option:
            key = reverse_option[ch]
            target_option_char = target_option.get(key)
            if target_option_char is not None and target_option_char.isalpha():
                out.append(target_option_char)
            elif key in dst:
                out.append(dst[key])
            else:
                out.append(ch)
        else:
            out.append(ch)
    return "".join(out)


def detect_source_layout(text: str, candidates: list[str]) -> str | None:
    """Розкладка-кандидат, чий набір символів покриває більше символів тексту."""
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


def _is_boundary_affix(c: str) -> bool:
    return not (c.isalpha() or c.isdigit()) and c not in _OPTION_ARTIFACTS


def _split_affixes(text: str) -> tuple[str, str, str]:
    """Split leading/trailing non-alphanumerics from the core.

    "ghbdsn." -> ("", "ghbdsn", "."); "(Руддщ)" -> ("(", "Руддщ", ")").
    Punctuation a user typed at a word boundary is theirs to keep — it must not
    be run through the layout map (where '.' would become 'ю', ',' -> 'б').

    ⌥-layer artifacts (© ≠ ∆ ...) are NOT punctuation even when they look like
    symbols, so they stay in the core and get recovered by convert().
    """
    i, j = 0, len(text)
    while i < j and _is_boundary_affix(text[i]):
        i += 1
    while j > i and _is_boundary_affix(text[j - 1]):
        j -= 1
    return text[:i], text[i:j], text[j:]


def convert_selected(text: str, layouts: list[str]) -> tuple[str, str] | None:
    """Повертає (конвертований текст, target_layout).

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
    # If the text carries the source layout's ⌥-layer artifacts, the user typed
    # diacritic chords — they intended the layout that owns those chords (Polish),
    # so prefer a target with an ⌥ map over the plain "first other" layout.
    # Only *distinctive* artifacts count: some ⌥ values (e.g. "и") are also
    # ordinary base-layer letters and must not trigger this.
    base_values = set(MAPS.get(src, {}).values())
    distinctive = set(_option_map(src).values()) - base_values
    target = None
    if any(c in distinctive for c in core):
        target = next((l for l in layouts if l != src and _option_map(l)), None)
    if target is None:
        target = next((l for l in layouts if l != src), None)
    if target is None:
        target = layouts[0]
    res = convert(core, src, target)
    if res is None:
        return None
    return lead + res + trail, target


def looks_like_wrong_layout(text: str, layouts: list[str]) -> bool:
    """True, якщо конвертація перемикає скрипт тексту (латиниця <-> кирилиця)."""
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
    """Консервативна перевірка для AUTO-режимів (конвертація після пробілу).

    ``looks_like_wrong_layout`` повертає True для *будь-якого* латинського слова,
    що мапиться в кирилицю, тому він годиться лише для явної дії користувача.
    Автоконвертація після пробілу потребує строгішого сигналу, інакше кожне
    звичайне англійське слово переписувалося б.

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


def _letters(text: str) -> str:
    """Букви й апостроф.

    Апостроф не сміття: у позиційній розкладці він — клавіша літери є
    („знаєш“ -> „pyf'i“), тож відкидати його означало б зіпсувати половину слів
    з є та ї.
    """
    return "".join(ch for ch in text if ch.isalpha() or ch in "'\u2019")


def _plain_word(text: str) -> bool:
    """Чи набране — саме слово, без клавіш, що в іншій розкладці стають буквами.

    «hello» і «don't» — так; «,elm» (це «будь») і «le;t» (це «дуже») — ні: кома
    й крапка з комою тут не пунктуація, а клавіші літер б і ж. Вето дивиться на
    очищене ядро, тож для таких слів воно бачить не те слово, яке набрали.
    """
    return all(ch.isalpha() or ch in "'\u2019" for ch in text.strip())


def _uk_words() -> frozenset:
    from words import uk_set  # ліниво: words.py ~1МБ, worker стартує на кожне слово
    return uk_set()


def _en_words() -> frozenset:
    from words import en_set
    return en_set()


def _uk_short_words() -> frozenset:
    from words import UK_SHORT_WORDS
    return UK_SHORT_WORDS


def _en_short_words() -> frozenset:
    from words import EN_SHORT_WORDS
    return EN_SHORT_WORDS


def _uk_rank() -> dict:
    from words import uk_rank
    return uk_rank()


def _en_rank() -> dict:
    from words import en_rank
    return en_rank()


def _uk_model() -> tuple:
    from words import uk_model
    return uk_model()


def _en_model() -> tuple:
    from words import en_model
    return en_model()


# Наскільки оцінка цільової абетки мусить переважити оцінку власної, коли
# словники мовчать про обидва варіанти. 5 підібрано на корпусах (вікі-стаття
# українською — 3 953 форми; англійська проза — 5 897 слів): 98.9% українських
# форм перетворюються, а серед англійських слів хибно спрацьовує одне («qnx»).
NGRAM_MARGIN = 5.0
# У зворотному напрямку мало не «чи є слово в списку», а «котре з двох частіше».
# Кириличне зображення дуже частого англійського слова саме є рідкісним
# українським («еру» — це the, «ин» — by), тож бінарне вето лишало 13% running
# англійського тексту неконвертованим. Поріг 4 виміряно на 12 вікі-статтях:
# реверс за зваженою частотою 86.6% -> 96.4%, ціна — одне нове хибне («рук»).
REVERSE_RANK_MARGIN = 4
_BACKOFF = 1e-4


def _ngram_score(text: str, model: tuple) -> float:
    """Лог-правдоподібність n-грамів рядка в одній абетці.

    Триграма з відкатом на біграму, далі на уніграму. Саме це ловить відмінкові
    форми та одруки, яких немає в жодному списку слів: «абетки» і «автономної»
    не походять від «абетка»/«автономний» жодним словниковим збігом.
    """
    unigrams, bigrams, trigrams = model
    padded = "^" + text + "$"
    total = 0.0
    for index in range(len(padded) - 2):
        gram = padded[index:index + 3]
        weight = trigrams.get(gram)
        if weight:
            total += math.log(weight / (bigrams.get(gram[:2], 0.0) + 1.0))
            continue
        weight = bigrams.get(gram[1:], 0.0)
        probability = weight / (unigrams.get(gram[1], 0.0) + 1.0) if weight else _BACKOFF
        total += math.log(max(probability, 1e-9))
    return total


def looks_like_wrong_layout_plausible(text: str, layouts: list[str],
                                      min_len: int = 1) -> bool:
    """Punto-стиль: чи слово набране в неправильній розкладці.

    Три рівні — від найпевнішого до найзагальнішого:

    1. **Слово власної мови не чіпаємо.** «hello», «test», «us» — англійські
       слова, «привіт» і «це» — українські. Набране, яке справді є словом своєї
       мови, лишається як є. Це вето, і саме воно тримає хибні спрацювання на
       звичайному тексті близько нуля.
    2. **Відоме слово цільової мови — перетворюємо.** Тут працюють списки слів і
       куровані набори коротких: «z» -> «я», «zr» -> «як», «wt» -> «це»,
       «]]» -> «її» (у списку частотних слів усі 33 літери позначені як слова,
       тому короткі вирішують окремі набори).
    3. **Інакше — літерна статистика:** оцінка n-грамів цілі мусить переважити
       оцінку джерела на ``NGRAM_MARGIN``. Це покриває те, чого списки не
       вміють: відмінювання (45% слів української вікі-статті — форми, яких
       немає в 50k-корпусі), одруки («ghbdsm» -> «привіт») і нові запозичення
       (IT-сленг).

    У зворотному напрямку рівень 1 працює з поправкою на ранги: набране
    кирилицею, яке справді є українським словом, усе одно конвертується, якщо
    англійська ціль значно частіша за нього (``REVERSE_RANK_MARGIN``) — інакше
    «еру» (the) і «ин» (by) лишалися б недоторканими в усьому англійському
    тексті, а це 13% його слів.

    Пунктуація не руйнує рішення, бо конвертація йде по всій клавіші, а не по
    «очищеному» ядру: „le;t“ -> „дуже“, „[jxe“ -> „хочу“, „,elm“ -> „будь“ (у
    цільовій розкладці ; [ , — це букви). Апостроф теж буква (є/ї).
    """
    if len(layouts) < 2 or _is_polish_text(text):
        return False
    resolved = convert_full(text, layouts)
    if resolved is None:
        return False
    conv, _ = resolved
    source = _letters(text).lower()
    target = _letters(conv).lower()
    if not target or target == source:
        return False
    if len(target) < max(1, min_len):
        return False
    # Вето дивиться на ядро, а не на очищені букви: «hello.» — це «hello», але
    # «le;t» — не «let» («;» у цільовій розкладці — буква ж), тож англійське
    # слово всередині не мусить його рятувати.
    source_word = _split_affixes(text.strip())[1].lower()
    plain = _plain_word(text)
    if text.isascii():
        source_known = source_word in _en_words() or source_word in _en_short_words()
        target_known = target in _uk_words() or target in _uk_short_words()
        # Вето тримає «hello» і «hello.», але не «,elm»: там провідна кома — це
        # «б», і очищене ядро «elm» — не те слово, яке набрали.
        if source_known and (plain or not target_known):
            return False
        if target_known:
            return True
        if len(target) <= 2:
            return False
        return (_ngram_score(target, _uk_model())
                - _ngram_score(source, _en_model())) > NGRAM_MARGIN
    # Зворотний напрямок. Справжнє українське слово зазвичай означає, що людина
    # й мала на увазі українську. Але кириличне зображення дуже частого
    # англійського слова саме є рідкісним українським словом, тож бінарне вето
    # тут не працює: порівнюємо ранги. Умова «конвертація — самі лише літери»
    # потрібна, бо ранг рахується по очищених літерах, а в застосунок пішов би
    # і розділовий знак («рух» -> «he[»).
    source_known = source_word in _uk_words() or source_word in _uk_short_words()
    target_known = target in _en_words() or target in _en_short_words()
    if source_known and (plain or not target_known):
        if not target_known or not conv.isalpha():
            return False
        source_rank = _uk_rank().get(source_word)
        target_rank = _en_rank().get(target)
        if source_rank is None or target_rank is None:
            return False
        return target_rank * REVERSE_RANK_MARGIN < source_rank
    if target_known:
        return True
    if len(target) <= 2:
        return False
    return (_ngram_score(target, _en_model())
            - _ngram_score(source, _uk_model())) > NGRAM_MARGIN


def convert_full(text: str, layouts: list[str]) -> tuple[str, str] | None:
    """Як ``convert_selected``, але без обрізання країв: у неправильній
    розкладці клавіша „[“ — це „х“, а не пунктуація, тому „[jxe“ -> „хочу“,
    а „ghbdsn.“ -> „привіт.“ (крапка лишається крапкою)."""
    if len(layouts) < 2:
        return None
    if _is_polish_text(text):
        return None
    src = detect_source_layout(text, layouts)
    if src is None:
        return None
    target = next((layout for layout in layouts if layout != src), layouts[0])
    converted = convert(text, src, target)
    if converted is None:
        return None
    return converted, target


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
    """Межа, з якої починається хвіст у неправильній розкладці (greedy two-pass, поріг 70%)."""
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
    """Конвертує хвіст рядка, набраний у неправильній розкладці."""
    b = find_wrong_boundary(text, layouts)
    if b is None:
        return None
    keep, conv_part = b
    r = convert_selected(conv_part, layouts)
    if r is None:
        return None
    converted, target = r
    return keep + converted, target
