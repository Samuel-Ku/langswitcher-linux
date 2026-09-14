#!/usr/bin/env python3
"""Tests for layout switching (Layout Switch mode). Run: python3 tests/test_layoutswitch.py"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "lib"))

import layoutswitch as ls  # noqa: E402

fails = []


def check(name, got, want):
    if got != want:
        fails.append(f"{name}: got {got!r}, want {want!r}")
    else:
        print(f"ok: {name}")


# ---- mode decision (macOS LayoutSwitchMode: always / if-converted / never) ----
check("always/switched", ls.should_switch("always", True), True)
check("always/not", ls.should_switch("always", False), True)
check("if-converted/switched", ls.should_switch("if-converted", True), True)
check("if-converted/not", ls.should_switch("if-converted", False), False)
check("never/switched", ls.should_switch("never", True), False)
check("unknown mode -> never", ls.should_switch("bogus", True), False)

# ---- keyboard selection ----
devices = {"keyboards": [
    {"name": "power-button", "layout": "us,ua", "main": False},
    {"name": "kbd-main", "layout": "us,ua", "main": True},
    {"name": "mouse", "layout": "us,ua", "main": False},
]}
check("picks main", ls.choose_keyboard(devices)["name"], "kbd-main")
no_main = {"keyboards": [{"name": "only", "layout": "us,ua", "main": False}]}
check("falls back to first with layout", ls.choose_keyboard(no_main)["name"], "only")
check("no keyboards -> None", ls.choose_keyboard({"keyboards": []}), None)
check("missing field -> None", ls.choose_keyboard(None), None)

# ---- lang -> xkb index ----
kb = {"name": "kbd", "layout": "us,ua"}
check("en -> index 0", ls.index_for_lang(kb, "en"), 0)
check("uk -> index 1", ls.index_for_lang(kb, "uk"), 1)
check("pl not installed -> None", ls.index_for_lang(kb, "pl"), None)
check("unknown lang -> None", ls.index_for_lang(kb, "xx"), None)
check("no keyboard -> None", ls.index_for_lang(None, "uk"), None)
kb3 = {"name": "kbd", "layout": "us,pl,ua"}
check("uk in 3-layout list -> 2", ls.index_for_lang(kb3, "uk"), 2)
check("pl in 3-layout list -> 1", ls.index_for_lang(kb3, "pl"), 1)

# ---- switch_to drives the runner only when there is something to switch to ----
calls = []


def fake_run(args, **kw):
    calls.append(args)
    class R:
        returncode = 0
        stdout = "ok"
    return R()


ok = ls.switch_to("uk", devices=devices, runner=fake_run)
check("switch_to uk ok", ok, True)
check("switch_to uk command", calls[-1], ["hyprctl", "switchxkblayout", "kbd-main", "1"])

calls.clear()
ok = ls.switch_to("pl", devices=devices, runner=fake_run)
check("switch_to pl missing -> False", ok, False)
check("switch_to pl did not call runner", calls, [])


def fail_run(args, **kw):
    class R:
        returncode = 1
        stdout = ""
    return R()


check("switch_to nonzero exit -> False",
      ls.switch_to("uk", devices=devices, runner=fail_run), False)

# ---- switching every keyboard (what automatic mode uses) ----
# The device the compositor calls "main" changes as virtual keyboards come and
# go, and keyboards switch independently, so a background conversion moves them
# all — the same call the Right-Alt binding makes.
calls.clear()
check("switch_everywhere uk", ls.switch_everywhere("uk", devices=devices, runner=fake_run), True)
check("switch_everywhere command", calls[-1], ["hyprctl", "switchxkblayout", "all", "1"])
calls.clear()
check("switch_everywhere missing layout -> False",
      ls.switch_everywhere("pl", devices=devices, runner=fake_run), False)
check("switch_everywhere did not call runner", calls, [])
check("switch_everywhere no keyboards -> False",
      ls.switch_everywhere("uk", devices={"keyboards": []}, runner=fake_run), False)
check("switch_everywhere nonzero exit -> False",
      ls.switch_everywhere("uk", devices=devices, runner=fail_run), False)

# ---- the runner the automatic path injects --------------------------------
# That runner (`autofix.run_command`) captures output itself, so asking it to
# capture again raised TypeError — and this module's `except Exception` reported
# that as a failed switch. The layout therefore never followed an automatic fix.
# A real runner and a fake hyprctl on PATH: the whole combination, not a stub
# that quietly accepts any keyword.
import tempfile  # noqa: E402

import autofix as af  # noqa: E402

bindir = tempfile.mkdtemp()
fake_hyprctl = os.path.join(bindir, "hyprctl")
with open(fake_hyprctl, "w", encoding="utf-8") as handle:
    handle.write("#!/bin/sh\necho ok\nexit 0\n")
os.chmod(fake_hyprctl, 0o755)
real_path = os.environ.get("PATH", "")
os.environ["PATH"] = bindir + os.pathsep + real_path
try:
    check("switch_everywhere works with the automatic path's runner",
          ls.switch_everywhere("uk", devices=devices, runner=af.run_command), True)
    check("switch_to works with the automatic path's runner",
          ls.switch_to("uk", devices=devices, runner=af.run_command), True)
finally:
    os.environ["PATH"] = real_path

if fails:
    print("\nFAILURES:")
    for f in fails:
        print(" -", f)
    sys.exit(1)
print("\nALL-OK")
