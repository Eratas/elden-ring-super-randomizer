# Development

Running the randomizer from source, and the checks that keep it honest. For what the tool does and how to
use it, see [README.md](README.md).

## Requirements

* **Python 3.10–3.14** (developed on 3.14, which `.python-version` pins). Tk must be available (on
  Windows, tick *tcl/tk and IDLE* in the python.org installer; on Linux, `sudo apt install python3-tk`).
  **3.15 is not supported**: `zstandard` publishes no 3.15 wheel, so pip falls back to a source build
  (needs MSVC) and the install fails; `findpython.bat` and the launchers deliberately skip it.
* Two dependencies only: `zstandard` (zstd output) and `cryptography` (the file's AES-256-CBC
  encryption). `oo2core_6_win64.dll` is **not** a dependency: it is RAD Game Tools' and ships with the
  game; without it the tool writes zstd instead of kraken.

## Set up a virtual environment

```bat
rem Windows (cmd)
python -m venv "%USERPROFILE%\.venvs\er_mod"
"%USERPROFILE%\.venvs\er_mod\Scripts\python.exe" -m pip install -r tools\requirements.txt
```

```bash
# Linux / macOS
python3 -m venv ~/.venvs/er_mod
~/.venvs/er_mod/bin/python -m pip install -r tools/requirements.txt
```

`build_exe.bat` creates this same venv if it is missing, so the commands above are only needed to run from
source.

## Run

```bat
python tools\gui.py                rem the window
python tools\randomize.py --help   rem the command line
randomize_gui.bat                  rem the window, using the venv above
```

## The gate

```bat
python tools\gate.py               rem byte-compile + packs + phases + contract + nexus + logic + synthetic + lint
```

`gate.py` runs, in order: byte-compile every `tools/*.py`, `check_packs.py --min-tip 120
--strict-structure` (the language packs), `test_phases.py` (the progress bar cannot drift from the
engine), `test_packs.py` (keys, placeholders, paragraphs, choices), `md2nexus.py --check` (the Nexus
description matches the README), `test_logic.py`, `test_passes_synthetic.py` (the weapons / gems /
gear / spells / goods / shops / enemy-drop passes on a built regulation), and `lint.py` (ruff's
pyflakes + syntax checks). Exit code 0 means all green.

Against a real `regulation.bin` (slow, needs the game's DLL for the kraken round-trip):

```bat
python tools\test_logic.py --fuzz "C:\Games\ELDEN RING\Game\regulation.bin"
```

## Linting

`tools/lint.py` runs ruff's real-bug checks (pyflakes `F` + syntax `E9`) over `tools/`. Ruff is a dev
tool, not a runtime dependency, so the lint step is *skipped* (not failed) when it is not installed:

```bat
pip install -r requirements-dev.txt    rem installs ruff (dev only; the tool itself needs requirements.txt)
python tools\lint.py             rem or directly: python -m ruff check tools\ --select F,E9
```

`gate.py` runs it as its last step, so a green gate also means no undefined names (an annotation that
references a module that was never imported), unused locals, or f-strings without a placeholder
slipped in.

## The Nexus description

Nexus Mods' description editor takes **BBCode, not Markdown** (there is no Markdown support and none is
planned), so the mod page cannot be a copy of README.md. It is generated instead:

```bat
python tools\md2nexus.py            rem rewrite NEXUS_DESCRIPTION.txt + NEXUS_DESCRIPTION.strict.txt
python tools\md2nexus.py --check    rem what the gate runs: fail if either file is stale
python tools\md2nexus.py --stdout   rem print the normal render
python tools\md2nexus.py --stdout --strict-tags   rem ... the wiki-tags-only render
```

Two artifacts, identical except for the fenced-block wrapper and the callout:

| File | Fenced blocks | Callout (`> …`) | Use it when |
|---|---|---|---|
| `NEXUS_DESCRIPTION.txt` | `[code]` | `[quote]` | normal case — it is what Nexus's own Markdown→BBCode converters emit |
| `NEXUS_DESCRIPTION.strict.txt` | `[quote]` | plain paragraph | you want zero risk on a first upload: `[code]` is the one emitted tag the Nexus wiki does not document |

The strict render leaves the callout unwrapped on purpose: `[quote]` is its fenced-block tag there, and
two indistinguishable `[quote]` blocks would make the raw file unreadable. The count is exact — the
strict file carries one `[quote]` per fenced block and no other.

