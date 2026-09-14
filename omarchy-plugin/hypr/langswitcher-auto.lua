-- LangSwitcher automatic mode (Punto-style) for Hyprland + the Omarchy plugin.
--
-- Enable it by adding one line to ~/.config/hypr/hyprland.lua, next to the
-- other requires:
--
--   require("hypr.langswitcher-auto")
--
-- This file is only a keyboard buffer. Wayland gives applications no way to see
-- the keyboard, but Hyprland has an event for every key, so the word being typed
-- is buffered here as X11 keycodes and handed to the plugin's worker when Space
-- ends it. The worker decodes those keycodes with the layout that was active,
-- decides whether the word was typed in the wrong layout, and rewrites it —
-- see omarchy-plugin/lib/autofix.py (bilingual documentation) for the decision
-- and the safety gates.
--
-- Nothing is consumed or delayed here: the keys keep flowing to the application
-- exactly as before, and the worker only ever edits a word it can prove is still
-- behind the caret.
--
-- Turn it off without removing the require:
--   ~/.config/omarchy/langswitcher-auto.json  {"enabled": false}

local WORKER = (os.getenv("HOME") or "")
  .. "/.config/omarchy/plugins/stealth.langswitcher/bin/langswitcher-auto"

-- Modifiers never become text. Shift is tracked separately (it makes letters
-- upper case), the rest also end the word: MOD5+SPACE switches the layout, and
-- that keypress must not be mistaken for "a word was just finished".
local MODIFIER = {
  [37] = true, [50] = true, [62] = true, [64] = true, [105] = true,
  [108] = true, [133] = true, [134] = true, [66] = true, [77] = true,
}
local WORD_ENDERS = { [37] = true, [64] = true, [105] = true, [108] = true, [133] = true, [134] = true, [66] = true }
local SHIFT = { [50] = true, [62] = true }

-- Keys that move the caret or take another meaning: the word being buffered is
-- no longer the word behind the caret, so the buffer is dropped.
local NOT_TEXT = {
  [9] = true, [22] = true, [23] = true, [36] = true, [104] = true, [107] = true,
  [110] = true, [111] = true, [112] = true, [113] = true, [114] = true,
  [115] = true, [116] = true, [117] = true, [118] = true, [119] = true,
  [127] = true, [135] = true,
  -- F1..F12 (and the "F" keys above the keypad)
  [67] = true, [68] = true, [69] = true, [70] = true, [71] = true, [72] = true,
  [73] = true, [74] = true, [75] = true, [76] = true, [95] = true, [96] = true,
}

-- The X11 keycodes that produce text (the 47 main-block keys plus the extra ISO
-- key left of Z). Everything else ends the word being buffered, because we
-- cannot know what it did to the text in the application.
--
-- This set, and not the event's timestamp, is what separates typing from
-- synthetic input: wtype (and every other virtual keyboard) uploads its own
-- keymap and numbers its keysyms from 9 upwards, so a keysym can arrive as a
-- low, unrelated keycode, and the timestamp is no guide either — measured on
-- this machine: keys forwarded through the fcitx5 virtual keyboard carry the
-- real keycode with timestamp 0, while keys typed on the physical keyboard
-- carry the real keycode and a real timestamp.
local TEXT = { [49] = true, [51] = true, [94] = true }
for code = 10, 21 do TEXT[code] = true end   -- 1..0, -, =
for code = 24, 35 do TEXT[code] = true end   -- q..p, [, ]
for code = 38, 48 do TEXT[code] = true end   -- a..l, ;, '
for code = 52, 61 do TEXT[code] = true end   -- z..m, ., /

local SPACE = 65
local MIN_KEYS = 3
local MAX_KEYS = 64

local buffer = {}
local shift_down = false
local last_was_modifier = false
local last_code, last_time, last_pressed = nil, nil, nil

-- Every key arrives twice on this setup (measured: the same keycode, the same
-- timestamp, twice in a row — Hyprland's input event and fcitx5's virtual
-- keyboard forwarding it). Buffering both turned "ghbdsn" into
-- "gghhbbddssnn", so the word no longer matched what the caret was sitting
-- behind and every run refused to act. Identical neighbouring events are
-- ignored; a genuine repeat always carries a new timestamp.
local function repeated(keycode, timestamp, pressed)
  local same = last_code == keycode and last_time == timestamp and last_pressed == pressed
  last_code, last_time, last_pressed = keycode, timestamp, pressed
  return same
end

local function clear()
  buffer = {}
end

local function safe_class(win)
  local raw = (win and win.class) or ""
  return (raw:gsub("[^%w%._%+%-]", ""))
end

local function fire()
  if #buffer < MIN_KEYS then
    return
  end
  local codes = table.concat(buffer, ",")
  local window = safe_class(hl.get_active_window and hl.get_active_window() or nil)
  clear()
  if window ~= "" then
    hl.exec_cmd(string.format("%s %s --window %s", WORKER, codes, window))
  else
    hl.exec_cmd(string.format("%s %s", WORKER, codes))
  end
end

local function on_key(keycode, timestamp, pressed)
  if repeated(keycode, timestamp, pressed) then
    return
  end

  if SHIFT[keycode] then
    if pressed == 1 or pressed == true then
      shift_down = true
      last_was_modifier = true
    else
      shift_down = false
    end
    return
  end

  if MODIFIER[keycode] then
    if pressed == 1 or pressed == true then
      last_was_modifier = true
      if WORD_ENDERS[keycode] then
        clear()
      end
    end
    return
  end

  local is_press = pressed == 1 or pressed == true

  if not is_press then
    return
  end

  if keycode == SPACE then
    local was_modifier = last_was_modifier
    last_was_modifier = false
    if not was_modifier then
      fire()
    end
    clear()
    return
  end

  if NOT_TEXT[keycode] or not TEXT[keycode] then
    clear()
    last_was_modifier = false
    return
  end

  last_was_modifier = false
  if #buffer >= MAX_KEYS then
    clear()
  end
  buffer[#buffer + 1] = shift_down and ("s" .. keycode) or tostring(keycode)
end

-- One subscription per session: `hyprctl reload` re-runs this file, and without
-- this the old handler would keep firing and every word would be processed twice.
if _G.langswitcher_auto_key_sub then
  _G.langswitcher_auto_key_sub:remove()
end
_G.langswitcher_auto_key_sub = hl.on("input.keyboard.key", on_key)

if _G.langswitcher_auto_focus_sub then
  _G.langswitcher_auto_focus_sub:remove()
end
-- Focus moving means the caret did too.
_G.langswitcher_auto_focus_sub = hl.on("window.active", function()
  clear()
  shift_down = false
  last_was_modifier = false
end)
