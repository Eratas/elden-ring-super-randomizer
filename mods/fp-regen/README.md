# FP Regeneration — Mod Engine 3 native mod spec

**Goal:** give the player a slow, steady Focus Point (FP / mana) regeneration, so they are not
permanently gated behind the Cerulean Tears flask or the next Site of Grace.

**Target:** Elden Ring **1.17.3** (regulation.bin 1.17.2), Mod Engine 3.

*Last updated 2026-11-20.*

## What the install actually is (checked `C:\Games\ERR`)

`C:\Games\ERR` runs **Mod Engine 3** (`internals\modengine\bin\win64\me3.exe`), driven by the profile
`internals\modengine\err_offline.me3` (TOML, `profileVersion = "v1"`). It loads:

| kind | where | example |
|---|---|---|
| `[[natives]]` | compiled DLLs injected into the game | `reforged.dll`, `ertransmogrify.dll`, `PauseTheGame.dll` |
| `[[packages]]` | asset/param mods (file replacement) | `mod/` (regulation.bin + assets), `addons/*` |

**There is no C# runtime** — that was Mod Engine 2. So the FP regen is a **native DLL** (Rust) added
under `[[natives]]`.

## Two ways to get FP regen (pick one)

### Option A — use a proven, maintained mod (recommended)

Both are DLL mods that load in ME3 and support 1.17.2:

| mod | what it does | ME3 install |
|---|---|---|
| **NativeTweaks** ([Nexus 11339](https://www.nexusmods.com/eldenring/mods/11339)) | in-game System-menu tab with **HP/FP/Stamina regen in points per second** (+ max-stat %), supports 1.17 / 1.17.1 / 1.17.2 | extract next to the `.me3` profile, add `ERNativeUI.dll` **then** `NativeTweaks.dll` to `[[natives]]` (order matters) |
| **Auto Regen** ([Nexus 10548](https://www.nexusmods.com/eldenring/mods/10548)) | Rust DLL: passive HP/FP/Stamina regen (flat / % / % of missing), on-hit restore, out-of-combat/idle/sitting gates, F5 hot-reload | add `AutoRegen.dll` to `[[natives]]`, keep `AutoRegen.ini` next to it |

Both are **offline only** (EAC disabled). If you just want FP regen working today, install one of these
and skip the rest.

### Option B — the minimal mod in this folder (built, always-on, slow)

This folder is a complete Rust `cdylib` project (`Cargo.toml`, `src/lib.rs`) that adds a **slow,
always-on** FP regen — **1 FP per second**, no toggle, no combat gating (it only pauses while dead or
at full FP). It uses the [`eldenring` crate](https://docs.rs/eldenring) (v0.14.0) instead of hardcoded
1.17.x offsets, following the official `eldenring-rs` example's `DllMain` + `CSTaskImp` pattern.

**It is already built and installed** at `C:\Games\ERR\dll\offline\fp_regen.dll` (2.3 MB, valid PE,
`DllMain` entry point). Because it sits in `dll\offline`, the loader picks it up — no `err_offline.me3`
edit needed.

To rebuild after a change:
1. Run `.\build.ps1` — installs Rust (GNU) + WinLibs (MinGW) if missing, builds, and copies the DLL
   back to `C:\Games\ERR\dll\offline\fp_regen.dll`.
2. Tune `REGEN_PER_SEC` (default `1.0`) at the top of `src/lib.rs` and re-run.

Unsigned/experimental: test offline first.

## Why runtime, not regulation.bin

Stamina regen is hardcoded (not a `regulation.bin` value), and vanilla FP does not regenerate. `SpEffect`
*has* the fields (`changeMpRate`, `changeMpPoint`, `mpRecoverChangeSpeed`, ...) and armour has free
`residentSpEffectId` slots — but a resident effect is not guaranteed to tick, and the result cannot be
verified without in-game testing. A runtime DLL is the verifiable path and never touches
`regulation.bin`, so it composes with the Super Randomizer's output.

## Risks / caveats

- `src/lib.rs` writes FP from the game's **per-frame task** (main thread, `CSTaskImp` at
  `ChrIns_PostPhysics`), one `u32` store per tick; if the HUD ever stutters, lower `REGEN_PER_SEC`.
- The `eldenring` crate version must be pinned to one that supports 1.17.x (check crates.io).
- Single-player QoL only; disable for PvP / invasions.
- Fail-soft: if the player pointer is not ready, the tick does nothing.