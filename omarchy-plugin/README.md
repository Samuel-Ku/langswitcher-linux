# LangSwitcher for Omarchy

Omarchy shell plugin that fixes text typed in the wrong keyboard layout: select
it, press a hotkey, and it is replaced with the same text in the other layout
(`ghbdsn` → `привіт`).

The conversion core is Python — physical key positions, auto-detected direction,
Greedy Line, punctuation preservation, Polish ⌥-layer recovery — wrapped as an
Omarchy shell plugin (`service` + `bar-widget`).

## Install

`omarchy plugin add <git-url>` clones the repository and validates
`manifest.json` at its **root**; here the plugin lives in `omarchy-plugin/`, so
that command cannot install it. Use the bundled installer instead:

```sh
git clone https://github.com/Samuel-Ku/langswitcher-linux ~/src/langswitcher-linux
~/src/langswitcher-linux/omarchy-plugin/install-plugin.sh
```

Or, from an existing checkout:

```sh
./omarchy-plugin/install-plugin.sh
```

Or run the repository's universal installer, which detects Omarchy and calls the
same script:

```sh
curl -fsSL https://raw.githubusercontent.com/Samuel-Ku/langswitcher-linux/main/install.sh | bash
```

Any of these puts the plugin in `~/.config/omarchy/plugins/stealth.langswitcher`,
enables it, and appends the hotkeys to `~/.config/hypr/bindings.lua` (same two
lines as `bindings.snippet.lua`):

```lua
o.bind("SUPER + GRAVE", "LangSwitcher: конвертувати виділення", "$HOME/.config/omarchy/plugins/stealth.langswitcher/bin/langswitcher-convert selection")
o.bind("SUPER + SHIFT + GRAVE", "LangSwitcher: конвертувати рядок (greedy)", "$HOME/.config/omarchy/plugins/stealth.langswitcher/bin/langswitcher-convert greedy")
```

```sh
hyprctl reload
```

## Automatic mode (Punto-style)

Off by default. Type a word in the wrong layout and press space, and it is
rewritten in place and the layout is switched, without selecting anything:
`ghbdsn ` → `привіт `.

```sh
./omarchy-plugin/install-plugin.sh --auto
```

The flag copies `hypr/langswitcher-auto.lua` to `~/.config/hypr/` and adds one
line to `~/.config/hypr/hyprland.lua`:

```lua
require("hypr.langswitcher-auto")
```

Without the flag the module is installed but not enabled — this mode rewrites
text while you type, so it asks first. Turn it off at any time with
`~/.config/omarchy/langswitcher-auto.json`:

```json
{ "enabled": false }
```

The settings file also takes `verify` (see below), `switch` (move the active
layout after a fix, default `true`), `min_len` (shortest word worth judging,
default 3), `layouts`, `skip_classes` (extra window classes to stay out of) and
`debug` — which adds the raw keycodes that arrived, the text they decoded to and
the layout in force to `last-auto.json`. That is what a "nothing happened"
report needs; it is off by default because the log is otherwise metadata-only.

The words automatic mode must never touch live in a file of their own, not here:
`~/.config/omarchy/langswitcher-dictionary.json` — see **Dictionary and undo**.

How it works, and what keeps it safe:

- Wayland forbids applications from watching the keyboard, but Hyprland itself
  has every key: the Lua module buffers the X11 keycodes of the word being typed
  and hands them to `bin/langswitcher-auto` when space ends it. The keycodes are
  turned into characters with the layout that was active (`lib/keycodes.py`,
  checked against the keymaps the compositor compiles), so the plugin sees what
  the app actually received.
- That layout is read from a **physical** keyboard, not from whatever Hyprland
  calls "main": fcitx5's virtual keyboard *is* "main" on a machine that runs
  fcitx5, and it was measured sitting on `us` while every physical keyboard was
  on `ua`. Decoding with it read Ukrainian typing as Latin, which made the plugin
  try to "fix" text that was already correct (`lib/autofix.py`, `keyboard()`).
