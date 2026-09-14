#!/usr/bin/env python3
"""Automatic (Punto-style) conversion, driven by Hyprland's key events.

Wayland gives applications no way to watch the keyboard, but Hyprland itself has
one: ``hypr/langswitcher-auto.lua`` subscribes to ``input.keyboard.key``, buffers
the X11 keycodes of the word being typed and, on a boundary key, hands them to
``bin/langswitcher-auto``, which calls into this module. If that word was typed
in the wrong layout, it is rewritten in place and the layout is switched — what
people know from Punto Switcher.

Decisions are the core's: ``looks_like_wrong_layout_strict`` (a word is only
rewritten when it is implausible in its own script) and ``convert_selected``.
The decode from keycodes to characters is ``keycodes.py``.

Safety is most of this file, because it edits text nobody asked about:

* the caret is *proved* before anything is deleted — the previous word is
  selected and read back through the primary selection (falling back to Ctrl+C),
  so a run that arrives late, while the user is already in the next word, fails
  the proof and does nothing instead of eating characters;
* terminals are refused (Ctrl+Shift+Left/Ctrl+C mean other things there), a
  window that changed under the run is refused, an open Omarchy panel (which
  owns the keyboard) is refused, and a keycode we cannot decode aborts the run;
* the replacement is typed with wtype, whose output does not depend on the
  active layout (measured: the same Cyrillic arrives under us and ua), so no
  clipboard round-trip is needed — the two calls the edit does make are
  ``wtype -k BackSpace`` and ``wtype "<fixed> "``.

Verification can be turned off (``"verify": false``) for a lower-latency edit
that trusts the key buffer; that is the only mode where a fast typist can lose
characters, and it is off by default.

The heuristic cannot know that ``kbd`` or ``ssh`` is a word the user means to
keep, so the user's own verdict is remembered: ``dictionary.py`` holds the words
auto mode never touches, ``--undo`` puts the last fix back (and learns the word),
and a word retyped in the same window within ``REJECT_SECONDS`` of a fix is
learned as a rejection.

This file is intentionally duplicated in the omarchy-plugin and linux bundles;
keep both copies byte-identical.

No dependencies, stdlib only.
"""

# Deliberately small: this module is started once per finished word, so every
# import is latency the user can feel, and the gate below has to run before a
# fast typist has moved on to the next word. (concurrent.futures alone costs
# ~90ms of interpreter start-up — threads from the stdlib cost nothing.)
import json
import os
import subprocess
import sys
import threading
import time

import dictionary
import keycodes
import layoutswitch
from langswitcher import convert_selected, looks_like_wrong_layout_strict

SETTINGS_PATH = "~/.config/omarchy/langswitcher-auto.json"
STATE_PATH = "~/.local/state/langswitcher/last-auto.json"
# The last fix, kept apart from the diagnostics: a word retyped after it is a
# rejection, and --undo puts it back. Unlike the logs, this one holds the words.
FIX_PATH = "~/.local/state/langswitcher/last-fix.json"

# How long a fix can still be rejected by retyping, and how long it stays
# undoable. Both are short on purpose: a word typed again much later is a new
# word, not a verdict on an earlier fix.
REJECT_SECONDS = 60
UNDO_SECONDS = 120

# Windows where the gate keys mean something else: Ctrl+C interrupts in a
# terminal, and "copy the previous word" is a shell or vim binding there, not a
# text-editing gesture. Auto mode stays out of terminal emulators; GUI editors
# are fine (Ctrl+Shift+Left selects a word, Ctrl+C copies it, and both are
# undone by the single Right the gate sends when the proof fails).
TERMINALS = (
    "alacritty", "foot", "kitty", "ghostty", "wezterm", "xterm", "konsole",
    "terminal", "tilix", "terminator", "tilda", "urxvt", "rio", "yakuake",
)

DEFAULTS = {
    "enabled": True,
    "verify": True,
    # Switch the active layout to the target after a fix, so the next word is
    # already in the right language. On by default; the kill switch is here so
    # "the layout must not move on its own" stays a choice.
    "switch": True,
    "layouts": "en,uk,pl",
    "min_len": 3,
    "skip_classes": [],
    # Off by default: the log is metadata-only on purpose. Turning this on adds
    # the keycodes that arrived and the text they decoded to, which is what a
    # "nothing happened" report needs and is the user's call to make.
    "debug": False,
}


