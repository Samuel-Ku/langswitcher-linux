; LangSwitcher for Windows 11 — port of macOS LangSwitcher + Punto-style auto-switch.
; Double-Shift converts the selection; typing Space auto-converts the last word
; if it looks like the wrong layout. Tray icon toggles the auto mode.
; Requires AutoHotkey v2 (winget install AutoHotkey.AutoHotkey).
; Keep this file UTF-8 encoded (Cyrillic maps inside).
; Escape rules are v2's: a literal quote inside a string is `" (doubling it is
; v1 syntax and ends the string, which is why the parser rejected these maps),
; and a literal backtick is ``. Keep them that way.
#Requires AutoHotkey v2.0
#SingleInstance Force
SendMode "Input"

; A runner cannot click the error dialog AutoHotkey shows for a runtime error,
; so a headless run reports to stdout and exits instead of hanging the job.
HeadlessError(err, mode) {
    FileAppend("ahk-error: " err.Message " (" err.File ":" err.Line ")`n", "*")
    ExitApp(1)
    return true
}

if (A_Args.Length >= 1 && A_Args[1] = "--dump")
    OnError(HeadlessError)

; ================= Settings =================
DoubleShiftMs := 300
AutoEnabled := true
SwitchAfterConvert := true
SettingsFile := A_ScriptDir "\settings.ini"
if FileExist(SettingsFile) {
    AutoEnabled := IniRead(SettingsFile, "main", "auto", 1) ? true : false
    SwitchAfterConvert := IniRead(SettingsFile, "main", "switch", 1) ? true : false
}

; Layout Switch mode: target language -> Windows input locale id (HKL).
LangHKL := Map("en", "00000409", "uk", "00000422", "pl", "00000415")
LastTargetLang := ""

A_IconTip := "LangSwitcher — Shift+Shift: convert, Space: auto"

; ================= Layout maps (same tables as the macOS original) =================
QWERTY := "``1234567890-=qwertyuiop[]\asdfghjkl;'zxcvbnm,./~!@#$%^&*()_+QWERTYUIOP{}|ASDFGHJKL:`"ZXCVBNM<>?"
UKR    := "'1234567890-=йцукенгшщзхї\фівапролджєячсмитьбю.₴!`"№;%:?*()_+ЙЦУКЕНГШЩЗХЇ/ФІВАПРОЛДЖЄЯЧСМИТЬБЮ,"

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
    global LastTargetLang
    if (text = "" || HasPolish(text))
        return ""
    SplitAffixes(text, &lead, &core, &trail)
    if (core = "")
        return ""
    if HasCyrillic(core) {
        toLang := HasDistinctiveUkrOpt(core) ? "pl" : "en"
        LastTargetLang := toLang
        return lead . CoreConvert(core, "uk", toLang) . trail
    }
    LastTargetLang := "uk"
    return lead . CoreConvert(core, "en", "uk") . trail
}

; ================= Decision data =================
; Frequency lists, curated short words and letter n-gram weights generated by
; tools/build_words.py and installed next to this script as
; langswitcher-data.txt (its own header carries the sources and the CC BY-SA 4.0
; licence; the repository is MIT and ships no derived data).
;
; Automatic mode stays out of the way until the data loads: without it the
; three-tier decision cannot run, and guessing would rewrite correct text.
DataVersion := ""
UkWords := Map(), EnWords := Map(), UkRank := Map(), EnRank := Map()
UkShort := Map(), EnShort := Map()
UkUni := Map(), UkBi := Map(), UkTri := Map()
EnUni := Map(), EnBi := Map(), EnTri := Map()
DataReady := false
DataPath := ""
DataError := ""

; Kept identical to NGRAM_MARGIN / REVERSE_RANK_MARGIN in lib/langswitcher.py.
NgramMargin := 5.0
ReverseRankMargin := 4
DataScale := 100          ; the artifact stores n-gram weights scaled to integers

