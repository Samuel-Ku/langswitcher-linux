#!/usr/bin/env python3
"""Dump or compare automatic-mode decisions for the Windows parity job.

The same corpus (``linux/tests/parity-corpus.txt``) goes through the Python core
here and through ``windows/LangSwitcher.ahk --dump`` on a Windows runner.  The
AHK reimplements the three-tier decision by hand, so ``compare`` is the only
thing that catches the two drifting apart — there is no shared code to lean on.

    python3 linux/tests/windows_parity_corpus.py dump <corpus> <out.tsv>
    python3 linux/tests/windows_parity_corpus.py compare <python.tsv> <ahk.tsv>

Not named ``test_*`` on purpose: it needs an AHK run, so it is a job, not a
local unit test.  Run the dump on its own to see the Python side's answers.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "omarchy-plugin", "lib"))

LAYOUTS = ["en", "uk"]      # the Windows port handles en/uk; pl is identity
MISSING = "-"


def tokens(path):
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            word = line.strip()
            if word and not word.startswith("#"):
                yield word


def dump(corpus: str, out: str) -> None:
    import autofix  # imported here so `--help` works without the data artifact

    with open(out, "w", encoding="utf-8") as handle:
        for word in tokens(corpus):
            chosen = autofix.plan(word, LAYOUTS, min_len=1)
            handle.write(f"{word}\t{1 if chosen else 0}\t"
                         f"{chosen['target'] if chosen else MISSING}\n")


def compare(left: str, right: str) -> int:
    with open(left, encoding="utf-8") as handle:
        ours = [line.rstrip("\n") for line in handle]
    with open(right, encoding="utf-8") as handle:
        theirs = [line.rstrip("\n") for line in handle]
    if len(ours) != len(theirs):
        print(f"FAIL: {len(ours)} Python decisions vs {len(theirs)} AHK decisions")
        return 1
    bad = [(a, b) for a, b in zip(ours, theirs) if a != b]
    for a, b in bad:
        print(f"FAIL: python {a!r} != ahk {b!r}")
    if bad:
        print(f"\n{len(bad)} of {len(ours)} decisions differ")
        return 1
    print(f"ok: {len(ours)} decisions identical")
    return 0


def main(argv: list[str]) -> int:
    if len(argv) == 3 and argv[0] == "dump":
        dump(argv[1], argv[2])
        return 0
    if len(argv) == 3 and argv[0] == "compare":
        return compare(argv[1], argv[2])
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
