# LangSwitcher for Windows 11 — one-line installer.
# Run in PowerShell:
#   irm https://raw.githubusercontent.com/Samuel-Ku/langswitcher-linux/main/windows/install.ps1 | iex
$ErrorActionPreference = "Stop"
$Repo = if ($env:LANGSWITCHER_REPO) { $env:LANGSWITCHER_REPO } else { "Samuel-Ku/langswitcher-linux" }
$Branch = if ($env:LANGSWITCHER_BRANCH) { $env:LANGSWITCHER_BRANCH } else { "main" }

if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
  throw "winget not found. Install 'App Installer' from Microsoft Store, then rerun."
}
if (-not (winget list --id AutoHotkey.AutoHotkey 2>$null | Select-String "AutoHotkey")) {
  Write-Host "[*] Installing AutoHotkey v2..."
  winget install -e --id AutoHotkey.AutoHotkey --silent `
    --accept-package-agreements --accept-source-agreements | Out-Null
} else {
  Write-Host "[*] AutoHotkey already installed."
}

$Dst = Join-Path $env:APPDATA "LangSwitcher"
New-Item -ItemType Directory -Force -Path $Dst | Out-Null
$zip = Join-Path $env:TEMP "langswitcher.zip"
Invoke-WebRequest -Uri "https://github.com/$Repo/archive/refs/heads/$Branch.zip" -OutFile $zip
Expand-Archive -Path $zip -DestinationPath (Join-Path $env:TEMP "langswitcher-dl") -Force
$ahk = Get-ChildItem -Path (Join-Path $env:TEMP "langswitcher-dl") -Filter "LangSwitcher.ahk" -Recurse | Select-Object -First 1
if (-not $ahk) { throw "LangSwitcher.ahk not found in downloaded archive." }
Copy-Item $ahk.FullName (Join-Path $Dst "LangSwitcher.ahk") -Force

$Wsh = New-Object -ComObject WScript.Shell
$lnk = $Wsh.CreateShortcut((Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\Startup\LangSwitcher.lnk"))
$lnk.TargetPath = Join-Path $Dst "LangSwitcher.ahk"
$lnk.WorkingDirectory = $Dst
$lnk.Save()

Get-Process AutoHotkey64 -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep 1
Start-Process (Join-Path $Dst "LangSwitcher.ahk")
Write-Host ""
Write-Host "[OK] LangSwitcher running (tray icon)."
Write-Host " - Double-Shift: convert selected text"
Write-Host " - Space: auto-convert last word (toggle in tray menu)"
