#!/usr/bin/env python3
"""Cross-language parity: the Windows AHK tables must match the Python core.

The AHK hook reimplements the conversion tables by hand, so they can drift.
This reads the data strings out of windows/LangSwitcher.ahk and asserts they
reconstruct exactly the core's base layout maps, its Polish fold and its
Ukrainian ⌥-layer map.

The base maps matter because they are where the file had never been executed:
the AHK parser rejected them for their whole life (v1 quote doubling, a missing
literal backtick) and nothing on Linux could tell. The Windows CI job is what
finally ran the file; this check keeps the tables honest without one.

Run: python3 tests/test_windows_parity.py
"""
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "lib"))

from langswitcher import (  # noqa: E402
    QWERTY, _POLISH_DIACRITIC_BASES, _UKRAINIAN, _UKRAINIAN_OPTION)

AHK = os.path.join(os.path.dirname(__file__), "..", "..", "windows", "LangSwitcher.ahk")


def literal(name: str) -> str | None:
    """The raw text between the quotes of `name := "..."`.

    Scanned rather than regexed: the base maps contain an escaped quote (`"),
    which a `[^"]*` pattern would mistake for the end of the string.
    """
    with open(AHK, encoding="utf-8") as f:
        src = f.read()
    m = re.search(rf'^\s*{name}\s*:=\s*"', src, re.MULTILINE)
    if not m:
        return None
    out, index = [], m.end()
    while index < len(src):
        if src[index] == "`" and index + 1 < len(src):
            out.append(src[index:index + 2])
            index += 2
            continue
        if src[index] == '"':
            break
        out.append(src[index])
        index += 1
    return "".join(out)


def unescape_ahk(text: str) -> str:
    """Undo the v2 escapes used in the map literals: `" is a quote, `` a backtick."""
    out, index = [], 0
    while index < len(text):
        if text[index] == "`" and index + 1 < len(text) and text[index + 1] in '"`':
            out.append(text[index + 1])
            index += 2
        else:
            out.append(text[index])
            index += 1
    return "".join(out)


def check(name, got, want):
    if got != want:
        print(f"FAIL {name}:\n  got  {got!r}\n  want {want!r}")
        return False
    print(f"ok: {name}")
    return True


def main() -> int:
    if not os.path.exists(AHK):
        print("skip: windows/LangSwitcher.ahk not present")
        return 0

    ok = True

    for name, want in (("QWERTY", QWERTY), ("UKR", _UKRAINIAN)):
        raw = literal(name)
        check(f"AHK {name} base map == core", unescape_ahk(raw) if raw else None, want)

    keys = literal("UkrOptKeys")
    vals = literal("UkrOptVals")
    if keys is None or vals is None:
        print("FAIL: UkrOptKeys/UkrOptVals not found in AHK")
        return 1
    ukr_from_ahk = dict(zip(keys, vals))
    ok &= check("AHK Ukrainian ⌥ map == core", ukr_from_ahk, _UKRAINIAN_OPTION)

    bases = literal("PolBases")
    base_to = literal("PolBaseTo")
    if bases is None or base_to is None:
        print("FAIL: PolBases/PolBaseTo not found in AHK")
        return 1
    pol_from_ahk = dict(zip(bases, base_to))
    ok &= check("AHK Polish fold == core", pol_from_ahk, _POLISH_DIACRITIC_BASES)

    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
