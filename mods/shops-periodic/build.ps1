# build.ps1 - build shops_periodic.dll, run the host-side tests, optionally install it for Mod Engine.
#
# Uses MinGW g++ (WinLibs); result links statically like mods\loot-variants\build.ps1.
#
#   .\build.ps1            build dist\shops_periodic.dll, ship it to <repo>\dist\, run the host tests
#   .\build.ps1 -Install   ... and copy the DLL to C:\Games\ERR\dll\offline
#   .\build.ps1 -TestOnly  only compile and run the tests
#
# The DLL only reads the manifest (shops_periodic_init).  The in-game reroll (the probe step) is a
# TODO in src/shops_periodic.cpp until verify_aobs.py is run against a fresh Elden Ring.
param(
    [switch]$Install,
    [switch]$TestOnly,
    [string]$DllDir = "C:\Games\ERR\dll\offline"
)
$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$src = Join-Path $here "src"
$dist = Join-Path $here "dist"
$mods = Split-Path -Parent $here
$root = Split-Path -Parent $mods
$ship = Join-Path $root "dist"

# 1. MinGW g++: PATH first, then the WinGet package WinLibs installs into.
$gxx = $null
$cmd = Get-Command g++ -ErrorAction SilentlyContinue
if ($cmd) {
    $gxx = $cmd.Source
} else {
    $found = Get-ChildItem "$env:LOCALAPPDATA\Microsoft\WinGet\Packages" -Filter g++.exe -Recurse `
        -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($found) { $gxx = $found.FullName }
}
if (-not $gxx) {
    throw "MinGW g++ not found. Install it with: winget install --id BrechtSanders.WinLibs.POSIX.UCRT -e"
}
Write-Host "g++: $gxx"

New-Item -ItemType Directory -Force -Path $dist | Out-Null
$flags = @("-std=c++17", "-O2", "-Wall", "-Wextra", "-static", "-static-libgcc", "-static-libstdc++")

# 2. The tests first.
Write-Host "`n==> building the tests"
& $gxx @flags "-I" $src (Join-Path $src "test_shops_periodic.cpp") (Join-Path $src "manifest.cpp") `
    "-o" (Join-Path $dist "test_shops_periodic.exe")
if ($LASTEXITCODE -ne 0) { throw "test build failed" }
Write-Host "==> running the tests"
& (Join-Path $dist "test_shops_periodic.exe")
if ($LASTEXITCODE -ne 0) { throw "tests failed" }

if ($TestOnly) {
    Write-Host "`nOK (tests only)"
    exit 0
}

# 3. The DLL.
Write-Host "`n==> building shops_periodic.dll"
$dll = Join-Path $dist "shops_periodic.dll"
& $gxx @flags "-shared" "-static" (Join-Path $src "shops_periodic.cpp") (Join-Path $src "manifest.cpp") `
    "-o" $dll
if ($LASTEXITCODE -ne 0) { throw "DLL build failed" }
$size = (Get-Item $dll).Length
Write-Host ("OK -> {0} ({1:N0} bytes)" -f $dll, $size)

# The shipped location: the randomizer's installer (and the exe's dist folder) look here first.
New-Item -ItemType Directory -Force -Path $ship | Out-Null
Copy-Item $dll (Join-Path $ship "shops_periodic.dll") -Force
Write-Host ("OK -> {0}" -f (Join-Path $ship "shops_periodic.dll"))

# 4. Optionally install it next to the other offline natives.
if ($Install) {
    if (-not (Test-Path $DllDir)) {
        throw "install folder not found: $DllDir (pass -DllDir <mod>\dll\offline)"
    }
    Copy-Item $dll (Join-Path $DllDir "shops_periodic.dll") -Force
    Write-Host "OK -> $(Join-Path $DllDir 'shops_periodic.dll')"
}

# 5. Copy the sample ini (never overwrites an existing one).
if ($Install) {
    $ini = Join-Path $DllDir "shops_periodic.ini"
    if (-not (Test-Path $ini)) {
        Copy-Item (Join-Path $here "shops_periodic.ini") $ini -Force
        Write-Host "installed a fresh shops_periodic.ini"
    }
}
