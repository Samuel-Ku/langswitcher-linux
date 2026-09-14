#!/usr/bin/env python3
"""Tests for automatic mode (Punto-style). Run: python3 tests/test_autofix.py

Auto mode edits text the user never asked about, so what is asserted here is
mostly what it *refuses* to do: which windows it stays out of, what happens when
the proof that the caret still sits behind the word fails, and that a run which
changes nothing is visible rather than silent.

The runner is injected, so the whole flow is checked without touching a real
clipboard, keyboard or compositor — the command sequence is the observable.
"""
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "lib"))

import autofix  # noqa: E402
import dictionary  # noqa: E402
import keycodes as kc  # noqa: E402

L = ["en", "uk", "pl"]
fails = []

GHBDSN = "42,43,56,40,39,57"     # g h b d s n, the canonical wrong-layout word
HELLO = "43,26,46,46,32"         # h e l l o, already a word in its own script
KBD = "45,56,40"                 # k b d, a real word with no Latin vowel


def check(name, got, want):
    if got != want:
        fails.append(f"{name}: got {got!r}, want {want!r}")
    else:
        print(f"ok: {name}")


# ---- the decision is the core's, not a second implementation ---------------
check("plan converts gibberish", autofix.plan("ghbdsn", L),
      {"typed": "ghbdsn", "fixed": "привіт", "target": "uk"})
check("plan keeps english", autofix.plan("hello", L), None)
check("plan keeps ukrainian", autofix.plan("привіт", L), None)
check("plan keeps polish", autofix.plan("Zażółć", L), None)
check("plan keeps too short", autofix.plan("gh", L), None)
check("plan keeps punctuation only", autofix.plan("...", L), None)
check("plan converts reverse", autofix.plan("руддщ", L),
      None)  # conservative: "руддщ" has a Ukrainian vowel, so it is left alone
check("plan min_len is honoured", autofix.plan("ghbd", L, min_len=5), None)


# ---- settings --------------------------------------------------------------
def settings_file(payload):
    handle = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
    handle.write(payload)
    handle.close()
    return handle.name


# layoutswitch asks the runner to capture output; this runner always captures,
# so it has to drop that request instead of forwarding it twice. Forwarding it
# raised TypeError, which layoutswitch reported as "the switch failed" — the
# layout silently stopped following an automatic fix.
done = autofix.run_command(["sh", "-c", "exit 7"], capture_output=True, text=True,
                           timeout=3)
check("run_command tolerates layoutswitch's kwargs", done.returncode, 7)


check("settings default", autofix.load_settings(settings_file("{}")), autofix.DEFAULTS)
check("settings missing file", autofix.load_settings("/nonexistent/langswitcher.json"),
      autofix.DEFAULTS)
check("settings junk", autofix.load_settings(settings_file("[1, 2]")), autofix.DEFAULTS)
merged = autofix.load_settings(settings_file('{"enabled": false, "min_len": 5}'))
check("settings merged", (merged["enabled"], merged["min_len"], merged["verify"]),
      (False, 5, True))
check("debug is off unless asked for", merged["debug"], False)


# ---- layout detection ------------------------------------------------------
# Shaped like the machine this was written on: Hyprland marks the *virtual*
# fcitx5 keyboard as "main", and it sat on the first layout ("us") while every
# physical keyboard was on the second ("ua"). A worker that trusts "main"
# decodes Ukrainian typing as Latin, so the physical device has to decide.
def devices(layout="us,ua", index=0, virtual_index=0):
    return {"keyboards": [
        {"name": "video-bus", "layout": layout, "main": False,
         "active_layout_index": index},
        {"name": "at-translated-set-2-keyboard", "layout": layout, "main": False,
         "active_layout_index": index},
        {"name": "hl-virtual-keyboard-fcitx5", "layout": layout, "main": True,
         "active_layout_index": virtual_index},
    ]}


