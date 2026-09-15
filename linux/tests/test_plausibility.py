#!/usr/bin/env python3
"""Регресія авто-режиму: чи перетворюється текст, набраний не в тій розкладці.

Тримає три речі, на яких ця евристика ламалася, і кожна з них — реальний звіт:

* **слова з латинськими голосними** («пишу» -> „gbie“, «україна» -> „erhf]yf“) —
  стара евристика «нема латинської голосної» лишала 263 з 400 звичайних
  українських слів недоторканими, тому перетворювався лише кожен третій рядок;
* **короткі слова й однолітерні** («я» -> „z“, «це» -> „wt“, «її» -> „]]“) — вони
  не доходили до воркера взагалі (MIN_KEYS=3), а «z» так і лишався «z»;
* **відмінкові форми** («абетки», «автономної», «адміністративних») — їх немає в
  жодному 50k-списку слів, їх ловить оцінка літерних n-грамів.

І зворотний бік: справжні англійські слова (зокрема весь IT-жаргон латиницею) та
вже правильно набрана українська лишаються як є.

Run: python3 tests/test_plausibility.py
"""
import os
import sys

# Automatic mode ships only in the Omarchy plugin (the Linux bundles are
# hotkey-only), so its tests import the core from there.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..",
                                "omarchy-plugin", "lib"))

import autofix  # noqa: E402
from langswitcher import MAPS  # noqa: E402

fails = []

LAYOUTS = ["en", "uk", "pl"]
# uk letter -> the US key that types it: what ends up on screen when the layout
# is English and the user is thinking Ukrainian.
_TO_US = {value: key for key, value in MAPS["uk"].items()}


def wrong(word: str) -> str:
    """The keystrokes a Ukrainian word turns into on the English layout."""
    return "".join(_TO_US.get(ch, ch) for ch in word)


def image(word: str) -> str:
    """The Cyrillic an English word turns into on the Ukrainian layout."""
    return "".join(MAPS["uk"].get(ch, ch) for ch in word)


def plan(typed: str):
    return autofix.plan(typed, LAYOUTS, min_len=1)


def check(name, got, want):
    if got != want:
        fails.append(f"{name}: got {got!r}, want {want!r}")
    else:
        print(f"ok: {name}")


def converts(word: str) -> None:
    """`word`, typed on the wrong layout, must come back as `word`."""
    typed = wrong(word)
    check(f"{word!r} (typed {typed!r})", plan(typed),
          {"typed": typed, "fixed": word, "target": "uk"})


def keeps(typed: str) -> None:
    check(f"keeps {typed!r}", plan(typed), None)


# ---- the reported phrase: «z gbie jnfrt» = «я пишу отаке» ------------------
# Only «отаке» used to convert (no Latin vowel); «z» never reached the worker
# and «gbie» had i/e, so the whole first half stayed Latin.
converts("я")
converts("пишу")
converts("отаке")
check("whole phrase",
      "".join(plan(wrong(w))["fixed"] + " " for w in ("я", "пишу", "отаке")).strip(),
      "я пишу отаке")

# ---- one-letter words: only real Ukrainian ones, never a / i -----------------
for _letter in ("я", "і", "в", "у", "о", "а", "з", "к", "б", "ж", "й"):
    converts(_letter)
for _english in ("a", "i"):
    keeps(_english)          # English words: the article and the pronoun
keeps("o")                   # «щ» is a letter, not a word

# ---- short words: the frequency list marks every letter as a word, so these
# come from the curated sets instead.
for _short in ("як", "що", "це", "ти", "ви", "ми", "до", "по", "та", "не", "на",
               "за", "ні", "чи", "є", "то", "ну", "її", "їх", "їй", "їм", "їв"):
    converts(_short)
for _english in ("us", "no", "to", "in", "of", "is", "it", "at", "by", "he", "we",
                 "do", "go", "so", "on", "my", "an", "be", "me", "up", "if", "or",
                 "as", "am", "ok", "hi", "oh"):
    keeps(_english)

# ---- words with Latin vowels and inner punctuation --------------------------
for _word in ("привіт", "дуже", "хочу", "будь", "більше", "знаєш", "україна",
              "сьогодні", "звичайно", "відповідь", "дякую", "люблю"):
    converts(_word)

# ---- inflected forms that are in no frequency list --------------------------
# Every one of these is a real form from a Ukrainian Wikipedia article; the old
# dictionary-only rule missed 45% of the article's distinct words.
for _form in ("абетки", "абетку", "автономної", "адміністративних", "алфавіту",
              "апостроф", "архімандрит", "берестейщини", "правопису", "значення"):
    converts(_form)

# ---- IT slang: Ukrainian words a subtitle corpus never contains -------------
for _term in ("коміт", "комітити", "деплой", "задеплоїти", "фіксити", "мержити",
              "білдити", "таска", "тікет", "ревью", "сервер", "плагін", "скрипт",
              "конфіг", "воркер", "логи", "ребейз", "гілка", "квері", "ендпоінт",
              "тести", "покриття"):
    converts(_term)

# ---- typos: conversion must fire anyway, the typo stays for the user to fix --
check("typo still converts", plan("ghbdsm"),
      {"typed": "ghbdsm", "fixed": "привіь", "target": "uk"})

# ---- real English text is never touched -------------------------------------
for _english in ("hello", "world", "operating", "kernel", "system", "the", "and",
                 "code", "file", "fix", "merge", "commit", "branch", "server",
                 "config", "log", "tests", "deploy", "build", "user", "bug",
                 "feature", "task", "ticket", "review", "release", "plugin",
                 "script", "worker", "pull", "request", "instance", "router",
                 "repo", "image", "container", "console", "terminal", "debug"):
    keeps(_english)

# ---- reverse: the most common English words must come back ------------------
# «еру» is "the" and «ин» is "by", and both are themselves Ukrainian words, so
# a binary veto kept them: measured on 12 articles the reverse direction
# converted only 86.6% of running English text (95.4% counted by distinct token,
# which hid it). The rank rule fixes all four of the misses — the(5144),
# by(541), on(394), it(330).
for _english in ("the", "by", "on", "it", "of", "and", "to", "in", "is", "that",
                 "this", "with", "you", "not", "or", "are"):
    _typed = image(_english)
    check(f"reverse {_english!r} (typed {_typed!r})", plan(_typed),
          {"typed": _typed, "fixed": _english, "target": "en"})

# The rank rule must not eat real Ukrainian. «рух» survives because its literal
# conversion would carry a punctuation mark («he[») that the letters-only rank
# test ignores — that guard removed three of the four new false positives at no
# cost in coverage.
for _word in ("рух", "привіт", "ти", "це", "абетки"):
    keeps(_word)
# The measured cost of the rule, on the same 12 articles: exactly one token,
# «рук» (genitive plural, corpus frequency 2 — 0.003% of running Ukrainian).
check("rank rule keeps its measured cost", plan("рук"),
      {"typed": "рук", "fixed": "her", "target": "en"})

# ---- already-correct Ukrainian and Polish stay -------------------------------
for _word in ("привіт", "абетки", "автономної", "коміт", "деплой", "це", "я"):
    keeps(_word)
keeps("Zażółć")

if fails:
    print("\nFAILURES:")
    for failure in fails:
        print(" -", failure)
    sys.exit(1)
print("\nALL-OK")
