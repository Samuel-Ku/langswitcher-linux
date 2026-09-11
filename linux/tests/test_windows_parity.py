#!/usr/bin/env python3
"""Cross-language parity: the Windows AHK tables must match the Python core.

The AHK hook reimplements the conversion tables by hand, so they can drift.
This reads the data strings out of windows/LangSwitcher.ahk and asserts they
reconstruct exactly the core's Polish fold and Ukrainian ⌥-layer map.

Run: python3 tests/test_windows_parity.py
"""
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "lib"))

from langswitcher import _POLISH_DIACRITIC_BASES, _UKRAINIAN_OPTION  # noqa: E402

AHK = os.path.join(os.path.dirname(__file__), "..", "..", "windows", "LangSwitcher.ahk")


def literal(name: str) -> str | None:
    with open(AHK, encoding="utf-8") as f:
        src = f.read()
    m = re.search(rf'^\s*{name}\s*:=\s*"([^"]*)"', src, re.MULTILINE)
    return m.group(1) if m else None


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