def _expand(path: str) -> str:
    return os.path.expanduser(path) if path.startswith("~") else path


def load_settings(path: str | None = None) -> dict:
    """Settings from ``~/.config/omarchy/langswitcher-auto.json`` over defaults.

    A missing or malformed file is not an error: the feature is opt-in by
    installing the Lua module, and its defaults are the safe ones.
    """
    settings = dict(DEFAULTS)
    target = _expand(path or SETTINGS_PATH)
    try:
        with open(target, encoding="utf-8") as handle:
            loaded = json.load(handle)
    except (OSError, ValueError):
        return settings
    if isinstance(loaded, dict):
        settings.update(loaded)
    return settings


def run_command(argv, timeout: float = 5, **kwargs):
    """Default runner: never raises, never blocks on stdin/stdout pipes.

    ``capture_output`` and ``text`` are dropped rather than forwarded: this
    runner always captures, and a caller that asks for the same thing
    (``layoutswitch`` does) would pass them twice, raise TypeError, and have its
    own ``except Exception`` report the switch as failed — which is how the
    layout silently stopped following an automatic fix.
    """
    kwargs.pop("capture_output", None)
    kwargs.pop("text", None)
    try:
        return subprocess.run(argv, capture_output=True, text=True,
                              stdin=subprocess.DEVNULL, timeout=timeout, **kwargs)
    except (OSError, subprocess.SubprocessError) as exc:  # missing binary, timeout
        return subprocess.CompletedProcess(argv, 127, "", str(exc))


def hyprctl_json(args: list[str], run=run_command) -> dict:
    done = run(["hyprctl", "-j", *args])
    try:
        return json.loads(done.stdout or "{}") or {}
    except ValueError:
        return {}


# Hyprland's own virtual keyboards (fcitx5's, wtype's). They come and go, and
# they carry a layout of their own: measured on the developer's machine,
# ``hl-virtual-keyboard-fcitx5`` sat on ``us`` while every physical keyboard was
# on ``ua`` — and it is the device Hyprland calls "main". Decoding a word with
# that layout reads Ukrainian typing as Latin, so the physical keyboard decides.
VIRTUAL_KEYBOARDS = ("hl-virtual-keyboard", "virtual-keyboard", "wtype")


def is_virtual(board: dict) -> bool:
    return str(board.get("name") or "").lower().startswith(VIRTUAL_KEYBOARDS)


def keyboard(devices: dict) -> dict | None:
    """The keyboard whose layout the app actually receives.

    Physical keyboards come first (``main`` among them wins) because a virtual
    one can be on a stale layout; if there is nothing but virtual keyboards, one
    of them is still better than refusing to work at all.
    """
    boards = [b for b in (devices.get("keyboards") or []) if b.get("layout")]
    if not boards:
        return None
    physical = [b for b in boards if not is_virtual(b)]
    pool = physical or boards
    main = [b for b in pool if b.get("main")]
    return (main or pool)[0]


def layout_codes(devices: dict) -> list[str]:
    board = keyboard(devices) or {}
    return [code.strip() for code in (board.get("layout") or "").split(",") if code.strip()]


def active_layout_id(devices: dict) -> str | None:
    """Turn the active index into one of our layout ids (us -> en, ua -> uk).

    None means "a layout we have no map for": calling it wrong would mean
    rewriting text with the wrong character set, so the caller skips instead.
    """
    board = keyboard(devices)
    codes = layout_codes(devices)
    if not board or not codes:
        return None
    index = board.get("active_layout_index") or 0
    if not 0 <= index < len(codes):
        return None
    code = codes[index]
    for layout, xkb in layoutswitch.LANG_TO_XKB.items():
        if xkb == code:
            return layout
    return None


def window_class(run=run_command) -> str:
    """Active window class, reduced to characters that are safe in a log."""
    win = hyprctl_json(["activewindow"], run=run)
    raw = str(win.get("class") or "")
    return "".join(c for c in raw if c.isalnum() or c in "._+-")