check("device codes", autofix.layout_codes(devices()), ["us", "ua"])
check("active layout us", autofix.active_layout_id(devices()), "en")
check("active layout ua", autofix.active_layout_id(devices(index=1)), "uk")
check("virtual main does not decide", autofix.active_layout_id(devices(index=1)), "uk")
check("virtual board is recognised",
      autofix.is_virtual({"name": "hl-virtual-keyboard-fcitx5"}), True)
check("physical board is not virtual", autofix.is_virtual({"name": "video-bus"}), False)
check("unknown code -> None", autofix.active_layout_id(devices("us,de", 1)), None)
check("index out of range -> None", autofix.active_layout_id(devices("us,ua", 9)), None)
check("no keyboards -> None", autofix.active_layout_id({"keyboards": []}), None)
check("main keyboard wins", autofix.keyboard({"keyboards": [
    {"name": "extra", "layout": "de", "main": False},
    {"name": "main", "layout": "us,ua", "main": True}]})["name"], "main")
check("physical picked over a virtual main",
      autofix.keyboard(devices(index=1))["name"], "video-bus")
check("nothing but virtual -> falls back to it", autofix.active_layout_id({"keyboards": [
    {"name": "hl-virtual-keyboard-fcitx5", "layout": "us,ua", "main": True,
     "active_layout_index": 1}]}), "uk")
check("boards without a layout are ignored", autofix.keyboard({"keyboards": [
    {"name": "mouse", "layout": "", "main": True}]}), None)

# The --check self-test must not depend on the layout in force: on a Ukrainian
# keyboard it used to read "привіт" and call a healthy plugin broken.
check("self-test decodes with a fixed layout",
      autofix.self_test("uk")["selftest"]["decoded"], "ghbdsn")
check("self-test reports what the layout in force gives",
      autofix.self_test("uk")["selftest"]["decoded_in_force"], "привіт")
check("self-test is ok on a ukrainian keyboard", autofix.self_test("uk")["ok"], True)
check("self-test is ok on an english keyboard", autofix.self_test("en")["ok"], True)
check("self-test fails when the layout is unknown", autofix.self_test(None)["ok"], False)


# ---- the rewrite itself ----------------------------------------------------
class Fake:
    """Enough of Hyprland, wtype and wl-clipboard to observe the flow."""

    def __init__(self, *, window="gtk", primary="", clipboard="", copies=None,
                 layers="", layout="us,ua", index=0):
        self.calls = []
        self.window = window
        self.primary = primary
        self.clipboard = clipboard
        self.copies = copies          # what a Ctrl+C would put on the clipboard
        self.layers = layers
        self.layout = layout
        self.index = index

    def __call__(self, argv, **kwargs):
        self.calls.append(list(argv))
        stdout, code = "", 0
        if argv[:2] == ["hyprctl", "-j"]:
            what = argv[2]
            if what == "devices":
                stdout = json.dumps(devices(self.layout, self.index))
            elif what == "activewindow":
                stdout = json.dumps({"class": self.window})
            elif what == "layers":
                # `hyprctl -j layers` only names a panel when one is mapped.
                stdout = self.layers
        elif argv[:2] == ["wl-paste", "--no-newline"]:
            stdout = self.primary if "--primary" in argv else self.clipboard
        elif argv[0] == "wtype":
            text = " ".join(argv[1:])
            if "-k c" in text and "-M ctrl" in text and self.copies is not None:
                self.clipboard = self.copies
        elif argv[:2] == ["hyprctl", "switchxkblayout"]:
            code = 0
        return type("Done", (), {"stdout": stdout, "stderr": "", "returncode": code})()

PLAN = {"typed": "ghbdsn", "fixed": "привіт", "target": "uk"}


def wtypes(fake):
    """Only the keystrokes: the flow also asks Hyprland and reads the selections."""
    return [c for c in fake.calls if c[0] == "wtype"]

# Verified path: the previous word is selected and read back, the selection is
# collapsed, the word plus its boundary is deleted, the layout is switched, and
# the fixed word plus a space is typed.
fake = Fake(primary="ghbdsn")
result = autofix.fix(PLAN, run=fake, sleep=lambda _s: None, switch=lambda lang: True)
check("verified: outcome", result["outcome"], "fixed")
check("verified: gate first", wtypes(fake)[0], ["wtype", "-M", "ctrl", "-M", "shift",
                                                 "-k", "Left", "-m", "shift", "-m", "ctrl"])
