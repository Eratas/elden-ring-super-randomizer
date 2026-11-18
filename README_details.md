# Elden Ring Randomizer — details

Everything the tool does, pass by pass, plus the file layout and the design notes behind the parts that
look arbitrary. The short version is in [README.md](README.md).

```
tools/
  gui.py            window entry point (thin: it starts ui/app.py)
  randomize.py      command line entry point: parses options, runs the passes, writes the reports
  options.py        the one table of every option: flag, label, default, group, dependencies
  tips.py           the hover text of every option: plain language, an example, then the details
  settings.py       not a module: settings.json next to the program (window state, last paths)
  erreg.py          regulation.bin: AES, DCX, BND4, PARAM/BND4/BND, paramdef XML
  oodle.py          oo2core_6_win64.dll (Kraken / Leviathan) through ctypes
  textarchives.py   where the game's text archives are, and which copy to patch
  talkmsg.py        FMG (text table) read/write inside a msgbnd archive
  gear.py           armour columns (EquipParamProtector) and talisman rows (EquipParamAccessory)
  gems.py           Ash of War skills and on-hit effects (EquipParamGem)
  goods.py          consumable stack sizes (EquipParamGoods.maxNum)
  dropshuffle.py    move one category of loot between the places it drops
  loot.py           random upgrade levels on drops, chests and shops, with a rarity curve
  enemy_drops.py    enemy drop tables, enemy hit points, and the loot simulator
  weapons.py        somber affinities, movesets, default skills, per-affinity stats
  weapon_names.py   names and descriptions for the rows weapons.py adds
  spells.py         spell effects and spell stats (Magic)
  runes.py          enemy rune drops (NpcParam.getSoul)
  durations.py      buff durations (SpEffectParam.effectEndurance)
  flasks.py         where the two flasks are (ItemLotParam_map)
  start_items.py    starting items (item lot 2000)
  locations.py      builds names/item_locations.txt: the map lots and shop slots that really exist
  ui/               window: theme.py (colours), widgets.py (hover help, scroll page, sections), app.py
  paramdef/         the field tables of the params this tool reads
  names/            Paramdex row names for the reports
  msg/engus/        item_dlc02.msgbnd.dcx — the weapon-name text archive
  findpython.bat    prints the Python command the launchers should use (3.10–3.14)
```

---

## 1. What a pass can and cannot do

A `regulation.bin` is a set of tables of **rows**. Every copy of an item in the game reads the same
row, so a static rewrite can change what an item *is*, never what one *copy* is. Two consequences run
through the whole tool:

* **Rows can be added** (a somber weapon gains the 12 affinity rows a normal weapon has) and **fields
  can be permuted** (every affinity row gets its own attack values), but a single row cannot hold two
  different outcomes.
* **Drops are rolled by the game.** An `ItemLotParam_enemy` row says "this enemy may drop this item at
  this chance". Give an enemy several rows and the game rolls each one, which is the only way to get
  per-kill variety out of a static file.

What that means for the "Borderlands" feel:

| Wish | Static rewrite | Why |
|---|---|---|
| same weapon, different stats per copy | no | one row is shared by every copy |
| same weapon, different stats per **affinity** | yes | 13 rows per weapon, each with its own numbers (`--random-stats`) |
| a drop can be +2 or +18 | yes | the upgrade level is part of the item id in the drop row (`--random-loot-levels`) |
| the same enemy drops different things each kill | yes | several drop rows, each rolled on every kill (`--enemy-drop-rolls`) |
| a piece of armour with other numbers | yes | every column is permuted (`--random-armor`) |

---

## 2. The passes, in order

The order is not cosmetic: all passes draw from one `random.Random`, and some read values another pass
is about to change. Changing the order changes every seed.

