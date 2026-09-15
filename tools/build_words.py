#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate the LangSwitcher data artifact from one pinned source.

The artifact is what makes the automatic (Punto-style) mode decide the way it
does: frequency-ordered word lists, curated one/two-letter words, Ukrainian IT
slang, and letter n-gram weights.  It is published as a GitHub Release asset,
pinned by URL and SHA-256 in the installers — never committed, because it is
derived from CC BY-SA 4.0 content and this repository is MIT.

Source (one repository, pinned to a commit so two installs a month apart decide
the same way):

    hermitdave/FrequencyWords @ 525f9b560de45753a5ea01069454e72e9aa541c6
      content/2018/uk/uk_50k.txt   (Ukrainian vocabulary + n-grams)
      content/2018/en/en_50k.txt   (English vocabulary + n-grams)

    MIT for the code, CC BY-SA 4.0 for the content, derived from
    OPUS/OpenSubtitles.  google-10000-english was dropped: it carries no clean
    data licence and its own LICENSE.md warns against commercial use, which an
    MIT-licensed project cannot pass on to its users.

Outputs, all under ``dist/``:

    words.py    the module the Python core imports
    words.txt   the same data for AutoHotkey (FileRead, no Python on Windows)
    NOTICE      attribution and licence for the data
    SHA256SUMS  hashes for the release job

Run:

    python3 tools/build_words.py                  # write dist/
    python3 tools/build_words.py --install        # ...and place words.py in lib/
    python3 tools/build_words.py --print          # words.py to stdout
    python3 tools/build_words.py --check dist     # verify an existing artifact