check("verified: collapse after proof", wtypes(fake)[1], ["wtype", "-k", "Right"])
check("verified: deletes word and boundary",
      wtypes(fake).count(["wtype", "-k", "BackSpace"]), 7)
check("verified: switch recorded", ["switch", "uk", "True"] in result["steps"], True)
check("verified: types the fix with a space", wtypes(fake)[-1], ["wtype", "--", "привіт "])
check("verified: clipboard untouched", any(c[0] == "wl-copy" for c in fake.calls), False)

# Selection may include the boundary space; the proof strips it either way.
fake = Fake(primary="ghbdsn ")
autofix.fix(PLAN, run=fake, sleep=lambda _s: None, switch=lambda lang: True)
check("proof tolerates selected space", wtypes(fake)[-1], ["wtype", "--", "привіт "])

# A fast typist already in the next word: the proof fails and nothing is deleted.
fake = Fake(primary="hello", clipboard="hello")
result = autofix.fix(PLAN, run=fake, sleep=lambda _s: None, switch=lambda lang: True)
check("mismatch: outcome", result["outcome"], "gate-mismatch")
check("mismatch: no deletion",
      any(c == ["wtype", "-k", "BackSpace"] for c in fake.calls), False)
check("mismatch: caret restored", wtypes(fake)[-1], ["wtype", "-k", "Right"])
check("mismatch: no switch", [s for s in result["steps"] if s[0] == "switch"], [])

# Apps that publish no primary selection still prove the range through Ctrl+C,
# and the clipboard they clobbered is put back.
fake = Fake(primary="", clipboard="OLD", copies="ghbdsn")
result = autofix.fix(PLAN, run=fake, sleep=lambda _s: None, switch=lambda lang: True)
check("fallback: outcome", result["outcome"], "fixed")
check("fallback: restores clipboard", fake.calls[-1], ["wl-copy", "OLD"])
check("fallback: restored flag", result["clipboard_restored"], True)

# Clipboard happened to already hold exactly the selection: proof still holds,
# and nothing was clobbered, so nothing is restored.
fake = Fake(primary="", clipboard="ghbdsn", copies="ghbdsn")
result = autofix.fix(PLAN, run=fake, sleep=lambda _s: None, switch=lambda lang: True)
check("fallback: already-copied outcome", result["outcome"], "fixed")
check("fallback: no pointless restore", any(c[0] == "wl-copy" for c in fake.calls), False)

# Unverified (opt-in) path: no gate, straight to the edit.
fake = Fake()
result = autofix.fix(PLAN, verify=False, run=fake, sleep=lambda _s: None,
                     switch=lambda lang: True)
check("unverified: outcome", result["outcome"], "fixed")
check("unverified: no gate", wtypes(fake)[0], ["wtype", "-k", "BackSpace"])
check("unverified: types the fix", wtypes(fake)[-1], ["wtype", "--", "привіт "])

# A refused switch must not stop the text from being right.
fake = Fake(primary="ghbdsn")
result = autofix.fix(PLAN, run=fake, sleep=lambda _s: None, switch=lambda lang: False)
check("switch refused: text still fixed", result["outcome"], "fixed")
check("switch refused: recorded", ["switch", "uk", "False"] in result["steps"], True)


