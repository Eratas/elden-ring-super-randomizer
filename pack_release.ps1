# pack_release.ps1 - build the exe, build/ship the optional DLL, then zip a player-ready release.
#
#   pwsh -NoProfile -File pack_release.ps1
#
# The zip is written next to this script.  It contains only the exe, the shipped msg archives, the
# optional loot-variants and shops-periodic DLLs + sample inis, and the docs - never settings.json, randomized/ or backups/.
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

Write-Host "==> building loot_variants.dll and copying it to dist\"
& pwsh -NoProfile -File "mods\loot-variants\build.ps1"
if ($LASTEXITCODE -ne 0) { throw "native mod build failed" }

Write-Host "`n==> building the executable"
& cmd /c "build_exe.bat < nul"
if ($LASTEXITCODE -ne 0) { throw "build_exe.bat failed" }

$python = "$env:USERPROFILE\.venvs\er_mod\Scripts\python.exe"
if (-not (Test-Path $python)) { $python = "python" }
Write-Host "`n==> writing the release zip"
& $python "tools\pack_release.py"
if ($LASTEXITCODE -ne 0) { throw "pack_release.py failed" }
