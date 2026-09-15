@echo off
setlocal
REM LangSwitcher for Windows 11 — installer. Just double-click this file.
REM Needs internet (winget installs AutoHotkey v2 if missing, and the decision
REM data comes from a pinned release asset).
REM
REM The data (langswitcher-data.txt) is derived from CC BY-SA 4.0 content and is
REM not in the repository, which is MIT. Offline: unpack that release asset
REM yourself and set LANGSWITCHER_DATA_DIR to the unpacked directory.
set "REPO=%LANGSWITCHER_REPO%"
if not defined REPO set "REPO=Samuel-Ku/langswitcher-linux"

REM Keep in step with DATA_VERSION/DATA_SHA256 in omarchy-plugin/install-plugin.sh
REM and windows/install.ps1.
set "DATA_VERSION=2026.09.15"
set "DATA_FILE=langswitcher-data-%DATA_VERSION%.tar.gz"
set "DATA_SHA256=ac9776dbe5a97d68cb038b3e61316f7bed7b7990232aa87cd8129000ae90feb7"
set "DATA_URL=%LANGSWITCHER_DATA_URL%"
if not defined DATA_URL set "DATA_URL=https://github.com/%REPO%/releases/download/data-%DATA_VERSION%/%DATA_FILE%"
if defined LANGSWITCHER_DATA_SHA256 set "DATA_SHA256=%LANGSWITCHER_DATA_SHA256%"

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

REM Stage first: the live install is untouched until the data is verified.
set "STAGE=%TEMP%\langswitcher-stage"
if exist "%STAGE%" rmdir /s /q "%STAGE%"
mkdir "%STAGE%" 2>nul
copy /y "%~dp0LangSwitcher.ahk" "%STAGE%\" >nul
if errorlevel 1 (
  echo [!] Copy failed.
  pause
  exit /b 1
)

if defined LANGSWITCHER_DATA_DIR (
  echo [*] Decision data %DATA_VERSION% from %LANGSWITCHER_DATA_DIR% ^(offline^).
  copy /y "%LANGSWITCHER_DATA_DIR%\words.txt" "%STAGE%\langswitcher-data.txt" >nul
  if errorlevel 1 (
    echo [!] %LANGSWITCHER_DATA_DIR%\words.txt not found. Unpack the release asset there.
    pause
    exit /b 1
  )
) else (
  echo [*] Fetching decision data %DATA_VERSION%...
  curl -fsSL "%DATA_URL%" -o "%STAGE%\%DATA_FILE%"
  if errorlevel 1 (
    echo [!] Download failed. Offline: unpack %DATA_FILE% and set LANGSWITCHER_DATA_DIR.
    pause
    exit /b 1
  )
  set "GOT="
  for /f "skip=1 delims=" %%h in ('certutil -hashfile "%STAGE%\%DATA_FILE%" SHA256') do (
    if not defined GOT set "GOT=%%h"
  )
  set "GOT=%GOT: =%"
  if /i not "%GOT%"=="%DATA_SHA256%" (
    echo [!] Decision data checksum mismatch.
    echo     got  %GOT%
    echo     want %DATA_SHA256%
    echo Nothing was installed.
    pause
    exit /b 1
  )
  tar -xzf "%STAGE%\%DATA_FILE%" -C "%STAGE%" words.txt
  if errorlevel 1 (
    echo [!] Could not unpack the data artifact.
    pause
    exit /b 1
  )
  move /y "%STAGE%\words.txt" "%STAGE%\langswitcher-data.txt" >nul
  del "%STAGE%\%DATA_FILE%"
  echo [*] Decision data verified.
)

set DST=%APPDATA%\LangSwitcher
mkdir "%DST%" 2>nul
copy /y "%STAGE%\LangSwitcher.ahk" "%DST%\" >nul
copy /y "%STAGE%\langswitcher-data.txt" "%DST%\" >nul
if errorlevel 1 (
  echo [!] Copy failed.
  pause
  exit /b 1
)
rmdir /s /q "%STAGE%"

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