# ---- one run, end to end ---------------------------------------------------
class Rig:
    """A run whose settings, dictionary and fix state live in a temp dir.

    The real files are the user's: a test that learns "ghbdsn" into
    ~/.config/omarchy/langswitcher-dictionary.json changes the machine it runs
    on, and the first version of this suite did exactly that.
    """

    def __init__(self, tmp):
        self.auto = os.path.join(tmp, "last-auto.json")
        self.dictionary = os.path.join(tmp, "dictionary.json")
        self.fix = os.path.join(tmp, "last-fix.json")

    def handle(self, keys=GHBDSN, *, window="gtk", fake=None, settings=None, **kwargs):
        fake = fake if fake is not None else Fake(window=window)
        # Settings, dictionary and fix state all stay in the temp dir: the real
        # files are the user's, and a test that reads them (or writes to them)
        # behaves differently on the machine it happens to run on.
        record = autofix.handle(keys, window=window, run=fake, sleep=lambda _s: None,
                                settings=dict(autofix.DEFAULTS) if settings is None else settings,
                                state_path=self.auto, dictionary_path=self.dictionary,
                                fix_path=self.fix, **kwargs)
        return record, fake

    def logged(self):
        with open(self.auto) as handle:
            return json.load(handle)

    def stored(self):
        document = dictionary.read(self.dictionary)
        return [entry["word"] for entry in (document or {}).get("entries") or []]

    def last_fix(self):
        return autofix.read_fix_state(self.fix)


def run_case(name, *, keys=GHBDSN, window="gtk", **fake_args):
    with tempfile.TemporaryDirectory() as tmp:
        rig = Rig(tmp)
        record, fake = rig.handle(keys, window=window,
                                  fake=Fake(window=window, **fake_args))
        check(f"handle {name}: outcome", record["outcome"], rig.logged()["outcome"])
    return record, fake


record, fake = run_case("gibberish", primary="ghbdsn")
check("handle gibberish: fixed", record["outcome"], "fixed")
check("handle gibberish: target", record["target"], "uk")
check("handle gibberish: no text in the log",
      any("ghbdsn" in str(v) for v in record.values()), False)
check("handle gibberish: typed digest only", record["typed_digest"], autofix._digest("ghbdsn"))

record, _ = run_case("english", keys=HELLO, primary="hello", clipboard="hello")
check("handle english: kept", record["outcome"], "kept")

# A word that *does* deserve an edit, arriving too late to be proved.
record, _ = run_case("too late", primary="hello", clipboard="hello", copies="hello")
check("handle too late: no edits", record["outcome"], "gate-mismatch")

record, _ = run_case("terminal", window="Alacritty")
check("handle terminal: skipped", record["outcome"], "skipped-terminal")

with tempfile.TemporaryDirectory() as tmp:
    record, _ = Rig(tmp).handle(fake=Fake(window="other"))
check("handle focus moved: skipped", record["outcome"], "skipped-focus-moved")

record, _ = run_case("panel", primary="ghbdsn", layers="omarchy-keyboard-panel")
check("handle panel: skipped", record["outcome"], "skipped-panel")

record, _ = run_case("unknown layout", primary="ghbdsn", layout="us,de", index=1)
check("handle unknown layout: skipped", record["outcome"], "skipped-layout")

record, _ = run_case("undecodable", keys="42,65,43", primary="ghbdsn")
check("handle undecodable: skipped", record["outcome"], "skipped-undecodable")
check("handle undecodable: names the keycode", record["unknown"], [65])

with tempfile.TemporaryDirectory() as tmp:
    record, fake = Rig(tmp).handle(settings={**autofix.DEFAULTS, "enabled": False},
                                   fake=Fake(primary="ghbdsn"))
check("handle disabled: skipped", record["outcome"], "disabled")
check("handle disabled: no commands at all", fake.calls, [])

with tempfile.TemporaryDirectory() as tmp:
    record, fake = Rig(tmp).handle(settings={**autofix.DEFAULTS, "verify": False},
                                   fake=Fake(primary="ghbdsn"))
check("handle unverified setting: fixed", record["outcome"], "fixed")
check("handle unverified setting: no gate", wtypes(fake)[0], ["wtype", "-k", "BackSpace"])

# The layout the app is really using decides the decode: the same keys read as
# "ghbdsn" under us are already Ukrainian under ua and must be left alone. The
# virtual keyboard stays on "us" here, which is exactly the trap.
record, _ = run_case("already ukrainian", primary="привіт", index=1)
check("handle ua layout: kept", record["outcome"], "kept")

