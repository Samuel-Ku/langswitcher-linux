#!/usr/bin/env python3
"""The three installers must pin the same data artifact.

`words.py` / `langswitcher-data.txt` is not in the repository — it is a CC BY-SA
4.0 release asset — so each installer carries its own copy of DATA_VERSION and
DATA_SHA256. Three copies of a version string is exactly the kind of thing that
drifts, and the failure mode is the worst one: installs break for other people,
not for whoever made the edit.

Run: python3 tests/test_data_pin.py
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..", "..")
GENERATOR = os.path.join(ROOT, "tools", "build_words.py")
INSTALLERS = {
    "omarchy": os.path.join(ROOT, "omarchy-plugin", "install-plugin.sh"),
    "windows/install.ps1": os.path.join(ROOT, "windows", "install.ps1"),
    "windows/install.bat": os.path.join(ROOT, "windows", "install.bat"),
}

fails = []


def check(name, got, want):
    if got != want:
        fails.append(f"{name}: got {got!r}, want {want!r}")
    else:
        print(f"ok: {name}")


def read(path):
    with open(path, encoding="utf-8") as handle:
        return handle.read()


version = re.search(r'^DATA_VERSION = "([^"]+)"', read(GENERATOR), re.MULTILINE)
check("the generator declares a DATA_VERSION", bool(version), True)
want_version = version.group(1) if version else None

seen = {}
for name, path in INSTALLERS.items():
    body = read(path)
    # DATA_VERSION="..." in shell, $DataVersion = "..." in PowerShell,
    # set "DATA_VERSION=..." in batch — one pattern, case-insensitive.
    found_version = re.search(r'(?i)data_?version[="\s]+"?([0-9]{4}\.[0-9]{2}\.[0-9]{2})', body)
    found_sha = re.search(r"\b([0-9a-f]{64})\b", body)
    check(f"{name}: names a data version", bool(found_version), True)
    check(f"{name}: names a full sha256", bool(found_sha), True)
    check(f"{name}: version matches the generator",
          found_version.group(1) if found_version else None, want_version)
    seen[name] = (
        found_version.group(1) if found_version else None,
        found_sha.group(1) if found_sha else None,
    )

versions = {entry[0] for entry in seen.values()}
hashes = {entry[1] for entry in seen.values()}
check("all installers pin the same version", len(versions), 1)
check("all installers pin the same hash", len(hashes), 1)

if fails:
    print("\nFAILURES:")
    for failure in fails:
        print(" -", failure)
    sys.exit(1)
print("\nALL-OK")