Never hand-edit either file; edit `README.md` and re-run the generator. The renderer only
emits tags from the Nexus wiki's list (plus `[code]`), refuses any other tag, refuses leftover Markdown
outside a fenced block, and refuses unbalanced BBCode — `test_logic.test_nexus_doc` checks the mapping,
those invariants, the strict variant, and the staleness of both checked-in files. A fuzz test
(`test_md2nexus_fuzz`) generates random Markdown and asserts the render always satisfies the invariants.

## What the tests pin

`test_logic.py` covers the behaviour that would otherwise fail *silently* in the field:

* `dropshuffle.set_plan` — armour sets stay coherent (the test calls the production function; a
  hand-written copy of the branch once diverged from it on 200 of 200 seeds while both "passed");
* `dropshuffle` protection — `shuffle()` leaves a one-time flagged drop and a row holding a key item
  untouched, and the items it does move stay conserved (a permutation);
* loot upgrade caps and rarity tiers — `--loot-max-level` with `--zone-loot-levels` never collapses a
  zone's cap to 0 (which would roll the full ceiling), and the half-open tiers cover every upgrade
  level with none double-counted;
* `erreg` round-trips — DCX (zstd + deflate), AES-256-CBC encrypt/decrypt, and a BND4 rebuilt
  byte-for-byte from the shipped `msg` archive;
* `erreg` robustness — truncated or corrupt input fails as a clean `ValueError`, never a raw
  `struct.error` / `IndexError`, and never the `read_bnd4` name-scan hang;
* **the options round trip** — `dict -> argv -> dict` for every option, and again over 600 random
  *combinations* of options (`test_argv_fuzz`). The window builds the command line with
  `options.argv_from_values()` and runs it verbatim, so an option that function forgets to emit looks
  ticked in the window and does nothing in the engine. `--goods`, `--spells`, `--loot-rarity` and
  `--no-backup-replace` all shipped that way once;
* empty pools — `new_prices`, the price passes and `talkmsg.read_fmg` must report "nothing to do", not
  crash on a regulation.bin that does not fill them;
* `version.py` vs `version_info.txt` — the window footer and the exe's PE resource must not drift.

`test_passes_synthetic.py` builds a small regulation in memory (real paramdefs, a few weapon types,
40 distinct Ashes of War, armour and talisman rows, a handful of sorceries, enemy lots and a boss) and
drives every randomizer pass over it: `--somber-infusable`, the three `--random-movesets` modes,
`--random-default-ash`, the weapon-effect switches (`--random-weapon-onhit-shuffle`,
`--random-weapon-holder-shuffle`, `--random-weapon-status-roll`, `--random-loot-effects`),
`--random-stats`, the gem / armour / talisman / spell / goods / shop passes, an FMG write/read round
trip, the enemy-drop and HP passes, a same-seed determinism check, and the degenerate cases (too few
Ashes, a single moveset, a regulation with no timed buffs) failing soft.

## Layout

* `tools/options.py` — the option table (flags, labels, hints, defaults, dependencies) **and** the
  argv builder. The window and the command line are both generated from it, so they cannot disagree.
* `tools/phases.py` — the run's passes in order; `randomize.py`, the window and the README table all read
  from it.
* `tools/tips.py` — the English hover text of every option.
* `tools/lang_<code>.py` — the translated window text; `tools/check_packs.py` gates them.
* `tools/version.py` — the version shown in the window footer; bump it here **and** the version tuple in
  `tools/version_info.txt` (a test fails if they drift).
* Naming: option **keys** and CLI flags use US spelling (`armor_variants`, `--armor-variants`), while
  labels, tips and docs use UK spelling (`armour`). Keep that split for new options; the older
  `armour_keep_sets` key is the historical exception.
* `tools/randomize.py` — the engine: parse, run the passes, write the output and the reports.
* `tools/backup.py` — backup-and-replace, revert and backup pruning.
* `tools/test_logic.py` — the logic tests above; also used by `gui.py --self-test` inside the frozen exe.
  Add `--self-test-headless` to skip the message box and get a real exit code in scripts / CI.
* `tools/test_passes_synthetic.py` — the randomizer passes (weapons, gems, gear, spells, goods, shops,
  enemy-drops) on a built regulation; part of the gate (`tools/gate.py`).
* `tools/loot_variants.py` — the per-pickup manifest (weapon affinities/Ash, armour levels and stat
  clones) and its `bind` fingerprint over the written regulation.
* `tools/armor_variants.py` — clones `EquipParamProtector` rows with the same appearance and selected
  stat columns; the runtime picks one per pickup.
