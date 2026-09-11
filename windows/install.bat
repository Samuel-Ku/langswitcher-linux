@echo off
setlocal
REM LangSwitcher for Windows 11 — installer. Just double-click this file.
REM Needs internet (winget installs AutoHotkey v2 if missing).

where winget >nul 2>&1
if errorlevel 1 (
  echo [!] winget not found. Install "App Installer" from Microsoft Store, then rerun.
  pause
  exit /b 1
)

winget list --id AutoHotkey.AutoHotkey >nul 2>&1
if errorlevel 1 (
  echo [*] Installing AutoHotkey v2...
  winget install -e --id AutoHotkey.AutoHotkey --silent --accept-package-agreements --accept-source-agreements
  if errorlevel 1 (
    echo [!] AutoHotkey install failed. Get it at https://www.autohotkey.com/ and rerun.
    pause
    exit /b 1
  )
) else (
  echo [*] AutoHotkey already installed.
)

set DST=%APPDATA%\LangSwitcher
mkdir "%DST%" 2>nul
copy /y "%~dp0LangSwitcher.ahk" "%DST%\" >nul
if errorlevel 1 (
  echo [!] Copy failed.
  pause
  exit /b 1
)

REM Autostart shortcut
powershell -NoProfile -ExecutionPolicy Bypass -Command "$s=(New-Object -ComObject WScript.Shell).CreateShortcut($env:APPDATA+'\Microsoft\Windows\Start Menu\Programs\Startup\LangSwitcher.lnk');$s.TargetPath=$env:APPDATA+'\LangSwitcher\LangSwitcher.ahk';$s.WorkingDirectory=$env:APPDATA+'\LangSwitcher';$s.Save()"

REM Restart running instance if any
taskkill /f /im AutoHotkey64.exe >nul 2>&1
timeout /t 1 /nobreak >nul
start "" "%DST%\LangSwitcher.ahk"

echo.
echo [OK] LangSwitcher running (tray icon).
echo  - Double-Shift: convert selected text
echo  - Space: auto-convert last word (toggle in tray menu)
echo  - Layouts: EN/UK/PL. Polish diacritics are never touched.
pause