# A synthetic key's numbering can land inside the text block; decoding it must
# not look like a word (wtype's own keymap numbers keysyms from 9 upwards).
record, _ = run_case("synthetic keycodes", keys="10,11,12,13,14", primary="12345")
check("handle synthetic keycodes: kept", record["outcome"], "kept")

# ...and with debug on, the record says what arrived and what it decoded to,
# which is what a "nothing happened" report needs.
with tempfile.TemporaryDirectory() as tmp:
    record, fake = Rig(tmp).handle(settings={**autofix.DEFAULTS, "debug": True},
                                   fake=Fake(primary="ghbdsn"))
check("debug record: raw keys", record["raw_keys"], GHBDSN)
check("debug record: decoded text", record["typed"], "ghbdsn")
check("debug record: layout", record["layout"], "en")
check("debug record: still fixed", record["outcome"], "fixed")


# ---- the user's dictionary -------------------------------------------------
# "kbd" is a real word with no Latin vowel: without the dictionary the strict
# check rewrites it, and that is the false positive this whole list exists for.
with tempfile.TemporaryDirectory() as tmp:
    rig = Rig(tmp)
    record, fake = rig.handle(KBD, fake=Fake(primary="kbd"))
    check("dictionary: outcome", record["outcome"], "dictionary")
    check("dictionary: nothing is rewritten",
          any(call[0] == "wtype" for call in fake.calls), False)
    check("dictionary: the seed list is materialized", "kbd" in rig.stored(), True)
    check("dictionary: and written one word per line",
          '{"word": "kbd", "source": "seed", "ts": 0}' in
          open(rig.dictionary, encoding="utf-8").read(), True)

# A file the user wrote by hand is read as-is, case-insensitively, whatever the
# entry looks like.
with tempfile.TemporaryDirectory() as tmp:
    rig = Rig(tmp)
    with open(rig.dictionary, "w", encoding="utf-8") as handle:
        handle.write('{"entries": [{"word": "GHBDSN", "source": "manual", "ts": 1}]}')
    record, fake = rig.handle(fake=Fake(primary="ghbdsn"))
    check("dictionary: hand-written entry, any case", record["outcome"], "dictionary")
    check("dictionary: hand-written entry blocks the edit",
          any(call[0] == "wtype" for call in fake.calls), False)

# The dictionary is a setting for *automatic* mode only: the user's explicit
# hotkey path is a different worker and must stay able to convert anything.
check("dictionary does not change plan()",
      autofix.plan("kbd", L), {"typed": "kbd", "fixed": "лив", "target": "uk"})

# The layout switch is a setting too.
with tempfile.TemporaryDirectory() as tmp:
    record, _ = Rig(tmp).handle(settings={**autofix.DEFAULTS, "switch": False},
                                fake=Fake(primary="ghbdsn"))
check("switch off: the text is still fixed", record["outcome"], "fixed")
check("switch off: no switch happened", record["switched"], False)


# ---- learning a rejection --------------------------------------------------
# Type a word, watch it be rewritten, delete it and type the word you meant:
# that is the verdict, and it is remembered.
with tempfile.TemporaryDirectory() as tmp:
    rig = Rig(tmp)
    first, _ = rig.handle(fake=Fake(primary="ghbdsn"))
    check("learn: the first run fixes", first["outcome"], "fixed")
    check("learn: the fix holds the words", rig.last_fix().get("typed"), "ghbdsn")
    check("learn: and the layout it came from", rig.last_fix().get("source"), "en")

    again, _ = rig.handle(fake=Fake(primary="ghbdsn"), now=first["ts"] / 1000 + 5)
    check("learn: retyping is a rejection", again["outcome"], "learned")
    check("learn: the word is in the dictionary", "ghbdsn" in rig.stored(), True)
    check("learn: the fix record is consumed", rig.last_fix(), {})

    third, _ = rig.handle(fake=Fake(primary="ghbdsn"), now=first["ts"] / 1000 + 10)
    check("learn: never converted again", third["outcome"], "dictionary")

