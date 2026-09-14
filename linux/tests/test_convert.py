#!/usr/bin/env python3
"""Port self-tests: conversion core (lib/). Run: python3 tests/test_convert.py"""
import filecmp
import os
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "lib"))

from langswitcher import (  # noqa: E402
    convert,
    convert_greedy,
    convert_selected,
    looks_like_wrong_layout,
    looks_like_wrong_layout_strict,
)

L = ["en", "uk", "pl"]
fails = []


def check(name, got, want):
    if got != want:
        fails.append(f"{name}: got {got!r}, want {want!r}")
    else:
        print(f"ok: {name}")


check("en->uk", convert_selected("ghbdsn", L), ("привіт", "uk"))
check("uk->en", convert_selected("привіт", L), ("ghbdsn", "en"))
check("uk->en caps", convert_selected("Руддщ", L), ("Hello", "en"))
check("explicit", convert("Hello", "en", "uk"), "Руддщ")
check("greedy", convert_greedy("ghbdsn zr ltkf lheu", L),
      ("привіт як дела друг", "uk"))
check("greedy mixed pl", convert_greedy("Zażółć ghbdsn", L),
      ("Zażółć привіт", "uk"))
check("polish untouched", convert_selected("Zażółć gęślą jaźń", L), None)
check("polish word untouched", convert_selected("gęślą", L), None)
check("wrong-layout en word", looks_like_wrong_layout("ghbdsn", L), True)
check("polish not wrong", looks_like_wrong_layout("Zażółć", L), False)
check("punct: trailing period kept", convert_selected("ghbdsn.", L), ("привіт.", "uk"))
check("punct: trailing comma kept", convert_selected("ghbdsn,", L), ("привіт,", "uk"))
check("punct: surrounded kept", convert_selected("(Руддщ)", L), ("(Hello)", "en"))
check("punct: quotes kept", convert_selected('"ghbdsn"', L), ('"привіт"', "uk"))

# Option-layer (⌥) recovery, ported from macOS: Polish typed while a Cyrillic
# layout is active (ą=⌥+A -> ƒ on Ukrainian-PC, ś=⌥+S -> ы, ć=⌥+C -> ≠, ...).
check("opt: canonical uk->pl", convert("ьƒлф", "uk", "pl"), "mąka")
check("opt: selection recovers pl", convert_selected("ьƒлф", L), ("mąka", "pl"))
check("opt: cześć via ⌥+C", convert_selected("сяуы≠", L), ("cześć", "pl"))
check("opt: Polish fold pl->uk", convert("mąka", "pl", "uk"), "ьфлф")
check("opt: guard still skips real Polish", convert_selected("mąka", L), None)
check("opt: uk->en unaffected by opt rule", convert_selected("привіт", L), ("ghbdsn", "en"))

# Strict (auto) heuristic: must fire on vowel-less Latin gibberish, but NEVER on
# ordinary English/Ukrainian words, or auto-mode would rewrite normal typing.
check("auto: latin gibberish", looks_like_wrong_layout_strict("ghbdsn", L), True)
check("auto: latin gibberish 2", looks_like_wrong_layout_strict("ghbdtn", L), True)
check("auto: english hello", looks_like_wrong_layout_strict("hello", L), False)
check("auto: english test", looks_like_wrong_layout_strict("test", L), False)
check("auto: english the", looks_like_wrong_layout_strict("the", L), False)
check("auto: english rhythm", looks_like_wrong_layout_strict("rhythm", L), False)
check("auto: uk word", looks_like_wrong_layout_strict("привіт", L), False)
check("auto: uk word 2", looks_like_wrong_layout_strict("робота", L), False)
check("auto: polish", looks_like_wrong_layout_strict("Zażółć", L), False)
check("auto: too short", looks_like_wrong_layout_strict("ab", L), False)
check("auto: has digit", looks_like_wrong_layout_strict("ghb2", L), False)
check("auto: no vowels but no target vowel", looks_like_wrong_layout_strict("hmm", L), False)
check("punct: strict with period", looks_like_wrong_layout_strict("ghbdsn.", L), True)
check("punct: strict with comma", looks_like_wrong_layout_strict("ghbdsn,", L), True)
check("punct: strict english period", looks_like_wrong_layout_strict("hello.", L), False)
check("punct: strict only symbols", looks_like_wrong_layout_strict("...", L), False)

# The core lib is duplicated into the plugin bundle on purpose; guard against drift.
_libdir = os.path.join(os.path.dirname(__file__), "..", "lib")
_twindir = os.path.join(os.path.dirname(__file__), "..", "..", "omarchy-plugin", "lib")
if os.path.isdir(_twindir):
    for _name in ("langswitcher.py", "switch.py", "layoutswitch.py",
                  "keycodes.py", "autofix.py"):
        check(f"lib copies identical: {_name}",
              filecmp.cmp(os.path.join(_libdir, _name), os.path.join(_twindir, _name),
                          shallow=False), True)
else:
    print("skip: lib copies identical (twin not present in this deployment)")

# The KDE bundle shares the same core — the three files its worker runs — but not
# the Hyprland-only automatic mode, which needs Hyprland's own key events.
_kdedir = os.path.join(os.path.dirname(__file__), "..", "..", "fedora-kde", "lib")
if os.path.isdir(_kdedir):
    for _name in ("langswitcher.py", "switch.py", "layoutswitch.py"):
        check(f"kde lib copy identical: {_name}",
              filecmp.cmp(os.path.join(_libdir, _name), os.path.join(_kdedir, _name),
                          shallow=False), True)
else:
    print("skip: kde lib copies identical (bundle not present)")

# --mode auto is the production path that the Windows auto hook mirrors.
_switch = os.path.join(os.path.dirname(__file__), "..", "lib", "switch.py")


def run_auto(word):
    r = subprocess.run([sys.executable, _switch, "--mode", "auto", word],
                       capture_output=True, text=True)
    return (r.returncode, r.stdout)


check("auto CLI gibberish", run_auto("ghbdsn"), (0, "привіт"))
check("auto CLI english", run_auto("hello"), (2, ""))
check("auto CLI trailing period", run_auto("ghbdsn."), (0, "привіт."))

# last-word with a single token must still go through the greedy path, not skip.
_r = subprocess.run([sys.executable, _switch, "--mode", "last-word", "ghbdsn"],
                    capture_output=True, text=True)
check("last-word single word", (_r.returncode, _r.stdout), (0, "привіт"))

if fails:
    print("\nFAILURES:")
    for f in fails:
        print(" -", f)
    sys.exit(1)
print("\nALL-OK")