def panel_open(run=run_command) -> bool:
    """An Omarchy keyboard panel owns the keyboard; our keys went to it."""
    done = run(["hyprctl", "-j", "layers"])
    return "omarchy-keyboard-panel" in (done.stdout or "")


def plan(typed: str, layouts: list[str], min_len: int = 3) -> dict | None:
    """What to do with `typed`, or None to leave it alone.

    `typed` is what the app received, so it is its own source of truth: the
    strict check asks whether that string is implausible in the script it is
    written in while the other script's version is plausible.
    """
    if len(typed) < max(2, min_len):
        return None
    if not looks_like_wrong_layout_strict(typed, layouts, min_len=min_len):
        return None
    resolved = convert_selected(typed, layouts)
    if resolved is None:
        return None
    fixed, target = resolved
    if fixed == typed:
        return None
    return {"typed": typed, "fixed": fixed, "target": target}


def _digest(text: str) -> str:
    """Short, stable digest of a word, for a log that must not hold the word."""
    import hashlib  # only needed when something is logged, i.e. after the edit

    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def _in_parallel(*calls) -> list:
    """Run independent calls at once and return their results in order."""
    results: list = [None] * len(calls)

    def worker(index, call):
        try:
            results[index] = call()
        except Exception:  # a failed query is a missing fact, not a crash
            results[index] = None

    threads = [threading.Thread(target=worker, args=(index, call), daemon=True)
               for index, call in enumerate(calls)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=3)
    return results


def _clipboard(run, primary: bool = False) -> str:
    argv = ["wl-paste", "--no-newline"]
    if primary:
        argv.append("--primary")
    return (run(argv).stdout or "")


def _settle(read, *, sleep, attempts: int = 12, different_from: str | None = None) -> str:
    """Read a selection until it has something to say.

    Polling instead of a fixed sleep is what keeps auto mode usable: the whole
    run has to finish before a fast typist is already in the next word, so the
    wait after asking the application for its selection is "as long as the
    application takes" — tens of milliseconds — not a guessed constant. The
    attempt count (rather than a clock) keeps it deterministic under test.
    """
    value = ""
    for _ in range(max(1, attempts)):
        value = read()
        if different_from is not None:
            if value != different_from:
                return value
        elif value.strip():
            return value
        sleep(0.02)
    return value


def fix(fixed_plan: dict, *, verify: bool = True, run=run_command, sleep=time.sleep,
        switch=layoutswitch.switch_everywhere) -> dict:
    """Rewrite `fixed_plan["typed"]` as `fixed_plan["fixed"]` and switch layout.

    Returns the outcome plus the exact command sequence, which is what the tests
    assert on. Nothing here decides *whether* to act — that is `plan()`.
    """
    typed, fixed = fixed_plan["typed"], fixed_plan["fixed"]
    steps: list[list[str]] = []
    clobbered: str | None = None

    def wtype(*args):
        steps.append(["wtype", *args])
        return run(["wtype", *args])

    if verify:
        # Select the previous word and read it back: only a live selection can
        # be read, so this proves both that the caret is behind `typed` and that
        # the word is still there. Primary first (no clipboard side effect),
        # Ctrl+C as the fallback for apps that do not publish one.
        wtype("-M", "ctrl", "-M", "shift", "-k", "Left", "-m", "shift", "-m", "ctrl")
        proof = _settle(lambda: _clipboard(run, primary=True), sleep=sleep)
        if proof.strip() != typed:
            previous = _clipboard(run)
            wtype("-M", "ctrl", "-k", "c", "-m", "ctrl")
            copied = _settle(lambda: _clipboard(run), sleep=sleep, different_from=previous)
            if copied.strip() != typed:
                wtype("-k", "Right")  # collapse the selection back where it was
                return {"outcome": "gate-mismatch", "steps": steps}
            if copied != previous:
                clobbered = previous
        # Collapse the selection to its right edge == the caret as it was, so
        # the deletion below is an ordinary "backspace behind the caret".
        wtype("-k", "Right")

    # typed + the boundary character that triggered us (Lua only fires on one of
    # the keys this module treats as a boundary, so there is exactly one). The
    # seat delivers these in order, so no waiting is needed between them.
    for _ in range(len(typed) + 1):
        wtype("-k", "BackSpace")

    switched = bool(switch(fixed_plan["target"]))
    steps.append(["switch", fixed_plan["target"], str(switched)])

    wtype("--", fixed + " ")

    if verify:
        if clobbered is not None:
            run(["wl-copy", clobbered])
    return {"outcome": "fixed", "steps": steps, "switched": switched,
            "clipboard_restored": clobbered is not None}


