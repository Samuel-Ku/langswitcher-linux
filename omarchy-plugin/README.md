# LangSwitcher for Omarchy

Omarchy plugin + standalone Linux port of [LangSwitcher for macOS](https://github.com/Samuel-Ku/langSwitcher)
(open-source keyboard-layout text converter, MIT). The macOS app is Swift +
Carbon/Cocoa-only and cannot run on Linux — this repo ports its conversion
core (physical key positions, auto-detect, Greedy Line, punctuation
preservation) to Python and wraps it as a Quattro shell plugin
(`service` + `bar-widget`).

## Install

```sh
omarchy plugin add https://github.com/<you>/omarchy-langswitcher.git --enable
```

Then add the hotkeys to `~/.config/hypr/bindings.lua` (copy from
`bindings.snippet.lua`):

```lua
o.bind("SUPER + GRAVE", "LangSwitcher: конвертувати виділення", "$HOME/.config/omarchy/plugins/stealth.langswitcher/bin/langswitcher-convert selection")
o.bind("SUPER + SHIFT + GRAVE", "LangSwitcher: конвертувати рядок (greedy)", "$HOME/.config/omarchy/plugins/stealth.langswitcher/bin/langswitcher-convert greedy")
```

```sh
hyprctl reload
```

Dependencies (checked automatically by the service, shown in the panel):

```sh
sudo pacman -S --needed wl-clipboard wtype python3 libnotify
```

## Usage

1. Type text with the wrong layout active (`ghbdsn` instead of `привіт`).
2. Select it (or leave the cursor at the end of the line for greedy mode).
3. Press `SUPER+\`` — the text is replaced with the converted version.
4. Or: click the ⌨ widget → panel buttons; middle-click the widget converts
   the selection directly.

Default layouts: `en,uk,pl` (change via `--layouts` in the binds).

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
python3 tests/test_convert.py                                  # self-tests
```

## Layouts

Maps are ported 1:1 from the original, but the core ships exactly the three
layouts this project needs: `en`, `uk`, `pl` (`en/us` and `uk/ua` are aliases).
Russian and the other originals are intentionally absent.

- Polish (`pl`, programmer's) is physically identical to US QWERTY, so there
  is no `en↔pl` wrong-layout case — and text with Polish diacritics
  (`ą ć ę ł ń ó ś ź ż`) is **never touched**, in every mode.
- Real conversion happens on the `en↔uk` pair with auto-detection.
- **Polish ⌥-layer recovery (as on macOS):** typing Polish while a Cyrillic
  layout is active emits that layout's ⌥ symbols (`ą`=⌥+A→`ƒ`, `ś`=⌥+S→`ы`,
  `ć`=⌥+C→`≠`). The converter maps them back by physical key: `ьƒлф` → `mąka`,
  `сяуы≠` → `cześć`. When such artifacts are present, `pl` is picked as target.

## Files

- `manifest.json` — plugin contract (`service`, `bar-widget`)
- `Service.qml` — dep check + `convert()` + `statusObject()` (clipboard text never enters QML)
- `BarWidget.qml` — ⌨ glyph, status colour, panel toggle, middle-click convert, IPC
- `Panel.qml` — Convert buttons, status, layouts, hotkey hints
- `bin/langswitcher-convert` — Wayland worker (wl-paste → `lib/switch.py` → wl-copy → wtype)
- `lib/` — Python core + CLI (stdlib only)
- `bindings.snippet.lua` — hotkeys for `bindings.lua`
- `tests/test_convert.py` — core self-tests

## Wayland limits (honest)

- No on-the-fly auto-switching like X11 Punto Switcher: Wayland forbids
  global key listening, so conversion is hotkey-driven (like the original's
  manual mode). `xneur` does not work on Hyprland.
- Double-Shift cannot be bound under Wayland — `SUPER+\`` is the equivalent.
- In XWayland windows, selecting with the mouse (primary selection) is the
  most reliable.

## Remove

```sh
omarchy plugin remove stealth.langswitcher
```

(also delete the two `o.bind` lines from `~/.config/hypr/bindings.lua`)

## Attribution

Conversion maps and algorithm: [reg2005/langSwitcher](https://github.com/reg2005/langSwitcher)
(and Samuel-Ku's fork), MIT. This port keeps the MIT license — see `LICENSE`.