The downloads are cached under ``tools/.cache/<sha>/`` and are not committed.
"""
import argparse
import hashlib
import math
import os
import sys
import urllib.request

SOURCE_REPO = "hermitdave/FrequencyWords"
# Bump deliberately: this is the pin that makes the artifact reproducible.
SOURCE_SHA = "525f9b560de45753a5ea01069454e72e9aa541c6"
UK_PATH = "content/2018/uk/uk_50k.txt"
EN_PATH = "content/2018/en/en_50k.txt"
SOURCE_RAW = "https://raw.githubusercontent.com/" + SOURCE_REPO + "/" + SOURCE_SHA + "/"

# Bumped when the pinned source or the curated lists below change.
DATA_VERSION = "2026.09.15"

# How many of the frequency-ordered English words become the veto vocabulary and
# the English rank table.  Measured on 12 Wikipedia articles: 10k and 20k are
# within noise on Ukrainian coverage, and the larger table gives the reverse
# rank rule more words to compare against.
EN_WORDS_LIMIT = 20000

UK_ALPHABET = set("абвгґдеєжзиіїйклмнопрстуфхцчшщьюя")
APOSTROPHE = "'’"
SCALE = 100          # n-gram weights are stored as round(weight * SCALE)
SLANG_RANK_DIVISOR = 4   # IT slang gets a synthetic rank of len(uk) / 4 + i

# One- and two-letter Ukrainian words.  The frequency list contains every letter
# as an entry, so it cannot tell «я» from «щ»; this can.
UK_SHORT_WORDS = (
    "а б в ж з і й к о с у я "
    "ти ви ми до по та не що як на за зі із ні є чи то ну же ся би бі мі ві ті "
    "ці сі її їх їй їм ім їв їж го ох ой"
).split()

# Real English one- and two-letter words; anything else that shape is a corpus
# artifact.  Adding one here *stops* its Ukrainian counterpart from converting
# («a» is the article, not «ф»), which is why this stays curated.
EN_SHORT_WORDS = (
    "a i us to in of is it at by he we do go no so on my an be me up if or as "
    "am ok hi oh"
).split()

# Ukrainian IT slang: everyday words of the trade that a subtitle corpus never
# contains.  The user dictionary (SUPER+BACKSPACE on Omarchy) covers the rest.
UK_IT_SLANG = (
    "апдейт апдейти апдейтити білд білдити білдів баг баги багів багфікс бекенд "
    "бранч бранчі відкат відкотити відкотитись воркер гілка гілки гіт дебажити "
    "дебажив деплой деплоїти деплою докер ендпоінт задеплоїти закомітити "
    "замержити закомічений інстанс квері кейс код кодити коміт комітити комітнути "
    "консоль контейнер конфіг конфіги лог логи логувати мерж мержити образ "
    "папка перформанс плагін покриття пул пулреквест ребейз ревью реліз "
    "репозиторій роутер скрипт сервер таска таски тікет тест тести тестити "
    "фікс фіксити фіксив фіча фічі фронтенд юзер юзкейс"
).split()


def norm(word: str) -> str:
    return word.replace("’", "'").lower()


def keep_uk(word: str) -> bool:
    word = norm(word)
    if len(word) < 2 or any(ch in "ыэёъ" for ch in word):
        return False
    return all(ch in UK_ALPHABET or ch in APOSTROPHE for ch in word)


def keep_en(word: str) -> bool:
    """English vocabulary: three letters or more, a-z only.

    The ``len >= 3`` half is load-bearing.  The frequency list keeps one- and
    two-letter tokens (``e``, ``d``, ``s``); letting them into the veto set
    makes the most common Ukrainian words stop converting, because ``у`` is
    typed as ``e`` and ``і`` as ``s``.  Short English words belong in the
    curated set above, where each one is a decision.
    """
    word = norm(word)
    return len(word) >= 3 and word.isascii() and word.isalpha()


def keep_en_list(word: str) -> bool:
    """What goes into the English *word list*: the vocabulary plus the curated
    short words.

    The short words must be in the list even though the n-gram model skips
    them, because the rank table is built from the list and the reverse rule
    compares ranks — ``by``, ``on`` and ``it`` hinge on it.
    """
    return keep_en(word) or norm(word) in EN_SHORT_WORDS


def read_counts(path: str, keep) -> dict[str, int]:
    out: dict[str, int] = {}
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            parts = line.split()
            if len(parts) < 2:
                continue
            word = norm(parts[0])
            if not keep(word):
                continue
            out[word] = out.get(word, 0) + int(parts[1])
    return out


def ngrams(counts: dict[str, int]) -> tuple[dict[str, float], ...]:
    """Character n-gram weights of ``^word$``, weighted by word frequency."""
    uni: dict[str, float] = {}
    bi: dict[str, float] = {}
    tri: dict[str, float] = {}
    for word, count in counts.items():
        weight = math.log1p(count)
        padded = "^" + word + "$"
        for index, char in enumerate(padded):
            uni[char] = uni.get(char, 0.0) + weight
            if index:
                gram = padded[index - 1:index + 1]
                bi[gram] = bi.get(gram, 0.0) + weight
            if index > 1:
                gram = padded[index - 2:index + 1]
                tri[gram] = tri.get(gram, 0.0) + weight
    return uni, bi, tri


def dump(table: dict[str, float], per_line: int = 1) -> str:
    items = [f"{gram} {round(weight * SCALE)}" for gram, weight in sorted(table.items())]
    return "\n".join(" ".join(items[i:i + per_line])
                     for i in range(0, len(items), per_line))


def dump_words(words, per_line: int = 1) -> str:
    words = list(words)
    return "\n".join(" ".join(words[i:i + per_line])
                     for i in range(0, len(words), per_line))


def pinned(path: str) -> str:
    return SOURCE_RAW + path


def header() -> str:
    """The attribution block every artifact file carries.

    A user can copy the generated file anywhere, so the file has to name its
    own sources and licence — the repository's MIT notice does not travel with
    it, and CC BY-SA 4.0 requires attribution wherever the data goes.
    """
    lines = [
        f"LangSwitcher data, version {DATA_VERSION}",
        "",
        f"Source: {SOURCE_REPO} @ {SOURCE_SHA} (MIT for code, CC BY-SA 4.0 for content)",
        f"  {pinned(UK_PATH)}",
        f"  {pinned(EN_PATH)}",
        "  derived from OPUS/OpenSubtitles (https://opus.nlpl.eu/OpenSubtitles2018.php)",
        "",
        "This file is Adapted Material of CC BY-SA 4.0 content: it is licensed",
        "CC BY-SA 4.0, not MIT.  https://creativecommons.org/licenses/by-sa/4.0/",
        "Modifications: filtered to each alphabet, one- and two-letter tokens moved",
        "to a curated set, Ukrainian IT slang added, letter n-gram weights computed.",
        "Please attribute opensubtitles.org and cite Lison & Tiedemann 2016 and",
        "Tiedemann 2012.  See NOTICE next to this file.",
    ]
    return "\n".join(lines)


BODY = """Частотні списки слів і літерна статистика для правдоподібності (Punto-стиль).

