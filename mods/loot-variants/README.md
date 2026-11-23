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

1. Build: `pwsh -NoProfile -File build.ps1 -Install`
   (or `build.ps1` and copy `dist\loot_variants.dll` yourself).
2. Run the randomizer with `--loot-variants`.  It writes `loot_variants.txt` **next to the new
   `regulation.bin`** — i.e. in your mod folder, which is the file ME3 mounts.
3. The DLL goes in the same place as the other offline natives, e.g.
   `C:\Games\ERR\dll\offline\loot_variants.dll`.  The manifest does **not** need copying: the mod
   searches its own folder, every parent folder and the `<mod>` folder for `loot_variants.txt`.
4. Launch as usual (`ReforgedLauncher.exe --offline`).  Check `loot_variants.log` next to the DLL.

The log's last line should read `active, 4 call site(s), ...`.  If it says `inert`, the reason is on
the line before it: no manifest, unsupported game version, or `enabled = 0` in the ini.

## Files

```
mods/loot-variants/
  build.ps1              MinGW g++ build + host tests + optional install
  loot_variants.ini      optional overrides (roll keys are commented out by default)
  src/variant_logic.h    manifest parser + roll logic, free of Windows headers
  src/loot_variants.cpp  PE scan, call-site patch, detour, ini and logging
  src/test_variants.cpp  host-side tests for the parse and the roll
  dist/                  build output (gitignored)
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
* Ammo, armour, talismans, goods, Ashes themselves and any weapon not in the manifest pass through
  untouched.  So do cut rows with an affinity outside 0–12.

## How the hook works

The give function is resolved from the two AOBs used by the item randomizer (verified once against
the installed 1.16.1 executable: both resolve to RVA `0x5618b0`).  Every `E8 rel32` in the game's
executable sections that targets it — four on 1.16.1 — is then found by arithmetic and repointed at
a 14-byte relay allocated within ±2 GB of the game module.  The relay jumps to the detour, which
edits the `ItemGiveStruct` in place and calls the original function.  No function prologue is moved,
so this composes with mods that hook the give function itself.  If a game update moves the function
but keeps the AOBs, the arithmetic scan still finds all callers.

Everything is fail-soft: a missing manifest, a version mismatch, no AOB hit, no relay or a failed
`VirtualProtect` leaves the game untouched and logs why.  The detour itself does no allocation and
never throws.

## Verification

`build.ps1` compiles and runs `dist\test_variants.exe`, which checks the manifest parser (including
malformed lines and rejected versions), the tier arithmetic against `loot.py`'s `_tier_range`, and
the roll itself (affinity membership, level ceiling, Ash pools, chance 0/100 and pass-through).

Pass a real manifest to validate the exact file a run wrote and roll every weapon in it:

```
dist\test_variants.exe <mod folder>\loot_variants.txt
```

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
