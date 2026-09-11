; LangSwitcher for Windows 11 — port of macOS LangSwitcher + Punto-style auto-switch.
; Double-Shift converts the selection; typing Space auto-converts the last word
; if it looks like the wrong layout. Tray icon toggles the auto mode.
; Requires AutoHotkey v2 (winget install AutoHotkey.AutoHotkey).
; Keep this file UTF-8 encoded (Cyrillic maps inside).
#Requires AutoHotkey v2.0
#SingleInstance Force
SendMode "Input"

; ================= Settings =================
DoubleShiftMs := 300
AutoEnabled := true
SettingsFile := A_ScriptDir "\settings.ini"
if FileExist(SettingsFile)
    AutoEnabled := IniRead(SettingsFile, "main", "auto", 1) ? true : false

A_IconTip := "LangSwitcher — Shift+Shift: convert, Space: auto"

; ================= Layout maps (same tables as the macOS original) =================
QWERTY := "`1234567890-=qwertyuiop[]\asdfghjkl;'zxcvbnm,./~!@#$%^&*()_+QWERTYUIOP{}|ASDFGHJKL:""ZXCVBNM<>?"
UKR    := "'1234567890-=йцукенгшщзхї\фівапролджєячсмитьбю.₴!""№;%:?*()_+ЙЦУКЕНГШЩЗХЇ/ФІВАПРОЛДЖЄЯЧСМИТЬБЮ,"

EnToUk := Map()
UkToEn := Map()
Loop Min(StrLen(QWERTY), StrLen(UKR)) {
    q := SubStr(QWERTY, A_Index, 1)
    u := SubStr(UKR, A_Index, 1)
    EnToUk[q] := u
    if !UkToEn.Has(u)
        UkToEn[u] := q
}

IsLetter(c) => RegExMatch(c, "\pL")
HasCyrillic(text) => RegExMatch(text, "[\x{0400}-\x{04FF}]")
HasPolish(text) => RegExMatch(text, "[ąćęłńóśźżĄĆĘŁŃÓŚŹŻ]")

EnToUkWord(text) {
    global EnToUk
    out := ""
    Loop Parse, text {
        c := A_LoopField
        if EnToUk.Has(c) {
            t := EnToUk[c]
            out .= (!IsLetter(c) && !IsLetter(t)) ? c : t
        } else {
            out .= c
        }
    }
    return out
}

UkToEnWord(text) {
    global UkToEn
    out := ""
    Loop Parse, text {
        c := A_LoopField
        if UkToEn.Has(c) {
            t := UkToEn[c]
            out .= (!IsLetter(c) && !IsLetter(t)) ? c : t
        } else {
            out .= c
        }
    }
    return out
}

; Split leading/trailing non-alphanumerics from the core, so sentence-ending
; punctuation is kept ("ghbdsn." -> core "ghbdsn", trail "."). Empty core when
; there is nothing alphanumeric to convert.
SplitAffixes(text, &lead, &core, &trail) {
    if RegExMatch(text, "^([^\pL\pN]*)([\pL\pN]+)([^\pL\pN]*)$", &m) {
        lead := m[1]
        core := m[2]
        trail := m[3]
    } else {
        lead := "", core := "", trail := ""
    }
    return core
}

