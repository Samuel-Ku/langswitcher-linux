#!/usr/bin/env python3
"""Port self-tests: conversion core (lib/). Run: python3 tests/test_convert.py"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "lib"))

from langswitcher import (  # noqa: E402
    convert,
    convert_greedy,
    convert_selected,
    looks_like_wrong_layout,
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

if fails:
    print("\nFAILURES:")
    for f in fails:
        print(" -", f)
    sys.exit(1)
print("\nALL-OK")