- Two measured properties of that event stream shape the module: every key
  arrives twice (the same keycode and timestamp — Hyprland's input event plus
  fcitx5's virtual keyboard forwarding it), so identical neighbouring events are
  dropped; and a key forwarded by a virtual keyboard can carry timestamp 0 while
  still carrying the real keycode, so *keycode*, not timestamp, decides whether
  something counts as typing. Wtype (and any other virtual keyboard) uploads its
  own keymap and numbers keysyms from 9 upwards, so its keycodes fall outside the
  text block and end the buffered word instead of pretending to extend it.
- The decision is the same conservative one the hotkey path uses:
  `looks_like_wrong_layout_strict`. A word is only touched when it is implausible
  in its own script and plausible in the other one, so `hello` and `привіт` are
  never rewritten; `ghbdsn` (no Latin vowel, Cyrillic vowels after conversion) is.
- Before anything is deleted it *proves* the caret is still behind that word:
  it selects the previous word and reads it back (primary selection, Ctrl+C as
  the fallback). If you have already moved on and typed the next word, the proof
  fails, the selection is collapsed back where it was and nothing happens.
- The replacement is typed with wtype, whose output does not depend on the
  active layout (measured: the same Cyrillic arrives under `us` and `ua`), so the
  clipboard is not used at all — unless the proof needed Ctrl+C, in which case
  the previous clipboard is put back.
- It stays out of terminals (there Ctrl+C interrupts and Ctrl+Shift+Left is the
  shell's select-word), out of a window that changed under it, out of a run that
  starts while an Omarchy panel owns the keyboard, and out of any keycode it
  cannot decode. Everything it refuses is logged rather than guessed.
- Conservative by construction: `руддщ` (English typed with the Ukrainian layout)
  already contains a Ukrainian vowel, so the strict check leaves it alone — the
  hotkey is still the tool for the other direction.
- The heuristic cannot know that `kbd` or `ssh` is a word, so the user's own
  verdict is recorded and consulted *before* the heuristic: a rejected word is
  never touched again. See **Dictionary and undo**.
- `"verify": false` in the config skips the proof for a lower-latency edit. That
  is the only mode where typing fast can lose characters; it is off by default.
- `"switch": false` leaves the layout alone: the text is still fixed, the layout
  is not moved.

Diagnostics for this mode:

```sh
bin/langswitcher-auto --check                # deps, settings, dictionary, decoded sample (JSON)
bin/langswitcher-auto --decode 42,43,56,40,39,57   # decode + decision + dictionary hit, no edits
bin/langswitcher-auto --undo                 # undo the last fix and learn the word
tail -1 ~/.local/state/langswitcher/last-auto.json
```

Dependencies (checked automatically by the service, shown in the panel):

```sh
sudo pacman -S --needed wl-clipboard wtype python3 libnotify
```

## Dictionary and undo

The heuristic decides from plausibility alone, so it cannot know that `kbd`,
`ssh` or `npm` is a word the user means to keep. The user's own verdict is kept
in a file the user owns — `~/.config/omarchy/langswitcher-dictionary.json`:

```json
{
 "version": 1,
 "entries": [
  {"word": "cfg", "source": "seed", "ts": 0},
  {"word": "ghbdsn", "source": "learned", "ts": 1789386298463},
  {"word": "Zażółć", "source": "manual", "ts": 1789386298463}
 ]
}
```

- The file is created on the first automatic run, seeded with a short list of
  Latin abbreviations that have no Latin vowel (`ssh`, `ftp`, `npm`, `kbd`,
  `tmp`, `cfg`, `src`, `txt`, `dbg`, `ctrl`, `psql`, `html`, `http`,
  `https`, …) — exactly the words the strict check would otherwise rewrite.
  Every entry is visible and can be deleted; nothing stays hidden in code.
- Matching is exact but case- and punctuation-insensitive: `Kbd.` is `kbd`.
- `source` is `seed`, `learned` or `manual`. The list is capped at 1000 entries:
  the oldest `learned` words go first, then `seed`; `manual` entries are never
  dropped.
- A bare string works as an entry too, if you want the file short:
  `{"entries": ["kbd", "ssh"]}`.
- **Automatic mode only.** `SUPER+\`` and the panel buttons are explicit actions
  and convert anything, dictionary or not.
- Logs stay metadata-only, but this file (and `last-fix.json`) necessarily hold
  the words themselves.

A word gets in three ways:

1. **Retyping it** — the normal way. After a fix, deleting the rewrite and typing
   the word you actually meant (same window, within a minute) is a rejection: the
   word is learned and never converted again.
2. **`SUPER+BACKSPACE`** — undo the last fix. The typed word comes back, the
   layout returns to the one it was typed in, and the word is learned. It only
   works for the last fix, while the focus has not moved and for two minutes, and
   the text is proved first (the previous word is selected and read back), so a
   late press changes nothing.
3. **Editing the file**, by hand.

The bind for the undo (add it to `~/.config/hypr/bindings.lua`, or re-run the
installer, which now adds it):

```lua
o.bind("SUPER + BACKSPACE", "LangSwitcher: скасувати останнє авто-виправлення", "$HOME/.config/omarchy/plugins/stealth.langswitcher/bin/langswitcher-auto --undo")
```

## Usage

1. Type text with the wrong layout active (`ghbdsn` instead of `привіт`).
2. Select it (or leave the cursor at the end of the line for greedy mode).
3. Press `SUPER+\`` — the text is replaced with the converted version.
4. Or: left-click the ⌨ widget — it converts the selection straight away,
   without opening anything. Right-click it for the panel with the line and
   last-word actions, dependency status and hotkeys; a panel button closes the
   popup first — an open Omarchy panel owns the keyboard, so the paste would
   otherwise land in the shell instead of the app.

### Click actions

Which button does what is a per-widget setting, with these defaults: left click
converts the selection, middle click converts the selection, right click opens
the panel.

```sh
omarchy bar set stealth.langswitcher leftClick line     # left click converts the whole line
omarchy bar set stealth.langswitcher middleClick word   # middle click the last word
omarchy bar set stealth.langswitcher rightClick panel
```

or add the keys to the widget's entry in `~/.config/omarchy/shell.json`:

```json
{ "id": "stealth.langswitcher", "leftClick": "line", "rightClick": "panel" }
```

The panel edits the same setting: its **CLICK ACTIONS** section has one dropdown
per button, so the mapping can be changed without remembering the command line —
both write paths go through the widget, and the tooltip follows. The panel itself
is mouse-driven (Esc closes it; there is no cursor model to walk with the
keyboard).

Accepted values are `selection`, `line`, `word` and `panel` (the worker's own
`greedy` and `last-word` names are accepted as aliases, and an unknown value
falls back to that button's default instead of doing nothing). Give all three to
conversions and the panel is still reachable with
`omarchy-shell stealth.langswitcher toggle`.

The tooltip always shows the mapping that is in force, and it can be checked
without clicking:

```sh
omarchy-shell stealth.langswitcher clickActions
```

Default layouts: `en,uk,pl` (change via `--layouts` in the binds).

The bar glyph carries the plugin's state: accent when it can convert, amber when
the last run found nothing to convert, urgent when a dependency is missing or the
check failed. Hover it for the layouts, the hotkeys and the last run.

```sh
# IPC (same worker the hotkeys use)
omarchy-shell stealth.langswitcher statusJson
omarchy-shell stealth.langswitcher convertSelection
omarchy-shell shell summon stealth.langswitcher '{}'
```

## Standalone CLI (no shell needed)

```sh
echo -n 'ghbdsn' | python3 lib/switch.py --layouts en,uk,pl   # привіт
echo -n 'привіт' | python3 lib/switch.py --layouts en,uk,pl   # ghbdsn
python3 ../linux/tests/test_convert.py                        # self-tests
```

## Layouts

- The core ships exactly the three layouts this project needs: `en`, `uk`, `pl`
  (`en`/`us` and `uk`/`ua` are aliases). Russian and the other originals are
  intentionally absent.
- Polish (programmer's) is physically identical to US QWERTY, so there is no
  `en↔pl` wrong-layout case — and text with Polish diacritics
  (`ą ć ę ł ń ó ś ź ż`) is **never touched**, in every mode.
- Real conversion happens on the `en↔uk` pair with auto-detection.
- **Layout Switch mode:** after a conversion the plugin switches the active
  Hyprland layout to the target via `hyprctl switchxkblayout`, so the next word
  is already in the right language. Automatic mode switches *every* keyboard
  (`switchxkblayout all <index>`, the same call as the Right-Alt binding): the
  device the compositor calls "main" is whichever keyboard it listed first and
  changes as virtual keyboards (fcitx5, wtype) come and go, and keyboards switch
  independently. What the layout *is* before the conversion is read from a
  physical keyboard, for the reason above. `"switch": false` turns the switch
  off and leaves the text fix in place.
- **Polish ⌥-layer recovery:** typing Polish while a Cyrillic layout is active
  emits that layout's ⌥ symbols (`ą`=⌥+A→`ƒ`, `ś`=⌥+S→`ы`, `ć`=⌥+C→`≠`). The
  converter maps them back by physical key: `ьƒлф` → `mąka`, `сяуы≠` → `cześć`.
  When such artifacts are present, `pl` is picked as target.

## Files

- `manifest.json` — plugin contract (`service`, `bar-widget`)
- `Service.qml` — dependency check + `convert()` + `statusObject()` (clipboard text never enters QML)
- `BarWidget.qml` — ⌨ glyph, status colour, configurable click actions, IPC
- `Panel.qml` — convert buttons, click-mapping dropdowns, status, layouts, hotkey hints
- `bin/langswitcher-convert` — Wayland worker (wl-paste → `lib/switch.py` → wl-copy → wtype)
- `bin/langswitcher-auto` — automatic mode's entry point (what the Lua module calls)
- `hypr/langswitcher-auto.lua` — Hyprland key buffer; enable with `require("hypr.langswitcher-auto")`
- `lib/keycodes.py` — X11 keycode → character, per layout
- `lib/langswitcher.py` — conversion core + the strict auto-mode heuristic
- `lib/layoutswitch.py` — `hyprctl switchxkblayout`, after a conversion
- `lib/dictionary.py` — the user's dictionary: a hand-editable word list, cap and eviction
- `lib/autofix.py` — automatic mode: decode, decide, prove, rewrite, switch, learn, undo
- `lib/` — Python core + CLI (stdlib only, kept byte-identical with `../linux/lib`)
- run log: `~/.local/state/langswitcher/last-run.json` (metadata only, overwritten each run)
- `~/.local/state/langswitcher/last-auto.json` — the same for automatic mode
- `~/.local/state/langswitcher/last-fix.json` — the last fix, so it can be rejected or undone (holds words)
- `~/.config/omarchy/langswitcher-auto.json` — automatic mode's settings (optional)
- `~/.config/omarchy/langswitcher-dictionary.json` — the words automatic mode must never touch
- `bindings.snippet.lua` — hotkeys for `bindings.lua`
- `install-plugin.sh` — copy the plugin in, enable it, ensure the binds (`--auto` enables
  automatic mode)
- shared tests live in `../linux/tests/`

## Limits

- Automatic mode (above) is the on-the-fly path; it is opt-in and needs the
  `require` in `hyprland.lua`. Without it, conversion is hotkey-driven (or an
  explicit click in the panel).
- An open shell panel (this plugin's popup, the emoji picker, the calendar, …)
  owns the keyboard: the worker dismisses it and waits for the surface to go
  away before converting, so the paste reaches the app. If a panel refuses to
  close, the worker says so instead of reporting a conversion that pasted
  nowhere.
- Double-Shift cannot be bound under Wayland — `SUPER+\`` replaces it.
- In XWayland windows, selecting with the mouse (primary selection) is the most
  reliable.
- A replacement only works if the app *still* has a live selection when Ctrl+V
  arrives. Chromium, for one, keeps serving the range it already replaced through
  the primary selection (measured: the value became `привіт` while primary still
  reported `ghbdsn`), so trusting a non-empty primary used to paste the converted
  text *next to* the original instead of replacing it. The worker now proves the
  selection first: Ctrl+C has to copy something. If the clipboard did not change,
  the selection is accepted only when the app's primary selection equals what the
  clipboard already holds — the same text converted twice, where the copy is a
  no-op — and otherwise nothing is converted and a notification says so.
- Keys go to the focused window, so the worker never pastes into a different
  window than the one it read from: if the focus moved during the run, it stops
  and says so.
- Terminals keep the old primary-based behaviour for the selection mode (Ctrl+C
  there is SIGINT, not copy) and cannot replace a mouse highlight on paste — a
  terminal buffer is not editable from the outside. Use the greedy/last-word
  modes there.

## Diagnostics

Every run writes one metadata-only JSON line (no clipboard text) to
`~/.local/state/langswitcher/last-run.json`:

| field | meaning |
|---|---|
| `mode`, `layouts` | what was asked for |
| `panel_at_start`, `panel_close_ms` | a shell panel held the keyboard and how long it took to dismiss |
| `source` | `primary`, `copy-fallback`, `line`, `word` |
| `copy_changed` | `true` = Ctrl+C refreshed the clipboard, `false` = nothing was selected, `already` = the clipboard already held the selection, `skipped` = terminal |
| `verify` | `live`, `no-live-selection`, `terminal` |
| `in_len`, `out_len`, `same` | sizes, so a wrong conversion is visible without the text |
| `window`, `window_at_paste` | focused window class at start and before Ctrl+V |
| `exit`, `ms` | exit code and duration |

`exit` is `0` when the text was replaced, `2` when nothing was converted (no
text, no live selection, a panel that refused to close, or text that does not
look like a wrong layout) and `1` for a usage or dependency error.

Automatic mode writes its own single-line record to `last-auto.json`, also
without any text: `outcome` (`fixed`, `kept`, `dictionary`, `learned`,
`gate-mismatch`, `disabled`, `skipped-terminal`, `skipped-focus-moved`,
`skipped-panel`, `skipped-layout`, `skipped-undecodable`, `skipped-empty`), the
settings in force (`verify`, `switch`, `min_len`, `debug`), the focused window
class, how many keys were buffered, how long the word was, a truncated SHA-256 of
the decoded word (so a run can be compared without storing it), the target layout
and whether the switch call succeeded (`switched`).

`--undo` prints its own one-line JSON (`undone`, `undo-nothing`,
`undo-gate-mismatch`, `undo-focus-moved` or `undo-expired`) and keeps the words
out of it. The words a fix touched are in `last-fix.json` — state, not a log: it
is consumed by learning and by `--undo`, and it is the one file besides the
dictionary that holds text.

## Remove

```sh
omarchy plugin remove stealth.langswitcher
```

Also delete the three `o.bind` lines from `~/.config/hypr/bindings.lua`, and for
automatic mode the `require("hypr.langswitcher-auto")` line from
`~/.config/hypr/hyprland.lua` plus `~/.config/hypr/langswitcher-auto.lua`. The
dictionary is yours and is not removed by the command; keep it if you reinstall:
`~/.config/omarchy/langswitcher-dictionary.json`.

## Attribution

Conversion maps and algorithm follow the MIT-licensed LangSwitcher project —
see `LICENSE`.