def write_state(record: dict, path: str | None = None) -> None:
    target = _expand(path or STATE_PATH)
    try:
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, "w", encoding="utf-8") as handle:
            json.dump(record, handle)
            handle.write("\n")
    except OSError:
        pass


def read_fix_state(path: str | None = None) -> dict:
    """The last fix, or {} — what --undo and the rejection check work from."""
    try:
        with open(_expand(path or FIX_PATH), encoding="utf-8") as handle:
            loaded = json.load(handle)
    except (OSError, ValueError):
        return {}
    return loaded if isinstance(loaded, dict) else {}


def write_fix_state(record: dict, path: str | None = None) -> None:
    """Remember a fix: what was typed, what it became, and where."""
    target = _expand(path or FIX_PATH)
    try:
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, "w", encoding="utf-8") as handle:
            json.dump(record, handle, ensure_ascii=False)
            handle.write("\n")
    except OSError:
        pass


def clear_fix_state(path: str | None = None) -> None:
    try:
        os.remove(_expand(path or FIX_PATH))
    except OSError:
        pass


def is_rejection(record: dict, word: str, window: str, now: float) -> bool:
    """Has the user just typed `word` again, in the same window, after a fix?

    That is how a false positive is reported without any hotkey: the user deletes
    the rewrite and types the word they actually meant. Only the same window and
    a short stretch of time count, so an unrelated word later on is not mistaken
    for a verdict on an earlier fix.
    """
    if not record:
        return False
    if str(record.get("window") or "") != window:
        return False
    age = now - int(record.get("ts") or 0) / 1000
    if age < 0 or age > REJECT_SECONDS:
        return False
    typed_before = dictionary.core(str(record.get("typed") or "")).casefold()
    return bool(typed_before) and typed_before == dictionary.core(word).casefold()


def undo(*, verify: bool = True, run=run_command, sleep=time.sleep,
         switch=layoutswitch.switch_everywhere, fix_path: str | None = None,
         dictionary_path: str | None = None, now: float | None = None) -> dict:
    """Put the last fix back, restore the layout it came from, and learn the word.

    Explicitly reverting a rewrite is the strongest statement that the word was
    meant as typed, so the word goes into the dictionary in the same run — there
    is no separate "add to dictionary" gesture to remember.
    """
    now = time.time() if now is None else now
    record = read_fix_state(fix_path)
    typed = str(record.get("typed") or "")
    fixed = str(record.get("fixed") or "")
    if not typed or not fixed:
        return {"outcome": "undo-nothing"}

    current = window_class(run=run)
    if record.get("window") and current and current != record["window"]:
        return {"outcome": "undo-focus-moved", "window": current}
    age = now - int(record.get("ts") or 0) / 1000
    if age < 0 or age > UNDO_SECONDS:
        return {"outcome": "undo-expired"}

    steps: list[list[str]] = []

    def wtype(*args):
        steps.append(["wtype", *args])
        return run(["wtype", *args])

    if verify:
        # The same proof fix() makes: only a live selection can be read, so this
        # shows the rewrite is still the word behind the caret before it goes.
        wtype("-M", "ctrl", "-M", "shift", "-k", "Left", "-m", "shift", "-m", "ctrl")
        proof = _settle(lambda: _clipboard(run, primary=True), sleep=sleep)
        if proof.strip() != fixed:
            previous = _clipboard(run)
            wtype("-M", "ctrl", "-k", "c", "-m", "ctrl")
            copied = _settle(lambda: _clipboard(run), sleep=sleep, different_from=previous)
            if copied.strip() != fixed:
                wtype("-k", "Right")
                return {"outcome": "undo-gate-mismatch", "steps": steps}
            if copied != previous:
                run(["wl-copy", previous])
        wtype("-k", "Right")

    # Mirror of fix(): the rewrite plus the boundary character it typed.
    for _ in range(len(fixed) + 1):
        wtype("-k", "BackSpace")

    source = str(record.get("source") or "")
    switched = bool(switch(source)) if source else False
    steps.append(["switch", source, str(switched)])

    wtype("--", typed + " ")

    words = dictionary.ensure(dictionary_path)
    dictionary.trim(dictionary.add(words, typed, source="learned", now=int(now * 1000)))
    dictionary.save(words, path=dictionary_path)
    clear_fix_state(fix_path)
    return {"outcome": "undone", "steps": steps, "switched": switched,
            "typed_len": len(typed), "fixed_len": len(fixed)}


