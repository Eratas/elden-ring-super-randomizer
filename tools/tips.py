"""The hover text of every option.

Every entry has the same shape, with two or three paragraphs:

  paragraph 1  one sentence: what the option changes.  `randomize.py --help` shows this line.
  paragraph 2  the facts: which table or field is written, the ranges and weights, what the pass
               leaves alone and which other option it depends on.
  paragraph 3  a concrete example, followed by a risk sentence when there is a real one.

Plain text only: the tooltip is a plain label, so there is no markdown, no indentation and no list;
long lines wrap on their own.  The text is written for a reader who has never seen this program, so
it names the game's own terms (regulation.bin, affinity, Ash of War, Site of Grace) and never refers
to earlier versions of the tool or to a conversation.
"""
from __future__ import annotations

TIPS: dict[str, str] = {
    # ------------------------------------------------------------------ files
    "input": (
        "The regulation.bin this run reads and rewrites.\n\n"
        "It can be the vanilla file from the game's Game folder or one that another randomizer already "
        "wrote; the Item and Enemy Randomizer, the Fog Gate Randomizer and Elden Ring Reforged all "
        "produce readable files. The file is only read, so the original is never modified, and the "
        "tables it contains decide which items, statuses and Ashes of War a run can use.\n\n"
        "Example: C:\\Games\\ELDEN RING\\Game\\regulation.bin for the base game, or "
        "C:\\Games\\ERR\\mod\\regulation.bin for Elden Ring Reforged."
    ),
    "output": (
        "Where the new regulation.bin is written.\n\n"
        "The reports (mapping.txt, weapons.txt, drops.txt and the rest) and the msg folder that carries "
        "the new weapon names are written next to it, so a folder of its own keeps a mod tidy. Writing "
        "into the input's own folder under the input's own name is refused, because that would replace "
        "the input and bury it under reports.\n\n"
        "Example: D:\\mods\\my-randomizer\\regulation.bin creates D:\\mods\\my-randomizer\\ plus its "
        "reports and msg folder. Risk: an output inside the game's Game folder is overwritten by the "
        "next game update."
    ),
    "backup_replace": (
        "Copies the files a run is about to change into a timestamped backup folder, then replaces "
        "them.\n\n"
        "The backup takes the input regulation.bin and every msg archive the run patches, stores them "
        "under backups\\<date-time>\\ next to the program, and then writes the new file over the input "
        "and its archives. The randomized\\ output folder is still written separately and keeps the "
        "reports. The Revert button in the window puts a backup back; the folder is ordinary files, so "
        "copying one by hand works too.\n\n"
        "Example: a run at 2026-11-22 14:03 saves the original regulation.bin and "
        "msg\\engus\\item_dlc02.msgbnd.dcx to backups\\2026-11-22_140312\\ before overwriting them. "
        "Risk: with this off, the previous files are gone once the run finishes."
    ),
    "oodle_dll": (
        "oo2core_6_win64.dll, the compressor the game itself uses.\n\n"
        "Kraken and leviathan output need this file, which ships with Elden Ring in the Game folder and "
        "is also present in the mod folders of the fog gate and item randomizers. The tool never ships "
        "it. Without it the output falls back to zstd, which needs no DLL.\n\n"
        "Example: C:\\Games\\ELDEN RING\\Game\\oo2core_6_win64.dll, or press Find next to the field. "
        "Risk: without the DLL the file is roughly a third larger, which is enough to pass the game's "
        "size limit on a large mod."
    ),
    "archives": (
        "The msg folder whose item text receives the new weapon names.\n\n"
        "Making somber weapons infusable adds twelve affinity rows per weapon, and the game shows a "
        "placeholder for a row that has no name. The tool writes a name and a description for each new "
        "row into item_dlc02.msgbnd.dcx of the folder given here. Empty uses the English copy shipped "
        "with the tool; several folders can be given separated by semicolons, one per language.\n\n"
        "Example: point it at C:\\Games\\ERR\\mod\\msg when randomizing on top of another mod, so the "
        "names describe the items that mod actually hands out. Risk: patching only the English archive "
        "leaves a French or Japanese game showing English names."
    ),
    "seed": (
        "Fixes the random seed, so a run can be repeated exactly.\n\n"
        "Every draw in the run comes from one generator seeded here: the same seed with the same "
        "options and the same input gives the same items, drops, prices and stats. An empty field "
        "draws a fresh seed; the number that was used is printed at the top of the log and in "
        "mapping.txt, so a good world can be rebuilt later.\n\n"
        "Example: seed 12345 run twice gives two byte-identical regulations. Risk: a seed only "
        "reproduces a run while the input file and the options stay the same."
    ),
    "compression": (
        "The codec used for the output: auto, kraken, zstd or leviathan.\n\n"
        "kraken is the game's own Oodle format and needs oo2core_6_win64.dll. leviathan is Oodle's "
        "stronger setting, a little smaller and a little slower. zstd needs no DLL and writes a file "
        "about a third larger. auto uses kraken when the DLL is found and zstd when it is not.\n\n"
        "Example: the same content measured 1.59 MB as kraken and 2.16 MB as zstd. Risk: a zstd file "
        "can pass the game's 2,359,296-byte limit and be refused at load."
    ),
    "compression_level": (
        "How much work the encoder spends: fast or max.\n\n"
        "max is the default. It takes one to four minutes on a full regulation and produces the "
        "smallest file, which leaves the most room under the size check; the window shows the pass and "
        "an elapsed clock while it runs. fast finishes in seconds and produces a file about 20% "
        "larger, which is useful for trying seeds.\n\n"
        "Example: fast wrote 1.92 MB in 7 seconds, max wrote 1.59 MB in 155 seconds. Risk: fast on a "
        "large mod can pass the limit, and the tool then refuses to write the file at all."
    ),
    "repack": (
        "Reads the input and writes it back with nothing changed.\n\n"
        "Some tools produce a regulation.bin that the game rejects at startup. Reading such a file and "
        "writing it with this tool's own encoder produces a file the game accepts while every table "
        "stays identical. No randomization pass runs and every other option is ignored.\n\n"
        "Example: a Fog Gate Randomizer 0.2.3 output that crashed on game 1.17.1 loads after a repack. "
        "Risk: a repack fixes the container, not a table whose contents the game cannot read."
    ),
    "dry_run": (
        "Runs every pass and prints the reports without writing a file.\n\n"
        "The seed, the options and the tables are used exactly as in a real run and the console shows "
        "the same summary, but nothing is written and nothing is compressed, so a run costs seconds "
        "instead of minutes. The Preview button in the window does the same thing.\n\n"
        "Example: preview a new seed, read drops.txt, then run for real once the world looks right. "
        "Risk: dry_run writes no reports either; only the console summary is produced."
    ),
    "no_reports": (
        "Skips the plain-text report files next to the output.\n\n"
        "A normal run writes mapping.txt (item to effect, prices, flasks), weapons.txt, spells.txt, "
        "gear.txt, ashes.txt, goods.txt, loot.txt, loot-shuffle.txt, drops.txt, runes.txt and hp.txt. "
        "They are the exact record of what changed and the only way to see which item received which "
        "effect. The console summary is printed either way.\n\n"
        "Example: a 780-line weapons.txt lists every weapon row with its new numbers. Risk: without "
        "mapping.txt a seed cannot be inspected afterwards, only rebuilt from its seed number."
    ),
    "max_size": (
        "The size the output must stay under, in bytes.\n\n"
        "Elden Ring reads its regulation through a save blob of 2,359,296 bytes (0x240000), so that is "
        "the default and a larger output is refused rather than written. An input that is already "
        "larger than that clearly loads in its own loader, so the ceiling becomes the input's own size "
        "unless a smaller number is entered here: Elden Ring Reforged ships 3.03 MB and is allowed to "
        "stay 3.03 MB.\n\n"
        "Example: with a 3,031,632-byte input the run may write up to 3,031,632 bytes; "
        "--max-size 2359296 puts the vanilla limit back. Risk: raising it on a loader that does not "
        "accept the size produces a file the game will not open."
    ),
    "simulate": (
        "Builds the tables, prints N random kills and writes nothing.\n\n"
        "The passes run exactly as in a real run with the same seed, and then the tool rolls N random "
        "enemies and prints what each one dropped, including the affinity and upgrade level of a "
        "weapon. Every row is rolled at the chance the drop settings give it, so a kill that gives "
        "nothing is printed as nothing. Nothing is written and nothing is compressed.\n\n"
        "Example: --simulate 20 prints twenty lines such as \"Rat -> Short Sword +3\". Risk: the "
        "simulation reads the tables it just built, so it shows this seed, not every seed."
    ),

    # ------------------------------------------------------------------ consumables and spells
    "goods": (
        "Shuffles what every usable item does when it is used.\n\n"
        "Each row of EquipParamGoods that has a use effect receives the effect of another such row: "
        "pots, greases, meats, boluses, throwing tools and usable key items all take part, while the "
        "item id, the name and the icon stay where they are. Turning the option off leaves the table "
        "exactly as the game shipped it.\n\n"
        "Example: a Fire Grease heals instead of greasing the weapon, and a pot casts a glintstone "
        "shard. Risk: an item can end up far stronger or far weaker than its name suggests."
    ),
    "mode": (
        "How the shuffled effects are handed out: shuffle or random.\n\n"
        "shuffle deals the effects out like a pack of cards, so every effect lands on exactly one item, "
        "nothing keeps its own effect, and the world contains each effect once. random lets every item "
        "draw on its own, so effects repeat, some are missing, and an item can keep what it had. The "
        "same choice applies to the spell shuffle.\n\n"
        "Example: with shuffle, 242 usable items receive 242 different effects; with random, three "
        "items can all cast the same spell. Risk: random can remove an effect from the world entirely."
    ),
    "include_flasks": (
        "Lets the two healing flasks take part in the consumable shuffle.\n\n"
        "The Flask of Crimson Tears and the Flask of Cerulean Tears normally heal, and they are kept "
        "out of the pool by default so a run always has healing. With this on they can receive another "
        "item's effect, and another item can receive their healing.\n\n"
        "Example: a Golden Rune heals for a flask's worth instead of giving runes. Risk: a run can "
        "start with no healing flask until one that heals is found."
    ),
    "include_remembrances": (
        "Lets remembrances take part in the consumable shuffle.\n\n"
        "A remembrance is used to obtain a boss weapon or a large amount of runes. With this on, a "
        "remembrance can receive another item's effect and an ordinary item can receive the runes, "
        "which changes what a boss soul is worth without changing the weapon trade.\n\n"
        "Example: using a remembrance applies a grease instead of granting 50,000 runes. Risk: the "
        "weapon trade at Enia is untouched, so a remembrance still buys its boss weapon."
    ),
    "goods_quantity": (
        "Shuffles how many of an item a pickup gives and how many can be carried.\n\n"
        "The game stores the two numbers as a pair, and vanilla only uses a handful of sizes (1, 10, "
        "20, 99, 999). This moves the pair from one stackable item to another, so the numbers always "
        "stay consistent with each other, and only rows that already stack take part.\n\n"
        "Example: Festering Bloody Finger at 99 carried and 99 per pickup becomes 999 and 999. Risk: a "
        "consumable can arrive in a stack of one, which makes it scarce rather than generous."
    ),
    "split_anim": (
        "Chooses where the use animation comes from: none, same or any.\n\n"
        "none keeps the animation attached to the effect, so a pot is still thrown. same takes the "
        "animation from another item of the same class, so thrown items stay thrown and applied items "
        "stay applied. any lets any item donate the animation, so a pot can be eaten and a fist can be "
        "thrown. The same split applies to the cast animation of sorceries and incantations.\n\n"
        "Example: with same, a pot whose effect now heals is still thrown and bursts into healing. "
        "Risk: any is untested in game; an item can play no animation or refuse to be used."
    ),
    "spells": (
        "Shuffles what sorceries and incantations do.\n\n"
        "Every Magic row that is a sorcery or an incantation receives another spell's effect, and both "
        "kinds draw from one shared pool, so a glintstone spell can end up as a dragon communion "
        "breath. Costs, requirements and animations stay on their own rows unless Randomize spell stats "
        "is on as well.\n\n"
        "Example: Glintstone Pebble heals, and a breath attack fires a glintstone shard. Risk: a spell "
        "can end up with an effect that needs a hitbox its animation does not have."
    ),
    "spell_stats": (
        "Redraws what every sorcery and incantation costs and requires.\n\n"
        "Each spell receives new FP and stamina costs drawn in bands around the vanilla values, and the "
        "Intelligence, Faith and Arcane requirement set of a random vanilla spell, capped at a 60-point "
        "sum. The option stands alone: it runs with the effect shuffle off, and spells keep their own "
        "effects and animations unless Shuffle spell effects is on.\n\n"
        "Example: a comet that cost 40 FP and needed 60 Intelligence now costs 22 and needs 38. Risk: a "
        "cheap, low-requirement spell can arrive very early in a run."
    ),

    # ------------------------------------------------------------------ prices and shops
    "random_shop_stock": (
        "Fills every merchant slot with a different item from the same kind of stock.\n\n"
        "Each slot of ShopLineupParam is drawn from a curated pool of its own category, so a slot that "
        "sold smithing stones can sell a weapon and the next seed gives it something else. The price, "
        "the stock limit and the cost type stay on the slot, so the new item sells at the old slot's "
        "price. The pools only hold items with a real use, no debug or NPC rows, no \"Type N\" "
        "placeholder names and no depleted Ashes; a shop never repeats an item it already stocks, and "
        "a small general shop is filled up to forty slots from its own categories.\n\n"
        "Example: a smithy's first weapon slot sells a Lordsworn's Greatsword at the price of the "
        "dagger it replaced. Risk: the stock is fixed for the run, because a rewritten regulation.bin "
        "cannot refresh itself on a timer."
    ),
    "shop_stock_kinds": (
        "Chooses which kinds of item merchants may sell.\n\n"
        "Weapons, armor, talismans, goods and Ashes of War can be ticked independently, and an empty "
        "selection means all five, which is the widest and the default. Talismans are stocked from "
        "their names table, so they work without the accessory field table.\n\n"
        "Example: ticking weapons and armor only turns every merchant into a gear seller. Requires "
        "Randomize what shops sell."
    ),
    "random_prices": (
        "Shuffles what shops charge.\n\n"
        "Every goods slot of every shop receives another slot's rune price (ShopLineupParam.value), so "
        "a slot filled by another randomizer is priced too, because the slot is what carries the price. "
        "Turning the option off leaves prices exactly as the game shipped them.\n\n"
        "Example: a Golden Rune [4] that cost 12,000 runes now costs 800. Risk: a rune that costs 800 "
        "makes levelling cheap for the whole run."
    ),
    "price_mode": (
        "How buy prices are rolled: shuffle or range.\n\n"
        "shuffle permutes the prices that already exist, so no price is invented and the total cost of "
        "a shop stays roughly the same. range draws a fresh price for every entry between the two "
        "limits, rounded so the numbers still look like shop prices.\n\n"
        "Example: range 500 to 20,000 asks 640 runes for a pot and 15,000 for a rune. Requires Shuffle "
        "shop prices."
    ),
    "price_min": (
        "Range method: the lowest buy price that may be drawn.\n\n"
        "An empty field uses the cheapest price that exists in the input today, so the draw starts from "
        "the game's own floor. The value applies to every slot of every shop, including weapons when "
        "they are sold.\n\n"
        "Example: 100 means no shop asks less than 100 runes for anything. Requires Shuffle shop "
        "prices, set to range."
    ),
    "price_max": (
        "Range method: the highest buy price that may be drawn.\n\n"
        "An empty field uses the most expensive price that exists in the input today. The number is the "
        "ceiling of the draw, not a guarantee: most items land well below it, because prices are drawn "
        "over orders of magnitude.\n\n"
        "Example: 20,000 means nothing costs more than 20,000 runes. Risk: the minimum cannot be above "
        "the maximum, and validation reports it. Requires Shuffle shop prices, set to range."
    ),
    "sell_prices": (
        "Also shuffles what merchants pay for goods.\n\n"
        "Buy and sell prices are drawn independently, so an item can sell for more than the shop asks "
        "for it. With this off, only the buy price changes and every sell value stays vanilla.\n\n"
        "Example: a shop asks 900 runes for a pot and pays 1,200 for it. Requires Shuffle shop prices."
    ),
    "sell_min": (
        "Range method: the lowest sell price that may be drawn.\n\n"
        "An empty field uses the lowest sell value that exists today. The value applies to the goods "
        "pool, and to weapons, armor and ashes when Include weapons, armor and Ashes of War is on.\n\n"
        "Example: 1 means a merchant always pays at least one rune. Requires Shuffle shop prices, "
        "Shuffle sell prices too, and the range method."
    ),
    "sell_max": (
        "Range method: the highest sell price that may be drawn.\n\n"
        "An empty field uses the highest sell value that exists today. A high ceiling makes selling "
        "loot a source of runes, which changes the economy far more than a price shuffle does.\n\n"
        "Example: 9,999 means the richest merchant pays 9,999 runes for anything. Requires Shuffle shop "
        "prices, Shuffle sell prices too, and the range method."
    ),
    "sell_equipment": (
        "Lets weapons, armor and Ashes of War join the sell-price shuffle.\n\n"
        "Merchants normally buy only goods. With this on, weapon, armor and Ash of War sell values are "
        "shuffled in three separate pools, and every affinity row of a weapon receives the same new "
        "value so one weapon does not sell at ten different prices.\n\n"
        "Example: a +10 Lordsworn's Greatsword that sold for 1,200 runes now sells for 48,000. Requires "
        "Shuffle shop prices."
    ),

    # ------------------------------------------------------------------ weapons
    "weapons": (
        "Switches the four weapon options on or off together.\n\n"
        "A shortcut for the command line that turns on Make somber weapons infusable, Shuffle movesets, "
        "Random default skill and affinity, and Randomize weapon stats in one flag. The window shows "
        "those four options individually and never needs the shortcut.\n\n"
        "Example: --weapons is the same as passing all four flags. Risk: it cannot switch only three "
        "of them on; use the individual options for that."
    ),
    "somber_infusable": (
        "Gives somber and unique weapons the twelve affinities of an ordinary weapon.\n\n"
        "A somber weapon has one row in the game, so it can never be infused and never carries an Ash "
        "of War. This adds the missing Heavy, Keen, Quality, Magic, Fire, Lightning, Holy, Poison, "
        "Blood, Cold, Occult and unique rows, copies the weapon's numbers into them and lets Ashes of "
        "War be mounted. Each added row receives a name and a description in the item text archive "
        "unless the text patch is turned off.\n\n"
        "Example: a somber Longsword now exists as Heavy, Keen and Occult as well as Standard, and can "
        "carry Lion's Claw. Risk: the rows are new ids, so a save made before the change does not know "
        "them."
    ),
    "random_weapon_onhit_shuffle": (
        "Permutes the complete on-hit bundle between weapons of the same class.\n\n"
        "A bundle is the three on-hit effect slots plus the three effect-text slots. Moving the text "
        "with the effect keeps the passive line in the inventory honest: the description a player reads "
        "belongs to the status the weapon actually causes. A dead placeholder id is cleared instead of "
        "being passed on, and a real non-status effect is preserved. Held effects and weapon numbers "
        "are not touched.\n\n"
        "Example: a Longsword that caused blood loss takes another sword's frostbite bundle, text "
        "included, and that sword takes the blood loss. Risk: a class can end up with a status its "
        "members rarely caused, because the bundles come from real weapons of that class."
    ),
    "random_weapon_holder_shuffle": (
        "Exchanges the held-effect bundle between weapons of the same class that already have one.\n\n"
        "A held effect is what a weapon grants while it is equipped: a shield that blocks for less "
        "stamina, a weapon that raises an attribute. Only rows that already carry such an effect take "
        "part, so a plain dagger never gains a shield's always-on effect, and rows with none stay "
        "empty. On-hit slots are untouched.\n\n"
        "Example: a shield that blocks for less stamina takes another shield's held effect, and that "
        "shield takes the first one's. Risk: a held effect can look odd on another weapon of the class, "
        "but every effect already exists on a real weapon of that class."
    ),
    "random_weapon_status_roll": (
        "Gives every weapon row zero to two real statuses.\n\n"
        "The pool is built from the loaded regulation rather than from fixed ids: every candidate is "
        "checked against SpEffectParam, must carry a build-up value above zero, and the ids the input's "
        "own weapons already use are always accepted. That is what prevents a passive that reads "
        "\"Poison (0)\" on a mod that renumbers its effect rows. A row never repeats a status family, "
        "the matching effect text is written with each status, and a slot that the game adds the "
        "upgrade level to receives only the base id of a growing series. 25% of rows get none, 55% one "
        "and 20% two.\n\n"
        "Example: a Dagger rolls frostbite and scarlet rot, while a Heavy Dagger rolls nothing. Risk: a "
        "weapon can lose its vanilla status or gain a rarer one; every id drawn exists in the loaded "
        "file."
    ),
    "random_loot_effects": (
        "Restricts the chaotic status draw to weapons that can be found as loot.\n\n"
        "A scope switch rather than a second pass: it needs Roll chaotic statuses and narrows that pass "
        "from every weapon row to the weapons that appear in enemy drop lots and map lots. Ordinary "
        "shop stock and starting weapons then keep their identity while found weapons are strange.\n\n"
        "Example: a looted Longsword causes frostbite while the Longsword a merchant sells stays "
        "ordinary. Risk: a loot weapon can share a status with another; the draw does not enforce "
        "variety. Requires Roll chaotic statuses."
    ),
    "random_default_ash": (
        "Gives every weapon row a random default skill and randomizes the affinity of found weapons.\n\n"
        "Each row receives an Ash of War as its default skill, drawn only from ashes that animate with "
        "that row's moveset, so the skill can be used the moment the weapon is picked up. The weapons "
        "handed out by map lots, shops and starting classes also receive a random affinity, which is "
        "what makes two copies of the same weapon play differently.\n\n"
        "Example: two Longswords, one Keen with Quickstep and one Heavy with Lion's Claw. Risk: a "
        "weapon's default skill can be one a player has not found yet, which is harmless because the "
        "skill is part of the row."
    ),
    "random_stats": (
        "Redraws the numbers of every weapon row.\n\n"
        "Attack per element, critical, poise and stamina damage, guard negation, attribute "
        "requirements, scaling, status build-up and stamina cost are all redrawn, for bows and "
        "catalysts as well as melee weapons. Every affinity row is drawn separately, so one weapon at "
        "two infusions really is two weapons. Requirements are derived from the scaling that was "
        "drawn, so a weapon that now scales with Intelligence also asks for Intelligence, and the "
        "result stays inside the weapon's own tier.\n\n"
        "Example: Longsword (Keen) rolls 118 physical, Longsword (Heavy) rolls 141. Risk: a low-tier "
        "weapon can roll better numbers than a high-tier one."
    ),
    "req_mode": (
        "How far attribute requirements may move from the vanilla values: tight, normal or wild.\n\n"
        "tight keeps a dagger in single figures and a greatsword in the dozens, so a looted weapon is "
        "almost always usable by a character of the right level. normal is the widest band that still "
        "respects the weapon's own tier. wild can put a starter weapon behind thirty points of "
        "Strength. In every band the requirement follows the scaling that was drawn.\n\n"
        "Example: tight gives a dagger 4 to 6 Strength and 7 to 11 Dexterity where it had 5 and 9. "
        "Risk: wild can produce a weapon a character cannot use for a long time. Requires Randomize "
        "weapon stats."
    ),
    "stat_groups": (
        "Chooses which groups of weapon numbers are redrawn.\n\n"
        "attack covers damage per element; guard covers damage negation and guard boost; requirements "
        "covers the attribute minimums; scaling covers the letters and their weights; effects covers "
        "critical, poise damage and status build-up; stamina covers the stamina cost multiplier. An "
        "empty selection means all six, and anything unticked stays exactly as the weapon had it.\n\n"
        "Example: ticking attack and scaling only changes how a weapon hits, never what it asks for. "
        "Requires Randomize weapon stats."
    ),
    "stamina_rate": (
        "The range the stamina cost multiplier is drawn from.\n\n"
        "Every weapon row's stamina cost is multiplied by a value inside this range, written as low "
        "then high, and the cost is normalised so the first light attack costs the weapon's base cost "
        "times the multiplier whatever moveset the row ended up with. 0 allows a free attack and 2.0 "
        "doubles the cost.\n\n"
        "Example: 0.5 to 1.5 means no weapon costs more than one and a half times its vanilla stamina. "
        "Risk: a value near 0 makes a heavy weapon cost nothing to swing. Requires Randomize weapon "
        "stats."
    ),
    "weapon_names": (
        "Where the names of the new affinity rows are written.\n\n"
        "Making somber weapons infusable adds twelve rows per weapon, and the game shows a placeholder "
        "for a row with no name. The tool writes a name and a description for each new row into the "
        "item text archive (item_dlc02.msgbnd.dcx) of every folder given, using the word each language "
        "already uses for that affinity and the Paramdex name of the weapon. An id that already has a "
        "name is never overwritten, so a mod's own text survives.\n\n"
        "Example: Heavy Longsword, Keen Longsword through Occult Longsword. Risk: a folder that "
        "belongs to a different game version is refused rather than written. Requires Make somber "
        "weapons infusable."
    ),
    "no_weapon_names": (
        "Makes somber weapons infusable without writing any text archive.\n\n"
        "The twelve added rows then appear in game with a placeholder name instead of \"Heavy "
        "Longsword\". This keeps a mod folder free of a msg directory, which matters when another mod "
        "already owns that folder and its files should not be touched.\n\n"
        "Example: a run that only wants the extra affinities for its own testing uses this. Risk: every "
        "new row shows a placeholder, so the inventory is hard to read. Requires Make somber weapons "
        "infusable."
    ),
    "random_movesets": (
        "Gives every melee weapon and shield another weapon's moveset.\n\n"
        "A moveset is the animation set plus the attack behaviour: the swing, the timing and the "
        "hitbox. With this on a Longsword can swing like a greatsword, a dagger like a colossal sword "
        "and a shield like a mace. Shields swap only with shields and bows only with bows, so a "
        "left-hand shield still guards and a bow still fires arrows, and damage, requirements and "
        "statuses stay with the weapon itself.\n\n"
        "Example: a Short Sword swings with the slow rhythm of a colossal sword while keeping a short "
        "sword's damage. Risk: a slow moveset on a fast weapon makes the weapon feel worse, which the "
        "Weapon type follows the moveset option can partly offset."
    ),
    "moveset_mode": (
        "How the new movesets are handed out: affinity, bound or weapon.\n\n"
        "affinity draws a separate moveset for every affinity row, so one Longsword's Heavy row and "
        "Keen row can move differently. bound draws rows from per-affinity clusters and keeps only the "
        "affinities each Ash of War can animate. weapon gives one moveset to the whole weapon and "
        "changes the weapon type to match, which keeps the smithing table coherent.\n\n"
        "Example: affinity is the most chaotic, weapon the most coherent. Risk: affinity can leave a "
        "row whose moveset no Ash of War animates; bound avoids that at the cost of variety. Requires "
        "Shuffle movesets."
    ),
    "moveset_variety": (
        "Bound mode: how many animation styles each affinity owns.\n\n"
        "1 gives every weapon of an affinity the same moveset. 3 is the default and mixes three styles "
        "per affinity. A higher number mixes more styles but leaves fewer affinities that an Ash of War "
        "can animate, so some ashes lose usable infusions.\n\n"
        "Example: 2 gives two styles per affinity, so a Heavy Longsword and a Heavy Dagger may share "
        "one. Risk: above 3 or 4 some ashes end up with fewer usable affinities. Requires Shuffle "
        "movesets, set to bound."
    ),
    "keep_standard": (
        "Affinity mode: leaves each weapon's own Standard row alone.\n\n"
        "The weapon keeps its original moveset at +0 and only the twelve infused rows are randomized, "
        "so a weapon found plain still feels like itself while its infusions are strange. Bound mode "
        "always keeps Standard rows, so the option has no effect there.\n\n"
        "Example: a Longsword at +0 swings normally, at Heavy it swings like a hammer. Requires Shuffle "
        "movesets."
    ),
    "shield": (
        "What shields may swap movesets with: shields, none or all.\n\n"
        "shields keeps the swap inside the four shield animation sets and never gives a shield's "
        "moveset to a weapon, so a left-hand shield still blocks. none leaves shields untouched. all "
        "lets shields and weapons swap freely.\n\n"
        "Example: shields gives a kite shield that bashes like a greatshield. Risk: all can make a "
        "left-hand shield attack instead of guarding, which breaks a block build. Requires Shuffle "
        "movesets."
    ),
    "bow": (
        "What bows, crossbows and ballistae may swap movesets with: bows or none.\n\n"
        "bows keeps the swap inside the bow class, with ammunition unchanged, so a longbow can draw "
        "like a crossbow but still uses arrows. none leaves the class untouched.\n\n"
        "Example: a short bow that draws and fires like a greatbow, still using arrows. Requires "
        "Shuffle movesets."
    ),
    "weptype": (
        "Makes the weapon type follow the moveset.\n\n"
        "Each randomized row also takes the donor's weapon type. The smithing table reads that type to "
        "decide which Ashes of War to list, so the list matches the animation the row actually got "
        "instead of the weapon's old class. Damage and requirements are untouched.\n\n"
        "Example: a row that swings like a hammer is listed as a hammer, so only hammer ashes appear. "
        "Risk: the game's save checks have not been exercised against every type change, so mounting a "
        "safe Ash before switching regulation.bin is prudent. Requires Shuffle movesets."
    ),

    # ------------------------------------------------------------------ armour and talismans
    "random_armor_fresh": (
        "Rolls every armor piece's numbers again instead of swapping them.\n\n"
        "Each column of each piece is drawn inside the range its own slot uses in vanilla, so a helm "
        "rolls like a helm and a chest piece like a chest piece. No two pieces share a stat block, and "
        "a starter piece can roll near a late-game one while staying inside the slot's range.\n\n"
        "Example: the Iron Helmet's 0.972 negation becomes 0.952 and its 8.1 weight becomes 11.5. Risk: "
        "a light set can roll heavy; Shuffle armor stats widens the spread further."
    ),
    "armour_keep_sets": (
        "Keeps armor sets internally consistent when their numbers are rolled again.\n\n"
        "Pieces that share a set name (Knight Helm, Knight Armor, Knight Gauntlets, Knight Greaves) are "
        "scaled by one factor instead of being rolled separately, so the set keeps its balance while "
        "still differing from vanilla. Turning it off rolls every piece on its own.\n\n"
        "Example: a Knight set stays a knight set, with all four pieces moving up or down together. "
        "Risk: with it off one piece of a set can roll well and another uselessly. Requires Randomize "
        "armor stats."
    ),
    "random_armor": (
        "Swaps armor numbers between pieces of the same slot.\n\n"
        "Every column, including damage negation, resistances, poise and weight, is permuted among the "
        "pieces that occupy the same slot, so a helm receives another helm's numbers and no value is "
        "invented. Only values the game already uses are dealt out.\n\n"
        "Example: the Iron Helmet's 0.972 negation and 8.1 weight become the Kaiden Helm's 0.942 and "
        "3.8. Risk: a plain-looking piece can end up with excellent negation, which is the point of the "
        "shuffle."
    ),
    "random_talismans": (
        "Gives every talisman another talisman's effect and numbers.\n\n"
        "Whole talisman rows are permuted, so every talisman keeps its name and its icon while receiving "
        "another talisman's effect and values. This tool has no field table for the accessory param, so "
        "whole rows move rather than single stats.\n\n"
        "Example: Erdtree's Favor +2 carries the numbers of Dragoncrest Greatshield Talisman +3. Risk: "
        "the icon belongs to the row, so a talisman can show the icon of the effect it received."
    ),
    "random_flask_locations": (
        "Moves the two healing flasks somewhere else in the world.\n\n"
        "The Flask of Crimson Tears and the Flask of Cerulean Tears are placed at a random pickup, boss "
        "reward, NPC gift or merchant, and whatever was at that spot is moved to the first Site of "
        "Grace instead. Chance drops, map fragments and one-time rows are never used as a destination.\n\n"
        "Example: the flask that stood at the Stranded Graveyard becomes a boss reward in Caelid. Risk: "
        "without a region restriction both flasks can end up late in the game."
    ),
    "flask_where": (
        "Where the two flasks may end up: anywhere, overworld or early.\n\n"
        "anywhere allows any real location: a pickup, a boss reward, an NPC gift or a merchant. "
        "overworld keeps them out of dungeons, caves, catacombs, evergaols and the late-game regions. "
        "early keeps them in the regions reachable first: Limgrave, the Weeping Peninsula, Stormveil, "
        "Murkwater, Agheel Lake and Liurnia.\n\n"
        "Example: early puts the Crimson Tears in a Limgrave pickup and the Cerulean Tears in a Liurnia "
        "merchant's stock. Risk: early fails loudly when a region has no eligible spot. Requires Move "
        "the two flasks."
    ),
    "start_bell": (
        "Starts the game with the Spirit Calling Bell.\n\n"
        "The bell is normally bought from the Twin Maiden Husks. This hands it out with the flasks at "
        "the very start, which matters in a fog gate run where the hub may be out of reach early.\n\n"
        "Example: a new character begins with the flasks and the bell already in the inventory."
    ),
    "start_lantern": (
        "Starts the game with the Lantern.\n\n"
        "The nomadic merchants sell the Lantern in Liurnia and the Weeping Peninsula, which a fog gate "
        "run may not reach early. This hands it out with the flasks at the start, so dark caves are lit "
        "from the first minute.\n\n"
        "Example: a character begins with the Lantern and no runes spent on it."
    ),

    # ------------------------------------------------------------------ loot and drops
    "random_enemy_drops": (
        "Replaces the contents of every enemy drop table with random loot from the game's own item "
        "pools.\n\n"
        "Each kill rolls a number of independent dice, and every die has its own chance of producing "
        "an item, so a kill can give nothing, one item or several. Items are drawn from five weighted "
        "categories (goods 40, weapons 25, armor 20, talismans 10, Ashes of War 5), a lot never repeats "
        "an item it already rolled, and a row that awards a key item or a one-time flag drop is left "
        "untouched. The pool is every item the input hands out somewhere: pickups, rewards, gifts, "
        "shops and its own drop tables.\n\n"
        "Example: 3 rolls at 10% give nothing on 73% of kills, one item on 24% and three items "
        "occasionally; a lucky soldier can drop a sword, a pair of gauntlets and a grease at once. Risk: "
        "a boss can drop something trivial, and the chance and rolls are the only knobs that control "
        "it."
    ),
    "enemy_drop_rolls": (
        "The number of independent dice rolled for each enemy killed.\n\n"
        "Every die uses Chance per roll, so the chance that a kill gives nothing is one minus the "
        "chance, raised to the number of rolls, and the expected number of items is rolls times chance. "
        "0, or an empty field, means one guaranteed item per kill. An item that drops is still subject "
        "to the category pool and to Random upgrade levels on loot.\n\n"
        "Example: 3 rolls at 25% average 0.75 items per kill, and 5 rolls at 50% average 2.5. Risk: "
        "many rolls also mean many upgrade-level rolls, so high-level gear becomes more common. "
        "Requires Randomize enemy drops."
    ),
    "enemy_drop_chance": (
        "The weight of each drop die, in percent.\n\n"
        "From 1 to 100, applied to every roll including the first, so no item is guaranteed unless the "
        "chance is 100 or the rolls are set to 0. It is independent of Rolls per enemy: the chance "
        "decides how often a die lands, the rolls decide how many dice there are.\n\n"
        "Example: 1 roll at 10% makes one kill in ten drop something, while 3 rolls at 10% make one kill "
        "in four drop at least one item. Risk: raising the chance also raises how often uniques and "
        "upgrade materials appear, because those draws only happen when a die lands. Requires Randomize "
        "enemy drops."
    ),
    "enemy_drop_kinds": (
        "Chooses which kinds of item a random enemy drop can be.\n\n"
        "Weapons, armor, talismans, goods and Ashes of War can be ticked independently, and an empty "
        "selection means all five, which is the default. Rows that award a key item and one-time flag "
        "rewards are left alone whatever this says.\n\n"
        "Example: ticking weapons and armor only turns every enemy into a gear pinata and removes "
        "consumable clutter from drops. Requires Randomize enemy drops."
    ),
    "unique_drops": (
        "Allows unique weapons to appear in random enemy drops.\n\n"
        "Off by default: with it off no random drop is ever a unique weapon, whatever the rate says. "
        "When on, every item that actually drops rolls the unique rate, and a hit replaces the ordinary "
        "draw with a unique weapon that cannot be infused or reinforced. A unique weapon is a named "
        "weapon with a single row and no smithing material set.\n\n"
        "Example: at 3% and 3 rolls at 25%, about one unique appears every 44 kills. Risk: because the "
        "roll happens per dropped item rather than per kill, a low drop chance keeps uniques rare even "
        "at a high rate. Requires Randomize enemy drops."
    ),
    "unique_rate": (
        "How often a dropped item is a unique weapon, in whole percent.\n\n"
        "From 1 to 20, rolled once per item that actually drops rather than once per kill, so the "
        "effective frequency is the drop rate multiplied by this value. The field is greyed out unless "
        "Rare unique weapons is on. When upgrade material drops are also on, the material roll happens "
        "first and lowers the effective unique rate slightly.\n\n"
        "Example: at 10% with 3 rolls at 25%, a unique shows up about every 13 kills; at 2% the same "
        "settings give one every 67 kills. Risk: at 20% uniques stop feeling special. Requires "
        "Randomize enemy drops and Rare unique weapons."
    ),
    "material_drops": (
        "Lets enemies drop upgrade materials now and then.\n\n"
        "Each item that drops has an 8% chance to be a smithing stone instead of the ordinary draw, in a "
        "stack of one to five. The material roll happens before the unique roll, so one drop cannot be "
        "both. Sparse by design, so materials stay something a player goes looking for.\n\n"
        "Example: with 3 rolls at 25%, a kill has a 6% chance of a material, about one every 17 kills. "
        "Risk: with both rare options on, the effective unique rate falls by 8%. Requires Randomize "
        "enemy drops."
    ),
    "random_loot_levels": (
        "Gives the weapons the game hands out a random upgrade level.\n\n"
        "A weapon id is the base weapon plus its affinity plus its upgrade level, and vanilla drop "
        "tables, chests, boss rewards and shops all use +0. This rewrites the level part of those ids "
        "for enemy drop tables, map lots (chests, rewards, gifts, pickups) and weapon shop slots. The "
        "level is drawn from a curve against the weapon's own ceiling: 25 for a weapon with affinity "
        "rows, 10 for a somber weapon, 0 for a unique weapon that cannot be reinforced. Starting "
        "classes are left alone.\n\n"
        "Example: a Longsword that drops at +5 and another copy at +0. Risk: every drop row rolls the "
        "level again, so a generous drop setting produces more high levels."
    ),
    "loot_rarity": (
        "How the upgrade level is drawn, so that a +25 stays an event: even, common or legendary.\n\n"
        "common gives 55% of drops at +0 to +3, 28% at +4 to +9, 12% at +10 to +15, 4% at +16 to +20 "
        "and 1% at +21 to +25. legendary gives 70% at +0 to +2, 20% at +3 to +8, 7% at +9 to +14, 2.5% "
        "at +15 to +20 and 0.5% at +21 to +25. even makes every level equally likely. The same shares "
        "scale to a somber weapon's +10.\n\n"
        "Example: common produced 3 drops at +21 or better out of 780 in a measured run. Risk: the level "
        "is rolled per drop, so a high drop rate produces far more top-end gear. Requires Random "
        "upgrade levels on loot."
    ),
    "loot_boss_bonus": (
        "Bosses roll their upgrade level from a better curve: same, better or best.\n\n"
        "same gives every enemy the chosen curve. better lets bosses use the next curve up, so even "
        "becomes common and common becomes legendary. best makes bosses always use the legendary curve. "
        "A boss is an enemy with the isSoulGetByBoss flag, plus every enemy at or above the boss rune "
        "threshold when that is set.\n\n"
        "Example: with common and best, a boss can drop a +24 while a soldier drops a +2. Requires "
        "Random upgrade levels on loot."
    ),
    "loot_max_level": (
        "The highest upgrade level a dropped weapon may roll.\n\n"
        "An empty field or 0 means no cap, so a weapon can reach its own ceiling: +25, or +10 for a "
        "somber weapon. A number lowers every weapon's ceiling to that value, which is the simplest way "
        "to keep a run from handing out endgame gear in Limgrave.\n\n"
        "Example: 10 keeps every drop at +10 or lower, somber weapons included. Risk: a cap below a "
        "weapon's own maximum makes the top of its curve unreachable, so +25 drops never appear. "
        "Requires Random upgrade levels on loot."
    ),
    "zone_loot_levels": (
        "Scales weapon upgrade levels with the area the loot is found in.\n\n"
        "Limgrave and the Weeping Peninsula stay low, Liurnia, Caelid and Altus mid, the Mountaintops, "
        "Haligtree and Farum Azula high, and the Land of Shadow at the full ceiling, with the draw curve "
        "shifting toward even in late areas so the average climbs as well as the ceiling. Enemy drops "
        "belong to an enemy rather than a place, so only chests, boss rewards and shops scale.\n\n"
        "Example: an early chest holds a +1 weapon while a Haligtree chest can hold +20. Requires Random "
        "upgrade levels on loot."
    ),
    "random_weapon_drops": (
        "Moves weapons to other enemies without changing the weapons.\n\n"
        "Every weapon keeps its affinity, its upgrade level and its numbers, and only the place it "
        "drops changes, so any enemy can drop any weapon. Enemy drop tables, map lots and weapon shops "
        "take part, and one-time flag drops are never moved.\n\n"
        "Example: a Longsword +5 that was a chest reward becomes a drop from a rat. Risk: none for the "
        "weapon itself, but a powerful weapon can end up behind a trivial enemy."
    ),
    "random_dropped_weapons": (
        "Every weapon slot in the enemy drop lots and the map lots (chest pickups, boss rewards, gifts) shows a random weapon.\n\nThe pass rewrites the weapon id of every weapon slot to a fresh draw from the pool that 'Move weapons to random enemies' uses - the weapons the input hands out somewhere. Slots take distinct weapon rows where the world has them: two rows of one appearance are two instances (different stats), so the same appearance can be found in two loot spots with different stats; where the world has no other row, the repeat is forced. It changes what you find when you pick up a drop, not where loot drops and not what a weapon is; the drop still comes from the same lot, but the weapon it shows is a new, random one every run.\n\nExample: the [Omen] drop of 214000990 (Omen Cleaver) now drops a different random weapon. Risk: it changes what drops, not what weapons are - see Randomize weapon stats."
    ),
    "random_dropped_shop_weapons": (
        "Rerolls the weapon slots of every weapon shop (ShopLineupParam).\n\n"
        "The per-run reroll: the weapon each merchant slot sells is redrawn from the pool of weapons the "
        "world has, so what you buy changes every run; where the world has different rows of one "
        "appearance, sold weapons are distinct rows. Only weapon slots are touched; the shop's other "
        "slots are unchanged.\n\n"
        "Example: a weapon shop sells a different random weapon every run. Risk: none - the shop stock "
        "is the run's random draw, like every other option. Requires Randomize dropped weapons."
    ),
    "loot_variants": (
        "Rerolls a weapon on every pickup, so five copies of one sword are five different swords.\n\n"
        "A weapon id is its base, an affinity and an upgrade level. This writes a small manifest for "
        "the optional runtime mod in mods/loot-variants: which affinity rows exist, the weapon's own "
        "upgrade ceiling and which Ashes of War fit each row. The DLL draws a fresh affinity, level "
        "and Ash each time the game hands you that weapon, in drops, chests, boss rewards and shops. "
        "The model, icon and moveset stay recognisable; the stats, scaling, status build-up and skill "
        "change. Weapon rows are never cloned; the optional armour-variant pass adds only the extra "
        "rows you ask for.\n\n"
        "Example: looting the same sword five times gives five different rolls. Risk: it needs the DLL "
        "installed, and it replaces the static level roll for these weapons; without the DLL the "
        "regulation is still a complete run."
    ),
    "armor_variants": (
        "Gives each armour piece extra stat blocks with the same look, so picks differ by more than level.\n\n"
        "The pass clones a few EquipParamProtector rows, changes only the selected stat columns, and "
        "copies every appearance field: model, icons, slot and name. The runtime mod then draws one of "
        "those ids on each pickup, on top of the ordinary +0..+10 reroll. Standard, weighted and "
        "somber pieces keep their own reinforce rules because each clone inherits its source row.\n\n"
        "Example: four variants of the same helm give four defence profiles under one model. Risk: each "
        "clone costs about 416 bytes before compression; keep the count modest on large modpacks."
    ),
    "armor_variant_stats": (
        "Chooses which armour numbers the variant pass is allowed to change.\n\n"
        "Negation covers the eight damage-type cut rates, resistance covers the seven status resistances, "
        "poise covers durability and toughness correction, and weight changes how heavy the piece is. "
        "Unselected columns stay exactly as the input wrote them, so a heavy set stays heavy if you "
        "leave weight off.\n\n"
        "Example: negation plus resistance gives different protection but identical poise and weight. "
        "Risk: wide ranges can produce unusual pieces; the values stay inside the vanilla range of "
        "the piece's own slot."
    ),
    "rarity_labels": (
        "Adds a plain-text rarity tag to weapon and armour names in the patched item text.\n\n"
        "The game's item archives contain no verified colour control code, so this writes an honest "
        "label instead: a Common, Uncommon, Rare or Legendary row gets [COMMON], [UNCOMMON], [RARE] "
        "or [LEGENDARY] after its name. The tag comes from the row's own rarity field and is "
        "idempotent, so running twice never stacks labels.\n\n"
        "Example: Iron Helmet [RARE] in the inventory. Risk: the tag is literal text; if a real "
        "colour code is confirmed later it can replace the brackets without changing the rest."
    ),
    "random_armor_drops": (
        "Moves armor to other enemies without changing the armor.\n\n"
        "Every piece keeps its numbers and only the place it drops changes, so a chest piece from one "
        "dungeon can end up on a soldier on the other side of the map. Enemy drop tables, map lots and "
        "armor shops take part, and one-time flag drops are never moved.\n\n"
        "Example: the Exile Hood from Castle Morne becomes Radahn's Redmane Helm. Risk: a set can be "
        "split across the map, which Move armor sets as a set prevents."
    ),
    "armour_drop_sets": (
        "Moves armor sets as a set instead of piece by piece.\n\n"
        "Pieces that share a set name (Knight Helm, Knight Armor, Knight Gauntlets, Knight Greaves) are "
        "moved together, so a whole set is replaced by another whole set and finding one piece tells a "
        "player what the rest of that set is. Turning it off moves each piece on its own.\n\n"
        "Example: finding the Knight Helm means the other three Knight pieces are the ones that "
        "replaced its set. Risk: only sets with the same number of pieces swap with each other, so a "
        "few sets do not move at all. Requires Move armor to random enemies."
    ),
    "random_talisman_drops": (
        "Moves talismans to other enemies without changing the talismans.\n\n"
        "Every talisman keeps its name, effect and numbers, and only the place it is found changes. "
        "Shops are included and one-time flag drops are never moved.\n\n"
        "Example: Host's Trick-Mirror from a merchant becomes Lord of Blood's Exultation. Risk: a "
        "talisman a build needs can move behind a late boss."
    ),
    "random_goods_drops": (
        "Moves goods to other enemies without changing the goods.\n\n"
        "Every consumable keeps its effect and stack size, and only the place it drops changes, so a "
        "grease that sat in a chest can end up on a soldier across the map. Enemy drop tables, map lots "
        "and goods shops take part, and one-time flag drops are never moved.\n\n"
        "Example: a Golden Rune [4] that was a pickup becomes a boss reward. Risk: a utility item such "
        "as a bolus can become rare, because the shuffle ignores how useful an item is."
    ),
    "random_ashes_drops": (
        "Moves Ashes of War to other enemies without changing the ashes.\n\n"
        "Every ash keeps its skill and its effects, and only the place it drops changes, so any enemy "
        "can drop any ash. Enemy drop tables, map lots and the shops that sell ashes take part, and "
        "one-time flag drops are never moved.\n\n"
        "Example: Lion's Claw that was a boss reward becomes a drop from a soldier. Risk: an ash needed "
        "for a build can move behind content that comes much later."
    ),

    # ------------------------------------------------------------------ ashes of war
    "random_gem_skills": (
        "Gives every Ash of War another ash's skill.\n\n"
        "The skill is the animation and the hit logic that plays when the ash is used. Permuting it "
        "means Lion's Claw can become Sky Shot, and donors are drawn only from ashes that can be "
        "mounted on the same weapon types, so a skill never lands where it could not animate. The name "
        "of the ash stays with its row.\n\n"
        "Example: Ash of War: Through and Through gains the skill of Rain of Arrows. Risk: a name and "
        "its skill can disagree, which is the point of the shuffle."
    ),
    "random_gem_effects": (
        "Gives every Ash of War another ash's on-hit effects.\n\n"
        "Some ashes add bleed, frostbite, a buff or damage over time when they connect. Those effect "
        "triples are swapped between ashes with the same weapon-type grouping as the skill shuffle, and "
        "the three slots of one ash always travel together. Only a few dozen ashes carry effects, so "
        "this changes less than the skill shuffle.\n\n"
        "Example: an ash that caused frostbite now causes blood loss. Risk: an ash whose skill does not "
        "hit can carry an on-hit effect that never triggers."
    ),

    # ------------------------------------------------------------------ enemies: health and runes
    "random_enemy_hp": (
        "Redraws how much health every enemy has.\n\n"
        "Every NpcParam row with hit points above zero takes part. shuffle permutes the values that "
        "exist, so the world total is unchanged and a rat can end up with a dragon's health. range "
        "draws new values between two limits, and bands picks a band per enemy so most stay near their "
        "old toughness.\n\n"
        "Example: a soldier with 400 HP next to a boss with 1,200. Risk: shuffle can make a boss trivial "
        "and a rat a wall; the boss multiplier range can scale bosses back up."
    ),
    "hp_mode": (
        "How enemy health is rolled: shuffle, range, bands or balanced.\n\n"
        "shuffle permutes the hit point values that exist. range draws a new value for every enemy "
        "between the two limits, spread over orders of magnitude. bands gives 50% of enemies 0.5 to 1.5 "
        "times their vanilla value, 35% 1.5 to 2.5 times and 15% 2.5 to 4 times. balanced keeps every "
        "enemy within 0.75 to 1.5 times its vanilla value, so there are no bullet sponges and no "
        "pushovers.\n\n"
        "Example: range 0 to 200 means nothing has more than 200 HP, bosses included. Requires Shuffle "
        "enemy HP."
    ),
    "hp_min": (
        "Range method: the lowest hit point value that may be drawn.\n\n"
        "An empty field uses the lowest value that exists in the input today. Every enemy that has hit "
        "points is drawn above this floor, so a high floor makes the whole game tougher.\n\n"
        "Example: 1 means every enemy can be killed with one hit. Requires Shuffle enemy HP, set to "
        "range."
    ),
    "hp_max": (
        "Range method: the highest hit point value that may be drawn.\n\n"
        "An empty field uses the highest value that exists in the input today. The number is the "
        "ceiling of the draw, so a boss and a rat can both land near it, and the rune coupling follows "
        "whatever is rolled.\n\n"
        "Example: 5000 means the hardest fight in the game is a 5,000 HP enemy. Requires Shuffle enemy "
        "HP, set to range."
    ),
    "random_runes": (
        "Redraws how many runes every enemy gives.\n\n"
        "Every enemy's rune bounty (NpcParam.getSoul) is replaced. shuffle permutes the amounts that "
        "exist, so the world total is unchanged and a rat can be worth a dragon; range draws new "
        "amounts between two limits; bands multiplies each enemy's own bounty by a band.\n\n"
        "Example: a rat worth 40,000 runes and a shardbearer worth 120. Risk: with shuffle a rich enemy "
        "means a poor one somewhere, because the total is fixed."
    ),
    "rune_mode": (
        "How rune drops are rolled: shuffle, range or bands.\n\n"
        "shuffle keeps the world's total runes and moves them between enemies. range ignores the "
        "existing values and draws new ones between the limits. bands multiplies every enemy's own "
        "bounty by a band: 50% of enemies get 0.5 to 1.5 times, 35% get 1.5 to 2.5 times and 15% get "
        "2.5 to 4 times, so most enemies stay near their old worth.\n\n"
        "Example: range 1 to 99,999 means a boss and a rat can be worth the same. Requires Shuffle enemy "
        "runes."
    ),
    "rune_min": (
        "Range method: the fewest runes an enemy can give.\n\n"
        "An empty field uses the lowest amount that exists in the input today. The floor applies to "
        "every enemy that gives runes at all, so a high floor makes levelling quick.\n\n"
        "Example: 1 means every enemy gives something. Requires Shuffle enemy runes, set to range."
    ),
    "rune_max": (
        "Range method: the most runes an enemy can give.\n\n"
        "An empty field uses the highest amount that exists in the input today. The number is the "
        "ceiling of the draw; most enemies land well below it because amounts are drawn over orders of "
        "magnitude.\n\n"
        "Example: 500,000 means a single kill can fund several levels. Requires Shuffle enemy runes, set "
        "to range."
    ),
    "boss_hp_scale": (
        "Multiplies every boss's hit points by a factor drawn from a range.\n\n"
        "The multiplier is applied after the HP pass, so a boss that the shuffle weakened is scaled "
        "back up and keeps both effects. A boss is an enemy with the isSoulGetByBoss flag, plus every "
        "enemy at or above the boss rune threshold when that is set. 1.0,1.0 switches the option off.\n\n"
        "Example: 1.5,2.0 makes every boss half again to twice as tough as the value it rolled. Risk: a "
        "boss that already rolled a high value can become a long fight."
    ),
    "boss_rune_scale": (
        "Multiplies every boss's rune bounty by a factor drawn from a range.\n\n"
        "The multiplier is applied after the rune pass, so a boss whose bounty was shuffled away stays "
        "worth the fight. A boss is an enemy with the isSoulGetByBoss flag, plus every enemy at or above "
        "the boss rune threshold when that is set. 1.0,1.0 switches the option off.\n\n"
        "Example: 1.5,2.0 pays a boss half again to twice its rolled bounty. Risk: with a high "
        "multiplier on a shuffled world, one boss can fund the rest of the run."
    ),
    "couple_runes_to_hp": (
        "Recomputes every enemy's rune bounty from its randomized hit points.\n\n"
        "Each enemy keeps its original worth per hit point, and the bounty is recomputed from the new "
        "HP, so a tougher enemy gives more runes and a pushover fewer. It runs after the rune shuffle "
        "and therefore overrides that shuffle when both are on; boss multipliers still apply "
        "afterwards.\n\n"
        "Example: an enemy that rolled twice its old HP gives about twice the runes. Requires Shuffle "
        "enemy HP."
    ),
    "boss_min_runes": (
        "Also treats an enemy as a boss when its unmodified bounty reaches this many runes.\n\n"
        "0 uses the isSoulGetByBoss flag alone, which is the default. A positive value adds high-bounty "
        "enemies on top of the flag, which widens everything that acts on bosses: the two boss "
        "multipliers and the boss curve for loot levels.\n\n"
        "Example: 5000 also treats every 5000-rune enemy as a boss. Risk: a low threshold turns elite "
        "enemies into bosses and multiplies their health and runes."
    ),

    # ------------------------------------------------------------------ consumables: durations
    "random_durations": (
        "Redraws how long buffs last.\n\n"
        "Greases, meats, blessings and buff spells keep their effect and receive a new duration "
        "(SpEffectParam.effectEndurance). Timed effects under five seconds are treated as mechanics, "
        "such as holy water, cures and the frenzy seal, and are never touched.\n\n"
        "Example: a Fire Grease that lasted 80 seconds lasts 40. Risk: a buff can end before a boss "
        "fight is over."
    ),
    "duration_mode": (
        "How buff durations are rolled: shuffle or range.\n\n"
        "shuffle keeps the set of durations that exist and moves them between buffs, so no duration is "
        "invented. range draws a new duration for every buff between the two limits, in seconds.\n\n"
        "Example: range 10 to 600 makes every buff last between ten seconds and ten minutes. Requires "
        "Shuffle buff durations."
    ),
    "duration_min": (
        "Range method: the shortest buff duration, in seconds.\n\n"
        "An empty field uses the shortest duration that exists in the input today. It applies to every "
        "timed effect that is treated as a buff.\n\n"
        "Example: 10 means no buff is shorter than ten seconds. Requires Shuffle buff durations, set to "
        "range."
    ),
    "duration_max": (
        "Range method: the longest buff duration, in seconds.\n\n"
        "An empty field uses the longest duration that exists in the input today. A high ceiling can "
        "turn a short grease into an all-purpose buff that outlasts several encounters.\n\n"
        "Example: 600 means every buff lasts ten minutes at most. Requires Shuffle buff durations, set "
        "to range."
    ),

    # ------------------------------------------------------------------ advanced
    "brief_reports": (
        "Writes only the summary lines of each report.\n\n"
        "drops.txt and hp.txt list every enemy and reach about 500 KB each; with this on they keep the "
        "summary lines and shrink to a few kilobytes. mapping.txt always stays complete, and the full "
        "detail is still printed to the console and the log.\n\n"
        "Example: a 509 KB drops.txt becomes 688 bytes. Risk: a per-enemy record is no longer available "
        "after the run."
    ),
    "zstd_window": (
        "The window size of the zstd output; leave it at 16.\n\n"
        "A log of 16 means a 64 KB window, which is the only value Elden Ring accepts. The other values "
        "exist for experiments and produce files the game may refuse. The setting only affects the "
        "zstd codec; kraken and leviathan have no window.\n\n"
        "Example: 16 is the default and the safe value for every game version. Risk: any other value "
        "can crash the game at load."
    ),
}