| # | Pass | Table(s) | Option |
|---|---|---|---|
| 1 | buff durations | `SpEffectParam` | `--random-durations`, `--duration-mode`, `--duration-min/max` |
| 2 | goods effects | `EquipParamGoods` | `--goods` / `--no-goods`, `--mode`, `--split-anim`, `--include-flasks`, `--include-remembrances` |
| 3 | shop prices | `ShopLineupParam`, `EquipParamGoods` | `--random-prices`, `--price-mode`, `--price-min/max`, `--sell-prices`, `--sell-min/max`, `--sell-equipment` |
| 4 | enemy runes | `NpcParam.getSoul` | `--random-runes`, `--rune-mode`, `--rune-min/max` |
| 5 | enemy hit points | `NpcParam.hp` | `--random-enemy-hp`, `--hp-mode`, `--hp-min/max` |
| 6 | enemy drops | `ItemLotParam_enemy` (+ `ItemLotParam_map`, `ShopLineupParam`, `EquipParamGoods`, equipment tables for the pool) | `--random-enemy-drops`, `--enemy-drop-rolls`, `--enemy-drop-chance` |
| 7 | weapons | `EquipParamWeapon` (+ Gem, SwordArts, Reinforce, AttackElementCorrect) | `--somber-infusable`, `--random-movesets`, `--random-default-ash`, `--random-stats` |
| 8 | ashes of war | `EquipParamGem` | `--random-gem-skills`, `--random-gem-effects` |
| 9 | armor, talismans | `EquipParamProtector`, `EquipParamAccessory` | `--random-armor`, `--random-armor-fresh`, `--random-talismans` |
| 10 | loot shuffle | `ItemLotParam_enemy` + map, `ShopLineupParam` | `--random-armor-drops`, `--random-talisman-drops` |
| 11 | loot upgrade levels | `ItemLotParam_enemy`, `ItemLotParam_map`, `ShopLineupParam` | `--random-loot-levels`, `--loot-rarity` |
| 12 | weapon names | `item_dlc02.msgbnd.dcx` | `--weapon-names`, `--no-weapon-names` |
| 13 | spell effects | `Magic` | `--spells` / `--no-spells`, `--mode`, `--split-anim` |
| 14 | spell stats | `Magic` | `--spell-stats` |
| 15 | flask locations | `ItemLotParam_map`, `ItemLotParam_enemy`, `ShopLineupParam` | `--random-flask-locations` |
| 16 | starting items | item lot 2000 (`ItemLotParam_map`) | `--start-with-bell`, `--start-with-lantern` |
| 17 | loot simulation | reads the tables, writes nothing | `--simulate N` |

`--repack` runs none of them: it rewrites the input unchanged, which repairs a file another tool wrote
in a form the game rejects. **Everything is off by default** – `--goods`, `--spells` and every other pass
have to be asked for – and the only defaults are the paths and `kraken` + `max` compression.

---

## 3. Consumables and spells

### The pool

`EquipParamGoods` rows are eligible when they are usable from the inventory:

* `goodsType` 0 (consumable) or 1 (key item), and 3 (remembrance) only with `--include-remembrances`;
* `refCategory` 1 (bullet) or 2 (SpEffect) and a real `refId_default`;
* `opmeMenuType` 0 or 1 (using it does not open a menu — this removes fingers, effigies, whistles);
* `disable_offline` clear (multiplayer-only items are skipped);
* `isSummonHorse` clear (the Spectral Steed Whistle keeps its lit / unlit pair);
* an icon and a sort id (removes unused and placeholder rows);
* `suppleType` 0 (flasks) only with `--include-flasks`.

Excluded by id: 2070 (Lantern — its two states are two SpEffects, not one effect).

### What moves

The "effect" of an item is a bundle of 56 fields: the reference (`refCategory`, `refId_default`,
`refId_1`, `spEffectCategory`, `refVirtualWepId`), the behaviour and effects (`behaviorId`,
`sfxVariationId`, `sfxVariationId`), the item's own animation and sounds, and every consumption /
restriction / multiplayer flag. The bundle moves as a whole, so a pot that receives "spit out a
crystal tear" also receives the animations and the restrictions that belong to that effect.