; Parse the artifact into Map(section -> Array of tokens), in one pass.
; The obvious "append every line to one buffer" version is quadratic — 74,000
; concatenations over ~1 MB — and took the whole CI job's ten minutes on a
; runner before it was cancelled.
ParseData(text) {
    out := Map(), name := ""
    for line in StrSplit(text, "`n", "`r") {
        t := Trim(line)
        if (t = "" || SubStr(t, 1, 1) = "#")
            continue
        if (SubStr(t, 1, 1) = "[") {
            close := InStr(t, "]")
            name := SubStr(t, 2, close - 2)
            out[name] := []
            continue
        }
        if (name = "" || !out.Has(name))
            continue
        for token in StrSplit(t, " ")
            if (token != "")
                out[name].Push(token)
    }
    return out
}

; Rank is the position in the token list, exactly as words.py builds it, so both
; sides rank a word identically.
FillWords(tokens, &setMap, &rankMap) {
    setMap := Map(), rankMap := Map()
    for index, token in tokens {
        setMap[token] := true
        rankMap[token] := index
    }
    return tokens.Length
}

AddSlang(tokens, &setMap, &rankMap, base) {
    index := 0
    for token in tokens {
        setMap[token] := true
        if (!rankMap.Has(token))
            rankMap[token] := base + index
        index += 1
    }
}

FillGrams(tokens, &map) {
    map := Map()
    Loop tokens.Length // 2 {
        i := (A_Index - 1) * 2 + 1
        map[tokens[i]] := (tokens[i + 1] + 0.0) / DataScale
    }
}

