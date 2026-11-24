# loot-variants — Borderlands-style weapon loot

A Mod Engine 3 native mod that makes **every pickup of the same weapon a different weapon**: fresh
affinity (stats, scaling, status build-up), fresh upgrade level and a random Ash of War that the row
can actually use.  The model, icon and moveset stay the same, so the weapon is still recognisable —
five copies of the same sword are five different swords.

It is the runtime half of the randomizer's `--loot-variants` option.  The static tool writes
`loot_variants.txt` next to `regulation.bin`; this DLL reads it and rerolls the item id at the moment
the game hands it out.  No param rows are cloned, so the regulation stays **~44 KB smaller** than a
solution that adds variant rows would need (the tool has ~76 KB of headroom against the game's
2,359,296-byte limit).

## Three separate switches

| Option | What it changes |
|---|---|
| `--random-weapon-drops` | **where** weapon rows are found (placement shuffle) |
| `--random-dropped-weapons` | **which** weapon row a drop shows (a fresh draw per run) |
| `--loot-variants` | **what that weapon rolls like on each pickup** (runtime, needs this DLL) |

They compose; none of them implies another.  `--loot-variants` alone works on a completely vanilla
regulation (every weapon still gets a random level, and every infusable weapon a random Ash).

## Install (Mod Engine 3 / Reforged offline)

The DLL is **optional**: the randomizer writes a complete regulation whether or not it is installed.

1. Build: `pwsh -NoProfile -File build.ps1`.  The tests run first, then the DLL is written to both
   `mods\loot-variants\dist\` and the program's own `dist\` folder (next to
   `EldenRingSuperRandomizer.exe`).  `build.ps1 -Install` also copies it straight to
   `C:\Games\ERR\dll\offline`.
2. Install it with the program: `randomize.py --install-runtime`, or the **Install DLL** button in
   the GUI's action bar.  Both find the DLL in `dist\`, detect `C:\Games\ERR\dll\offline`, copy the
   sample ini if you have none, and never overwrite an ini you already have.  For another layout,
   `python tools\install_runtime.py --dll-dir <mod>\dll\offline` (or `--check` to only look).
3. Run the randomizer with `--loot-variants`.  It writes `loot_variants.txt` **next to the new
   `regulation.bin`** — i.e. in your mod folder, which is the file ME3 mounts.
4. **Copy `regulation.bin` and `loot_variants.txt` together.**  The manifest's `bind` fingerprint is
   checked against the regulation at startup; a manifest from another run leaves the mod inert.
5. Launch as usual (`ReforgedLauncher.exe --offline`).  Check `loot_variants.log` next to the DLL.

The log's last line should read `active, 4 call site(s), ...`.  If it says `inert`, the reason is on
the line before it: no manifest, a stale bind, an unsupported game version, or `enabled = 0`.

## Files

```
mods/loot-variants/
  build.ps1              MinGW g++ build + host tests + optional install
  loot_variants.ini      optional overrides (roll keys are commented out by default)
  src/variant_logic.h    manifest parser + roll logic, free of Windows headers
  src/loot_variants.cpp  PE scan, call-site patch, detour, ini and logging
  src/test_variants.cpp  host-side tests for the parse and the roll
  dist/                  build output (gitignored); also copied to <repo>\dist\
