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

; ---- Polish ⌥-layer recovery (mirrors lib/langswitcher.py) -------------------
; When Polish is typed while a Cyrillic layout is active, the diacritic chords
; emit that layout's own ⌥-layer characters (ą=⌥+A -> ƒ, ś=⌥+S -> ы, ć=⌥+C -> ≠,
; ż=⌥+Z -> ђ). These tables map them back by physical key ("ьƒлф" -> "mąka",
; "сяуы≠" -> "cześć"). Keep identical to _POLISH_DIACRITIC_BASES / _UKRAINIAN_OPTION
; in lib/langswitcher.py — tests/test_windows_parity.py guards the parity.
PolBases   := "ąćęłńóśźżĄĆĘŁŃÓŚŹŻ"
PolBaseTo  := "acelnosxzACELNOSXZ"
UkrOptKeys := "abcdefghijklmnopqrstuvwxyz"
UkrOptVals := "ƒи≠ћќ÷©}ѕ°љ∆~™ў‘ј®ыёґµџ≈њђ"

PolFold := Map()
Loop Parse, PolBases
    PolFold[A_LoopField] := SubStr(PolBaseTo, A_Index, 1)

; Polish Pro ⌥ layer: base key -> diacritic (lowercase only).
PolProOpt := Map()
Loop Parse, PolBases {
    d := A_LoopField
    if (d = StrLower(d))
        PolProOpt[SubStr(PolBaseTo, A_Index, 1)] := d
}

; Reverse ⌥ map: artifact -> physical key (only this direction is used).
UkrOptRev := Map()
Loop Parse, UkrOptKeys {
    k := A_LoopField
    v := SubStr(UkrOptVals, A_Index, 1)
    if !UkrOptRev.Has(v)
        UkrOptRev[v] := k
}

; Target-layout base character for a physical QWERTY key. Only "uk" changes the
; base layer; en and pl are physically QWERTY (identity).
TargetBase(key, toLang) {
    global EnToUk
    if (toLang = "uk")
        return EnToUk.Has(key) ? EnToUk[key] : ""
    return key
}

TargetBaseHas(key, toLang) {
    global EnToUk
    return (toLang = "uk") ? EnToUk.Has(key) : true
}

; Core conversion mirroring langswitcher.py convert(): base map, then Polish
; diacritic fold (source pl), then ⌥-layer recovery. `core` is alphanumeric-only.
CoreConvert(core, fromLang, toLang) {
    global EnToUk, UkToEn, UkrOptRev, PolFold, PolProOpt
    out := ""
    Loop Parse, core {
        ch := A_LoopField
        if (fromLang = "uk")
            key := UkToEn.Has(ch) ? UkToEn[ch] : ""
        else
            key := EnToUk.Has(ch) ? ch : ""
        if (key != "" && TargetBaseHas(key, toLang)) {
            t := TargetBase(key, toLang)
            out .= (!IsLetter(ch) && !IsLetter(t)) ? ch : t
        } else if (fromLang = "pl" && PolFold.Has(ch) && TargetBaseHas(PolFold[ch], toLang)) {
            out .= TargetBase(PolFold[ch], toLang)
        } else if (fromLang = "uk" && UkrOptRev.Has(ch)) {
            k2 := UkrOptRev[ch]
            if (toLang = "pl" && PolProOpt.Has(k2))
                out .= PolProOpt[k2]
            else
                out .= TargetBase(k2, toLang)
        } else {
            out .= ch
        }
    }
    return out
}

; True when the core carries a Ukrainian ⌥-layer artifact that is NOT also a
; base-layer letter (e.g. ƒ ы ≠) — i.e. the user typed Polish diacritic chords.
HasDistinctiveUkrOpt(core) {
    global UkrOptRev, UkToEn
    Loop Parse, core {
        c := A_LoopField
        if (UkrOptRev.Has(c) && !UkToEn.Has(c))
            return true
    }
    return false
}

; A boundary char is leading/trailing "punctuation" only if it is neither a
; letter/digit NOR a layout ⌥ artifact: symbols like ≠ ÷ © are artifacts typed
; by a diacritic chord, not user punctuation, and must stay in the core so
; CoreConvert can recover them ("сяуы≠" -> "cześć").
IsCoreChar(c) {
    global UkrOptVals
    return RegExMatch(c, "[\pL\pN]") || InStr(UkrOptVals, c)
}

; Split leading/trailing non-core chars, so sentence-ending punctuation is kept
; ("ghbdsn." -> core "ghbdsn", trail "."). Empty core when nothing to convert.
SplitAffixes(text, &lead, &core, &trail) {
    i := 1
    j := StrLen(text)
    while (i <= j && !IsCoreChar(SubStr(text, i, 1)))
        i += 1
    while (j >= i && !IsCoreChar(SubStr(text, j, 1)))
        j -= 1
    if (i > j) {
        lead := text, core := "", trail := ""
        return core
    }
    lead := SubStr(text, 1, i - 1)
    core := SubStr(text, i, j - i + 1)
    trail := SubStr(text, j + 1)
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
    if HasCyrillic(core) {
        toLang := HasDistinctiveUkrOpt(core) ? "pl" : "en"
        return lead . CoreConvert(core, "uk", toLang) . trail
    }
    return lead . CoreConvert(core, "en", "uk") . trail
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
        back := CoreConvert(core, "uk", "en")
        return (!RegExMatch(core, "[аеєиіїоуюяАЕЄИІЇОУЮЯ]") && RegExMatch(back, "[aeiouyAEIOUY]")) ? true : false
    }
    fwd := CoreConvert(core, "en", "uk")
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