def handle(keycodes_arg: str, *, window: str = "", settings: dict | None = None,
           run=run_command, sleep=time.sleep, state_path: str | None = None,
           dictionary_path: str | None = None, fix_path: str | None = None,
           now: float | None = None) -> dict:
    """One auto run: decode, decide, edit. Returns a metadata-only record."""
    settings = settings or load_settings()
    now = time.time() if now is None else now
    debug = bool(settings.get("debug", False))
    record = {
        "ts": int(now * 1000),
        "settings": {"verify": bool(settings.get("verify", True)),
                     "switch": bool(settings.get("switch", True)),
                     "min_len": settings.get("min_len", 3),
                     "debug": debug},
    }

    def finish(outcome: str, **extra) -> dict:
        record.update({"outcome": outcome, **extra})
        write_state(record, path=state_path)
        return record

    if not settings.get("enabled", True):
        return finish("disabled")

    # Three separate IPC round trips; asking them at once keeps the run (and so
    # the gap in which a fast typist can move the caret) as short as possible.
    devices, current, panel = _in_parallel(
        lambda: hyprctl_json(["devices"], run=run),
        lambda: window_class(run=run),
        lambda: panel_open(run=run),
    )
    devices = devices or {}
    current = current or ""
    record["window"] = current

    skip = [str(c).lower() for c in (settings.get("skip_classes") or [])]
    for terminal in TERMINALS + tuple(skip):
        if terminal and terminal in current.lower():
            return finish("skipped-terminal")

    if window and current and current != window:
        return finish("skipped-focus-moved")

    if panel:
        return finish("skipped-panel")

    layout = active_layout_id(devices)
    if layout is None:
        return finish("skipped-layout", layouts=layout_codes(devices))

    typed, unknown = keycodes.decode(keycodes_arg, layout)
    record["keys"] = len(keycodes.parse_tokens(keycodes_arg))
    if debug:
        record["raw_keys"] = str(keycodes_arg)
        record["typed"] = typed
        record["layout"] = layout
    if unknown:
        return finish("skipped-undecodable", unknown=unknown)
    if not typed:
        return finish("skipped-empty")

    # The user's own verdicts come before the heuristic: a word they rejected
    # (dictionary) is never touched, and a word typed again after a fix is a
    # rejection that is learned right now.
    words = dictionary.ensure(dictionary_path)
    if dictionary.covers(words, typed):
        return finish("dictionary", typed_digest=_digest(typed), typed_len=len(typed))

    previous = read_fix_state(fix_path)
    if is_rejection(previous, typed, current, now):
        dictionary.trim(dictionary.add(words, str(previous.get("typed") or typed),
                                       source="learned", now=int(now * 1000)))
        dictionary.save(words, path=dictionary_path)
        clear_fix_state(fix_path)
        return finish("learned", typed_digest=_digest(typed), typed_len=len(typed),
                      target=previous.get("target"))

    chosen = plan(typed, [l.strip() for l in str(settings.get("layouts")).split(",") if l.strip()],
                  int(settings.get("min_len", 3)))
    if chosen is None:
        return finish("kept", typed_digest=_digest(typed), typed_len=len(typed))

    def switch(lang: str) -> bool:
        if not settings.get("switch", True):
            return False
        return layoutswitch.switch_everywhere(lang, devices=devices, runner=run)

    result = fix(chosen, verify=bool(settings.get("verify", True)), run=run, sleep=sleep,
                 switch=switch)
    if result["outcome"] == "fixed":
        # What --undo needs, and what the rejection check compares against.
        write_fix_state({"ts": int(now * 1000), "window": current, "typed": typed,
                         "fixed": chosen["fixed"], "source": layout,
                         "target": chosen["target"],
                         "switched": result.get("switched")}, path=fix_path)
    return finish(result["outcome"], typed_digest=_digest(typed), typed_len=len(typed),
                  fixed_len=len(chosen["fixed"]), target=chosen["target"],
                  switched=result.get("switched"))