LoadData() {
    global DataVersion, UkWords, EnWords, UkRank, EnRank, UkShort, EnShort
    global UkUni, UkBi, UkTri, EnUni, EnBi, EnTri, DataReady, DataPath, DataError
    path := A_ScriptDir "\langswitcher-data.txt"
    Loop A_Args.Length {
        if (A_Args[A_Index] = "--data" && A_Args.Length >= A_Index + 1)
            path := A_Args[A_Index + 1]
    }
    DataPath := path, DataError := ""
    DataReady := false
    if !FileExist(path) {
        DataError := "no such file"
        return false
    }
    text := FileRead(path, "UTF-8")
    if RegExMatch(text, "version (\S+)", &m)
        DataVersion := m[1]
    parts := ParseData(text)
    for name in ["uk_words", "en_words", "uk_short", "en_short", "uk_slang",
                 "uk_uni", "uk_bi", "uk_tri", "en_uni", "en_bi", "en_tri"] {
        if !parts.Has(name) {
            DataError := "section missing: " name
            return false
        }
    }
    discard := Map()
    ukCount := FillWords(parts["uk_words"], &UkWords, &UkRank)
    FillWords(parts["en_words"], &EnWords, &EnRank)
    FillWords(parts["uk_short"], &UkShort, &discard)
    FillWords(parts["en_short"], &EnShort, &discard)
    AddSlang(parts["uk_slang"], &UkWords, &UkRank, ukCount // 4)
    FillGrams(parts["uk_uni"], &UkUni)
    FillGrams(parts["uk_bi"], &UkBi)
    FillGrams(parts["uk_tri"], &UkTri)
    FillGrams(parts["en_uni"], &EnUni)
    FillGrams(parts["en_bi"], &EnBi)
    FillGrams(parts["en_tri"], &EnTri)
    DataReady := true
    return true
}

Letters(text) {
    out := ""
    Loop Parse, text
        if RegExMatch(A_LoopField, "[\pL'\x{2019}]")
            out .= A_LoopField
    return out
}

; True when the typed text is only letters/apostrophes — no key that types a
; letter in the other layout. «hello» is plain; «,elm» (which is «будь») is not,
; because there the comma is the key that types «б».
IsPlainWord(text) => RegExMatch(Trim(text), "^[\pL'\x{2019}]*$")

IsAscii(text) => !RegExMatch(text, "[^\x00-\x7F]")

; Full-key conversion (mirrors convert_full in lib/langswitcher.py): every key is
; mapped, boundary punctuation included. In auto mode the user pressed keys
; blindly, so a «.» is the key that types «ю» in the intended layout. The hotkey
; path keeps AutoConvert, which preserves punctuation because there the
; conversion is an explicit request.
ConvertFull(text) {
    global LastTargetLang
    if (text = "" || HasPolish(text))
        return ""
    if HasCyrillic(text) {
        LastTargetLang := "en"
        return FullConvert(text, "uk", "en")
    }
    LastTargetLang := "uk"
    return FullConvert(text, "en", "uk")
}

FullConvert(text, fromLang, toLang) {
    out := ""
    Loop Parse, text
        out .= CoreConvert(A_LoopField, fromLang, toLang)
    return out
}

; Mirrors _ngram_score(): trigram with backoff to bigram, then unigram.
NgramScore(text, uni, bi, tri) {
    padded := "^" . text . "$"
    total := 0.0
    Loop StrLen(padded) - 2 {
        gram := SubStr(padded, A_Index, 3)
        w := tri.Has(gram) ? tri[gram] : 0
        if (w) {
            ctx := bi.Has(SubStr(gram, 1, 2)) ? bi[SubStr(gram, 1, 2)] : 0
            total += Ln(w / (ctx + 1))
            continue
        }
        w := bi.Has(SubStr(gram, 2, 2)) ? bi[SubStr(gram, 2, 2)] : 0
        if (w)
            p := w / ((uni.Has(SubStr(gram, 2, 1)) ? uni[SubStr(gram, 2, 1)] : 0) + 1)
        else
            p := 0.0001
        total += Ln(Max(p, 0.000000001))
    }
    return total
}

; Three-tier decision, mirroring looks_like_wrong_layout_plausible() in
; lib/langswitcher.py: a word of its own language vetoes the fix, a known word of
; the other language applies it, and letter n-grams decide the rest (with a rank
; comparison in the reverse direction, where «еру» is "the").
; Keep the two implementations in step: the Windows CI job replays a corpus
; through both and fails when the decisions differ.
LooksPlausible(text) {
    global DataReady, UkWords, EnWords, UkRank, EnRank, UkShort, EnShort
    global UkUni, UkBi, UkTri, EnUni, EnBi, EnTri, NgramMargin, ReverseRankMargin
    if (!DataReady || text = "" || HasPolish(text))
        return false
    conv := ConvertFull(text)
    if (conv = "" || conv = text)
        return false
    source := StrLower(Letters(text))
    target := StrLower(Letters(conv))
    if (target = "" || target = source)
        return false
    SplitAffixes(Trim(text), &lead, &core, &trail)
    sourceWord := StrLower(core)
    plain := IsPlainWord(text)
    if IsAscii(text) {
        sourceKnown := EnWords.Has(sourceWord) || EnShort.Has(sourceWord)
        targetKnown := UkWords.Has(target) || UkShort.Has(target)
        if (sourceKnown && (plain || !targetKnown))
            return false
        if (targetKnown)
            return true
        if (StrLen(target) <= 2)
            return false
        return NgramScore(target, UkUni, UkBi, UkTri)
             - NgramScore(source, EnUni, EnBi, EnTri) > NgramMargin
    }
    sourceKnown := UkWords.Has(sourceWord) || UkShort.Has(sourceWord)
    targetKnown := EnWords.Has(target) || EnShort.Has(target)
    if (sourceKnown && (plain || !targetKnown)) {
        if (!targetKnown || !RegExMatch(conv, "^[\pL]+$"))
            return false
        if (!UkRank.Has(sourceWord) || !EnRank.Has(target))
            return false
        return EnRank[target] * ReverseRankMargin < UkRank[sourceWord]
    }
    if (targetKnown)
        return true
    if (StrLen(target) <= 2)
        return false
    return NgramScore(target, EnUni, EnBi, EnTri)
         - NgramScore(source, UkUni, UkBi, UkTri) > NgramMargin
}

; ================= Clipboard helpers =================
; Switch the OS input language to `lang` (macOS Layout Switch mode). Best effort:
; no-op when the layout is not installed. LoadKeyboardLayout + the documented
; WM_INPUTLANGCHANGEREQUEST (0x50) to the active window.
SwitchToLang(lang) {
    global LangHKL
    if !LangHKL.Has(lang)
        return false
    hkl := DllCall("LoadKeyboardLayout", "Str", LangHKL[lang], "UInt", 1, "Ptr")
    if !hkl
        return false
    try PostMessage(0x50, 0, hkl, , "A")
    return true
}

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
    global AutoEnabled, SwitchAfterConvert, LastTargetLang
    if (endKey = "{Space}" && AutoEnabled && LooksPlausible(word)) {
        conv := ConvertFull(word)
        if (conv != "" && conv != word) {
            StopHook()
            Send("{Backspace " StrLen(word) + 1 "}")
            Sleep(20)
            PasteText(conv)
            Send("{Space}")
            if (SwitchAfterConvert)
                SwitchToLang(LastTargetLang)
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
    global SwitchAfterConvert, LastTargetLang
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
                if (SwitchAfterConvert)
                    SwitchToLang(LastTargetLang)
            }
        }
    }
    A_Clipboard := saved
    StartHook()
}