`--split-anim` splits the animation out of the bundle: `goodsUseAnim`, `castSfxId`, `fireSfxId`,
`sfxVariationId` and `isEnableFastUseItem` are then taken from a second donor.

* `none` — no split, the animation travels with the effect.
* `same` — the donor's `refCategory` equals the effect donor's. Thrown items release a bullet, applied /
  eaten items apply a SpEffect; the two have different TAE events, so the animation has to come from the
  same class. If a category has fewer donors than receivers (more receivers than thrown items), the
  donors are reused, which is a graceful degradation, not an error.
* `any` — any pool item can donate the animation. A pot may then be eaten, a fist thrown, a grease
  swallowed. **Untested in game** (2026-10-17): the item may play no animation, or refuse to be used.

### Assignment: `shuffle` vs `random`

* `shuffle` builds a permutation of the pool with no fixed point: every effect is used exactly once and
  no item keeps its own. That also means the *multiset* of effects is preserved — the game remains
  winnable and no effect is duplicated.
* `random` lets every item draw a donor independently, so effects repeat and some items keep what they
  had.

Spells share the pool: sorceries and incantations are one list, so a glintstone spell can end up as an
incantation and vice versa (`Magic` rows with `charaInit` 1 or 4, effects excluded by
`quality = 255` / `isForceMagic = 2`). They are a section of their own, separate from the
consumables: `--spells` moves what a spell *does*, `--spell-stats` re-rolls what it *costs* (FP,
stamina, requirements). The two are independent switches, so a spell whose effect was shuffled can
keep its vanilla cost, and `--stat-groups spells` is still accepted for old command lines.

### Stack sizes (`--goods-quantity`)

`EquipParamGoods.maxNum` is how many of an item a pickup or a purchase gives, and `maxRepositoryNum` is
how many you can carry. Both are moved together from one stackable item to another, so the pair stays
consistent and no item ends up asking for more than it can hold. Only rows that already stack take part
(650 of the 2 184 named goods rows on 1.17.1).

### Buff durations

`SpEffectParam.effectEndurance` (seconds) of every effect that is a timed buff: greases, meats,
blessings, buff spells. An effect with `effectEndurance` below 5 seconds is treated as a mechanic (holy
water pots, the frenzy seal, cures) and never touched, whatever its id. `shuffle` permutes the
durations, `range` draws new ones between the limits.

---

## 4. Prices

* **Buy prices** – `ShopLineupParam.value` of every goods slot priced in runes (`equipType` 3,
  `costType` 0), whatever the slot sells. Because the slot is priced, not the item, shops that another
  randomizer filled with other items are included.
* **Sell prices** – `EquipParamGoods.sellValue` of every named row that can be sold (`sellValue > 0`;
  -1 is unsellable and stays). Buy and sell prices are drawn independently, so an item may sell for more
  than a shop asks for it. `--no-sell-prices` keeps sell prices vanilla.
* **`--sell-equipment`** – one pool each for weapons (`EquipParamWeapon`, base rows only, every affinity
  row of a weapon gets the same new price), armour (`EquipParamProtector`) and Ashes of War
  (`EquipParamGem`). Rows with `sellValue <= 0` stay.

`shuffle` permutes the prices that exist; `range` draws log-uniform values between the limits, rounded to
two significant digits so they still look like shop prices.

---

## 5. Weapons

### Somber weapons become infusable (`--somber-infusable`)

A somber or unique weapon has one row; a normal weapon has 13 (no affinity + 12 affinities). The pass
adds the missing 12 rows with fresh ids (`base + 100 … base + 1200`, or `+10000 …` when that range is
taken), copies the base row's model, icon, behaviour, materials, price and skill mount, and sets the
affinity fields (`gemMountType` 0, `materialSetId` -1, `disableMultiUse` 0). The new ids are named in
the game's text (`--weapon-names`) and appear at smithing tables (gem effect 600 = "affinity
unchanged"). Masterwork armour goes through `ReinforceParamProtector`.

