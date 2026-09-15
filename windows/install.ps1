# LangSwitcher for Windows 11 — one-line installer.
# Run in PowerShell:
#   irm https://raw.githubusercontent.com/Samuel-Ku/langswitcher-linux/main/windows/install.ps1 | iex
#
# The decision data (langswitcher-data.txt) is not in the repository: it is
# derived from CC BY-SA 4.0 content while the project is MIT, so it ships as a
# release asset pinned by hash below.  Offline: unpack that asset yourself and
# set LANGSWITCHER_DATA_DIR to the unpacked directory.
$ErrorActionPreference = "Stop"
$Repo = if ($env:LANGSWITCHER_REPO) { $env:LANGSWITCHER_REPO } else { "Samuel-Ku/langswitcher-linux" }
$Branch = if ($env:LANGSWITCHER_BRANCH) { $env:LANGSWITCHER_BRANCH } else { "main" }

# Keep these two in step with DATA_VERSION/DATA_SHA256 in
# omarchy-plugin/install-plugin.sh and windows/install.bat.
$DataVersion = "2026.09.15"
$DataFile = "langswitcher-data-$DataVersion.tar.gz"
$DataUrl = if ($env:LANGSWITCHER_DATA_URL) { $env:LANGSWITCHER_DATA_URL }
           else { "https://github.com/$Repo/releases/download/data-$DataVersion/$DataFile" }
$DataSha256 = if ($env:LANGSWITCHER_DATA_SHA256) { $env:LANGSWITCHER_DATA_SHA256 }
              else { "ac9776dbe5a97d68cb038b3e61316f7bed7b7990232aa87cd8129000ae90feb7" }

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

# Stage everything first: the live install is only touched once the data has
# been fetched and verified, so a network failure cannot break a working setup.
$Stage = Join-Path $env:TEMP "langswitcher-stage"
if (Test-Path $Stage) { Remove-Item -Recurse -Force $Stage }
New-Item -ItemType Directory -Force -Path $Stage | Out-Null

$zip = Join-Path $env:TEMP "langswitcher.zip"
Invoke-WebRequest -Uri "https://github.com/$Repo/archive/refs/heads/$Branch.zip" -OutFile $zip
Expand-Archive -Path $zip -DestinationPath (Join-Path $env:TEMP "langswitcher-dl") -Force
$ahk = Get-ChildItem -Path (Join-Path $env:TEMP "langswitcher-dl") -Filter "LangSwitcher.ahk" -Recurse | Select-Object -First 1
if (-not $ahk) { throw "LangSwitcher.ahk not found in downloaded archive." }
Copy-Item $ahk.FullName (Join-Path $Stage "LangSwitcher.ahk") -Force

if ($env:LANGSWITCHER_DATA_DIR) {
  $words = Join-Path $env:LANGSWITCHER_DATA_DIR "words.txt"
  if (-not (Test-Path $words)) { throw "$words not found (unpack the release asset there)." }
  Write-Host "[*] Decision data $DataVersion from $($env:LANGSWITCHER_DATA_DIR) (offline)."
  Copy-Item $words (Join-Path $Stage "langswitcher-data.txt") -Force
} else {
  $tar = Join-Path $Stage $DataFile
  Invoke-WebRequest -Uri $DataUrl -OutFile $tar
  $got = (Get-FileHash -Algorithm SHA256 $tar).Hash.ToLower()
  if ($got -ne $DataSha256) {
    throw "Decision data checksum mismatch:`n  got  $got`n  want $DataSha256`nNothing was installed."
  }
  tar -xzf $tar -C $Stage words.txt
  if (-not (Test-Path (Join-Path $Stage "words.txt"))) { throw "words.txt missing from the data artifact." }
  Move-Item (Join-Path $Stage "words.txt") (Join-Path $Stage "langswitcher-data.txt") -Force
  Remove-Item $tar -Force
  Write-Host "[*] Decision data $DataVersion verified."
}

$Dst = Join-Path $env:APPDATA "LangSwitcher"
New-Item -ItemType Directory -Force -Path $Dst | Out-Null
Copy-Item (Join-Path $Stage "LangSwitcher.ahk") (Join-Path $Dst "LangSwitcher.ahk") -Force
Copy-Item (Join-Path $Stage "langswitcher-data.txt") (Join-Path $Dst "langswitcher-data.txt") -Force
Remove-Item -Recurse -Force $Stage

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
