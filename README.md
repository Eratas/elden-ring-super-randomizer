# Elden Ring Super Randomizer

A window and a command line tool for **`regulation.bin`** — the single parameter file that holds every
item, weapon, spell, enemy drop, shop price, buff duration and flask location in Elden Ring. It rewrites
that file into a new mod folder, with a plain-text report of every change.

Written for game version **1.17.1** (Shadow of the Erdtree included) and the
[Mod Engine 2](https://www.nexusmods.com/site/mods/617) **1.4** / **ERR** mod loaders. Vanilla, the
[Item and Enemy Randomizer](https://www.nexusmods.com/eldenring/mods/12) and
[Elden Ring Reforged](https://www.nexusmods.com/eldenring/mods/11542) output all work as input, so you
can stack this on top of them.

> **What's new in v1.0.4** — weapon drops now scale upgrade level by area (an early chest is no
> longer a +25) and bosses roll better; enemy/map loot can no longer be forced onto protected
> unique items (the cause of "damaged save" from an oversized `regulation.bin`); backups are atomic
> (a crash can't truncate them); and the window wears a dark + gold theme. Full notes in the
> [Changelog](#changelog).

**Nothing is switched on when it starts.** You tick what you want, every control explains itself on
hover, options that cannot be used are greyed out, and the window remembers its size, its paths and
every setting. Current version: **1.0.4**, last updated **2026-11-20**.

```
Files and output
  Input   C:\Games\ELDEN RING\Game\regulation.bin
  Output  D:\mods\my-randomizer\regulation.bin
  Compression  kraken      Effort  max

Consumables and buffs
  [ ] Shuffle consumable effects
  [ ] Shuffle buff durations

Weapons
  [ ] Make somber weapons infusable
  [ ] Shuffle movesets
  [ ] Random default skill and affinity
  [ ] Randomize weapon stats

[Preview]  [Repack only]  [Randomize]
```

---

## Quick start

### Windows

Double-click **`randomize_gui.bat`**. It creates `%USERPROFILE%\.venvs\er_mod` on first run, installs
the two dependencies, and opens the window. A console stays behind it to show errors.

Command line:

```
randomize.bat --input "C:\Games\ELDEN RING\Game\regulation.bin" --output "D:\mods\my-mod\regulation.bin" --seed 12345 --weapons --random-loot-levels
randomize.bat --help
```

### Linux / macOS

```bash
./randomize_gui.sh                  # the window (needs python3-tk)
./randomize.sh --help
./randomize.sh --seed 12345 --weapons --dry-run
```

The venv lives at `~/.venvs/er_mod` (the project drive is exFAT and cannot hold a venv's symlinks).

### Requirements

* **Windows 10/11** for the window; Linux and macOS work through the `.sh` launchers.
* **Python 3.10 – 3.14** (the dependencies publish no wheels for 3.15 yet). The launchers find a
  suitable Python themselves; no `uv` needed.
* **tkinter** for the window — included in the python.org Windows installer, `sudo apt install
  python3-tk` on Ubuntu/WSL.
* Two dependencies only: `zstandard` (zstd output) and `cryptography` (the file's AES-256-CBC
  encryption). **`oo2core_6_win64.dll` is not a dependency** — it is RAD Game Tools' and ships with
  the game; without it the tool writes zstd instead of kraken.

### The output

A **mod folder**, not a single file:

```
D:\mods\my-mod\
  regulation.bin          <- load with Mod Engine 2 (or copy over the game's, backup first)
  msg\engus\...           <- only when weapon names are patched: ship it next to regulation.bin
  mapping.txt             <- item <- effect taken from, shop prices, sell prices, durations, flasks, start items
  weapons.txt             <- movesets, default skills, per-row stats
  gear.txt                <- armour columns, talisman rows
  loot.txt                <- which drop/chest/shop weapon got which upgrade level
  spells.txt              <- spell effects, spell stats
  drops.txt               <- enemy drop tables
  hp.txt, runes.txt       <- enemy hit points and rune drops
```

With Mod Engine 2:

```toml
[extension.regulation]
priority = 2               # higher than Fog Gate Randomizer, so it loads after it
```

Stacking with the Item and Enemy Randomizer / Fog Gate Randomizer: run their configured
`regulation.bin` through this tool. The last loaded file wins per row, and a row this tool *added* (a
synthesized somber affinity) does not exist in theirs, so their pass cannot see it.

---

## What it changes

| Area | Options |
|---|---|
| **Consumables** | every usable item (pots, greases, meats, boluses, tools, usable key items) receives another item's use effect; `shuffle` (every effect used exactly once) or `random` (repeats allowed); the use **animation** can stay with the effect, come from another item of the same class, or from any item; flasks and remembrances can join the pool; **stack sizes** shuffled; buff **durations** shuffled separately |
| **Spells** | every sorcery and incantation receives another spell's effect (one pool for both); the cast animation can stay, come from a spell with the same signature, or from any spell; **spell stats** (FP / stamina cost and requirements) randomized independently of the weapon stats |
| **Prices** | shop prices (`ShopLineupParam.value`) and sell prices (`EquipParamGoods.sellValue`) shuffled, or redrawn inside a range; sell prices optional; weapons, armour and Ashes of War can join the sell pool |
| **Shops** | every merchant slot can be filled with a random item of its own category, price untouched — every shop sells something else |
| **Weapons** | somber/unique weapons become infusable (12 affinities + Ashes of War, rows named in the game's own text); movesets shuffled (melee ↔ shields, bows among bows); default skill rolled so it animates with the row's moveset; every affinity row gets its own randomized attack, guard, requirements, scaling, status build-up and stamina cost — each group tickable on its own; **requirements stay in the weapon's own tier** so looted weapons stay usable; on-hit and holder **properties** shuffled, and on-hit **statuses** (from the game's own status pools) can be rolled true-random as well |
| **Ashes of War** | every Ash of War can receive another ash's **skill** (Lion's Claw becomes Sky Shot) and/or another ash's **on-hit effects**; donors come only from ashes that fit the same weapon types, and the two switches are independent |
| **Loot** | enemy drop tables rerolled (choose the kinds); 1…N rolls per enemy at P% each (default 3 at 10%, so most kills drop nothing); weapons in drop tables, chests, boss rewards and shops get a random upgrade level (+0…+25, somber +0…+10) with a **rarity curve**, and **bosses roll a better curve**; **rare unique weapons** and **upgrade materials** can turn up |
| **Where loot drops** | every category can be **moved between enemies** without changing the items: weapons, goods, armour, talismans, Ashes of War. Armour sets can move as a set |
| **Armour & talismans** | swap the stat columns between pieces of the same slot, roll each piece's numbers again (optionally **keeping each set coherent**), or move armour to different enemies; talismans shuffle whole rows and can move between enemies |
| **Enemies** | rune drops (`NpcParam.getSoul`) and hit points (`NpcParam.hp`) shuffled, redrawn in a range, or scaled per band; bosses can be scaled back up and their runes coupled to their hit points |
| **World** | the Flask of Crimson Tears and the Flask of Cerulean Tears move to a random pickup / boss reward / gift / merchant, and what was there goes to the first Site of Grace; start with the Spirit Calling Bell and/or the Lantern |
| **Checking a seed** | a **loot simulator** builds the tables in memory and shows what N random kills dropped, without writing or compressing anything |
| **Safety** | **backup and replace** copies your input files aside before overwriting them, and **Revert** puts them back |
| **Output** | kraken (the game's own Oodle format, needs the game's `oo2core_6_win64.dll`), leviathan, zstd (no DLL, larger), or auto; fast or maximum effort; `--repack` repairs a regulation.bin another tool wrote in a form the game rejects |

**Not included**: a character-creation / starting-class randomizer, a `regulation.bin`
**enemies-and-bosses** randomizer (that is the
[Item and Enemy Randomizer](https://www.nexusmods.com/eldenring/mods/12)'s job), connectivity / seamless
co-op, an Elden Ring installation, an unpacked game, the game's DLL.

### Static file vs. runtime mod — what "random" can mean here

`regulation.bin` is one table shared by the whole game. Every copy of a Longsword reads the same rows,
so **two copies of the same weapon can never have different stats in a static file** — that needs a
runtime mod. What this tool does instead:

* every **affinity row** of a weapon gets its own stats, so "Longsword (Heavy)" and "Longsword (Keen)"
  are different weapons (13 rows per weapon);
* the **affinity** of a dropped weapon is rerolled, so two Longsword drops usually are not the same
  weapon at all;
* the **upgrade level** of a dropped weapon is rerolled, so a drop can be +2 or +18;
* with several rolls per enemy, every kill rolls the drop table again, so the same enemy can hand you a
  different weapon each time.

That is as close to Borderlands-style loot as a static rewrite gets.

---

## The window

Eleven collapsible sections: **Files and output · Consumables and buffs · Spells · Prices and shops ·
Weapons · Ashes of War · Armour and talismans · Enemies, drops and loot · Where loot drops · Flasks and
starting items · Advanced.**

* **Presets** — a dropdown in the title bar loads a whole coherent set of options in one click; any
  manual change turns the box into **Custom**. Save your own with *Save preset*, move them between
  installs with *Export / Import* in the Advanced section, delete them with *Delete* (built-ins cannot be
  deleted).
* **Backup and replace** (Files and output, on by default) — before the generated file replaces your
  input, the tool copies every file it is about to overwrite into a timestamped
  `backups\<date-time>\` folder next to the program, with a `manifest.json` recording where each file
  came from. **Revert** restores the most recent one; the twenty newest are kept. Turn the option off to
  write only to the output folder and leave your files alone. Details below.
* **Open output folder** — opens the output folder in Explorer.
* **Loot simulator** — pick how many kills (1–200) and a seed; it builds the tables with the settings
  currently ticked and lists what those kills dropped, weapon affinity and upgrade level included.
  Nothing is written, nothing is compressed, so it costs seconds. The safe way to judge a seed.
* **Find** next to the input field, the Oodle DLL and the text-archive folder searches this machine
  (Steam library, the usual Games folders, mod folders) and fills the field with the first hit; the
  others land in the dropdown.
* **Language** — the **Aa** dropdown, top right. It changes the window only: reports, console output and
  the game text stay in English. English plus thirteen complete packs: German, Spanish, French, Italian,
  Dutch, Polish, Portuguese (Brazil), Swedish, Finnish, Russian, Japanese, Korean, Simplified Chinese.
  Adding one more is a single file, `tools/lang_<code>.py` — anything missing falls back to English per
  string, so a half-finished pack still runs. Start in a given language with
  `python tools/gui.py --lang pt`.
* **Log** — a toggle in the title bar; the log costs no height until you ask for it. *Copy log* copies
  everything the run printed.
* **Hover help** on every control: what it does in plain language, an example, then what it does under
  the hood (tables, fields, limits). It appears instantly and stays while the pointer is on it.
* **While a run is going**: a progress bar through every pass, the current pass, an elapsed clock.
  A two-minute maximum-effort compression looks like work, not a freeze.
* **The command line** the window will run is shown at the bottom — click it to copy. What you see is
  exactly what runs.
* **Preview** runs everything and shows the reports without writing a file; **Repack only** rewrites the
  input unchanged. Pressing *Randomize* with nothing ticked asks first, because the result would be a
  recompressed copy of the input.
* Size, position, open sections, the last paths and every option value are saved in `settings.json`
  next to the program. The window opens **centred** on the screen; the output folder you last used for an
  input file is offered again when you pick that input.
* The page scrolls, but the progress bar, command line, status line and buttons are packed **below** the
  scrolling area, not inside it, so nothing can end up behind the taskbar however the window is resized
  or maximized.

---

## Presets

| Preset | What it is for |
|---|---|
| **Gentle start** | consumables, spells, prices and buffs only. The safest first run. |
| **Classic randomizer** | the traditional set: effects and prices. Weapons stay as they are. |
| **Borderlands loot** | any enemy drops any weapon at a random affinity, upgrade level and stat roll, 3 rolls per kill. |
| **Loot and stats** | weapons get new movesets, skills and stats, and every weapon can drop anywhere. |
| **Armor and talismans** | armour numbers shaken and rolled, sets coherent, armour and talismans lootable anywhere. |
| **Ashes of War** | every ash gets another ash's skill and effects, and ashes drop from any enemy. |
| **Prices only** | what shops charge and pay. Nothing else. |
| **Boss rush** | runes and hit points redrawn, bosses roll the best upgrade curve, every enemy always drops. |
| **Boss hunt** | enemy HP redrawn but bosses scaled back up (1.5–2× HP and runes), runes coupled to HP. |
| **Level 1 run** | level 1 beginnings: every weapon and where it drops is random, but nothing is cruel. |
| **Balanced** | weapons and enemies tuned for an even, playable run. |
| **Glass cannon** | enemies hit much harder but die much faster. |
| **Full chaos** | every pass on. Expect a very different game and a slow compression. |
| **Vanilla-ish loot texture** | the usual 3 rolls at 10% per enemy, and a rare unique occasionally comes along with the ordinary loot. |
| **Event loot texture** | bigger drops: every enemy gets 5 rolls at 25%, and uniques are more common. |
| **Generous loot texture** | very rich loot: every enemy gets 8 rolls at 30%, and uniques are common. |

The bundles live in `presets.py`.

---

## How a run works

1. Decrypt `regulation.bin` (AES-256-CBC; the key is published by the modding community and a new key
   per version is added in `tools/erreg.py`), decompress the DCX (KRAK/zstd/DFLT) and read the BND4 of
   param files.
2. Parse only the tables it needs, from the paramdef XMLs in `tools/paramdef/`.
3. Run the passes in a fixed order — the random generator is shared, and some passes read what another
   is about to change: buff durations → consumable effects → stack sizes → prices → enemy runes → enemy
   hit points → enemy drops → shop stock → weapons → ashes of war → armour and talismans → loot shuffle →
   loot levels → weapon names → spells → flasks → starting items → boss scaling. The full table, with the
   tables and flags each pass touches, is below.
4. Rebuild the BND4, recompress (kraken via the game's own `oo2core_6_win64.dll`, or zstd) and
   re-encrypt with the same AES IV the file had.

The reports are generated from the same data structures, so `mapping.txt` is the exact list of what was
changed. **One seed, reproducible**: the seed is printed at the top of every report, and the same seed
with the same options produces a byte-identical file.

### The passes in detail

The order below is `tools/phases.py`; `tools/test_phases.py` fails if the engine or the window ever drifts
from it. Keep this table in step with that file.

| # | Pass | Table(s) | Option |
|---|---|---|---|
| 1 | buff durations | `SpEffectParam` | `--random-durations`, `--duration-mode`, `--duration-min/max` |
| 2 | consumable effects | `EquipParamGoods` | `--goods` / `--no-goods`, `--mode`, `--split-anim`, `--include-flasks`, `--include-remembrances` |
| 3 | stack sizes | `EquipParamGoods` | `--goods-quantity` |
| 4 | prices | `ShopLineupParam`, `EquipParamGoods` | `--random-prices`, `--price-mode`, `--price-min/max`, `--sell-prices`, `--sell-min/max`, `--sell-equipment` |
| 5 | enemy runes | `NpcParam.getSoul` | `--random-runes`, `--rune-mode`, `--rune-min/max` |
| 6 | enemy hit points | `NpcParam.hp` | `--random-enemy-hp`, `--hp-mode`, `--hp-min/max` |
| 7 | enemy drops | `ItemLotParam_enemy` (+ map, shops, goods, equipment for the pool) | `--random-enemy-drops`, `--enemy-drop-rolls`, `--enemy-drop-chance`, `--enemy-drop-kinds` |
| 8 | shop stock | `ShopLineupParam` | `--random-shop-stock`, `--shop-stock-kinds` |
| 9 | weapons | `EquipParamWeapon` (+ Gem, SwordArts, Reinforce, AttackElementCorrect) | `--somber-infusable`, `--random-movesets`, `--random-default-ash`, `--random-stats`, `--random-weapon-effects`, `--random-weapon-holder-fx`, `--random-weapon-status-effects` |
| 10 | ashes of war | `EquipParamGem` | `--random-gem-skills`, `--random-gem-effects` |
| 11 | armour, talismans | `EquipParamProtector`, `EquipParamAccessory` | `--random-armor`, `--random-armor-fresh`, `--armor-keep-sets`, `--random-talismans` |
| 12 | loot shuffle | `ItemLotParam_enemy` + map, `ShopLineupParam` | `--random-weapon-drops`, `--random-goods-drops`, `--random-armor-drops`, `--random-talisman-drops`, `--random-ashes-drops`, `--armor-drop-sets` |
| 13 | loot levels | `ItemLotParam_enemy`, `ItemLotParam_map`, `ShopLineupParam` | `--random-loot-levels`, `--loot-rarity`, `--loot-boss-bonus`, `--loot-max-level`, `--zone-loot-levels` |
| 14 | weapon names | `item_dlc02.msgbnd.dcx` | `--weapon-names`, `--no-weapon-names` |
| 15 | spells | `Magic` | `--spells` / `--no-spells`, `--mode`, `--split-anim`; `--spell-stats` runs inside this pass |
| 16 | flask locations | `ItemLotParam_map`, `ItemLotParam_enemy`, `ShopLineupParam` | `--random-flask-locations`, `--flask-where` |
| 17 | starting items | item lot 2000 (`ItemLotParam_map`) | `--start-with-bell`, `--start-with-lantern` |
| 18 | boss scaling | `NpcParam` | `--boss-hp-scale`, `--boss-rune-scale`, `--couple-runes-to-hp`, `--boss-min-runes` |
| — | loot simulation | reads the tables, writes nothing | `--simulate N` |

`--repack` runs none of them: it rewrites the input unchanged, which repairs a file another tool wrote in
a form the game rejects. **Everything is off by default** — every pass has to be asked for — and the only
defaults are the paths and `kraken` + `max` compression.

---

## Reference

### Consumables and spells

`EquipParamGoods` rows are eligible when they are usable from the inventory:

* `goodsType` 0 (consumable) or 1 (key item), and 3 (remembrance) only with `--include-remembrances`;
* `refCategory` 1 (bullet) or 2 (SpEffect) and a real `refId_default`;
* `opmeMenuType` 0 or 1 (using it does not open a menu — this removes fingers, effigies, whistles);
* `disable_offline` clear (multiplayer-only items are skipped);
* `isSummonHorse` clear (the Spectral Steed Whistle keeps its lit / unlit pair);
* an icon and a sort id (removes unused and placeholder rows);
* `suppleType` 0 (flasks) only with `--include-flasks`.

Excluded by id: 2070 (Lantern — its two states are two SpEffects, not one effect).

**What moves.** The "effect" of an item is a bundle of 56 fields: the reference (`refCategory`,
`refId_default`, `refId_1`, `spEffectCategory`, `refVirtualWepId`), the behaviour and effects
(`behaviorId`, `sfxVariationId`), the item's own animation and sounds, and every consumption /
restriction / multiplayer flag. The bundle moves as a whole, so a pot that receives "spit out a crystal
tear" also receives the animations and restrictions that belong to that effect.

`--split-anim` splits the animation out of the bundle (`goodsUseAnim`, `castSfxId`, `fireSfxId`,
`sfxVariationId`, `isEnableFastUseItem` come from a second donor):

* `none` — no split, the animation travels with the effect.
* `same` — the donor's `refCategory` equals the effect donor's. Thrown items release a bullet, applied /
  eaten items apply a SpEffect; the two have different TAE events, so the animation has to come from the
  same class. If a category has fewer donors than receivers, the donors are reused — a graceful
  degradation, not an error.
* `any` — any pool item can donate the animation. A pot may then be eaten, a fist thrown, a grease
  swallowed. **Untested in game**: the item may play no animation, or refuse to be used.

**Assignment: `shuffle` vs `random`.**

* `shuffle` builds a permutation of the pool with no fixed point: every effect is used exactly once and
  no item keeps its own. The *multiset* of effects is preserved, so the game remains winnable and no
  effect is duplicated.
* `random` lets every item draw a donor independently, so effects repeat and some items keep what they
  had.

Spells share the pool: sorceries and incantations are one list (`Magic` rows with `charaInit` 1 or 4,
effects excluded by `quality = 255` / `isForceMagic = 2`), so a glintstone spell can end up as an
incantation and vice versa. They are a section of their own: `--spells` moves what a spell *does*
(a shuffle: one derangement of the pool, so every effect is used exactly once and no spell keeps its
own), and `--spell-stats` re-rolls what it *costs* (FP, stamina, requirements). The two are independent:
a spell whose effect was shuffled can keep its vanilla cost, and `--spell-stats` works on its own,
without the shuffle. `--stat-groups spells` is still accepted for old command lines.

**Stack sizes (`--goods-quantity`).** `EquipParamGoods.maxNum` is how many of an item a pickup or a
purchase gives, `maxRepositoryNum` how many you can carry. Both move together from one stackable item to
another, so the pair stays consistent and no item asks for more than it can hold. Only rows that already
stack take part.

**Buff durations.** `SpEffectParam.effectEndurance` (seconds) of every effect that is a timed buff:
greases, meats, blessings, buff spells. An effect below 5 seconds is treated as a mechanic (holy water
pots, the frenzy seal, cures) and never touched, whatever its id.

### Prices

* **Buy prices** — `ShopLineupParam.value` of every goods slot priced in runes (`equipType` 3,
  `costType` 0), whatever the slot sells. Because the *slot* is priced, not the item, shops another
  randomizer filled are included.
* **Sell prices** — `EquipParamGoods.sellValue` of every named row that can be sold (`sellValue > 0`;
  -1 is unsellable and stays). Buy and sell prices are drawn independently, so an item may sell for more
  than a shop asks. `--no-sell-prices` keeps sell prices vanilla.
* **`--sell-equipment`** — one pool each for weapons (`EquipParamWeapon`, base rows only, every affinity
  row of a weapon gets the same new price), armour (`EquipParamProtector`) and Ashes of War
  (`EquipParamGem`). Rows with `sellValue <= 0` stay.

`shuffle` permutes the prices that exist; `range` draws log-uniform values between the limits, rounded to
two significant digits so they still look like shop prices.

### Weapons

**Somber weapons become infusable (`--somber-infusable`).** A somber or unique weapon has one row; a
normal weapon has 13 (no affinity + 12 affinities). The pass adds the missing 12 rows with fresh ids
(`base + 100 … base + 1200`, or `+10000 …` when that range is taken), copies the base row's model, icon,
behaviour, materials, price and skill mount, and sets the affinity fields (`gemMountType` 0,
`materialSetId` -1, `disableMultiUse` 0). The new ids are named in the game's text (`--weapon-names`) and
appear at smithing tables (gem effect 600 = "affinity unchanged"). Masterwork armour goes through
`ReinforceParamProtector`. Rows that already have 13 variants are left alone (DLC somber weapons such as
the Milady's Sword), so running the tool twice on the same file is safe.

**Movesets (`--random-movesets`).** Every randomized melee row takes another row's `wepType`,
`atkParamId` and `behaviorVariationId` — the moveset and the attack behaviour. Shields only swap with
shields and never take a weapon moveset, because a left-hand shield must keep `isShield` / the guard
behaviour or it attacks instead of blocking. Bows swap among bows / crossbows / ballistas, with the ammo
fields (`atkParamId` + 10000 / 20000) and the arrow rows left alone.

* `affinity` — every affinity row draws its own moveset; Standard can keep the weapon's own
  (`--keep-standard-moveset`).
* `bound` — movesets are grouped by attack category into per-affinity clusters (sword / thrust / axe /
  hammer / spear / fist); each cluster owns `--moveset-variety` categories and rows of that affinity draw
  from them. Every Ash of War lists 12 affinities it can animate, so a row only gets a moveset the Ash can
  animate.
* `weapon` — one moveset per weapon, chosen from the pool that suits its attack category.

`wepType follows` also works in the other modes: the row takes the donor's `wepType`, which is what the
smithing table reads. It is untested against the game's save checks.

**Default skill (`--random-default-ash`).** Every weapon row gets a random default skill
(`gemMountType` 3, gem effect 500) chosen from the Ashes of War that animate with the row's moveset — 115
ashes across 22 weapon types. It also rerolls the **affinity** of the weapons handed out by item lots, map
lots, shops and starting classes, which is what makes two copies of the same weapon play differently.

**Stats (`--random-stats`).** Every weapon and affinity row (bows and catalysts included) is randomized
per group:

* **attack** — physical plus the four elemental attacks, each a roll around the original share of the row
  (Element Correct rows are added when a row starts using an element, ids from 90000000);
* **guard** — the guard damage the weapon takes when it blocks;
* **requirements** — STR/Dex/Int/Fai/Arc, including the negative requirements DLC weapons use;
* **scaling** — the five saturations, with weapon types restricted to the stats they can use (an int
  weapon never gets STR/DEX scaling);
* **effects** — critical, stance, stamina and guard damage, status build-up;
* **stamina** — the stamina multiplier, normalized so the first light attack costs the weapon's base cost
  times the multiplier whatever moveset the row carries;
* **spells** — FP and stamina cost and the requirements of sorceries and incantations.

Only the groups you list (`--stat-groups`, empty = all) are rolled. `--req-mode` bounds how far
requirements may drift from vanilla: `tight` (default), `normal`, `wild`. `--stamina-rate lo,hi` sets the
multiplier range.

**Ashes of War (`EquipParamGem`).** Two fields matter in play: `swordArtsParamId` — the **skill** itself
(Lion's Claw, Sky Shot, …) — and `spEffectId0..2` — the **on-hit effects** (bleed, frostbite, a buff).
Both are permuted *inside groups of gems that accept the same weapon types*: the group key is the
`configurableWepAttr` bitfield (24 bits), so a skill never lands on a weapon that could not use it. The
effect triple moves as a unit (slot 0 is the primary effect) and the skill moves on its own, so the two
switches are independent.

### Armour and talismans

* **`--random-armor` (Shuffle armor stats)** permutes 18 columns of `EquipParamProtector` *inside each
  slot* (head / body / arms / legs never mix): the eight damage-negation rates the equipment screen shows,
  the seven status resistances, `saDurability`, `toughnessCorrectRate` and `weight`. Only values the game
  already uses are dealt out, so nothing becomes absurd. Elden Ring armour has no flat defence
  (`defensePhysics` is zero in 1.17.1), so those fields are not touched.
* **`--random-armor-fresh` (Randomize armor stats)** rolls each piece's numbers again instead of swapping
  them: every column is drawn uniformly between the lowest and highest value that column has inside the
  piece's own slot.
* **`--armor-keep-sets` (Keep armor sets together)** makes that roll coherent: the four pieces of a set
  (found from the name without its trailing piece word — Knight Helm, Knight Armor, Knight Gauntlets,
  Knight Greaves) are scaled by one factor per column instead of being rolled separately.
* **`--random-armor-drops` (Move armor to random enemies)** changes only *where* armour drops. One-time
  flag drops are never moved. **`--armor-drop-sets`** moves the pieces of a set as a unit.
* **`--random-talismans` (Shuffle talismans)** permutes whole `EquipParamAccessory` rows: every talisman
  keeps its name and icon and receives another one's effect and numbers. There is no paramdef for that
  table here, so whole rows move rather than single fields — which is why the icon can belong to a
  different talisman than the name.
* **`--random-talisman-drops`** is the talisman version of the drop shuffle.

### Loot upgrade levels (`--random-loot-levels`)

A weapon id is `base + affinity * 100 + upgrade`. In vanilla every weapon in a drop table, chest or shop
is +0. This pass rewrites only the upgrade digits, in enemy drop tables (the lots an
`NpcParam.itemLotId_enemy` points at, plus their consecutive rows), map lots (the rows in
`names/item_locations.txt`), and weapon shops.

The level is drawn between 0 and the ceiling read from the **pristine** weapon table: 25 for a weapon with
affinity rows, 10 for a somber weapon (one row and `materialSetId != -1`), 0 for a unique weapon that
cannot be reinforced. Because the ceiling is read before the weapon pass adds its rows,
`--random-loot-levels` must be combined with a pristine input to be exact.

**Rarity (`--loot-rarity`).** Drawing every level with the same probability makes +25 a one-in-26 event.
A tier is picked first, then the level is drawn uniformly inside that tier, as a fraction of the weapon's
own ceiling:

| Curve | +0..+3 | +4..+9 | +10..+15 | +16..+20 | +21..+25 |
|---|---|---|---|---|---|
| `even` | 100% spread evenly | | | | |
| `common` (default) | 55% | 28% | 12% | 4% | 1% |
| `legendary` | 70% (+0..+2) | 20% (+3..+8) | 7% (+9..+14) | 2.5% (+15..+20) | 0.5% (+21..+25) |

A drop at 80% or more of its weapon's ceiling is marked with a star in `loot.txt`, a drop at 90% or more is
announced as `LEGENDARY` at the top of the report, and the best twelve of the seed are listed at the end.
Because the tiers are fractions, the same curve works for a +25 weapon and a +10 somber one.

**Bosses (`--loot-boss-bonus`).** Bosses roll from a better curve. An enemy counts as a boss when its
`NpcParam.isSoulGetByBoss` flag is set; `--boss-min-runes N` additionally treats every enemy worth N runes
or more in the unmodified game as one.

| Setting | Ordinary enemies | Bosses |
|---|---|---|
| `same` | chosen curve | chosen curve |
| `better` (default) | chosen curve | the next curve up (even → common → legendary) |
| `best` | chosen curve | always legendary |

Map lots and shops always use the chosen curve. `--zone-loot-levels` scales the ceiling by area, so an
early chest is not a +25 weapon: Limgrave / Weeping Peninsula stay low, Liurnia / Caelid / Altus mid,
Mountaintops / Haligtree / Farum Azula high, the Land of Shadow at the full ceiling. `--loot-max-level N`
caps every drop at +N (0 = no cap).

### Enemies and drops

* **`--random-enemy-drops`** — reroll every enemy's drop table. Each enemy gets `--enemy-drop-rolls`
  independent rolls (default 3), each dropping at `--enemy-drop-chance` percent (default 10), so the
  default is 0.3 items per kill and roughly seven kills in ten drop nothing. `--enemy-drop-rolls 0`
  restores the old shape: the first row always drops and later rows keep their chance. The pool is every
  named goods row (no key items), every weapon / armour / talisman / Ash of War row with a real name and a
  price, with weapons normalized to +0 and flasks excluded. Rows that already hold a key item
  (`goodsType` 1) and one-time flag awards are left alone. `--enemy-drop-kinds` restricts the categories.
* **`--enemy-drop-rolls N` / `--enemy-drop-chance P`** — N independent rolls per enemy, each dropping at
  P%, so a kill drops 0…N items (N·P/100 on average). The added rows take ids above every existing one;
  the game caps a lot at 64 rows, and the tool refuses to add a row that would cross that cap.
* **`--unique-drops` / `--unique-rate`** — `--unique-drops` is the switch: off (the default), no random
  drop is ever a unique weapon. On, every item that actually drops rolls the rate: a whole percent from
  1 to 20 (default 3). The rate is per dropped item, not per roll, so at the default 3 × 10% drop
  settings it yields about 0.9 uniques per 100 kills. Upgrade material drops roll first, so with both on
  the effective unique rate is slightly lower.
* **`--random-enemy-hp`** — `NpcParam.hp` of every enemy with hit points: `shuffle`, `range`, `bands`
  (weak / normal / strong tiers), or `balanced` (every enemy stays within 0.75–1.5× vanilla).
* **`--random-runes`** — `NpcParam.getSoul`: `shuffle`, `range`, or `bands`.
* **`--boss-hp-scale lo,hi` / `--boss-rune-scale lo,hi`** — multiply boss HP / rune bounties by a factor
  drawn from the range (1.0,1.0 = off), so bosses stay worth the fight after a shuffle.
* **`--couple-runes-to-hp`** — recompute rune bounties from the (randomized) HP, keeping each enemy's
  original rune-per-HP ratio. Runs after the rune pass, so it overrides it.

### Flasks and starting items

* **`--random-flask-locations`** — the Flask of Crimson Tears (lot 2000) and the Flask of Cerulean Tears
  (lot 2001) move to a random real location: a boss / field boss / evergaol reward, an NPC gift or
  corpse, a legacy dungeon or overworld pickup, or a merchant slot. What was there goes into the flask's
  own lot, which is what the first Site of Grace hands out. Chance drops, map fragments, one-time-flag
  rows and DLC map areas are never used. `--flask-where` restricts them to `overworld` or `early`.
* **`--start-with-bell` / `--start-with-lantern`** — add the Spirit Calling Bell / the Lantern to lot
  2000, which the game hands out at the start.

### Weapon names

`--somber-infusable` adds 12 rows per somber weapon. Without names the game shows "?" for them, so the
pass writes a name and a description into `msg/<language>/item_dlc02.msgbnd.dcx` for every row that has
none: the name is the base weapon's name with the language's own affinity affix (learned from the archive
itself, "Heavy " in English), and the description is the base row's. Ids already in the archive are never
overwritten. With Mod Engine 2 the `msg` folder goes next to `regulation.bin`; the file is written next to
the output, never over its source. If the text archive is missing the rows are named "?" and the tool says
so — a missing vendor degrades, it never crashes.

---

## Backups and revert

When **Backup and replace** is on (the default), a run that would overwrite your files first copies them
aside:

```
<program>\backups\20261119-204453\
  00_regulation.bin
  01_item_dlc02.msgbnd.dcx
  manifest.json          <- which file goes back where
```

The originals keep their bytes and timestamps. **Revert** (next to the *Backup* button) restores the most
recent backup: every file in it goes back to where it came from. The 20 newest backups are kept, older ones
are pruned automatically. A revert with a missing or corrupt manifest fails softly and says so rather than
guessing. **Backup** makes a backup on demand, without running anything.

Turn the option off (**--no-backup-replace**) to write only to the output folder and leave your input
files untouched. The tool never writes into the input's own folder unless you asked it to replace it.

---

## Compression and the size limit

* **kraken / leviathan** — the game's own Oodle format, written through `oo2core_6_win64.dll` (RAD Game
  Tools', shipped with the game, never with this tool). `leviathan` writes an Oodle Leviathan stream under
  the same KRAK tag; `OodleLZ_Decompress` detects the codec from the stream.
* **zstd** — no DLL needed, but the game only accepts a 64 KB window (`--zstd-window 16`; other values are
  kept for experiments and can crash it), which makes the file about 35% larger.
* **effort** — `max` (Oodle level 9) is the default and the only safe one for a file that starts big.
  `fast` (level 3) costs seconds and gives a noticeably larger file.
* **auto** — kraken when the DLL is found, zstd otherwise. If the DLL is missing and stdin is a terminal,
  the tool asks for the path instead of silently falling back.

The game refuses a `regulation.bin` above **2,359,296 bytes** (`0x240000`) and reports corrupted save
data. The tool refuses to write one and tells you how far over it is.

Measured on this machine (2026-11-19, kraken, `--oodle-dll` set, limit 2,359,296 B):

| Input | Passes | Effort | Output | Time |
|---|---|---|---|---|
| vanilla (2,045,728 B) | none (`--repack`) | max | **1,365,104 B** | 159.1 s |
| vanilla | none (`--repack`) | fast | 1,631,424 B | 0.7 s |
| vanilla | all, seed 999 | max | **1,629,936 B** | 159.3 s |
| vanilla | all, seed 999 | fast | 1,968,528 B | 6.8 s |
| ERR (3,031,632 B) | none (`--repack`) | max | **2,011,824 B** | 220.8 s |
| ERR | none (`--repack`) | fast | 2,408,048 B — **refused**, 48,752 B over | 0.8 s |
| ERR | all, seed 999 | max | **2,327,328 B** | 227.7 s |

Two things follow. A maximum-effort run costs **two to four minutes**, and the progress bar, current pass
and elapsed clock show that it is working. And on a file that starts big, `fast` can produce something the
game will not load — which is why the window ships with **kraken + maximum effort**.

### Elden Ring Reforged (ERR)

[ERR](https://www.nexusmods.com/eldenring/mods/11542) is a total conversion mod: new enemies, weapons,
items and bosses. It ships as a Mod Engine 2 mod folder, and like every mod of that kind it carries its own
`regulation.bin` — **3,031,632 B**, which is 963 KB bigger than vanilla and already **672 KB over the
game's 2,359,296-byte limit** before this tool touches it. That is why the size of the file matters so
much here.

Stacking it on ERR:

1. Point **Input** at `C:\Games\ERR\mod\regulation.bin` (keep a copy of that folder first, or leave
   *Backup and replace* on).
2. Leave **Output** in its own new folder.
3. Either replace `mod\regulation.bin` with the new file, or add the new folder as a second mod in Mod
   Engine 2 with a **higher priority** than ERR's entry — the last one loaded wins per row.
4. If you ticked *Make somber weapons infusable*, copy the generated `msg\engus` folder next to the
   `regulation.bin` you load, or the added affinity rows show a placeholder name.

---

## Command line

Every option is documented by `randomize.bat --help` / `randomize.sh --help`. The flags, the window's
labels, its defaults and its dependencies all come from one table (`tools/options.py`), so the window
cannot offer a switch the CLI does not have. The shape:

```
randomize.py --input <regulation.bin> --output <regulation.bin>
             [--seed N] [--compression {auto,kraken,zstd,leviathan}]
             [--compression-level {fast,max}] [--oodle-dll PATH]
             [--repack] [--dry-run] [--no-reports] [--brief-reports]
             [--backup-replace | --no-backup-replace]
             [--max-size BYTES] [--simulate N] [--zstd-window 16..22]
             <pass switches>
```

Useful combinations:

```
randomize.bat --repack --input <broken.bin> --output <fixed.bin>     # repair a file the game rejects
randomize.bat --seed 12345 --weapons --dry-run                       # try a seed, write nothing
randomize.bat --goods --spells --random-prices --sell-prices         # the classic set
randomize.bat --simulate 200 --random-loot-levels --seed 999         # what would 200 kills drop?
```

`--dry-run` runs every pass and prints the reports but writes no file; `--simulate N` builds the tables
and prints N random kills.

---

## Building the executable

```bat
build_exe.bat
```

Needs PyInstaller (installed automatically into the same venv). The result is
`dist\EldenRingSuperRandomizer.exe` (Linux/macOS: `dist/EldenRingSuperRandomizer`) plus `dist\msg\` next
to it — ship both, and the user adds the game's `oo2core_6_win64.dll`.

The build embeds PE version metadata from `tools/version_info.txt` (company, product name, file/product
version). Keep its version tuple in step with `tools/version.py`: `tools/test_logic.py` fails if the two
drift.

---

## Antivirus notes

Antivirus engines and Microsoft SmartScreen flag unsigned PyInstaller executables more than almost any
other kind of file, because the packer's runtime behaviour (a one-file binary unpacking itself into a
temporary folder and running from there) looks like a dropper. The result is a false positive, not a real
detection — but it still stops users from running the tool. What lowers the risk, cheapest first:

1. **Code signing (the real fix).** Sign `EldenRingSuperRandomizer.exe` with an Authenticode certificate
   (`signtool sign /fd sha256 /a EldenRingSuperRandomizer.exe`). A valid signature, especially with a
   reputation-building EV certificate, clears SmartScreen and most AV heuristics.
2. **The build already embeds PE version metadata.** A generic binary with no version resource looks
   machine-generated and is flagged hardest; a file that declares who built it and what it is gives
   reputation systems something to key on.
3. **`--noupx` is already set.** UPX-packed executables are a classic AV trigger; leaving it off is
   correct. Do not add it back.
4. **Consider `--onedir` for distribution.** A one-*folder* build does not unpack itself into `%TEMP%` at
   run time, so it avoids the dropper heuristic entirely and is markedly friendlier to AV than the
   current `--onefile`. The trade-off is that you ship a folder instead of a single file.
5. **If a specific engine still flags it**, submit the file as a false positive to that vendor (Microsoft:
   the Security Intelligence / Defender submission portal). Do not disable AV or add exclusions to work
   around a detection — sign the binary instead.

The tool is fully offline: it makes no network requests, downloads nothing, and runs nothing but the
game's own `oo2core_6_win64.dll` that the user already has.

---

## Compatibility and limits

* Param layout of game **1.17.1** (format2D 0x85). Another version fails loudly with
  `row size … != paramdef row size …` instead of writing garbage.
* `oo2core_6_win64.dll` (kraken) is RAD Game Tools' and is never shipped.
* The output must stay under `0x240000` bytes (2,359,296); the tool reports the remaining bytes and
  refuses to write more.
* Adding param rows (`--somber-infusable`) keeps ids and names consistent; the rows it adds are named in
  the game's own text archives (`--weapon-names`, on by default with that option).
* `--split-anim any`, `wepType follows` and the per-affinity movesets are **untested against the game's
  own save checks** — they are the parts most likely to need a save-file test before a long playthrough.
* Only as lawful as your use of the game: randomizing single-player content you own is fine; do not
  redistribute the game's files or DLL.

## Changelog

**1.0.4** — 2026-11-20 — loot upgrade caps no longer overshoot when `--loot-max-level` meets
`--zone-loot-levels`; one-time and key-item drops are protected in the loot shuffle; backups are
written atomically (a crash can no longer leave a half-written file over your original); the window
wears a dark, gold-trimmed Elden Ring palette; and a synthetic pass test suite plus a stricter ruff
gate guard all of it.

**1.0.3** — 2026-11-19 — the thirteen boss tips, the KRAK decode fix, and three new test groups.

**1.0.2** — 2026-11-19 — rebuild with the corrected boss tooltip.

## Development

Source layout, the option table, the gate and the checks that keep it honest: see
[DEVELOPMENT.md](DEVELOPMENT.md).

The short version:

```bat
python tools\gate.py        rem byte-compile + packs + phases + nexus description + logic tests
python tools\test_logic.py --fuzz <regulation.bin>   rem the same tests against a real file
```

`gate.py` runs, in order: byte-compile every `tools/*.py`, `check_packs.py --min-tip 120
--strict-structure`, `test_phases.py`, `test_packs.py`, `md2nexus.py --check`, and `test_logic.py`. Exit
code 0 means all green.

**Nexus Mods takes BBCode, not Markdown** — it has no Markdown support and none is planned — so the mod
page is generated from this file:

```bat
python tools\md2nexus.py    rem rewrite NEXUS_DESCRIPTION.txt + NEXUS_DESCRIPTION.strict.txt
```

Never edit either file by hand. Two artifacts come out of the same README: `NEXUS_DESCRIPTION.txt` wraps
fenced blocks in the `code` tag (what Nexus's own converters emit), and `NEXUS_DESCRIPTION.strict.txt`
wraps them in a quote block instead, because `code` is the one tag this renderer emits that the Nexus
wiki does not document. The two are byte-identical apart from those 11 wrappers. The gate re-renders both
and fails if either drifts, so the description on the mod page cannot silently go stale.