tools/install_runtime.py  the --install-runtime flag and GUI button (no game data touched)
```

## The roll

For each granted weapon, `base + affinity*100 + level` becomes `base + rolled_affinity*100 +
rolled_level`:

* **affinity** is drawn from the affinity rows the manifest says exist for that weapon (up to 13).
  This is what changes attack power, scaling and status build-up.
* **level** is drawn from `0..ceiling` using loot.py's `even` / `common` / `legendary` curves; the
  ceiling is the weapon's *vanilla* one (+25 standard, +10 somber, +0 unique), not the inflated row
  count after `--somber-infusable`.
* **Ash of War** is mounted with probability `ash_chance` (manifest default 50%) from the pool of
  gems whose `canMountWep` bit fits the row's weapon type **and** whose `configurableWepAttr` bit is
  set for that affinity.  Those are the same two flags the smithing table checks, so the skill
  always animates; `--random-movesets` keeps the latter flag in sync with shuffled animations.
* **Armour** has no affinity rows, so the *piece* cannot change: rerolling the row would change the
  model.  Instead the give id's category bit (`0x10000000`) selects these entries and the runtime
  draws a new reinforcement level **+0..+10** for the same `EquipParamProtector` row.  Damage
  negation and resistances scale through `ReinforceParamProtector`, so five copies of the same helmet
  keep the same look and get five different stat blocks.  The give id is
  `0x10000000 | level << 24 | base` — the layout whose `level << 24` field is stored in each
  `ReinforceParamProtector` row.  Pieces that cannot be reinforced are omitted.  Set `[armor]
  enabled = 0` in the ini to leave armour alone.

Optional, off by default: `[auto_equip] enabled = 1` calls the game's own equip function right after
the grant, putting the rerolled piece into its head/body/arms/legs slot (the slot travels in the
manifest). It stays inert if the singleton or either function cannot be resolved. `[general]
dry_run = 1` logs `would roll …` without changing any item — useful to confirm the hook is live
before you commit to a run.
* Ammo, talismans, goods, Ashes themselves and any weapon or armour piece not in the manifest pass
  through untouched.  So do cut rows with an affinity outside 0–12.

## How the hook works

The give function is resolved from the two AOBs used by the item randomizer (verified once against
the installed 1.16.1 executable: both resolve to RVA `0x5618b0`).  Every `E8 rel32` in the game's
executable sections that targets it — four on 1.16.1 — is then found by arithmetic and repointed at
a 14-byte relay allocated within ±2 GB of the game module.  The relay jumps to the detour, which
edits the `ItemGiveStruct` in place and calls the original function.  No function prologue is moved,
so this composes with mods that hook the give function itself.  If a game update moves the function
but keeps the AOBs, the arithmetic scan still finds all callers.

The manifest carries a `bind` fingerprint of the exact `regulation.bin` it was generated from.  At
startup the DLL hashes the regulation next to the manifest and stays inert on a mismatch, so a
manifest copied from a different run (for example one with `--somber-infusable`) cannot hand out ids
whose affinity rows do not exist.  Copy both files together.  Other threads are suspended while the
four call sites are patched so no caller can read a torn displacement.

Everything is fail-soft: a missing manifest, a stale fingerprint, a version mismatch, no AOB hit, no
relay or a failed `VirtualProtect` leaves the game untouched and logs why.  The detour itself does no
allocation and never throws.

## Verification

`build.ps1` compiles and runs `dist\test_variants.exe`, which checks the manifest parser (including
malformed lines and rejected versions), the tier arithmetic against `loot.py`'s `_tier_range`, and
the roll itself (affinity membership, level ceiling, Ash pools, chance 0/100, armour level/base
preservation and pass-through).

Pass a real manifest to validate the exact file a run wrote and roll every weapon and armour piece in it:

```
dist\test_variants.exe <mod folder>\loot_variants.txt
```

The tier *selection* uses `roll < cumulative weight` while `loot.py` uses `roll <= ...`; that is a
one-in-ten-thousand boundary difference and it matches the documented weights slightly more closely.
The tier *ranges* themselves are identical, which is the part that decides which levels can appear.

**In-game behaviour is UNVERIFIED** in this environment: there is no headless way to grant an item
in Elden Ring.  The installed game's AOBs were checked statically, including the four call sites and
their shared target; the live detour needs a human to loot the same weapon a few times.

## Known limits

* Game version: the AOBs are verified on 1.16.1 (86,973,008-byte `eldenring.exe`).  A future update
  needs a fresh pattern check.
* The static level options (`--random-loot-levels`, `--loot-rarity`, `--loot-max-level`,
  `--zone-loot-levels`) still decide which level is written into the lot.  The runtime reroll then
  draws the pickup's level from the weapon's own ceiling and the curve in the manifest, so zone
  caps and boss bonuses no longer describe the *rerolled* level.  Use `[roll] level = 0` in the ini
  to keep the static levels and reroll only affinity and Ash.
* `--random-gem-skills` shuffles which skill an Ash grants *after* the manifest is written.  The pool
  (gem ids) stays valid and mountable, but a shuffled skill can have an animation that does not match
  the moveset - the same limitation the static smithing-table logic has with that option.
* The call-site patch happens on a loader thread shortly after startup.  Items granted in the first
  300 ms would miss the reroll; normal gameplay item grants happen much later.