; ================= Startup =================
; Without the data file automatic mode cannot decide anything, so it turns
; itself off and says why rather than guessing. The data is a CC BY-SA 4.0
; release artifact installed next to this script; see windows/README.md.
if (!LoadData()) {
    AutoEnabled := false
    A_IconTip := "LangSwitcher — no langswitcher-data.txt; auto mode is off"
} else {
    A_IconTip := "LangSwitcher " . DataVersion . " — Shift+Shift: convert, Space: auto"
}

; ================= Tray =================
tray := A_TrayMenu
tray.Add("Convert selection (Shift+Shift)", (*) => ConvertSelection())
tray.Add()
tray.Add("Auto-convert after Space", (*) => ToggleAuto())
if AutoEnabled
    tray.Check("Auto-convert after Space")
tray.Add("Switch layout after convert", (*) => ToggleSwitch())
if SwitchAfterConvert
    tray.Check("Switch layout after convert")

ToggleAuto() {
    global AutoEnabled
    AutoEnabled := !AutoEnabled
    IniWrite(AutoEnabled ? 1 : 0, SettingsFile, "main", "auto")
    if AutoEnabled
        A_TrayMenu.Check("Auto-convert after Space")
    else
        A_TrayMenu.Uncheck("Auto-convert after Space")
}

ToggleSwitch() {
    global SwitchAfterConvert
    SwitchAfterConvert := !SwitchAfterConvert
    IniWrite(SwitchAfterConvert ? 1 : 0, SettingsFile, "main", "switch")
    if SwitchAfterConvert
        A_TrayMenu.Check("Switch layout after convert")
    else
        A_TrayMenu.Uncheck("Switch layout after convert")
}

; ================= Headless mode for CI =================
; LangSwitcher.ahk --dump <corpus> <out> [--data <artifact>] reads one word per
; line and writes "<word><TAB><0|1><TAB><target>", so the Windows CI job can
; compare these decisions with the Python core's on the same corpus. Exits
; before the typing hook starts, so it is safe to run unattended.
if (A_Args.Length >= 3 && A_Args[1] = "--dump") {
    if (!DataReady) {
        FileAppend("data-not-loaded: " DataPath " (" DataError ")`n", "*")
        ExitApp(1)
    }
    out := ""
    for word in StrSplit(FileRead(A_Args[2], "UTF-8"), "`n", "`r") {
        word := Trim(word)
        if (word = "" || SubStr(word, 1, 1) = "#")
            continue
        decided := LooksPlausible(word)
        out .= word . "`t" . (decided ? 1 : 0) . "`t"
              . (decided ? LastTargetLang : "-") . "`n"
    }
    try FileDelete(A_Args[3])
    FileAppend(out, A_Args[3], "UTF-8")
    ExitApp(0)
}

StartHook()