Згенеровано ``tools/build_words.py`` — не редагувати руками. Версія даних і
джерела — у заголовку вище; той самий набір даних для AutoHotkey лежить у
``words.txt``.

Авто-режим рішає «це набрано не в тій розкладці?» так:

* якщо набране — справжнє слово власної мови, не чіпаємо (``*_WORDS_TEXT``);
* якщо конвертація — відоме слово цільової мови, перетворюємо;
* інакше — порівнюємо оцінку літерних n-грамів цілі й джерела
  (``*_TRIGRAMS`` тощо). Це те, що покриває відмінкові форми, яких немає в
  жодному 50k-корпусі, друкарські помилки й нові запозичення.

Порядок рядків — це ранг (1 — найчастіше); у зворотному напрямку саме ранг, а
не сама наявність, вирішує «еру» (the) чи «привіт».
Завантажується ліниво: worker стартує на кожне слово."""

PY_TEMPLATE = '''# -*- coding: utf-8 -*-
"""{header}

{body}
"""

UK_WORDS_TEXT = """
{uk}
"""
EN_WORDS_TEXT = """
{en}
"""

DATA_VERSION = "{data_version}"

# Справжні однолітерні й дволітерні слова (див. docstring генератора).
UK_SHORT_WORDS = frozenset("""
{uk_short}
""".split())
EN_SHORT_WORDS = frozenset("""
{en_short}
""".split())

# Український IT-сленг: словники субтитрів його не знають.
UK_IT_SLANG = frozenset("""
{slang}
""".split())

# Літерна статистика: n-грами слів у формі «^слово$».
UK_UNIGRAMS = """
{uk_uni}
"""
UK_BIGRAMS = """
{uk_bi}
"""
UK_TRIGRAMS = """
{uk_tri}
"""
EN_UNIGRAMS = """
{en_uni}
"""
EN_BIGRAMS = """
{en_bi}
"""
EN_TRIGRAMS = """
{en_tri}
"""

SCALE = {scale}

_UK = None
_EN = None
_UK_RANK = None
_EN_RANK = None
_UK_MODEL = None
_EN_MODEL = None


def _table(text: str) -> dict:
    out = {{}}
    for line in text.split("\\n"):
        parts = line.split()
        for index in range(0, len(parts) - 1, 2):
            out[parts[index]] = int(parts[index + 1]) / SCALE
    return out


def uk_set() -> frozenset:
    global _UK
    if _UK is None:
        _UK = frozenset(UK_WORDS_TEXT.split()) | UK_IT_SLANG
    return _UK


def en_set() -> frozenset:
    global _EN
    if _EN is None:
        _EN = frozenset(EN_WORDS_TEXT.split())
    return _EN


def uk_rank() -> dict:
    """word -> 1-based frequency rank, IT slang included."""
    global _UK_RANK
    if _UK_RANK is None:
        _UK_RANK = {{word: index + 1
                    for index, word in enumerate(UK_WORDS_TEXT.split())}}
        for offset, word in enumerate(sorted(UK_IT_SLANG)):
            _UK_RANK.setdefault(word, {slang_rank} + offset)
    return _UK_RANK


def en_rank() -> dict:
    global _EN_RANK
    if _EN_RANK is None:
        _EN_RANK = {{word: index + 1
                    for index, word in enumerate(EN_WORDS_TEXT.split())}}
    return _EN_RANK


def uk_model() -> tuple:
    """(unigrams, bigrams, trigrams) of Ukrainian, weighted by frequency."""
    global _UK_MODEL
    if _UK_MODEL is None:
        _UK_MODEL = (_table(UK_UNIGRAMS), _table(UK_BIGRAMS), _table(UK_TRIGRAMS))
    return _UK_MODEL


def en_model() -> tuple:
    global _EN_MODEL
    if _EN_MODEL is None:
        _EN_MODEL = (_table(EN_UNIGRAMS), _table(EN_BIGRAMS), _table(EN_TRIGRAMS))
    return _EN_MODEL
'''

TXT_SECTIONS = (
    ("uk_words", "Ukrainian word list, one per line, frequency order (rank = line)"),
    ("en_words", "English word list, one per line, frequency order (rank = line)"),
    ("uk_short", "curated one/two-letter Ukrainian words"),
    ("en_short", "curated one/two-letter English words"),
    ("uk_slang", "Ukrainian IT slang, sorted"),
    ("uk_uni", "Ukrainian unigrams: gram weight"),
    ("uk_bi", "Ukrainian bigrams: gram weight"),
    ("uk_tri", "Ukrainian trigrams: gram weight"),
    ("en_uni", "English unigrams: gram weight"),
    ("en_bi", "English bigrams: gram weight"),
    ("en_tri", "English trigrams: gram weight"),
)


def render_python(uk_words, en_words, tables) -> str:
    uk_uni, uk_bi, uk_tri = tables["uk"]
    en_uni, en_bi, en_tri = tables["en"]
    return PY_TEMPLATE.format(
        header=header(),
        body=BODY,
        data_version=DATA_VERSION,
        uk=dump_words(uk_words),
        en=dump_words(en_words),
        uk_short=dump_words(UK_SHORT_WORDS, per_line=10),
        en_short=dump_words(EN_SHORT_WORDS, per_line=10),
        slang=dump_words(sorted(UK_IT_SLANG), per_line=8),
        uk_uni=dump(uk_uni, per_line=8),
        uk_bi=dump(uk_bi, per_line=6),
        uk_tri=dump(uk_tri, per_line=4),
        en_uni=dump(en_uni, per_line=8),
        en_bi=dump(en_bi, per_line=6),
        en_tri=dump(en_tri, per_line=4),
        scale=SCALE,
        slang_rank=len(uk_words) // SLANG_RANK_DIVISOR,
    )


def render_text(uk_words, en_words, tables) -> str:
    """The same data for AutoHotkey: one section per table, no Python syntax.

    Rank is the line number inside ``uk_words``/``en_words``, exactly as in
    ``words.py``, so both sides rank a word the same way and the CI corpus test
    can compare decisions instead of data.
    """
    uk_uni, uk_bi, uk_tri = tables["uk"]
    en_uni, en_bi, en_tri = tables["en"]
    blocks = {
        "uk_words": dump_words(uk_words),
        "en_words": dump_words(en_words),
        "uk_short": dump_words(UK_SHORT_WORDS, per_line=10),
        "en_short": dump_words(EN_SHORT_WORDS, per_line=10),
        "uk_slang": dump_words(sorted(UK_IT_SLANG), per_line=8),
        "uk_uni": dump(uk_uni, per_line=8),
        "uk_bi": dump(uk_bi, per_line=6),
        "uk_tri": dump(uk_tri, per_line=4),
        "en_uni": dump(en_uni, per_line=8),
        "en_bi": dump(en_bi, per_line=6),
        "en_tri": dump(en_tri, per_line=4),
    }
    out = ["# " + line if line else "#" for line in header().splitlines()]
    out.append("")
    for name, note in TXT_SECTIONS:
        out.append(f"[{name}]  # {note}")
        out.append(blocks[name])
        out.append("")
    return "\n".join(out)


def render_notice() -> str:
    return f"""LangSwitcher data, version {DATA_VERSION}