# Anything else is not a rejection.
with tempfile.TemporaryDirectory() as tmp:
    rig = Rig(tmp)
    first, _ = rig.handle(fake=Fake(primary="ghbdsn"))
    other, _ = rig.handle(HELLO, fake=Fake(primary="hello"), now=first["ts"] / 1000 + 5)
    check("learn: another word is not a rejection", other["outcome"], "kept")
    late, _ = rig.handle(fake=Fake(primary="ghbdsn"), now=first["ts"] / 1000 + 61)
    check("learn: much later is a new word", late["outcome"], "fixed")

with tempfile.TemporaryDirectory() as tmp:
    rig = Rig(tmp)
    first, _ = rig.handle(fake=Fake(primary="ghbdsn"))
    moved, _ = rig.handle(fake=Fake(window="other", primary="ghbdsn"), window="",
                          now=first["ts"] / 1000 + 5)
    check("learn: another window is not a rejection", moved["outcome"], "fixed")
    check("learn: and nothing was learned", "ghbdsn" in rig.stored(), False)


# ---- undo ------------------------------------------------------------------
with tempfile.TemporaryDirectory() as tmp:
    rig = Rig(tmp)
    rig.handle(fake=Fake(primary="ghbdsn"))
    back = Fake(primary="привіт")
    result = autofix.undo(run=back, sleep=lambda _s: None, switch=lambda lang: True,
                          fix_path=rig.fix, dictionary_path=rig.dictionary)
    check("undo: outcome", result["outcome"], "undone")
    check("undo: the typed word comes back", wtypes(back)[-1], ["wtype", "--", "ghbdsn "])
    check("undo: deletes the rewrite plus its space",
          wtypes(back).count(["wtype", "-k", "BackSpace"]), len("привіт") + 1)
    check("undo: the layout goes back", ["switch", "en", "True"] in result["steps"], True)
    check("undo: the word is learned", "ghbdsn" in rig.stored(), True)
    check("undo: the fix record is cleared", rig.last_fix(), {})

with tempfile.TemporaryDirectory() as tmp:
    rig = Rig(tmp)
    rig.handle(fake=Fake(primary="ghbdsn"))
    stale = Fake(primary="hello", clipboard="hello")
    result = autofix.undo(run=stale, sleep=lambda _s: None, switch=lambda lang: True,
                          fix_path=rig.fix, dictionary_path=rig.dictionary)
    check("undo: a failed proof changes nothing", result["outcome"], "undo-gate-mismatch")
    check("undo: nothing is deleted",
          any(call == ["wtype", "-k", "BackSpace"] for call in stale.calls), False)
    check("undo: nothing is learned", "ghbdsn" in rig.stored(), False)

with tempfile.TemporaryDirectory() as tmp:
    rig = Rig(tmp)
    record, _ = rig.handle(fake=Fake(primary="ghbdsn"))
    late = autofix.undo(run=Fake(primary="привіт"), sleep=lambda _s: None,
                        switch=lambda lang: True, fix_path=rig.fix,
                        dictionary_path=rig.dictionary, now=record["ts"] / 1000 + 121)
    check("undo: expires", late["outcome"], "undo-expired")

with tempfile.TemporaryDirectory() as tmp:
    rig = Rig(tmp)
    rig.handle(fake=Fake(primary="ghbdsn"))
    moved = autofix.undo(run=Fake(window="other", primary="привіт"), sleep=lambda _s: None,
                         switch=lambda lang: True, fix_path=rig.fix,
                         dictionary_path=rig.dictionary)
    check("undo: refuses when the focus moved", moved["outcome"], "undo-focus-moved")

with tempfile.TemporaryDirectory() as tmp:
    empty = autofix.undo(run=Fake(primary="привіт"), sleep=lambda _s: None,
                         fix_path=os.path.join(tmp, "none.json"),
                         dictionary_path=os.path.join(tmp, "dictionary.json"))
    check("undo: nothing to undo", empty["outcome"], "undo-nothing")

if fails:
    print("\nFAILURES:")
    for f in fails:
        print(" -", f)
    sys.exit(1)
print("\nALL-OK")