* `tools/rarity_labels.py` — text rarity tags in the patched item-name archives.
* `tools/install_runtime.py` — the `--install-runtime` flag and the window's Install DLL button.
* `tools/pack_release.py` — the additive release-zip whitelist; `pack_release.ps1` drives the whole
  build order: `mods/loot-variants/build.ps1` → `build_exe.bat` → `python tools/pack_release.py`.
* `mods/loot-variants/` — the optional native mod: `build.ps1` builds the DLL and host tests, `src/`
  holds the PE hook, manifest parser and roll logic. The DLL is shipped in `dist/` for releases.

## Runtime mod: loot-variants

`regulation.bin` is one table shared by the whole game, so a static rewrite cannot give two copies of
the same sword different stats. The optional DLL is the only path to **per-pickup** variety. The static
tool writes `loot_variants.txt` next to the regulation; the DLL reads it and rerolls the give id at the
moment the game grants the item. Without the DLL the regulation is still a complete random run — the
manifest is simply unused.

Three switches stay separate and compose:

| Switch | What it changes |
|---|---|
| `--random-weapon-drops` | **where** weapon rows are found (placement shuffle) |
| `--random-dropped-weapons` | **which** weapon row a drop shows (a fresh draw per run) |
| `--loot-variants` | **what that weapon rolls like on each pickup** (runtime, needs this DLL) |

Build with `pwsh -NoProfile -File mods/loot-variants/build.ps1`: host tests run first, then the DLL is
written to `mods/loot-variants/dist/` and the program's `dist/`. Add `-Install` to copy it straight to
`C:\Games\ERR\dll\offline`. From the shipped program, `randomize.py --install-runtime` or the window's
**Install DLL** button finds the DLL in `dist/` and copies the sample ini without overwriting an
existing one; `python tools/install_runtime.py --dll-dir <dir>` handles another layout and `--check`
only looks.

**The roll.** For each granted weapon, `base + affinity*100 + level` becomes
`base + rolled_affinity*100 + rolled_level`. Affinity comes from the rows the manifest says exist for
that weapon (up to 13) — that is what changes attack power, scaling and status build-up. Level is drawn
from `0..ceiling` using the `even`/`common`/`legendary` curves, where the ceiling is the weapon's
*vanilla* one (+25 standard, +10 somber, +0 unique), not the inflated row count after
`--somber-infusable`. An Ash is mounted with probability `ash_chance` (manifest default 50%) from gems
whose `canMountWep` bit fits the row's weapon type **and** whose `configurableWepAttr` bit is set for
that affinity — the same two flags the smithing table checks, so the skill animates. Armour has no
affinity rows, so the runtime draws a reinforcement level +0..+10 for the same row with give id
`0x10000000 | level << 24 | base`; `--armor-variants N` adds up to N cloned rows that keep the model
and change only the columns selected by `--armor-variant-stats`, each with a `ProtectorName` entry.
Ammo, goods, Ashes, cut rows outside affinity 0..12 and anything absent from the manifest pass through
untouched. `[auto_equip] enabled = 1` calls the game's equip function after the grant (off by default);
`[general] dry_run = 1` logs `would roll ...` without changing anything.

**The hook.** Both give-call AOBs used by the item randomizer are resolved (verified on 1.16.1:
both target RVA `0x5618b0`). Every `E8 rel32` in the executable sections that targets it — four on
1.16.1 — is found by arithmetic and repointed at a 14-byte relay allocated within ±2 GB of the game
module. The relay jumps to a detour that edits the `ItemGiveStruct` in place and calls the original; no
prologue is moved, so it composes with other give-function hooks. Other threads are suspended while
the four call sites are patched so no caller reads a torn displacement. The manifest carries a `bind`
fingerprint (FNV-1a over the written `regulation.bin`); a mismatch leaves the DLL inert, so a manifest
from a different run cannot hand out ids whose rows do not exist. Everything is fail-soft: missing
manifest, stale fingerprint, version mismatch, no AOB hit, no relay or a failed `VirtualProtect`
leaves the game untouched and logs why. The detour itself does no allocation and never throws. The
log's last line should read `active, N call site(s), ...`; `inert` and the line before it give the
reason.

**After a game update**, run `python tools\verify_aobs.py` (optionally `--exe <path>`). It checks all
five patterns, including that both give patterns still resolve to the same target, and prints file
offsets for hits. A `FAIL` on a give pattern means that call site is skipped; the DLL is inert only if
**both** give patterns fail. A failure on one of the other three patterns only disables auto-equip.
Copy the new pattern and call offset into `src/loot_variants.cpp`, rebuild with `build.ps1 -Install`,
then re-run the verifier and the host tests. Offsets are file offsets; the DLL works in memory, so
only the pattern and the call offset inside it need updating. Version gate: the DLL accepts manifest
format v1/v2 only — a future v3 writer needs a DLL update.

