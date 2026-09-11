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

# The core is duplicated into the plugin bundle on purpose; guard against drift.
_here = os.path.join(os.path.dirname(__file__), "..", "lib", "langswitcher.py")
_twin = os.path.join(os.path.dirname(__file__), "..", "..", "omarchy-plugin", "lib", "langswitcher.py")
if os.path.exists(_twin):
    check("lib copies identical", filecmp.cmp(_here, _twin, shallow=False), True)
else:
    print("skip: lib copies identical (twin not present in this deployment)")

# --mode auto is the production path that the Windows auto hook mirrors.
_switch = os.path.join(os.path.dirname(__file__), "..", "lib", "switch.py")


def run_auto(word):
    r = subprocess.run([sys.executable, _switch, "--mode", "auto", word],
                       capture_output=True, text=True)
    return (r.returncode, r.stdout)


check("auto CLI gibberish", run_auto("ghbdsn"), (0, "привіт"))
check("auto CLI english", run_auto("hello"), (2, ""))

if fails:
    print("\nFAILURES:")
    for f in fails:
        print(" -", f)
    sys.exit(1)
print("\nALL-OK")
