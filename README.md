# Elden Ring Super Randomizer

A window and a command line tool for **regulation.bin** – the single parameter file that holds every
item, weapon, spell, enemy drop, shop price, spell effect and flask location in Elden Ring. The tool
rewrites that file: a new mod folder with the rewritten `regulation.bin` plus its report files, ready
to be loaded by [Mod Engine 2](https://www.nexusmods.com/site/mods/617) or merged with
[Fog Gate Randomizer](https://www.nexusmods.com/eldenring/mods/10).

Written for game version **1.17.1** (Shadow of the Erdtree included) and the Mod Engine 2 **1.4** /
**ERR** mod loaders. Vanilla, the Item and Enemy Randomizer and **Elden Ring Reforged** output all work
as input, so you can stack this on top of them.

The window is the whole program. **Nothing is switched on when it starts** – you tick what you want –
and every control explains itself on hover. Options that cannot be used are greyed out, and the window
remembers its size, the paths you used and every setting.

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

## What it can do

| Area | Options |
|---|---|
| **Consumables** | every usable item (pots, greases, meats, boluses, tools, usable key items) receives another item's use effect; `shuffle` (every effect used exactly once) or `random` (repeats allowed); the use **animation** can stay with the effect, come from another item of the same class, or from any item; flasks and remembrances can join the pool; **stack sizes** shuffled; buff **durations** shuffled separately |
| **Spells** | every sorcery and incantation receives another spell's effect (one pool for both); the cast animation can stay with the spell, come from another spell with the same signature, or from any spell; **spell stats** (FP / stamina cost and requirements) randomized independently of the weapon stats |
| **Prices** | shop prices (`ShopLineupParam.value`) and sell prices (`EquipParamGoods.sellValue`) shuffled, or redrawn inside a range; sell prices optional; weapons, armour and Ashes of War can join the sell pool |
| **Weapons** | somber/unique weapons become infusable (12 affinities + Ashes of War, rows named in the game's own text); movesets shuffled (melee ↔ shields, bows among bows); default skill rolled so it animates with the row's moveset; every affinity row gets its own randomized attack, guard, requirements, scaling, status build-up and stamina cost – each group can be ticked on its own; **requirements stay in the weapon's own tier** so looted weapons stay usable; on‑hit and holder **properties** shuffled |
| **Ashes of War** | every Ash of War can receive another ash's **skill** (Lion's Claw becomes Sky Shot) and/or another ash's **on-hit effects**; donors are only drawn from ashes that fit the same weapon types, and the two can be switched on separately |
| **Loot** | every enemy drops something random (you choose which kinds: weapons, armor, talismans, goods, Ashes of War); 1…N rolls per enemy at P% each; weapons in drop tables, chests, boss rewards and shops get a random upgrade level (+0…+25, somber +0…+10) with a **rarity curve**, and **bosses roll a better curve**; **rare unique weapons** (1 %, 3 % or 8 % per roll) and **upgrade materials** can turn up |
| **Shops** | every merchant slot can be filled with a random item of its own category, price untouched. Not a timed refresh (that needs a runtime mod) – every shop sells something else |
| **Where loot drops** | every category can be **moved between enemies** without changing the items: weapons, goods, armor, talismans and Ashes of War. Armor sets can move as a set |
| **Armor & talismans** | three armor options: swap the stat columns between pieces of the same slot, roll each piece's numbers again (optionally **keeping each set coherent**), or move armor to different enemies. Talismans: shuffle the rows, and move them to different enemies |
| **Enemies** | rune drops (`NpcParam.getSoul`) and hit points (`NpcParam.hp`) shuffled or redrawn inside a range |
| **World** | the Flask of Crimson Tears and the Flask of Cerulean Tears move to a random pickup / boss reward / gift / merchant, and what was there goes to the first Site of Grace; start with the Spirit Calling Bell and/or the Lantern |
| **Checking a seed** | a **loot simulator** builds the tables in memory and shows what N random kills dropped, without writing or compressing anything |
| **Output** | kraken (the game's own Oodle format, needs the game's `oo2core_6_win64.dll`) or zstd (no DLL, ~35% larger); fast or maximum compression effort; `--repack` repairs a regulation.bin another tool wrote in a form the game rejects |

**Not included**: character creation / starting class / starting equipment randomizer,
`regulation.bin` **enemies-and-bosses** randomizer (that is the
[Item and Enemy Randomizer](https://www.nexusmods.com/eldenring/mods/12)'s job), connectivity / seamless
co-op, an Elden Ring installation, an unpacked game, the game's DLL.

### Static file vs. runtime mod — what "random" can mean here

regulation.bin is one table shared by the whole game. Every copy of a Longsword reads the same rows,
so **two copies of the same weapon can never have different stats in a static file** — that needs a
runtime mod (the Item and Enemy Randomizer hooks the game and rerolls per item). What this tool does
instead:

* every **affinity row** of a weapon gets its own stats, so "Longsword (Heavy)" and "Longsword (Keen)"
  are different weapons (13 rows per weapon);
* the **affinity** of a dropped weapon is rerolled, so two Longsword drops usually are not the same
  weapon at all;
* the **upgrade level** of a dropped weapon is rerolled, so a drop can be +2 or +18;
* with several rolls per enemy, every kill rolls the drop table again, so the same enemy can hand you
  a different weapon each time.

That is as close to Borderlands-style loot as a static rewrite gets.

---

## Requirements

* **Windows 10/11** (the window) – Linux works too, see `randomize.sh` / `randomize_gui.sh`.
* **Python 3.10 to 3.14** – the dependencies (`zstandard`, `cryptography`) publish no wheels for 3.15
  yet. The launchers find a suitable Python themselves; no `uv` needed.
* **tkinter** for the window (included in the python.org Windows installer, `sudo apt install python3-tk`
  on Ubuntu/WSL).
* On Windows the launcher creates `%USERPROFILE%\.venvs\er_mod` once and installs the dependencies.
  On Linux it uses `~/.venvs/er_mod` (the project drive is exFAT and cannot hold a venv's symlinks).

---

## Run it

### Windows, window

Double-click `randomize_gui.bat` (it opens a console window that shows errors and closes with the
window), or `python tools\gui.py`.

### Windows, command line

```
randomize.bat --help
randomize.bat --input "C:\Games\ELDEN RING\Game\regulation.bin" --output "D:\mods\my-mod\regulation.bin" --seed 12345 --weapons --random-loot-levels
```

### Linux / macOS

```bash
./randomize_gui.sh                  # window (needs python3-tk)
./randomize.sh --help
./randomize.sh --seed 12345 --weapons --dry-run
```

### The output

The output is a **mod folder**:

```
D:\mods\my-mod\
  regulation.bin          <- load with Mod Engine 2 (or copy over the game's, backup first)
  msg\engus\...           <- only when weapon names are patched: ship it next to regulation.bin
  mapping.txt             <- item <- effect taken from, shop prices, sell prices, buff durations, flasks, start items
  weapons.txt             <- movesets, default skills, per-row stats
  gear.txt                <- armour columns, talisman rows
  loot.txt                <- which drop/chest/shop weapon got which upgrade level
  spells.txt              <- spell effects, spell stats
  drops.txt               <- enemy drop tables
  hp.txt, runes.txt       <- enemy hit points and rune drops
```

With Mod Engine 2, the config is:

```toml
[extension.regulation]
priority = 2               # a higher priority than Fog Gate Randomizer loads after it
```

Stacking with the Item and Enemy Randomizer / Fog Gate Randomizer: run their configured
`regulation.bin` through this tool. Note the order — the last loaded file wins per row, and a row this
tool added (a synthesized somber affinity) does not exist in theirs, so their pass cannot see it.

---

## Presets (plug and play)

A dropdown in the title bar loads a whole coherent set of options in one click. Pick one, look at what it
switched on, change anything you like – the box then says **Custom**.

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
| **Boss hunt** | bosses, runes, flasks and starting items – no overworld loot shuffle. |
| **Level 1 run** | level 1 beginnings: enemies and rune drops tuned for a fresh start. |
| **Balanced** | weapons and enemies tuned for an even, playable run (beta). |
| **Glass cannon** | enemies hit much harder but die much faster (beta). |
| **Full chaos** | every pass on. Expect a very different game and a slow compression. |

---

## Elden Ring Reforged (ERR)

[ERR](https://www.nexusmods.com/eldenring/mods/11542) is a total conversion mod: new enemies, weapons,
items and bosses. It is shipped as a **Mod Engine 2 mod folder**, and like every mod of that kind it
carries its own `regulation.bin` — which is why the size of the file matters so much here.

| File | Size | Notes |
|---|---|---|
| vanilla `regulation.bin` | 2,045,728 B | the game's own file |
| **ERR `mod\regulation.bin`** | **3,029,776 B** | already 670 KB *bigger* than vanilla |
| the game's hard limit (`0x240000`) | 2,359,296 B | above this the game reports corrupted save data |
| this tool, ERR input, effort **fast** | 2,405,424 B | **46 KB over the limit** – the tool refuses to write it |
| this tool, ERR input, effort **max** | **2,011,456 B** | no extra passes, 347,840 B to spare |
| this tool, ERR input, effort **max**, every pass on | **2,291,088 B** | 68,208 B to spare – fits, but only just |

That is why the window ships with **kraken + maximum effort** and why you should not switch to `fast`
when the input is an ERR file: `fast` produces a file the game will not load. A max run takes two to
four minutes; the progress bar, the current pass and the elapsed clock show that it is working.

Stacking it on ERR:

1. Point **Input** at `C:\Games\ERR\mod\regulation.bin` (keep a copy of that folder first).
2. Leave **Output** in its own new folder.
3. Either replace `mod\regulation.bin` with the new file, or add the new folder as a second mod in
   Mod Engine 2 with a **higher priority** than ERR's entry — the last one loaded wins per row.
4. If you ticked *Make somber weapons infusable*, copy the generated `msg\engus` folder next to the
   `regulation.bin` you load, or the added affinity rows show a placeholder name.

Measured on 2026-11-16 with an unmodified ERR install (`C:\Games\ERR`, Mod Engine 2 loader) and this
tool's own reports; your numbers will move a little with the seed and with how many passes you enable.

---

## Notes on a few settings

* **Nothing is on by default.** Every randomization switch starts unticked; the only defaults are the
  input / output paths and `kraken` + `max` compression. Press *Randomize* with nothing ticked and the
  tool asks whether you really want a recompressed copy of the input.
* **Consumables vs. spells vs. prices are independent.** "Shuffle consumable effects" is a master
  switch for `EquipParamGoods`; turn it off and goods are left exactly as they are. Prices are a
  separate pass over `ShopLineupParam` and `EquipParamGoods`, so shops with items another randomizer
  put there are included, because the *slot* is what is priced.
* **Spell stats are their own switch.** `Shuffle spell effects` moves what a spell *does*;
  `Randomize spell stats` re-rolls what it *costs* (FP, stamina, requirements). They are independent, so
  a spell can keep its vanilla cost while its effect changes.
* **Assignment (`--mode`)** decides how the effect donors are picked: `shuffle` deals the effects out
  like cards (every effect used exactly once, no item keeps its own), `random` lets every item draw
  independently (repeats, and an item may keep what it had). It applies to spells as well.
* **Use animation (`--split-anim`)** is a separate donor from the effect. `none` keeps them together
  (a pot stays a pot), `same` takes the animation from another item of the same class, `any` from any
  item at all — a pot may then be eaten and a fist thrown, which is untested in game.
* **Weapon movesets** – melee weapons swap among themselves, shields only with shields (so a left-hand
  shield still blocks) and bows only with bows. `wepType follows` makes the smithing table list only
  the Ashes of War that animate with the row's moveset; it is untested against the game's save checks.
* **Upgrade levels on loot** need no other option. The level is drawn between 0 and what the weapon can
  take (25, or 10 for a somber weapon, 0 for a unique one that cannot be reinforced). Combine it with
  "Rolls per enemy" for Borderlands-style drops.
* **Compression**: `max` is the default. On a full-featured run of the vanilla file that was 1.59 MB
  in 155 s; `fast` was 1.92 MB in 6.8 s. Both fit under the game's 2.36 MB limit, but on a file that
  starts big (Elden Ring Reforged, 3.03 MB) only `max` fits — see below. The window shows a progress bar,
  the current pass and an elapsed clock while it runs, so a two-minute compression never looks like a
  freeze.

---

## How it works

1. Decrypt `regulation.bin` (AES-256 CBC, the key is published by the modding community; a new key per
   version is added in `tools/erreg.py`), decompress the DCX (KRAK/zstd/DFLT) and read the BND4 of
   param files.
2. Parse only the tables it needs, from the paramdef XMLs in `tools/paramdef/`.
3. Run the passes in a fixed order (the random generator is shared, and some passes read what another
   is about to change):
   buff durations → consumable effects → prices → runes → enemy hit points → enemy drops → weapons →
   ashes of war → armour and talismans → loot shuffle → loot upgrade levels → weapon names → spells →
   flasks → starting items.
4. Rebuild the BND4, recompress (kraken via the game's own `oo2core_6_win64.dll`, or zstd) and
   re-encrypt with the same AES IV the file had.

The reports are generated from the same data structures, so `mapping.txt` is the exact list of what was
changed.

---

## Window

Ten collapsible sections: Files and output · Consumables and buffs · Spells · Prices · Weapons ·
Ashes of War · Armour and talismans · Enemies, drops and loot · Flasks and starting items · Advanced.

* **Loot simulator** – a button opens a panel where you pick how many kills to simulate and which seed to
  use; it builds the tables with the settings currently ticked and lists what those kills dropped, weapon
affinity and upgrade level included. Nothing is written, nothing is compressed, so it costs seconds.

* Scrollable page; the progress bar, the command line, the status line and the buttons live in a
  **79-pixel bar** at the bottom that never scrolls, so nothing can end up behind the taskbar however the
  window is resized or maximized. The log is a toggle (**Log** in the title bar) so it costs no height
  unless you want it.
* Hover any control for the full explanation: what it does in plain language, an example, and then what it
  does under the hood (tables, fields, limits). It appears instantly, stays while the pointer is on it, and
  is as long as it needs to be.
* Options that depend on another switch are indented under it and greyed out while it is off.
* While a run is going: a progress bar through every pass, the current pass, an elapsed clock and (if the
  log is open) the output. A two-minute maximum-effort compression looks like work, not a freeze.
* The command line the window will run is shown at the bottom (click it to copy); "Copy log" copies
  everything the run printed.
* A **preset dropdown** in the title bar loads a whole set of options; any manual change turns it into
  "Custom".
* **Find** next to the input field, the Oodle DLL and the text‑archive folder searches this machine (Steam library,
  the usual Games folders, mod folders) and fills the field with the first hit; the others land in the dropdown.
  Elden Ring Reforged's `C:\Games\ERR\mod\regulation.bin` and the game's `oo2core_6_win64.dll` are found
  this way.
* **Language** — the **Aa** dropdown in the top right corner. It changes the window only: reports, console
  output and the game text stay in English. The choice is **not saved**: the window always opens in English.
  Start in a given language with `python tools/gui.py --lang pt`; a wrong code prints the known codes and
  exits with 2. All eleven packs are complete (labels, hover text, buttons, phases, dialogs): English,
  French, Spanish, German, Italian, Brazilian Portuguese, Japanese, Simplified Chinese, Dutch, Swedish,
  Finnish and Polish. Adding another is one file, `tools/lang_<code>.py` — anything missing falls back to
  English per string, so a half-finished pack still runs.
* **Presets**: save your own bundle with *Save preset*, move it between installs with *Export / Import* in the
  Advanced section, delete it with *Delete* (built‑ins cannot be deleted).
* Size, position, open sections, the last paths and every option value are saved in `settings.json`
  next to the program. The window opens **centred on the screen**, and the output folder you last used for
  an input file is offered again when you pick that input.
* "Preview" runs everything and shows the reports without writing a file; "Repack only" rewrites the
  input unchanged. Pressing *Randomize* with nothing ticked asks first, because the result would be a
  recompressed copy of the input.

---

## Building a single executable

```bat
build_exe.bat
```

Needs PyInstaller (installed automatically into the same venv). The result is
`dist\EldenRingSuperRandomizer.exe` (Linux/macOS: `dist/EldenRingSuperRandomizer`) plus `dist\msg\` next to it – ship
both, and the user adds the game's `oo2core_6_win64.dll`.

---

## Antivirus notes

Antivirus engines and Microsoft SmartScreen flag unsigned PyInstaller executables more than almost any
other kind of file, because the packer's runtime behaviour (a one-file binary unpacking itself into a
temporary folder and running from there) looks like a dropper. The result is a false positive, not a
real detection – but it still stops users from running the tool. What lowers the risk, cheapest first:

1. **Code signing (the real fix).** Sign `EldenRingSuperRandomizer.exe` with an Authenticode certificate
   (`signtool sign /fd sha256 /a EldenRingSuperRandomizer.exe`). A valid signature, especially with a
   reputation-building EV certificate, clears SmartScreen and most AV heuristics. Without a certificate
   this step is not possible; everything below is mitigation.
2. **The build already embeds PE version metadata** (`tools/version_info.txt` via PyInstaller
   `--version-file`: company, product name, file/product version). A generic binary with no version
   resource looks machine-generated and is flagged hardest; a file that declares who built it and what
   it is gives reputation systems something to key on. Keep the version tuple in step with
   `tools/version.py`.
3. **`--noupx` is already set.** UPX-packed executables are a classic AV trigger; leaving it off is
   correct. Do not add it back.
4. **Consider `--onedir` for distribution.** A one-*folder* build (an exe next to its DLLs and data)
   does not unpack itself into `%TEMP%` at run time, so it avoids the dropper heuristic entirely and is
   markedly friendlier to AV than the current `--onefile`. The trade-off is that you ship a folder
   instead of a single file. This is a distribution decision; `--onefile` stays the default here.
5. **If a specific engine still flags it**, submit the file as a false positive to that vendor
   (Microsoft: the Security Intelligence / Defender submission portal). Do not disable AV or add
   exclusions to work around a detection – sign the binary instead.

The tool is fully offline: it makes no network requests, downloads nothing, and runs nothing but the
game's own `oo2core_6_win64.dll` that the user already has.

---

## Compatibility / limits

* Param layout of game **1.17.1** (format2D 0x85). Another version fails loudly with
  `row size … != paramdef row size …` instead of writing garbage.
* `oo2core_6_win64.dll` (kraken) is RAD Game Tools' and is never shipped.
* The output must stay under `0x240000` bytes (2,359,296); the tool reports the remaining bytes.
* Adding/removing param rows (`--somber-infusable`) keeps ids and names consistent; the rows it adds are
  named in the game's own text archives (`--weapon-names`, on by default with that option).
* Only as lawful as your use of the game: randomizing single-player content you own is fine; do not
  redistribute the game's files or DLL.

---

## Details

See [README_details.md](README_details.md) for the pass-by-pass description of every option, the file
layout, and the design notes (including why a static rewrite cannot do what a runtime mod does).