def self_test(layout: str | None) -> dict:
    """The decoder's own check, for ``--check``.

    Decoding the sample with the layout in force would read "привіт" on a
    Ukrainian keyboard and report a healthy plugin as broken — which is exactly
    what happened while the check assumed "en". So the decoder is checked with a
    fixed layout, and what the layout in force makes of the same keys is
    reported next to it.
    """
    sample = "42,43,56,40,39,57"  # g h b d s n
    typed, unknown = keycodes.decode(sample, "en")
    in_force, _ = keycodes.decode(sample, layout or "en")
    return {"ok": layout is not None and not unknown and typed == "ghbdsn",
            "selftest": {"keycodes": sample, "decoded": typed, "unknown": unknown,
                         "decoded_in_force": in_force}}


def main(argv: list[str]) -> int:
    args = list(argv)
    check = "--check" in args
    decode_only = "--decode" in args
    undo_only = "--undo" in args
    window = ""
    if "--window" in args:
        index = args.index("--window")
        window = args[index + 1] if index + 1 < len(args) else ""
        del args[index:index + 2]
    if check or decode_only or undo_only:
        for flag in ("--check", "--decode", "--undo"):
            if flag in args:
                args.remove(flag)
    keys = args[0] if args else ""

    if undo_only:
        result = undo()
        # The words stay out of the output on purpose: stdout ends up in logs.
        print(json.dumps({k: v for k, v in result.items() if k != "steps"},
                         ensure_ascii=False))
        return 0 if result["outcome"] == "undone" else 3

    if check:
        settings = load_settings()
        devices = hyprctl_json(["devices"])
        layout = active_layout_id(devices)
        result = self_test(layout)
        words = dictionary.read()
        payload = {
            "ok": result["ok"],
            "settings": settings,
            "layouts": layout_codes(devices),
            "active_layout": layout,
            "dictionary": {"path": dictionary.DEFAULT_PATH,
                           "exists": words is not None,
                           "words": len(dictionary.keys(words)) if words else 0},
            "selftest": result["selftest"],
            "deps": {tool: bool(subprocess.run(["sh", "-c", "command -v " + tool],
                                               capture_output=True).returncode == 0)
                     for tool in ("wtype", "wl-paste", "wl-copy", "hyprctl", "python3")},
        }
        print(json.dumps(payload, ensure_ascii=False))
        return 0 if payload["ok"] else 1

    if decode_only:
        settings = load_settings()
        layout = active_layout_id(hyprctl_json(["devices"]))
        typed, unknown = keycodes.decode(keys, layout or "en")
        chosen = plan(typed, [l.strip() for l in str(settings.get("layouts")).split(",") if l.strip()],
                      int(settings.get("min_len", 3))) if typed else None
        words = dictionary.read()
        listed = bool(typed) and bool(words) and dictionary.covers(words, typed)
        print(json.dumps({"layout": layout, "typed": typed, "unknown": unknown,
                          "dictionary": listed, "plan": chosen}, ensure_ascii=False))
        return 0

    if not keys:
        print("usage: langswitcher-auto <keycodes> [--window CLASS] | --check "
              "| --decode <keycodes> | --undo", file=sys.stderr)
        return 2
    record = handle(keys, window=window)
    return 0 if record["outcome"] in ("fixed", "kept", "dictionary", "learned") else 3


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
