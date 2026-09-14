#!/usr/bin/env python3
"""Tests for the user dictionary. Run: python3 tests/test_dictionary.py

The dictionary is the one file the user edits by hand, so most of what is
asserted here is that a hand-edited file cannot break the worker: junk, bare
strings, duplicates and a wrong ``source`` are all survivable, and a word can
always be found without regard to case or surrounding punctuation.
"""
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "lib"))

import dictionary as d  # noqa: E402

fails = []


def check(name, got, want):
    if got != want:
        fails.append(f"{name}: got {got!r}, want {want!r}")
    else:
        print(f"ok: {name}")


def tmp_path(name="dictionary.json"):
    handle = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
    handle.close()
    os.unlink(handle.name)
    return handle.name


# ---- the word's core -------------------------------------------------------
check("core strips punctuation", d.core("Kbd."), "Kbd")
check("core strips brackets", d.core("(ssh)"), "ssh")
check("core keeps inner punctuation", d.core("kbd-tool"), "kbd-tool")
check("core of punctuation only", d.core("..."), "")
check("core of empty", d.core(""), "")


# ---- the shipped list ------------------------------------------------------
# Every seed word must be something the strict check would otherwise fire on:
# three letters or more and no Latin vowel. A seed word with a vowel would be
# dead weight that hides how the list works.
bad = [w for w in d.SEED_WORDS
       if len(w) < 3 or not w.isascii() or not w.islower()
       or any(c in "aeiouy" for c in w)]
check("every seed word is a lowercase ASCII word without a Latin vowel", bad, [])
check("no seed duplicates", len(set(d.SEED_WORDS)), len(d.SEED_WORDS))
check("cap is 1000", d.CAP, 1000)


# ---- normalize -------------------------------------------------------------
document = d.normalize({"entries": [
    "kbd",                                              # a bare string is fine
    {"word": "SSH", "source": "manual", "ts": 2},
    {"word": "ssh", "source": "learned", "ts": 3},      # duplicate of the above
    {"word": "tmp", "source": "bogus", "ts": 4},        # unknown source
    {"word": "  "},                                     # nothing to look up
    {"word": "err", "source": "learned"},               # no ts
    42,                                                 # junk
]} )
check("normalize: duplicate dropped", [e["word"] for e in document["entries"]],
      ["kbd", "SSH", "tmp", "err"])
check("normalize: bare string becomes manual",
      document["entries"][0], {"word": "kbd", "source": "manual", "ts": 0})
check("normalize: unknown source becomes manual",
      document["entries"][2]["source"], "manual")
check("normalize: missing ts becomes 0", document["entries"][3]["ts"], 0)
check("normalize: junk document", d.normalize(None)["entries"], [])
check("normalize: version is written", d.normalize({})["version"], d.VERSION)

seeded = d.seeded()
check("seeded: all seed words", len(seeded["entries"]), len(d.SEED_WORDS))
check("seeded: source and ts", seeded["entries"][0]["source"], "seed")
check("seeded: ts is 0 so seed evicts first", seeded["entries"][0]["ts"], 0)


# ---- reading and writing ---------------------------------------------------
check("read: a missing file is None", d.read(tmp_path()), None)

junk = tmp_path()
with open(junk, "w", encoding="utf-8") as handle:
    handle.write("{not json")
check("read: a corrupt file is None", d.read(junk), None)

listed = tmp_path()
with open(listed, "w", encoding="utf-8") as handle:
    handle.write("[1, 2, 3]")
check("read: a non-object is None", d.read(listed), None)

path = tmp_path()
document = d.ensure(path)
check("ensure: materializes the seed list", len(document["entries"]), len(d.SEED_WORDS))
check("ensure: and writes the file", os.path.exists(path), True)
check("ensure: a second call finds it", len(d.ensure(path)["entries"]), len(d.SEED_WORDS))

# The written file is meant to be edited by hand: one entry per line, and a
# round trip has to leave it exactly as it was.
raw = open(path, encoding="utf-8").read()
check("saved: one entry per line", raw.count('{"word"'), len(d.SEED_WORDS))
check("saved: readable back", len(d.read(path)["entries"]), len(d.SEED_WORDS))
check("saved: no temp file left behind", os.path.exists(path + ".tmp"), False)

hand = tmp_path()
with open(hand, "w", encoding="utf-8") as handle:
    handle.write('{"version": 1, "entries": ["kbd", {"word": "ghbdsn"}]}')
check("hand-written: bare strings are read",
      sorted(d.keys(d.read(hand))), ["ghbdsn", "kbd"])


# ---- lookups ---------------------------------------------------------------
document = d.normalize({"entries": ["kbd", {"word": "SSH", "source": "learned"}]})
check("covers: exact", d.covers(document, "kbd"), True)
check("covers: case-insensitive", d.covers(document, "KBD"), True)
check("covers: punctuation-insensitive", d.covers(document, "ssh."), True)
check("covers: a different word", d.covers(document, "hello"), False)
check("covers: a prefix is not a match", d.covers(document, "kbd-tool"), False)
check("covers: empty word", d.covers(document, ""), False)


# ---- adding ----------------------------------------------------------------
document = d.seeded()
d.add(document, "ghbdsn", source="learned", now=1000)
check("add: appended", d.covers(document, "ghbdsn"), True)
check("add: source and ts", document["entries"][-1]["source"], "learned")
check("add: ts", document["entries"][-1]["ts"], 1000)

d.add(document, "GHBDSN", source="learned", now=2000)
check("add: a duplicate does not append",
      sum(1 for e in document["entries"] if d._key(e["word"]) == "ghbdsn"), 1)
check("add: the duplicate is refreshed", document["entries"][-1]["ts"], 2000)

before = len(document["entries"])
d.add(document, "kbd", source="learned", now=3000)
check("add: a seed word stays seed",
      [e["source"] for e in document["entries"] if e["word"] == "kbd"], ["seed"])
check("add: and is not appended again", len(document["entries"]), before)
check("add: an empty word is ignored", len(d.add(document, "  ...  ")["entries"]), before)


# ---- the cap ---------------------------------------------------------------
document = d.normalize({"entries": (
    [{"word": f"old{i}", "source": "learned", "ts": i} for i in range(3)]
    + [{"word": f"seed{i}", "source": "seed", "ts": 0} for i in range(3)]
    + [{"word": f"mine{i}", "source": "manual", "ts": 0} for i in range(3)]
)})
original_cap = d.CAP
d.CAP = 5                      # 9 entries, 4 over the cap
d.trim(document)
kept = [e["word"] for e in document["entries"]]
check("trim: oldest learned words go first, then seed",
      kept, ["seed1", "seed2", "mine0", "mine1", "mine2"])
check("trim: manual entries are never dropped",
      [w for w in kept if w.startswith("mine")], ["mine0", "mine1", "mine2"])

document = d.normalize({"entries": [{"word": f"mine{i}", "source": "manual", "ts": i}
                                    for i in range(6)]})
d.CAP = 2
d.trim(document)
check("trim: an all-manual file is left alone", len(document["entries"]), 6)
d.CAP = original_cap

document = d.normalize({"entries": [{"word": "kbd", "source": "manual", "ts": 1}]})
check("trim: nothing to do under the cap", len(d.trim(document)["entries"]), 1)

if fails:
    print("\nFAILURES:")
    for f in fails:
        print(" -", f)
    sys.exit(1)
print("\nALL-OK")
