#!/usr/bin/env python3
"""Tests for the Fedora KDE bundle. Run: python3 tests/test_kde_bundle.py

No KDE session exists where this was written, so the things that *can* be checked
are checked: that the worker uses the tools that work on KWin and not the ones
that silently do not, that the shared core is the same bytes as the Omarchy
bundle, that the installer and the packaging agree with the README about the two
traps that break a blind port (ydotool's numeric keycodes, and its socket), and
that the README states plainly what has not been tested.
"""
import filecmp
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BUNDLE = os.path.join(HERE, "..", "..", "fedora-kde")
OMARCHY_LIB = os.path.join(HERE, "..", "..", "omarchy-plugin", "lib")
fails = []


def check(name, got, want):
    if got != want:
        fails.append(f"{name}: got {got!r}, want {want!r}")
    else:
        print(f"ok: {name}")


def read(*parts):
    with open(os.path.join(BUNDLE, *parts), encoding="utf-8") as handle:
        return handle.read()


worker = read("bin", "kde-convert")

# wtype drives zwp_virtual_keyboard_v1, which KWin does not implement: it must not
# be the default typer, and the reason has to be written down where it is read.
check("worker defaults to ydotool",
      'TYPER="${LANGSWITCHER_TYPER:-ydotool}"' in worker, True)
check("worker explains the wtype trap", "zwp_virtual_keyboard" in worker, True)

# ydotool 1.x `key` takes evdev keycodes only, not key names.
check("ctrl+c is a keycode chord", "29:1 46:1 46:0 29:0" in worker, True)
check("ctrl+v is a keycode chord", "29:1 47:1 47:0 29:0" in worker, True)
check("word selection is a keycode chord", "105:1 105:0" in worker, True)
check("no key names are passed to ydotool",
      re.search(r"ydotool key \S*(ctrl\+|shift\+)", worker), None)

# The layout backend is named instead of left to desktop-name detection, so the
# switch does not depend on how the session spells XDG_CURRENT_DESKTOP.
check("worker names the layout backend", "LANGSWITCHER_LAYOUT_BACKEND" in worker, True)
check("worker asks the converter to switch", "--switch always" in worker, True)

# --check has to report what a blind port needs to see on the first run.
for field in ("hints", "ydotool", "layouts", "backend", "selftest"):
    check(f"--check reports {field}", f'"{field}"' in worker, True)

installer = read("install.sh")
check("installer hands the ydotoold socket to the user", "--socket-own" in installer, True)
check("installer restarts kglobalacceld", "plasma-kglobalaccel" in installer, True)
check("installer writes a command shortcut",
      "X-KDE-GlobalAccel-CommandShortcut=true" in installer, True)
check("installer nests the shortcuts section", installer.count("--group services") >= 2, True)
check("installer can be rehearsed", "--dry-run" in installer, True)
check("installer warns about X11", "xclip xdotool" in installer, True)

spec = read("packaging", "langswitcher-kde.spec")
check("spec requires ydotool", "Requires:       ydotool" in spec, True)
check("spec requires glib2 (gdbus)", "Requires:       glib2" in spec, True)
check("spec ships the command shortcuts",
      "net.local.langswitcher-selection.desktop" in spec, True)
check("spec checks the converter without a session", "grep -qx" in spec, True)
for name in ("net.local.langswitcher-selection.desktop",
             "net.local.langswitcher-line.desktop"):
    body = read("packaging", name)
    check(f"{name}: is a command shortcut",
          "X-KDE-GlobalAccel-CommandShortcut=true" in body, True)
    check(f"{name}: points at the installed worker",
          "Exec=/usr/bin/kde-convert" in body, True)

# The core is shared, not forked. The generated data (words.py) is not committed
# at all — it is a CC BY-SA 4.0 release artifact the installer fetches — so only
# the code the KDE worker runs is compared byte for byte.
for name in ("langswitcher.py", "switch.py", "layoutswitch.py"):
    check(f"core is byte-identical: {name}",
          filecmp.cmp(os.path.join(BUNDLE, "lib", name),
                      os.path.join(OMARCHY_LIB, name), shallow=False), True)
# ...and the Hyprland-only automatic mode is deliberately not part of it.
check("no Hyprland auto mode in the KDE bundle",
      os.path.exists(os.path.join(BUNDLE, "lib", "autofix.py")), False)

readme = read("README.md")
check("README states what was not verified", "НЕ перевірено" in readme, True)
check("README explains why auto mode is absent", "Orca" in readme, True)
check("README warns that qdbus6 does not exist", "qdbus6" in readme, True)

# ---- the one-liner has to route a Fedora KDE box here ---------------------
# `install.sh` picks a component from the distro and the desktop; a Fedora user
# who runs the documented curl line must land on this bundle, and a Fedora GNOME
# user must not.
import subprocess  # noqa: E402
import tempfile  # noqa: E402

osrel = tempfile.NamedTemporaryFile("w", suffix=".os-release", delete=False)
osrel.write("ID=fedora\nID_LIKE=\"rhel\"\n")
osrel.close()
root_installer = os.path.join(HERE, "..", "..", "install.sh")


def plan(desktop):
    done = subprocess.run(["bash", root_installer, "--print-plan"],
                          capture_output=True, text=True,
                          env={**os.environ, "OS_RELEASE": osrel.name,
                               "XDG_CURRENT_DESKTOP": desktop,
                               "LANGSWITCHER_COMPONENT": ""})
    return done.stdout


check("dispatcher: Fedora KDE -> fedora-kde", "component=fedora-kde" in plan("KDE"), True)
check("dispatcher: the Plasma spelling too", "component=fedora-kde" in plan("Plasma"), True)
check("dispatcher: Fedora GNOME stays on linux", "component=linux" in plan("GNOME"), True)
os.unlink(osrel.name)

if fails:
    print("\nFAILURES:")
    for f in fails:
        print(" -", f)
    sys.exit(1)
print("\nALL-OK")
