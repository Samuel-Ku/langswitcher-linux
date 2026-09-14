#!/usr/bin/env python3
"""Tests for the Hyprland Lua module of the plugin (auto mode's keyboard buffer).

Run: python3 tests/test_lua_module.py   (skips when the plugin bundle is absent)

The module is the one part that only exists inside Hyprland, so it is exercised
here with a stubbed `hl`: the file is loaded for real, its handler is called with
the same arguments Hyprland passes (X11 keycode, timestamp, pressed), and the
command it would spawn is the observable. What matters is what it *ignores*:
synthetic keys (timestamp 0 — wtype, the worker's own output, fcitx5's virtual
keyboard), modifier chords such as the Right-Alt layout switch, and words that
are too short to judge.
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
MODULE = os.path.join(HERE, "..", "..", "omarchy-plugin", "hypr", "langswitcher-auto.lua")
WORKER = "/home/test/.config/omarchy/plugins/stealth.langswitcher/bin/langswitcher-auto"

fails = []


def check(name, got, want):
    if got != want:
        fails.append(f"{name}: got {got!r}, want {want!r}")
    else:
        print(f"ok: {name}")


PREAMBLE = r"""
local calls, subs = {}, {}
local last_ts = nil
function key(code, ts, pressed)
  last_ts = ts
  subs["input.keyboard.key"].fn(code, ts, pressed)
end
function key_repeat(code)   -- the same event a second time, exactly as delivered
  key(code, last_ts, 1)
end
function focus(class)
  focus_class = class
  subs["window.active"].fn()
end
local function make_sub(name, fn)
  local sub = { fn = fn }
  sub.remove = function(self)
    self.removed = true
    print("REMOVED " .. name)
  end
  subs[name] = sub
  return sub
end
focus_class = "gtk"
hl = {
  on = function(name, fn) return make_sub(name, fn) end,
  exec_cmd = function(cmd) calls[#calls + 1] = cmd end,
  get_active_window = function() return { class = focus_class } end,
  dispatch = function() end,
  dsp = {},
}
dofile(os.getenv("LS_MODULE"))
if os.getenv("LS_LOAD_TWICE") then dofile(os.getenv("LS_MODULE")) end
"""


def lua_run(events):
    """Feed `events` to the module's handler; return the commands it spawned."""
    script = [PREAMBLE]
    for event in events:
        if isinstance(event, str):          # a helper call, e.g. 'focus("gtk")'
            script.append(event)
            continue
        kind, code = event[0], event[1]
        if kind == "press":
            script.append(f"key({code}, {1000 + len(script)}, 1)")
        elif kind == "release":
            script.append(f"key({code}, {1000 + len(script)}, 0)")
        elif kind == "synthetic":           # timestamp 0: not a real keyboard
            script.append(f"key({code}, 0, 1)")
        elif kind == "repeat":              # the same event delivered again
            script.append(f"key_repeat({code})")
        elif kind == "raw":                  # ("raw", code, ts, pressed)
            script.append(f"key({event[1]}, {event[2]}, {event[3]})")
    script.append('for i = 1, #calls do print("CMD " .. calls[i]) end')
    script.append('print("COUNT " .. #calls)')
    env = dict(os.environ, LS_MODULE=MODULE, HOME="/home/test")
    done = subprocess.run(["lua", "-"], input="\n".join(script), capture_output=True,
                          text=True, env=env, timeout=30)
    if done.returncode != 0:
        fails.append(f"lua failed: {done.stderr.strip()}")
    return [line[4:] for line in done.stdout.splitlines()
            if line.startswith("CMD ")], done.stdout


GHBDSN = [("press", c) for c in (42, 43, 56, 40, 39, 57)]   # g h b d s n
SPACE = 65
SHIFT, MOD5, SUPER, BACKSPACE, ESCAPE, LEFT = 50, 108, 133, 22, 9, 113


def press(code):
    return ("press", code)


# A word finished with a space is handed to the worker, in X11 keycode order.
commands, _ = lua_run(GHBDSN + [press(SPACE)])
check("fires on space", commands, [f"{WORKER} 42,43,56,40,39,57 --window gtk"])

# Shift is tracked per key: capital letters decode upper case.
commands, _ = lua_run([press(SHIFT), press(42), ("release", SHIFT)] + GHBDSN[1:]
                      + [press(SPACE)])
check("shift marks its own key", commands,
      [f"{WORKER} s42,43,56,40,39,57 --window gtk"])

# Releases are not characters, and the buffer is emptied once it has fired.
commands, _ = lua_run(GHBDSN + [press(SPACE)] + [("release", SPACE), press(SPACE)])
check("fires once per word", len(commands), 1)

# Words too short to judge are not reported at all.
commands, _ = lua_run([press(42), press(43), press(SPACE)])
check("too short: silent", commands, [])

# This machine delivers every key twice (Hyprland's event plus fcitx5's virtual
# keyboard forwarding it), with identical keycode and timestamp. Buffering both
# doubled the word and made every run refuse to act, so the repeat is dropped.
doubled = []
for code in (42, 43, 56, 40, 39, 57):
    doubled += [("press", code), ("repeat", code)]
commands, _ = lua_run(doubled + [press(SPACE)])
check("doubled delivery does not double the word", commands,
      [f"{WORKER} 42,43,56,40,39,57 --window gtk"])

# A real repeat is a different event (new timestamp) and must still be a key.
commands, _ = lua_run([press(42)] * 4 + [press(43)] + [press(SPACE)])
check("real repeats are kept", commands, [f"{WORKER} 42,42,42,42,43 --window gtk"])

# The capture that exposed the doubling bug, replayed verbatim: the physical
# keyboard delivered every key twice with an identical timestamp.
MEASURED = [(42, 224871486, 1), (42, 224871486, 1), (42, 224871611, 0), (42, 224871611, 0),
            (43, 224871672, 1), (43, 224871672, 1), (43, 224871760, 0), (43, 224871760, 0),
            (56, 224871840, 1), (56, 224871840, 1), (56, 224871955, 0), (56, 224871955, 0),
            (40, 224872023, 1), (40, 224872023, 1), (40, 224872225, 0), (40, 224872225, 0),
            (39, 224872234, 1), (39, 224872234, 1), (39, 224872379, 0), (39, 224872379, 0),
            (57, 224872403, 1), (57, 224872403, 1), (57, 224872552, 0), (57, 224872552, 0),
            (65, 224872775, 1), (65, 224872775, 1)]
commands, _ = lua_run([("raw",) + event for event in MEASURED])
check("measured capture fires once, with six keys", commands,
      [f"{WORKER} 42,43,56,40,39,57 --window gtk"])

# Keys forwarded by fcitx5's virtual keyboard carry a real keycode with
# timestamp 0 (measured), so the timestamp must not decide whether a key counts.
commands, _ = lua_run([("synthetic", c) for c in (42, 43, 56, 40, 39, 57)] + [press(SPACE)])
check("timestamp 0 does not hide real keycodes", commands,
      [f"{WORKER} 42,43,56,40,39,57 --window gtk"])

# A keycode that produces no text (a synthetic key's own numbering, a media key,
# the keypad) ends the word instead of silently leaving a gap in it.
#   "ghb" is typed, then two keycodes that produce no text (a stray Escape and a
#   synthetic numbering), then "bdsn" — only the second run is a word.
commands, _ = lua_run(GHBDSN[:3] + [press(9), press(200)] + GHBDSN[3:]
                      + [press(SPACE)])
check("keycodes outside the text block end the word", commands,
      [f"{WORKER} 40,39,57 --window gtk"])

# Every keycode the decoder knows about must be buffered here too; the two
# tables drifting apart would silently truncate words. The set comes from the
# Python decoder, so this is the drift guard.
_here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_here, "..", "lib"))
import keycodes  # noqa: E402

