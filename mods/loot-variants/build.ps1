# build.ps1 - build loot_variants.dll, run the host-side tests, optionally install it for Mod Engine.
#
# Uses MinGW g++ (WinLibs), because the MSVC C++ toolset is not installed on this machine.  The
# result is self-contained: libgcc, libstdc++ and winpthreads are linked statically, so the DLL needs
# nothing but the Windows UCRT that Elden Ring already loads.
#
#   .\build.ps1             build dist\loot_variants.dll, ship it to <repo>\dist\, run the host tests
#   .\build.ps1 -Install    ... and copy the DLL to C:\Games\ERR\dll\offline
#   .\build.ps1 -TestOnly   only compile and run the tests
#
# The copy in <repo>\dist\ is what the randomizer's --install-runtime flag and GUI button look for.
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
    $found = Get-ChildItem "$env:LOCALAPPDATA\Microsoft\WinGet\Packages" -Filter g++.exe -Recurse -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if ($found) { $gxx = $found.FullName }
}
if (-not $gxx) {
    throw "MinGW g++ not found. Install it with: winget install --id BrechtSanders.WinLibs.POSIX.UCRT -e"
}
Write-Host "g++: $gxx"
& $gxx --version | Select-Object -First 1

New-Item -ItemType Directory -Force -Path $dist | Out-Null
$flags = @("-std=c++17", "-O2", "-Wall", "-Wextra", "-static", "-static-libgcc", "-static-libstdc++")

# 2. The tests first: a broken roll must never produce a DLL that goes into the game.
Write-Host "`n==> building the tests"
& $gxx @flags "-I" $src (Join-Path $src "test_variants.cpp") "-o" (Join-Path $dist "test_variants.exe")
if ($LASTEXITCODE -ne 0) { throw "test build failed" }
Write-Host "==> running the tests"
& (Join-Path $dist "test_variants.exe")
if ($LASTEXITCODE -ne 0) { throw "tests failed" }

if ($TestOnly) {
    Write-Host "`nOK (tests only)"
    exit 0
}

# 3. The DLL.
Write-Host "`n==> building loot_variants.dll"
$dll = Join-Path $dist "loot_variants.dll"
& $gxx @flags "-shared" (Join-Path $src "loot_variants.cpp") "-o" $dll
if ($LASTEXITCODE -ne 0) { throw "DLL build failed" }
$size = (Get-Item $dll).Length
Write-Host ("OK -> {0} ({1:N0} bytes)" -f $dll, $size)

# The shipped location: the randomizer's installer (and the exe's dist folder) look here first.
New-Item -ItemType Directory -Force -Path $ship | Out-Null
Copy-Item $dll (Join-Path $ship "loot_variants.dll") -Force
Write-Host ("OK -> {0}" -f (Join-Path $ship "loot_variants.dll"))
Write-Host "install it with: randomize.py --install-runtime   (or the GUI's Install DLL button)"

# 4. Optionally install it next to the other offline natives.
if ($Install) {
    if (-not (Test-Path $DllDir)) {
        throw "install folder not found: $DllDir (pass -DllDir <mod>\dll\offline)"
    }
    Copy-Item $dll (Join-Path $DllDir "loot_variants.dll") -Force
    $ini = Join-Path $DllDir "loot_variants.ini"
    if (-not (Test-Path $ini)) {
        Copy-Item (Join-Path $here "loot_variants.ini") $ini -Force
        Write-Host "installed a fresh loot_variants.ini"
    }
    Write-Host "OK -> $(Join-Path $DllDir 'loot_variants.dll')"
    Write-Host "the randomizer writes loot_variants.txt next to regulation.bin; the mod finds it from there"
}