; Direction by content. Polish diacritics = definitely Polish intent, never touch.
; (Polish programmer's layout is physically US QWERTY, so en<->pl has no wrong-layout case.)
; Only the alphanumeric core is mapped; leading/trailing punctuation is preserved.
AutoConvert(text) {
    if (text = "" || HasPolish(text))
        return ""
    SplitAffixes(text, &lead, &core, &trail)
    if (core = "")
        return ""
    if HasCyrillic(core)
        return lead . UkToEnWord(core) . trail
    return lead . EnToUkWord(core) . trail
}

; Conservative check for AUTO mode only. The plain macOS heuristic flags every
; Latin word that maps to Cyrillic, so auto-converting after Space with it would
; rewrite ordinary English. Auto requires: no vowel in the current script AND a
; vowel in the converted script (single alphabetic word, length >= 3).
; Mirrors looks_like_wrong_layout_strict() in lib/langswitcher.py — keep these
; examples true on BOTH sides: ghbdsn/ghbdtn/ghbdsn. -> true; hello/test/the/
; rhythm, any Polish-diacritic word, anything shorter than 3 or with a digit -> false.
LooksWrongAuto(word) {
    SplitAffixes(word, &lead, &core, &trail)
    if (StrLen(core) < 3 || !RegExMatch(core, "^[\pL]+$") || HasPolish(word))
        return false
    if HasCyrillic(core) {
        back := UkToEnWord(core)
        return (!RegExMatch(core, "[аеєиіїоуюяАЕЄИІЇОУЮЯ]") && RegExMatch(back, "[aeiouyAEIOUY]")) ? true : false
    }
    fwd := EnToUkWord(core)
    return (!RegExMatch(core, "[aeiouyAEIOUY]") && RegExMatch(fwd, "[аеєиіїоуюяАЕЄИІЇОУЮЯ]")) ? true : false
}

; ================= Clipboard helpers =================
PasteText(text) {
    saved := ClipboardAll()
    A_Clipboard := ""
    A_Clipboard := text
    if ClipWait(0.8) {
        Send("^v")
        Sleep(120)
    }
    A_Clipboard := saved
}

; ================= Typing hook (auto-convert after Space) =================
ih := 0

StartHook() {
    global ih := InputHook("L0", "{Space}{Enter}{Escape}{Tab}")
    ih.OnEnd := OnWordEnd
    ih.Start()
}

StopHook() {
    global ih
    try ih.Stop()
}

OnWordEnd(hook) {
    word := hook.Input
    endKey := hook.EndKey
    StartHook()
    global AutoEnabled
    if (endKey = "{Space}" && AutoEnabled && LooksWrongAuto(word)) {
        conv := AutoConvert(word)
        if (conv != "" && conv != word) {
            StopHook()
            Send("{Backspace " StrLen(word) + 1 "}")
            Sleep(20)
            PasteText(conv)
            Send("{Space}")
            StartHook()
        }
    }
}

; ================= Double-Shift (manual convert, like macOS) =================
IsShiftKey(k) => (k = "Shift" || k = "LShift" || k = "RShift")

lastShift := 0

~Shift Up:: {
    global lastShift, DoubleShiftMs
    now := A_TickCount
    if (IsShiftKey(A_PriorKey) && now - lastShift < DoubleShiftMs) {
        lastShift := 0
        ConvertSelection()
    } else if IsShiftKey(A_PriorKey) {
        lastShift := now
    } else {
        lastShift := 0
    }
}

ConvertSelection() {
    StopHook()
    saved := ClipboardAll()
    A_Clipboard := ""
    Send("^c")
    if ClipWait(0.6) {
        sel := A_Clipboard
        conv := AutoConvert(sel)
        if (conv != "" && conv != sel) {
            A_Clipboard := ""
            A_Clipboard := conv
            if ClipWait(0.8) {
                Send("^v")
                Sleep(120)
            }
        }
    }
    A_Clipboard := saved
    StartHook()
}

; ================= Tray =================
tray := A_TrayMenu
tray.Add("Convert selection (Shift+Shift)", (*) => ConvertSelection())
tray.Add()
tray.Add("Auto-convert after Space", (*) => ToggleAuto())
if AutoEnabled
    tray.Check("Auto-convert after Space")

ToggleAuto() {
    global AutoEnabled
    AutoEnabled := !AutoEnabled
    IniWrite(AutoEnabled ? 1 : 0, SettingsFile, "main", "auto")
    if AutoEnabled
        A_TrayMenu.Check("Auto-convert after Space")
    else
        A_TrayMenu.Uncheck("Auto-convert after Space")
}

StartHook()