=========================================

The files words.py and words.txt in this artifact are derived data, not code.

Source
------
{SOURCE_REPO} @ {SOURCE_SHA}
  {pinned(UK_PATH)}
  {pinned(EN_PATH)}

That repository is MIT for its code and CC BY-SA 4.0 for its content, and its
content is derived from OPUS/OpenSubtitles
(https://opus.nlpl.eu/OpenSubtitles2018.php).  google-10000-english was
deliberately dropped from this pipeline: it has no clean data licence and its
own LICENSE.md warns against commercial use, which an MIT project cannot pass
on to its users.

Licence
-------
These files are Adapted Material of CC BY-SA 4.0 content and are licensed
under CC BY-SA 4.0: https://creativecommons.org/licenses/by-sa/4.0/
They are NOT covered by the MIT licence of the LangSwitcher source code.

Modifications
-------------
Filtered to each language's own alphabet; Russian-only letters removed;
one- and two-letter tokens moved into curated lists; Ukrainian IT slang added;
letter n-gram weights computed from the frequency lists and scaled to integers.

Attribution
-----------
Please credit opensubtitles.org and cite:

  Lison, P. and Tiedemann, J. (2016). OpenSubtitles2016: Extracting Large
  Parallel Corpora from Movie and TV Subtitles. LREC 2016.
  Tiedemann, J. (2012). Parallel Data, Tools and Interfaces in OPUS. LREC 2012.
"""


def render_all(data: dict) -> dict[str, str]:
    return {
        "words.py": render_python(data["uk_words"], data["en_words"], data["tables"]),
        "words.txt": render_text(data["uk_words"], data["en_words"], data["tables"]),
        "NOTICE": render_notice(),
    }


def build(uk_file: str, en_file: str) -> dict:
    uk_counts = read_counts(uk_file, keep_uk)
    # Two English sets on purpose: the n-gram model is trained on the plain
    # vocabulary (short tokens would only add noise), while the word list and
    # its ranks include the curated short words (see keep_en_list).
    en_all = read_counts(en_file, keep_en_list)
    en_counts = {word: count for word, count in en_all.items() if keep_en(word)}
    en_words = list(en_all)[:EN_WORDS_LIMIT]
    tables = {"uk": ngrams(uk_counts), "en": ngrams(en_counts)}
    return {"uk_words": list(uk_counts), "en_words": en_words, "tables": tables}


def write_dist(data: dict, dist: str) -> dict[str, str]:
    os.makedirs(dist, exist_ok=True)
    digests = {}
    for name, body in render_all(data).items():
        with open(os.path.join(dist, name), "w", encoding="utf-8") as handle:
            handle.write(body)
        digests[name] = hashlib.sha256(body.encode("utf-8")).hexdigest()
    with open(os.path.join(dist, "SHA256SUMS"), "w", encoding="utf-8") as handle:
        for name, digest in sorted(digests.items()):
            handle.write(f"{digest}  {name}\n")
    return digests


def install(data: dict, root: str) -> None:
    """Place words.py in the bundle lib dirs so tests and dev runs can import it.

    The artifact is not committed (CC BY-SA data in an MIT repository), so this
    is what a developer runs locally; CI does the same thing from the release
    asset.  ``.gitignore`` keeps the result out of git.
    """
    body = render_python(data["uk_words"], data["en_words"], data["tables"])
    # Automatic mode is Hyprland-only, so its data lives in the plugin bundle
    # alone; the Linux and KDE bundles never import it.
    for part in ("omarchy-plugin",):
        target = os.path.join(root, part, "lib", "words.py")
        if not os.path.isdir(os.path.dirname(target)):
            continue
        with open(target, "w", encoding="utf-8") as handle:
            handle.write(body)
        print(f"installed {os.path.relpath(target, root)}", file=sys.stderr)


def fetch(url: str, path: str) -> str:
    if not os.path.exists(path):
        print(f"downloading {url}", file=sys.stderr)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        urllib.request.urlretrieve(url, path)
    return path


def main(argv: list[str]) -> int:
    here = os.path.dirname(os.path.abspath(__file__))
    root = os.path.dirname(here)
    cache = os.path.join(here, ".cache", SOURCE_SHA)
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--uk-file", default=os.path.join(cache, "uk_50k.txt"))
    parser.add_argument("--en-file", default=os.path.join(cache, "en_50k.txt"))
    parser.add_argument("--dist", default=os.path.join(root, "dist"))
    parser.add_argument("--install", action="store_true",
                        help="also write words.py into <bundle>/lib/ for tests")
    parser.add_argument("--print", action="store_true", help="words.py to stdout")
    parser.add_argument("--check", metavar="DIR",
                        help="verify an existing artifact directory")
    args = parser.parse_args(argv)

    if args.check:
        data = build(fetch(pinned(UK_PATH), args.uk_file),
                     fetch(pinned(EN_PATH), args.en_file))
        bad = []
        for name, body in sorted(render_all(data).items()):
            digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
            target = os.path.join(args.check, name)
            have = (hashlib.sha256(open(target, "rb").read()).hexdigest()
                    if os.path.exists(target) else None)
            print(f"{'ok  ' if have == digest else 'DIFF'} {name} {digest[:16]}")
            if have != digest:
                bad.append(name)
        return 1 if bad else 0

    data = build(fetch(pinned(UK_PATH), args.uk_file),
                 fetch(pinned(EN_PATH), args.en_file))

    if args.print:
        sys.stdout.write(render_python(data["uk_words"], data["en_words"], data["tables"]))
        return 0

    digests = write_dist(data, args.dist)
    for name, digest in sorted(digests.items()):
        print(f"{name}: sha256 {digest}", file=sys.stderr)
    print(f"artifact version {DATA_VERSION} -> {os.path.relpath(args.dist, root)}",
          file=sys.stderr)
    if args.install:
        install(data, root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