**Verification.** `build.ps1` runs `dist\test_variants.exe`, which checks the manifest parser (malformed
lines, rejected versions), tier arithmetic against `loot.py::_tier_range`, and the roll itself
(affinity membership, level ceiling, Ash pools, chance 0/100, armour level/base preservation,
pass-through). Pass a real manifest as an argument to validate that exact run and roll every item in
it. Tier *selection* uses `roll < cumulative weight` while `loot.py` uses `roll <= ...` — a
one-in-ten-thousand boundary difference that matches the documented weights more closely; the tier
*ranges* are identical.

**Known limits.** AOBs are verified on 1.16.1 (86,973,008-byte `eldenring.exe`). The static level
options still decide what is written into the lot; the reroll draws from the weapon's own ceiling, so
zone caps and boss bonuses no longer describe the *rerolled* level (`[roll] level = 0` keeps static
levels and rerolls only affinity and Ash). `--random-gem-skills` shuffles a skill after the manifest is
written, so a shuffled skill's animation can mismatch the moveset. The call sites are patched shortly
after startup; items granted in the first 300 ms miss the reroll. **In-game behaviour is UNVERIFIED**
in this environment: no headless way to grant an item exists, so the live detour, auto-equip, armour
clone ids and rarity-label rendering need a human play session (`dry_run = 1` first).

## Optional mod: fp-regen

`mods/fp-regen/` is a standalone Rust `cdylib` spec (not built by the main release, not shipped in the
zip) that adds a slow, always-on **1 FP/second** regenerator for Mod Engine 3 / Reforged offline. It
uses the [`eldenring` crate](https://docs.rs/eldenring) (v0.14.0) with the `DllMain` + `CSTaskImp`
pattern instead of hardcoded 1.17.x offsets. `pwsh -NoProfile -File mods/fp-regen/build.ps1` installs
Rust (GNU) + MinGW if missing, builds, and copies the DLL to `C:\Games\ERR\dll\offline\fp_regen.dll`;
tune `REGEN_PER_SEC` at the top of `src/lib.rs`. Prefer a maintained mod when you just want the
feature: NativeTweaks ([Nexus 11339](https://www.nexusmods.com/eldenring/mods/11339)) or Auto Regen
([Nexus 10548](https://www.nexusmods.com/eldenring/mods/10548)); both are offline-only. Caveats: the
tick writes one `u32` from the game's per-frame task (lower the rate if the HUD stutters), the crate
must be pinned to a version supporting 1.17.x, disable for PvP, and the tick no-ops until the player
pointer is ready. Runtime rather than `regulation.bin` because vanilla FP does not regenerate and a
resident `SpEffect` cannot be verified without in-game testing; it never touches the regulation, so
it composes with randomizer output.

## Runtime mod: shops-periodic

Optional second DLL (`mods/shops-periodic/`) for Borderlands-style merchant stock: reroll the items on
offer **while** the game runs. `tools/shops.py::periodic_manifest()` writes `shops_periodic.txt` next
to `regulation.bin` on every `--random-shop-stock` run:

```
bind <regulation size> <fnv1a64>       # refuse a manifest from another regulation, like loot-variants
every <minutes>                        # the manifest default (15); ini can override
pool <cat> <id> <id> ...               # curated items for one category (1..5)
shop <block idx> <slot id> <cat> ...   # the sellable slots of one merchant block
```

`src/manifest.h` + `manifest.cpp` parse that file; `build.ps1` compiles `dist/test_shops_periodic.exe`
(self-contained fixture, or pass a real manifest as an argument) and then `dist/shops_periodic.dll`,
copying the DLL into the program's `dist/`. `tools/install_runtime.py --kind shops_periodic` (or the
GUI's **Install shops DLL** button) finds the DLL, asks for the Mod Engine `dll/offline` folder when
discovery fails, and copies the sample ini without overwriting an existing one. The ini has
`[general] enabled` and `every_minutes` (default 15, matching the manifest).

**Status: staged.** The DLL parses the manifest and starts a periodic tick; the write that changes the
game's in-memory `ShopLineupParam.equipId` is marked `--probe-step--` in `src/shops_periodic.cpp` and
is deliberately inert. A game update or a new AOB set has to be verified before that step is enabled:
run `python tools\verify_aobs.py` against `eldenring.exe` and add the shop-menu function's pattern and
target before wiring the write. Until then the DLL never changes game data. In-game periodic reroll is
**UNVERIFIED**; the parser is tested on the host (12 blocks and 5 pools from a real manifest).