Rows that already have 13 variants are left alone (DLC somber weapons such as the Milady's Sword do),
so running the tool twice on the same file is safe.

### Movesets (`--random-movesets`)

Every randomized melee row takes another row's `wepType`, `atkParamId` and `behaviorVariationId`, i.e.
the moveset (animation set) and the attack behaviour. Shields only swap with shields and never take a
weapon moveset, because a left-hand shield must keep `isShield` / the guard behaviour or it attacks
instead of blocking. Bows swap among bows / crossbows / ballistas, with the ammo fields
(`atkParamId` + 10000 / 20000) and the arrow rows left alone.

* `affinity` — every affinity row draws its own moveset; Standard can keep the weapon's own
  (`--keep-standard-moveset`).
* `bound` — movesets are grouped by attack category into per-affinity clusters (sword / thrust / axe /
  hammer / spear / fist); each cluster owns `--moveset-variety` categories and rows of that affinity draw
  from them. Every Ash of War lists 12 affinities it can animate, and this mode guarantees that a row
  only gets a moveset the Ash can animate.
* `weapon` — one moveset per weapon, chosen from the pool that suits its attack category, and the
  `wepType` follows (so the smithing table only offers animations that exist).

`wepType follows` also works in the other modes: the row takes the donor's `wepType`, which is what the
smithing table reads. It is untested against the game's save checks.

### Default skill (`--random-default-ash`)

Every weapon row gets a random default skill (`gemMountType` 3, gem effect 500) chosen from the Ashes of
War that animate with the row's moveset — 115 ashes across 22 weapon types. It also rerolls the
**affinity** of the weapons handed out by item lots, map lots, shops and starting classes, which is what
makes two copies of the same weapon play differently.

### Stats (`--random-stats`)

Every weapon and affinity row (bows and catalysts included) is randomized per group:

* **attack** – physical plus the four elemental attacks, each a roll around the original share of the row
  (Element Correct rows are added when a row starts using an element, ids from 90000000);
* **guard** – the guard damage the weapon takes when it blocks;
* **requirements** – STR/Dex/Int/Fai/Arc, including the negative requirements DLC weapons use;
* **scaling** – the five saturations, with weapon types restricted to the stats they can use (an int
  weapon never gets STR/DEX scaling);
* **effects** – critical, stance, stamina and guard damage, status build-up;
* **stamina** – the stamina multiplier, normalized so the first light attack costs the weapon's base cost
  times the multiplier whatever moveset the row carries;
* **spells** – FP and stamina cost and the requirements of sorceries and incantations.

Only the groups you list (`--stat-groups`, empty = all) are rolled; everything else stays vanilla.

### Ashes of War (`EquipParamGem`)

An Ash of War is a gem row, and two of its fields matter in play:

* `swordArtsParamId` — the **skill** itself (Lion's Claw, Sky Shot, ...) — `--random-gem-skills`;
* `spEffectId0..2` — the **on-hit effects** (bleed, frostbite, a buff) — `--random-gem-effects`.

Both are permuted *inside groups of gems that accept the same weapon types*. The group key is the
`configurableWepAttr` bitfield (24 bits): two gems with the same mask can be mounted on the same weapons,
so a skill never lands on a weapon that could not use it. The table has 11 such groups among the 237 gems
that own a skill, and 6 among the 14 that own an effect — a few dozen ashes have effects, so the skill
shuffle is the one that changes the game.

The effect triple moves as a unit (slot 0 is the primary effect, 1 and 2 the secondary ones) and the skill
moves on its own, so the two switches are independent.

---

## 6. Armor and talismans

Three independent armor options, and two for talismans:

* **`--random-armor` (Shuffle armor stats)** permutes 18 columns of `EquipParamProtector` *inside each slot*
  (head / body / arms / legs never mix): the eight damage-negation rates the equipment screen shows, the
  seven status resistances, `saDurability`, `toughnessCorrectRate` and `weight`. Only values the game
  already uses are dealt out, so nothing becomes absurd. Elden Ring armor has no flat defense
  (`defensePhysics` is zero in 1.17.1 - checked on a vanilla file), so those fields are not touched.
* **`--random-armor-fresh` (Randomize armor stats)** rolls each piece's numbers again instead of swapping
  them: every column is drawn uniformly between the lowest and highest value that column has inside the
  piece's own slot. A knight's armor keeps knightly numbers, but no two pieces share a stat block and a
  starter piece can roll like a late-game one. This is the "scramble each row" behaviour.
* **`--armor-keep-sets` (Keep armor sets together)** makes that roll coherent: the four pieces of a set
  (found from the name without its trailing piece word - Knight Helm, Knight Armor, Knight Gauntlets,
  Knight Greaves) are scaled by one factor per column instead of being rolled separately, so a set stays
  internally consistent while still being different from vanilla. Values are still clamped to each
  piece's own slot range. Turn it off and every piece rolls on its own.
* **`--random-armor-drops` (Move armor to random enemies)** changes only *where* armor drops: the item
  id of each slot is replaced by another armor id, so the armor itself is untouched. Enemy drop tables,
  map lots (chests, gifts, pickups) and armor shops are all included. One-time flag drops are never moved.
* **`--random-talismans` (Shuffle talismans)** permutes whole `EquipParamAccessory` rows: every talisman
  keeps its name and icon and receives another one's effect and numbers. There is no paramdef for that
  table here, so whole rows move rather than single fields - which is why the icon can belong to a
  different talisman than the name.
* **`--random-talisman-drops` (Move talismans to random enemies)** is the talisman version of the drop
  shuffle.

---

## 7. Loot upgrade levels (`--random-loot-levels`)

A weapon id is `base + affinity * 100 + upgrade`. In vanilla every weapon in a drop table, chest or shop
is +0 (947 weapon slots in `ItemLotParam_enemy`, all +0 on 1.17.1). This pass rewrites only the upgrade
digits:

* enemy drop tables — the rows an `NpcParam.itemLotId_enemy` points at, plus their consecutive rows;
* map lots — the rows in `names/item_locations.txt` (boss and field boss rewards, chests, gifts,
  pickups);
* shops — `ShopLineupParam` rows with `equipType` 0 (weapon), in the same list of real locations.

The level is drawn between 0 and the ceiling read from the **pristine** weapon table: 25 for a weapon with
affinity rows, 10 for a somber weapon (one row and `materialSetId != -1`), 0 for a unique weapon that
cannot be reinforced. Because the ceiling is read before the weapon pass adds its rows, `--random-loot-levels`
must be combined with a pristine input to be exact; run it on a file `--somber-infusable` already wrote
and somber weapons are treated as normal ones.

### Rarity (`--loot-rarity`)

Drawing every level with the same probability makes +25 a one‑in‑26 event, which is too often for a top
roll. A tier is picked first, then the level is drawn uniformly inside that tier, as a fraction of the
weapon's own ceiling:

| Curve | +0..+3 | +4..+9 | +10..+15 | +16..+20 | +21..+25 |
|---|---|---|---|---|---|
| `even` | 100% spread evenly | | | | |
| `common` (default) | 55% | 28% | 12% | 4% | 1% |
| `legendary` | 70% (+0..+2) | 20% (+3..+8) | 7% (+9..+14) | 2.5% (+15..+20) | 0.5% (+21..+25) |

A drop at 80% or more of its weapon's ceiling is marked with a star in loot.txt, a drop at 90% or more is
announced as `LEGENDARY` at the top of the report, and the best twelve of the seed are listed at the end.
Because the tiers are fractions, the same curve works for a +25 weapon and a +10 somber one.

### Bosses (`--loot-boss-bonus`)

Bosses roll their level from a better curve than ordinary enemies. An enemy counts as a boss when its
vanilla rune drop is 5000 or more (`NpcParam.getSoul`).

| Setting | Ordinary enemies | Bosses |
|---|---|---|
| `same` | chosen curve | chosen curve |
| `better` (default) | chosen curve | the next curve up (even → common → legendary) |
| `best` | chosen curve | always legendary |

Map lots (chests, gifts, pickups) and shops always use the chosen curve, because they have no enemy tier.

Verified: 905 entries changed across the three tables, none of them changed the weapon or the affinity
(2026-11-16, seed 999).

---

## 8. Enemies

### Moving loot between enemies

Five independent switches move one category of loot between the places it can drop, without changing the
items themselves: `--random-goods-drops`, `--random-weapon-drops`, `--random-armor-drops`,
`--random-talisman-drops`, `--random-ashes-drops`. The item id of a drop slot is replaced by another item
id of the same category, so names, stats, affinity and icons stay exactly as the game shipped them and only
the source moves. Enemy drop tables (the lots an NpcParam row points at), map lots that really exist, and
every shop slot of the matching equip type take part; one-time flag awards and key-item rows are never
moved.

With `--armor-drop-sets` the armour pieces of a set are moved as a unit: sets are grouped by size and
swapped with another set of the same size, piece by piece, so looting one piece tells you what the rest of
that set is. Pieces whose name has no trailing piece word move on their own.

### What enemies drop

* **`--random-enemy-drops`** – the first drop row of every enemy becomes a guaranteed drop of a random
  item; later rows keep their chance but drop random items too. The pool is every named goods row (no key
  items), every weapon / armour / talisman / Ash of War row with a real name and a price, with weapons
  normalized to +0 and flasks excluded. Rows that already hold a key item (`goodsType` 1) and rows whose
  drop is a one-time flag award are left alone.
* **`--enemy-drop-rolls N` / `--enemy-drop-chance P`** – give every enemy N rows instead of one, each
  dropping at P%, so a kill drops 0…N items (N·P/100 on average). The added rows take ids above every
  existing one; the game caps a lot at 64 rows, and the tool refuses to add a row that would cross that
  cap.
* **`--random-enemy-hp`** – `NpcParam.hp` of every enemy with hit points, `shuffle` or `range`.
* **`--random-runes`** – `NpcParam.getSoul`, `shuffle` or `range`.

---

## 9. World

* **`--random-flask-locations`** – the Flask of Crimson Tears (lot 20000) and the Flask of Cerulean Tears
  (lot 20001) move to a random real location: a boss / field boss / evergaol reward, an NPC gift or
  corpse, a legacy dungeon or overworld pickup, or a merchant slot. What was there goes to the first
  Site of Grace (lot 10000, "First Step"). Chance drops, map fragments, one-time-flag rows and DLC map
  areas are never used.
* **`--start-with-bell` / `--start-with-lantern`** – add the Spirit Calling Bell / the Lantern to lot
  2000, which the game hands out at the start.

---

## 10. Weapon names

`--somber-infusable` adds 12 rows per somber weapon. Without names the game shows "?" for them, so the
pass writes a name and a description into `msg/<language>/item_dlc02.msgbnd.dcx` for every row that has
none: the name is the base weapon's name with the language's own affinity affix (learned from the
archive itself, "Heavy " in English), and the description is the base row's. Ids already in the archive
are never overwritten. With Mod Engine 2 the `msg` folder goes next to `regulation.bin`; the file is
written next to the output, never over its source.

---

## 11. Compression

* **kraken / leviathan** — the game's own Oodle format, written through `oo2core_6_win64.dll` (RAD Game
  Tools', shipped with the game, never with this tool). `leviathan` writes an Oodle Leviathan stream
  under the same KRAK tag; OodleLZ_Decompress detects the codec from the stream.
* **zstd** — no DLL needed, but the game only accepts a 64 KB window (`--zstd-window 16`; other values
  are kept for experiments and can crash it), which makes the file about 35% larger.
* **effort** — `max` (Oodle level 9) is the default and the only safe one for a file that starts big:
  measured on the vanilla file 1.59 MB in 155 s, and on Elden Ring Reforged (3.03 MB in) 2.01 MB in
  245 s. `fast` (level 3) costs seconds and gives 1.92 MB on vanilla, but 2.41 MB on ERR — over the
  2.36 MB limit, so the tool refuses. The game's limit is 2,359,296 bytes; the tool reports what is left.
* **auto** — kraken when the DLL is found, zstd otherwise. If the DLL is missing and stdin is a
  terminal, the tool asks for the path instead of silently falling back.

---

## 12. The window

Everything it shows comes from `options.py`: the label, the hover text, the default and which options
depend on which. A tooltip therefore cannot disagree with the flag it describes, and a new option
appears in the CLI and in the window by being added once.

* Ten sections (Files and output · Consumables and buffs · Spells · Prices · Weapons · Ashes of War ·
  Armour and talismans · Enemies, drops and loot · Flasks and starting items · Advanced).
* The page scrolls; the progress bar, the command line, the status line and the buttons live in one 79-pixel
  bar at the bottom and never scroll, so no control can end up behind the taskbar. The log is a toggle in
  the title bar, so it costs no height until you ask for it. The window opens **centred** at 80% of the
  screen width and 84% of its height (max 1180×860) and remembers its own size.
* Each section is a grid, so its labels share one column and its controls line up; long labels wrap
  instead of being cut off. Options that depend on another switch are indented under it and greyed out
  while it is off.
* Hover help appears on `<Enter>` with no delay and stays until the pointer leaves.
* During a run: a progress bar over every pass, the current pass, an elapsed clock and the log. With
  maximum effort the run takes minutes and the window shows it working rather than looking frozen.
* **Loot simulator** – a button opens a panel: choose how many kills (1-200) and a seed, and it runs the
  passes in memory and lists what those kills dropped, with weapon affinity and upgrade level. It writes
  and compresses nothing, so it costs seconds. It is the safe way to judge a seed before playing.
* **Presets** – a dropdown in the title bar loads a whole bundle of options in one click (gentle start,
  classic, Borderlands loot, loot and stats, armor and talismans, ashes, prices only, boss rush, full
  chaos). The bundles live in `presets.py`; any manual change turns the box into "Custom".
* The command line the window will run is shown at the bottom; click it to copy. "Copy log" copies the
  whole run.
* `settings.json` next to the program holds the size, the open sections, the last paths (8 per field)
  and every option value. "Reset all" puts the options back without touching the path lists.
* "Preview" adds `--dry-run` (everything runs, nothing is written), "Repack only" adds `--repack`;
  pressing *Randomize* with nothing ticked asks first, because the result would be a recompressed copy.

---

## 13. Design notes

* **Rows never move between ids for named tables.** The Item and Enemy Randomizer's `scramble` mode moves
  data between rows and leaves the names behind, which is how a "?Gooditem?" appears. Here only *fields*
  move inside a row, except for talismans, where whole rows move and the name stays attached to the id —
  a cosmetic mismatch, never a missing name.
* **Column permutation keeps balance.** Armour negation and resistances are dealt out from the vanilla
  set, so no piece becomes invulnerable and none becomes useless.
* **Fail soft on missing vendors.** No Oodle DLL → zstd with a clear message; no text archive → the rows
  are named "?" and the tool says so.
* **One seed, reproducible.** The seed is printed at the top of every report and in the last line, and
  the reports list every change, so a run can be rebuilt exactly.
* **The GUI never patches the game's own files.** The output folder gets `regulation.bin`, the reports
  and a `msg` folder; the tool refuses to write into the input's folder, because that would litter (or
  overwrite) a mod folder.