missing = []
for code in list(keycodes.KEYCODE_ORDER) + [94]:
    commands, _ = lua_run([press(code)] * 3 + [press(SPACE)])
    want = f"{WORKER} " + ",".join([str(code)] * 3) + " --window gtk"
    if commands != [want]:
        missing.append(code)
check("every decodable keycode is buffered", missing, [])

# The Right-Alt layout switch must not be read as "a word was just finished".
commands, _ = lua_run(GHBDSN + [press(MOD5), press(SPACE)])
check("modifier chord ignored", commands, [])
commands, _ = lua_run(GHBDSN + [press(SHIFT), press(SPACE)])
check("shift+space ignored", commands, [])
commands, _ = lua_run(GHBDSN + [press(SUPER), press(SPACE)])
check("super+space ignored", commands, [])

# Anything that moves the caret or takes another meaning ends the word.
commands, _ = lua_run(GHBDSN + [press(BACKSPACE), press(SPACE)])
check("backspace clears", commands, [])
commands, _ = lua_run(GHBDSN + [press(ESCAPE), press(SPACE)])
check("escape clears", commands, [])
commands, _ = lua_run(GHBDSN + [press(LEFT), press(SPACE)])
check("arrow clears", commands, [])

# Focus moving means the caret did too.
commands, _ = lua_run(GHBDSN + ['focus("other")', press(SPACE)])
check("focus change clears", commands, [])

# A class with characters a shell would choke on is reduced before it is passed.
commands, _ = lua_run(['focus("weird; rm -rf /")'] + GHBDSN + [press(SPACE)])
check("class sanitized", commands, [f"{WORKER} 42,43,56,40,39,57 --window weirdrm-rf"])

# Reloading the config must not leave the previous handler alive, or every word
# would be processed twice.
script = PREAMBLE + '\nfor i = 1, #calls do print("CMD " .. calls[i]) end'
done = subprocess.run(["lua", "-"], input=script, capture_output=True, text=True,
                      env=dict(os.environ, LS_MODULE=MODULE, HOME="/home/test",
                               LS_LOAD_TWICE="1"), timeout=30)
check("reload run succeeded", done.returncode, 0)
check("reload removes the old handler",
      done.stdout.count("REMOVED input.keyboard.key"), 1)
check("reload removes the old focus handler",
      done.stdout.count("REMOVED window.active"), 1)

if fails:
    print("\nFAILURES:")
    for f in fails:
        print(" -", f)
    sys.exit(1)
print("\nALL-OK")
