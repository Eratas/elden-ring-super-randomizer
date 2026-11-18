# build.ps1 - build fp_regen.dll and copy it to the ERR offline DLL folder.
# Uses the GNU toolchain + WinLibs (MinGW), because the MSVC C++ toolset is not installed here.
$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$dllDir = "C:\Games\ERR\dll\offline"

# 1. Rust (install on first run, GNU host toolchain)
if (-not (Get-Command cargo -ErrorAction SilentlyContinue)) {
    Write-Host "Installing Rust (rustup, minimal, GNU)..."
    Invoke-WebRequest -Uri "https://win.rustup.rs/x86_64" -OutFile "$env:TEMP\rustup-init.exe"
    & "$env:TEMP\rustup-init.exe" -y --default-toolchain stable-x86_64-pc-windows-gnu --profile minimal
    $env:Path = "$env:USERPROFILE\.cargo\bin;$env:Path"
}

# 2. MinGW linker (WinLibs) - find gcc and put it on PATH
$gcc = Get-ChildItem "$env:LOCALAPPDATA\Microsoft\WinGet\Packages" -Filter gcc.exe -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $gcc) {
    Write-Host "Installing WinLibs (MinGW)..."
    winget install --id BrechtSanders.WinLibs.POSIX.UCRT -e --accept-package-agreements --accept-source-agreements
    $gcc = Get-ChildItem "$env:LOCALAPPDATA\Microsoft\WinGet\Packages" -Filter gcc.exe -Recurse | Select-Object -First 1
}
if (-not $gcc) { throw "MinGW gcc not found" }
$env:Path = "$(Split-Path $gcc.FullName -Parent);$env:USERPROFILE\.cargo\bin;$env:Path"

# 3. Build (GNU toolchain for host + target)
cargo +stable-x86_64-pc-windows-gnu build --release --manifest-path "$here\Cargo.toml"

# 4. Install next to the other offline natives
$src = Join-Path $here "target\release\fp_regen.dll"
if (-not (Test-Path $src)) { throw "build failed: $src not found" }
New-Item -ItemType Directory -Force -Path $dllDir | Out-Null
Copy-Item $src (Join-Path $dllDir "fp_regen.dll") -Force
Write-Host "OK -> $dllDir\fp_regen.dll"