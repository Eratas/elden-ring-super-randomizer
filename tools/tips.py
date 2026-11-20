"""The hover text of every option.

Shape of every entry, in this order:

  line 1      a short summary - this is also what `randomize.py --help` shows
  paragraph   what the option does, in plain words, for someone who plays the game
  Example:    one concrete sentence, when an example makes it click
  Risk:       what it costs or what can go wrong, when there is something real to say

Plain text only: the tooltip is a plain label, so no markdown and no indentation - long lines wrap by
themselves.  Keep the first paragraph short and the whole thing readable at a glance.
"""
from __future__ import annotations

TIPS: dict[str, str] = {
    # ------------------------------------------------------------------ files
    "input": (
        "The regulation.bin to rewrite.\n\n"
        "It can be the vanilla file from the game's Game folder, or one another randomizer already wrote. "
        "The tool only reads it, so the original is never changed. Use Find to look for it, or Browse.\n"
        "Example: C:\\Games\\ELDEN RING\\Game\\regulation.bin, or C:\\Games\\ERR\\mod\\regulation.bin for "
        "Elden Ring Reforged."
    ),
    "output": (
        "Where the new regulation.bin and the reports go.\n\n"
        "Give it a folder of its own. Next to the file the tool writes the reports, and a msg folder when "
        "weapon names are patched. Writing into the input's folder is refused, because that would fill a mod "
        "folder with reports.\n"
        "Example: D:\\mods\\my-randomizer\\regulation.bin.\n"
        "Risk: an output named regulation.bin in the input's folder would replace the input, which is why "
        "the tool stops instead."
    ),
    "seed": (
        "Fix the seed so the same run can be repeated.\n\n"
        "Every roll comes from one random generator. The same seed with the same options gives exactly the "
        "same items, drops and stats. Leave it empty for a fresh seed; the one used is printed in the log and "
        "in mapping.txt.\n"
        "Example: seed 12345 gives the same world every time."
    ),
    "compression": (
        "How the output is compressed: kraken, leviathan (the game's own Oodle) or zstd (no DLL).\n\n"
        "kraken gives a small file and needs oo2core_6_win64.dll from the game's Game folder. leviathan "
        "is Oodle's stronger setting: a little smaller than kraken, a little slower. zstd needs no DLL "
        "but the file is about a third larger. auto picks kraken when the DLL is found.\n"
        "Example: the same content is 1.59 MB as kraken and 2.16 MB as zstd.\n"
        "Risk: the zstd file can go over the game's 2.36 MB limit and be refused."
    ),
    "compression_level": (
        "How much effort the compression spends: fast or maximum.\n\n"
        "fast finishes in seconds and gives a file about 20% larger. maximum takes one to four minutes and "
        "gives the smallest file, which is what Elden Ring Reforged needs: its own regulation.bin is 3.03 MB "
        "and only maximum brings the result back under the limit. The window shows the current pass and an "
        "elapsed clock.\n"
        "Example: fast 1.92 MB in 7 s, maximum 1.59 MB in 155 s.\n"
        "Risk: with fast on a big file the output can be over the limit, and the tool will refuse to write it."
    ),
    "oodle_dll": (
        "oo2core_6_win64.dll, the game's own compressor, needed for kraken output.\n\n"
        "It ships with the game in the Game folder and is also in the mod folders of the fog gate and item "
        "randomizers. The tool never ships it. Without it the output is zstd, which is larger.\n"
        "Example: C:\\Games\\ELDEN RING\\Game\\oo2core_6_win64.dll, or press Find.\n"
        "Risk: without it you get zstd, which can go over the game's size limit."
    ),
    "archives": (
        "The msg folder whose item text is patched with the new weapon names.\n\n"
        "Making somber weapons infusable adds twelve rows per weapon, and without a name the game shows a "
        "placeholder. The tool writes the names into item_dlc02.msgbnd.dcx of the language you point at. "
        "Empty uses the English copy shipped with the tool.\n"
        "Example: point it at another mod's msg folder when you randomize on top of it.\n"
        "Risk: patching the wrong language gives you English names in a French game."
    ),
    "repack": (
        "Rewrite the input without changing anything.\n\n"
        "Some tools write a regulation.bin the game refuses at startup. Reading it and writing it back with "
        "this tool's own writer produces a file the game accepts, with the content untouched. No "
        "randomization runs and every other option is ignored.\n"
        "Example: Fog Gate Randomizer v0.2.3 output becomes a file that boots on game 1.17.1."
    ),
    "dry_run": (
        "Run every pass and show the reports, but write no file.\n\n"
        "A trial run: the seed, the options and the tables are used exactly as in a real run, and the console "
        "shows the same summary, but nothing is written and nothing is compressed. Use it to see what a seed "
        "will do before spending minutes on compression. The button is called Preview.\n"
        "Example: Preview with a new seed, read the reports, then run for real."
    ),
    "no_reports": (
        "Do not write the report files.\n\n"
        "Next to the output the tool writes plain‑text reports: mapping.txt (item <- effect, prices, "
        "flasks), weapons.txt, spells.txt, gear.txt, ashes.txt, goods.txt, loot.txt, loot‑shuffle.txt, "
        "drops.txt, runes.txt and hp.txt. They are the exact list of what changed. Switch this off to skip "
        "them; the console still prints the summary of every pass.\n"
        "Risk: without mapping.txt you cannot see which item received which effect."
    ),
    "max_size": (
        "The size the output must stay under.\n\n"
        "The game refuses a regulation.bin above 2,359,296 bytes and reports corrupted save data, so that is "
        "the default and the tool stops rather than write a file that will not load. Elden Ring Reforged "
        "ships a 3.03 MB file, so some loaders accept more.\n"
        "Risk: raising this on a loader that does not accept it produces a file that will not load."
    ),
    "simulate": (
        "Build the tables, print N random kills, and write nothing.\n\n"
        "The passes run exactly as in a real run, with the same seed, and then the tool rolls N random "
        "enemies and prints what each dropped, with the weapon's affinity and upgrade level. Nothing is "
        "written and nothing is compressed, so it costs seconds.\n"
        "Example: --simulate 20 prints 20 lines like \"Rat -> Short Sword +3 x1\"."
    ),

    # ------------------------------------------------------------------ consumables
    "goods": (
        "Shuffle what consumables do.\n\n"
        "Every usable item - pots, greases, meats, boluses, tools, usable key items - receives the effect of "
        "another item, so a Fire Grease may heal you and a pot may spit out a rock. Turn it off and goods are "
        "left exactly as the game shipped them.\n"
        "Example: pick up a pot and it casts a rock instead of a grease.\n"
        "Risk: a shuffled item can be much stronger or weaker than what it looks like."
    ),
    "mode": (
        "How the effects are handed out: shuffle (each effect used once) or random (repeats allowed).\n\n"
        "shuffle deals the effects out like a pack of cards: every effect ends up on exactly one item and no "
        "item keeps its own. random lets every item draw independently, so effects repeat and an item may keep "
        "what it had. It applies to spells too.\n"
        "Example: with shuffle, 242 items get 242 different effects."
    ),
    "include_flasks": (
        "Let the two healing flasks join the consumable pool.\n\n"
        "The Flask of Crimson Tears and the Flask of Cerulean Tears can then receive another item's effect, "
        "and some other item can receive theirs. Leave this off and the flasks keep their healing.\n"
        "Risk: with it on you can end up with no healing flask at all until you find one that heals again.\n"
        "Needs: Shuffle consumable effects."
    ),
    "include_remembrances": (
        "Let remembrances join the consumable pool.\n\n"
        "A remembrance normally gives runes when used. With this on it can receive a random effect instead, "
        "and some ordinary item can grant runes.\n"
        "Example: using a remembrance greases your weapon instead of giving 50,000 runes.\n"
        "Needs: Shuffle consumable effects."
    ),
    "goods_quantity": (
        "Shuffle how many of an item a pickup gives and how many you can carry.\n\n"
        "Vanilla only uses a few stack sizes (1, 10, 20, 99, 999). This moves the pair from one stackable "
        "item to another, so a fistful of pots can become a crate and a rune can become a single one. The two "
        "numbers always travel together, and only items that already stack take part.\n"
        "Example: Festering Bloody Finger 99/99 becomes 999/999."
    ),
    "split_anim": (
        "Where the use animation comes from: with the effect, from the same class, or from any item.\n\n"
        "none keeps the animation attached to the effect, so a pot stays a pot. same takes the animation from "
        "another item of the same class: thrown things stay thrown, applied things stay applied. any lets any "
        "item donate the animation, so a pot may be eaten and a fist thrown. It also splits the cast animation "
        "of sorceries and incantations.\n"
        "Risk: any is untested in game - an item may play no animation or refuse to be used."
    ),
    "spells": (
        "Shuffle what sorceries and incantations do.\n\n"
        "Every sorcery and incantation receives another spell's effect. Sorceries and incantations share one "
        "pool, so a glintstone spell can end up as an incantation and vice versa. Turn it off and Magic.param "
        "is left alone.\n"
        "Example: Glintstone Pebble heals, and a Dragon Communion breath casts a glintstone shard."
    ),
    "spell_stats": (
        "Randomize what spells cost and require.\n\n"
        "Every sorcery and incantation gets new FP and stamina costs and new stat requirements, drawn in bands "
        "around the vanilla values. It is independent of the weapon stats: a spell whose effect was shuffled "
        "can keep its original cost.\n"
        "Example: a comet that costs 40 FP and needs 60 Int instead of 30 and 50.\n"
        "Needs: Shuffle spell effects."
    ),

    # ------------------------------------------------------------------ prices
    "random_prices": (
        "Shuffle what shops charge.\n\n"
        "Every goods slot in every shop gets another slot's price, so the item an item randomizer put into a "
        "merchant's stock is priced too, because the slot is what is priced. Turn it off and prices stay "
        "vanilla.\n"
        "Example: a Golden Rune [4] that cost 12,000 now costs 800."
    ),
    "price_mode": (
        "How buy prices are rolled: shuffle the existing ones, or draw new ones in a range.\n\n"
        "shuffle permutes the prices that already exist, so nothing becomes absurd. range draws a fresh price "
        "for every entry between the two limits, rounded so prices still look like shop prices.\n"
        "Example: range 500 to 20,000 makes a shop ask 640 for a pot and 15,000 for a rune.\n"
        "Needs: Shuffle shop prices."
    ),
    "price_min": (
        "Range method: the lowest buy price to draw.\n\n"
        "Empty means the cheapest price that exists today.\n"
        "Example: 100 means no shop asks less than 100 runes.\n"
        "Needs: Shuffle shop prices, range method."
    ),
    "price_max": (
        "Range method: the highest buy price to draw.\n\n"
        "Empty means the most expensive price that exists today.\n"
        "Example: 20,000 means nothing costs more than 20,000 runes.\n"
        "Risk: the minimum cannot be above the maximum, and the tool will say so.\n"
        "Needs: Shuffle shop prices, range method."
    ),
    "sell_prices": (
        "Also shuffle what merchants pay you.\n\n"
        "Buy and sell prices are drawn independently, so an item may sell for more than a shop asks for it. "
        "Turn it off and only buy prices change.\n"
        "Example: a shop asks 900 for a pot and pays 1,200 for it.\n"
        "Needs: Shuffle shop prices."
    ),
    "sell_min": (
        "Range method: the lowest sell price to draw.\n\n"
        "Empty uses the lowest sell value that exists today.\n"
        "Example: 1 means merchants always pay at least one rune.\n"
        "Needs: Shuffle shop prices, Shuffle sell prices too, range method."
    ),
    "sell_max": (
        "Range method: the highest sell price to draw.\n\n"
        "Empty uses the highest sell value that exists today.\n"
        "Example: 9,999 means the richest merchant pays 9,999 for anything.\n"
        "Needs: Shuffle shop prices, Shuffle sell prices too, range method."
    ),
    "random_shop_stock": (
        "Fill every merchant slot with a random item of its own category.\n\n"
        "A slot that sold smithing stones can sell a weapon instead, and the next seed gives it something "
        "else. The price, the stock limit and the cost type stay exactly as they were, so the new item sells "
        "at the old slot's price - a bargain or a rip-off, decided by the seed. Each slot is drawn on its "
        "own, with replacement: two merchants can offer the same item, and one shop can repeat an item in "
        "two slots.\n"
        "Example: a smithy's first weapon slot now sells a Lordsworn's Greatsword at the old dagger's price.\n"
        "Risk: the stock is fixed for the whole run. Refreshing it on a timer would need a runtime mod; a "
        "rewritten regulation.bin cannot do that."
    ),
    "shop_stock_kinds": (
        "Choose which kinds of item merchants may sell.\n\n"
        "Tick weapons, armor, talismans, goods or Ashes of War. Empty means all five, which is the widest "
        "and the default. Untick weapons and no shop will ever offer one; tick only goods for a run where "
        "merchants sell consumables and nothing else.\n"
        "Example: weapons and armor only strips consumables from the shops, so every merchant sells gear.\n"
        "Risk: talismans are listed but cannot actually be stocked - this tool has no paramdef for "
        "EquipParamAccessory - so ticking only talismans changes nothing.\n"
        "Needs: Randomize what shops sell."
    ),
    "sell_equipment": (
        "Let weapons, armor and Ashes of War join the sell‑price shuffle.\n\n"
        "Merchants normally only buy goods. With this on their weapon, armor and Ash of War prices are "
        "shuffled too, one pool each. Every affinity row of a weapon gets the same new price.\n"
        "Example: a +10 Lordsworn's Greatsword that sold for 1,200 now sells for 48,000.\n"
        "Needs: Shuffle shop prices."
    ),

    # ------------------------------------------------------------------ weapons
    "weapons": (
        "Switch the four weapon options on or off together.\n\n"
        "A shortcut for the four options below, kept for old command lines. The window shows them "
        "individually and does not need it."
    ),
    "somber_infusable": (
        "Give somber and unique weapons the twelve affinities a normal weapon has.\n\n"
        "A somber weapon has a single row in the game, so it can never be infused and never carries an Ash of "
        "War. This adds the missing Heavy, Keen, Quality, Magic, Fire, Lightning, Holy, Poison, Blood, Cold, "
        "Occult and unique rows and lets Ashes of War be mounted on them. Without the name patch the new rows "
        "show a placeholder, so the tool names them.\n"
        "Example: a somber Longsword now comes in Heavy, Keen, Occult and can carry Lion's Claw.\n"
        "Risk: the rows are new, so a save made before the change will not know them."
    ),
    "random_movesets": (
        "Give every melee weapon and shield another weapon's moveset.\n\n"
        "A moveset is the animation set plus the attack behaviour: the swing, the timing, the hitbox. With "
        "this on a Longsword can swing like a greatsword, a dagger like a colossal sword, or a shield like a "
        "mace. Shields only swap with shields and bows only with bows, so a left-hand shield still guards "
        "and a bow still fires arrows.\n"
        "Example: a Short Sword that swings with the slow rhythm of a colossal sword, while its damage stays "
        "a short sword's.\n"
        "Risk: a moveset can be slower than the weapon's damage deserves. Pair it with Weapon type follows "
        "the moveset so the smithing table only lists Ashes of War that animate."
    ),
    "moveset_mode": (
        "How the new movesets are handed out: affinity, bound or weapon.\n\n"
        "affinity: every affinity row of a weapon draws its own moveset, so a Longsword's Heavy row and Keen "
        "row can move differently. bound: rows draw from per-affinity clusters, and each Ash of War keeps only "
        "the affinities it can animate. weapon: one moveset per weapon, shared by all its rows, and the weapon "
        "type follows it.\n"
        "Example: affinity is the most chaotic; weapon is the most coherent and is the only mode where the "
        "weapon type changes.\n"
        "Risk: affinity mode can leave a weapon with rows that no Ash of War animates. bound mode avoids that "
        "at the cost of less variety.\n"
        "Needs: Shuffle movesets."
    ),
    "moveset_variety": (
        "Bound mode: how many animation styles each affinity owns.\n\n"
        "1 gives every weapon of an affinity the same moveset. 3 is the default and mixes three styles per "
        "affinity. Higher numbers mix more, but leave fewer affinities per Ash of War, so some ashes lose "
        "animations.\n"
        "Example: 2 gives two styles per affinity, so a Heavy Longsword and a Heavy Dagger may share one.\n"
        "Risk: above 3 or 4, some Ashes of War end up with fewer usable affinities.\n"
        "Needs: Shuffle movesets, bound mode."
    ),
    "keep_standard": (
        "Affinity mode: leave each weapon's own Standard row alone.\n\n"
        "The weapon keeps its original moveset at +0 and only the twelve infused rows are randomized, so a "
        "weapon you find plain still feels like itself. Bound mode always keeps Standard rows.\n"
        "Example: a Longsword at +0 swings normally; at Heavy it swings like a hammer.\n"
        "Needs: Shuffle movesets."
    ),
    "shield": (
        "What shields may swap movesets with: shields, none or all.\n\n"
        "shields: shields swap only among the four shield animation sets, and weapons never receive one, so "
        "a left-hand shield still blocks. none: shields keep their own moveset. all: shields and weapons swap "
        "freely.\n"
        "Example: shields gives a kite shield that bashes like a greatshield.\n"
        "Risk: all can make a left-hand shield attack instead of guarding, which breaks a block build.\n"
        "Needs: Shuffle movesets."
    ),
    "bow": (
        "What bows, crossbows and ballistae may swap movesets with: bows or none.\n\n"
        "bows: every bow-class weapon takes the moveset of another bow-class weapon, with its ammunition "
        "unchanged, so a longbow can draw like a crossbow. none: they keep their own moveset.\n"
        "Example: a short bow that draws and fires like a greatbow, still using arrows.\n"
        "Needs: Shuffle movesets."
    ),
    "weptype": (
        "Make the weapon type follow the moveset.\n\n"
        "Each randomized row also takes the donor's weapon type. The smithing table reads that type to decide "
        "which Ashes of War to list, so the list matches the animation you actually got instead of the "
        "weapon's old class.\n"
        "Example: a row that swings like a hammer is listed as a hammer, so only hammer ashes appear.\n"
        "Risk: untested against the game's save checks. In weapon mode, mount a safe Ash before switching "
        "regulation.bin.\n"
        "Needs: Shuffle movesets."
    ),
    "random_weapon_effects": (
        "Shuffle the status effects a weapon inflicts on hit.\n\n"
        "Blood loss, frostbite, rot, poison, sleep and madness build-ups are dealt out among weapons of the "
        "same class: every bundle is used exactly once, so the number of bleed weapons in a class stays the "
        "same and no weapon gains an effect the game does not already have. This is a permutation, not a "
        "fresh roll - a donor's whole on-hit bundle moves to the recipient.\n"
        "Example: a Longsword that caused frostbite takes another sword's blood loss, and that sword takes "
        "the frostbite.\n"
        "Risk: a weapon can lose the status its moveset was balanced around. True random status ids are "
        "possible - the stat pass draws them - but arbitrary holder-effect ids are not safe."
    ),
    "random_weapon_holder_fx": (
        "Shuffle the effects a weapon grants while you hold it.\n\n"
        "Some weapons do something just by being equipped: a shield that blocks for less stamina, a weapon "
        "that raises a stat. Those resident effects are dealt out among weapons of the same class, one bundle "
        "each, so every effect still exists somewhere and nothing is invented.\n"
        "Example: a shield that reduced block stamina cost takes another shield's holder effect, and that "
        "shield takes its old one.\n"
        "Risk: a holder effect on the wrong class can look odd, though it never breaks anything. The pool is "
        "the game's own holder effects, not arbitrary ids, because a random residentSpEffectId can do nothing "
        "or crash."
    ),
    "random_weapon_status_effects": (
        "Roll the statuses a weapon inflicts on hit.\n\n"
        "Wherever a weapon carries a status slot (the game's spEffectBehaviorId0..2 fields), the slot is "
        "redrawn with a status id from the game's own pools: the flat statuses of STATUS_FLAT or the "
        "level-growing series of STATUS_SERIES (bleed, poison, rot, frost, sleep, madness). This is a true "
        "random draw, not a donor swap, so a Longsword can now inflict frostbite where it used to "
        "inflict blood loss. Slots that hold nothing stay empty, and the holder effects of the weapon "
        "(the block cost and friends) are not touched: they keep the permutation from Shuffle weapon "
        "properties, or stay vanilla when that switch is off.\n"
        "If Randomize weapon stats is also on, that pass rolls the statuses itself and this pass re-rolls "
        "the result: both draw from the game's own pools, so the final statuses are the same class of "
        "in-pool draws - there is no extra risk from having both switches on.\n"
        "Example: two swords, one found with a mandatory blood loss on hit, the other with no status - "
        "after this the second may carry frostbite instead.\n"
        "Risk: a rarer weapon rolls the rarer statuses on every hit, so what a specific weapon "
        "inflicts changes."
    ),
    "random_default_ash": (
        "Give every weapon a random default skill and randomize the affinity of weapons you find.\n\n"
        "Each weapon row gets a random Ash of War as its default skill, chosen so that it animates with the "
        "row's moveset. It also gives the weapons handed out by pickups, shops and starting classes a random "
        "affinity, which is what makes two copies of the same weapon play differently.\n"
        "Example: two Longswords, one Keen with Quickstep and one Heavy with Lion's Claw."
    ),
    "random_stats": (
        "Randomize the numbers of every weapon row.\n\n"
        "Every weapon and every affinity row gets its own attack values per element, critical, poise and "
        "stamina damage, guard negation, stat requirements, scaling, status build‑up and stamina cost, bows "
        "and catalysts included. Because every affinity is a separate row, the same weapon at a different "
        "infusion really is a different weapon.\n"
        "If Roll weapon statuses on hit is also on, it re-rolls the statuses after this pass: both draw "
        "from the game's own pools, so the final statuses are still the same class of in-pool draws.\n"
        "Example: Longsword (Keen) 118 physical, Longsword (Heavy) 141 physical."
    ),
    "req_mode": (
        "How far weapon requirements may wander from what the weapon needs in the vanilla game.\n\n"
        "tight (default) keeps a dagger needing a handful of points and a greatsword needing a lot, so a weapon "
        "you loot is almost always usable. normal is the widest band that still respects the weapon's own "
        "tier. wild can hand a starter weapon high requirements.\n"
        "Example: tight gives a dagger 4‑6 Strength and 7‑11 Dexterity, where it had 5 and 9.\n"
        "Risk: wild can produce weapons you cannot use for a long time.\n"
        "Needs: Randomize weapon stats."
    ),
    "stat_groups": (
        "Which groups of numbers are randomized.\n\n"
        "Tick only what you want to change: attack, guard, requirements, scaling, effects (critical, stance, "
        "status build‑up) or stamina. Anything left unticked stays exactly as the weapon had it. Empty means "
        "all of them.\n"
        "Example: attack and scaling only change how the weapon hits, not its requirements.\n"
        "Needs: Randomize weapon stats."
    ),
    "stamina_rate": (
        "The range the stamina multiplier is drawn from.\n\n"
        "Every weapon's stamina cost is multiplied by a value from this range, and the cost is normalised so "
        "the first light attack costs the weapon's base cost times the multiplier, whatever moveset the row "
        "ended up with. 0 to 2.0 means a weapon can cost nothing or twice as much.\n"
        "Example: 0.5 to 1.5 means no weapon costs more than one and a half times its vanilla stamina.\n"
        "Needs: Randomize weapon stats."
    ),
    "weapon_names": (
        "Where the names of the new affinity rows are written.\n\n"
        "Making somber weapons infusable adds twelve rows per weapon. The game shows a placeholder for rows "
        "with no name, so the tool writes a name and a description for each of them into the item text archive "
        "of the language you give.\n"
        "Example: Heavy Longsword, Keen Longsword through Occult Longsword.\n"
        "Needs: Make somber weapons infusable.\n"
        "Risk: ids that already have a name are never overwritten, so a mod's own names survive."
    ),
    "no_weapon_names": (
        "Make somber weapons infusable without touching any text archive.\n\n"
        "The added affinity rows then appear with a placeholder name in game. Useful when you do not want a "
        "msg folder in your mod.\n"
        "Risk: those rows show a placeholder instead of a real name.\n"
        "Needs: Make somber weapons infusable."
    ),

    # ------------------------------------------------------------------ ashes of war
    "random_gem_skills": (
        "Give every Ash of War another ash's skill.\n\n"
        "The skill is the animation and hit logic you get when you use the ash. Shuffling them means Lion's "
        "Claw may become Sky Shot, so looting ashes becomes interesting again. Donors are only drawn from ashes "
        "that can be mounted on the same weapon types.\n"
        "Example: Ash of War: Through and Through becomes Ash of War: Rain of Arrows.\n"
        "Risk: the name stays with the row, so the name and the skill can disagree - that is the point."
    ),
    "random_gem_effects": (
        "Give every Ash of War another ash's on‑hit effects.\n\n"
        "Some ashes add bleed, frostbite, a buff or damage over time when they hit. This swaps those effects "
        "between ashes, with the same weapon‑type grouping as the skill shuffle. Only a few dozen ashes have "
        "effects, so this changes less than the skill shuffle.\n"
        "Example: an ash that causes frostbite now causes blood loss."
    ),

    # ------------------------------------------------------------------ armor and talismans
    "random_armor_fresh": (
        "Roll every armor piece's numbers again instead of swapping them.\n\n"
        "Each piece draws fresh values inside the range its own slot uses in vanilla: a helm rolls like a "
        "helm, a chest piece like a chest piece. No two pieces share a stat block, and a starter piece can "
        "roll near a late-game one.\n"
        "Example: Iron Helmet's 0.972 negation becomes 0.952 and its 8.1 weight becomes 11.5.\n"
        "Risk: it can roll a light set heavy or a heavy set light. Pair it with Shuffle armor stats for the "
        "widest spread; alone it never leaves the slot's own range."
    ),
    "armour_keep_sets": (
        "Keep armor sets consistent when the numbers are rolled again.\n\n"
        "Pieces that share a set name (Knight Helm, Knight Armor, Knight Gauntlets, Knight Greaves) are "
        "scaled by one factor instead of being rolled separately, so the set keeps its internal balance "
        "while still differing from vanilla.\n"
        "Example: a Knight set stays a knight set - all four pieces move up or down together.\n"
        "Risk: with it off, one piece of a set can roll great and another useless.\n"
        "Needs: Randomize armor stats."
    ),
    "random_armor": (
        "Swap armor stats between pieces of the same slot.\n\n"
        "Every armor column - damage negation, resistances, poise, weight - is permuted among the pieces of "
        "the same slot, so a helm ends up with another helm's numbers and no value is invented. The pool is "
        "every value the game already uses, so nothing becomes absurd.\n"
        "Example: Iron Helmet's 0.972 negation and 8.1 weight become Kaiden Helm's 0.942 and 3.8.\n"
        "Risk: a plain-looking piece can end up with godlike negation, which is the point."
    ),
    "random_armor_drops": (
        "Move armor to different enemies without changing the armor.\n\n"
        "Every piece stays exactly as it is and only the place it drops changes: the chest piece from one "
        "dungeon can end up on a soldier on the other side of the map. Shops are included and one‑time flag "
        "drops are never moved.\n"
        "Example: Exile Hood from Castle Exile becomes Radahn's Redmane Helm."
    ),
    "random_talisman_drops": (
        "Move talismans to different enemies without changing the talismans.\n\n"
        "Every talisman keeps its name, effect and numbers, and only the place it is found changes. Shops are "
        "included and one‑time flag drops are never moved.\n"
        "Example: Host's Trick‑Mirror from a shop becomes Lord of Blood's Exultation."
    ),
    "random_goods_drops": (
        "Move goods to random enemies without changing the goods.\n\n"
        "Every consumable stays exactly as it is and only the place it drops changes, so a grease that sat in "
        "a chest can end up on a soldier across the map. Enemy drop tables, map lots and goods shops are all "
        "included, and one‑time flag drops are never moved.\n"
        "Example: a Golden Rune [4] that was a pickup becomes a boss reward.\n"
        "Risk: none - the items themselves are never touched."
    ),
    "random_weapon_drops": (
        "Move weapons to random enemies without changing the weapons.\n\n"
        "Every weapon stays exactly as it is - same affinity, same upgrade level, same stats - and only where "
        "it drops changes, so any enemy can drop any weapon. Enemy drop tables, map lots and weapon shops are "
        "included, and one‑time flag drops are never moved.\n"
        "Example: a Longsword +5 that was a chest reward becomes a drop from a rat.\n"
        "Risk: none - the weapons themselves are never touched."
    ),
    "random_ashes_drops": (
        "Move Ashes of War to random enemies without changing the ashes.\n\n"
        "Every ash keeps its skill and its effects and only the place it drops changes, so any enemy can drop "
        "any ash. Enemy drop tables, map lots and the shops that sell ashes are included, and one‑time flag "
        "drops are never moved.\n"
        "Example: Lion's Claw that was a boss reward becomes a drop from a soldier.\n"
        "Risk: none - the ashes themselves are never touched."
    ),
    "armour_drop_sets": (
        "Move armor sets as a set instead of piece by piece.\n\n"
        "Pieces that share a set name (Knight Helm, Knight Armor, Knight Gauntlets, Knight Greaves) are moved "
        "together: the whole set is replaced by another whole set, so looting one piece tells you what the "
        "rest of that set is. Turn it off and each piece moves on its own.\n"
        "Example: finding the Knight Helm means the Knight Armor, Gauntlets and Greaves are the pieces that "
        "replaced them.\n"
        "Risk: only sets with the same number of pieces are swapped with each other, so some sets may not "
        "move at all.\n"
        "Needs: Move armor to random enemies."
    ),
    "random_talismans": (
        "Give every talisman another talisman's effect and numbers.\n\n"
        "Whole talisman rows are permuted, so every talisman keeps its name but its icon and its numbers come "
        "from another talisman. This tool has no field table for talismans, so whole rows move rather than "
        "single stats.\n"
        "Example: Erdtree's Favor +2 with the numbers of Dragoncrest Greatshield Talisman +3.\n"
        "Risk: the icon can belong to a different talisman than the name."
    ),

    # ------------------------------------------------------------------ enemies and drops
    "random_flask_locations": (
        "Move the two healing flasks somewhere else in the world.\n\n"
        "The Flask of Crimson Tears and the Flask of Cerulean Tears are placed at a random pickup, boss "
        "reward, NPC gift or merchant, and what was there goes to the first Site of Grace instead. Chance "
        "drops, map fragments and one‑time rows are never used.\n"
        "Example: the flask that was at the Stranded Graveyard is now a boss reward in Caelid.\n"
        "Risk: without Where the flasks may go, both can end up late in the game."
    ),
    "flask_where": (
        "Where the two flasks may end up.\n\n"
        "anywhere (default) lets them go to any real location: a pickup, a boss reward, an NPC gift or a "
        "merchant. overworld keeps them out of dungeons, caves, catacombs, evergaols and the late‑game "
        "regions. early keeps them in the regions you can reach first - Limgrave, the Weeping Peninsula, "
        "Stormveil, Murkwater, Agheel Lake, Liurnia.\n"
        "Example: early put the Crimson Tears in a Limgrave pickup and the Cerulean in a Liurnia merchant's "
        "stock.\n"
        "Risk: early can fail if a region has no eligible spot, and the tool will say so.\n"
        "Needs: Move the two flasks."
    ),
    "start_bell": (
        "Start the game with the Spirit Calling Bell.\n\n"
        "The bell is normally bought from the Twin Maiden Husks. This hands it out with the flasks at the very "
        "start, which matters in a fog gate run where the hub may be out of reach early.\n"
        "Example: you begin with the flasks and the bell in your inventory."
    ),
    "start_lantern": (
        "Start the game with the Lantern.\n\n"
        "The nomadic merchants sell the Lantern in Liurnia and the Weeping Peninsula, which a fog gate run may "
        "not reach early. This hands it out with the flasks at the start, so dark caves are lit from the "
        "first minute."
    ),
    "random_enemy_drops": (
        "Reroll every enemy's drop table.\n\n"
        "This is the master switch: with it off, nothing below runs and every enemy keeps its vanilla drops. "
        "With it on, each enemy gets the number of rolls set below, and each roll can produce a random weapon, "
        "armor piece, talisman, Ash of War or consumable. The default is 3 rolls at 10%, which averages 0.3 items "
        "per kill - roughly seven kills in ten drop nothing. Set Rolls per enemy to 0 for one guaranteed drop "
        "per enemy instead.\n"
        "Example: a soldier that dropped a smithing stone can now drop a Lordsworn's Greatsword, nothing, or "
        "two items on a lucky kill.\n"
        "Risk: a boss can drop something trivial, and at 3 x 10% most kills are empty. Raise the chance if "
        "you want a generous world."
    ),
    "enemy_drop_rolls": (
        "How many independent drop rolls each enemy gets.\n\n"
        "3 is the default. Each roll is separate: it drops something at the chance below or it drops nothing, "
        "so a kill can give 0 to N items. 1 gives one roll per enemy. 0 is the legacy mode: the first row of "
        "every enemy always drops and later rows keep their vanilla chance.\n"
        "Example: 3 rolls at 10% averages 0.3 items per kill; 3 rolls at 50% averages 1.5.\n"
        "Risk: more rolls also mean more independent upgrade-level rolls, so high-level loot becomes more "
        "common.\n"
        "Needs: Randomize enemy drops."
    ),
    "enemy_drop_chance": (
        "How likely each drop roll is to produce an item, in percent.\n\n"
        "1 to 100, applied to every roll on its own. 10 is the default and pairs with 3 rolls for 0.3 items "
        "per kill. 100 means every roll drops, so 3 rolls give exactly three items per kill.\n"
        "Example: 3 rolls at 10% give at least one item on 27% of kills; at 50% that becomes 87.5%; at 100% "
        "every kill drops three.\n"
        "Risk: this is the main generosity knob. Raising it also raises how often uniques and upgrade "
        "materials appear, because those rolls only happen when a roll drops something.\n"
        "Needs: Randomize enemy drops, and Rolls per enemy above 0."
    ),
    "enemy_drop_kinds": (
        "Choose what a random enemy drop can be.\n\n"
        "Tick weapons, armor, talismans, goods or Ashes of War. Empty means all five, the default. Untick "
        "weapons and no random drop will ever be a weapon; tick only goods for a consumables-only world.\n"
        "Example: weapons and armor only turns every enemy into a gear pinata and removes consumable clutter.\n"
        "Risk: rows that award a key item, and one-time flag rewards, are left untouched whatever this says.\n"
        "Needs: Randomize enemy drops."
    ),
    "random_loot_levels": (
        "Give the weapons you loot a random upgrade level.\n\n"
        "In the vanilla game every weapon in a drop table, a chest or a shop is +0, so looting a weapon is "
        "always the same weapon. This rewrites the upgrade part of the item id, so a drop can be +2, +7 or "
        "+18. The level is drawn from a curve so a high roll is an event, and unique weapons that cannot be "
        "reinforced stay +0.\n"
        "Example: a Longsword that drops at +5, and another copy at +0."
    ),
    "loot_rarity": (
        "How the upgrade level is drawn, so that a +25 is an event.\n\n"
        "common gives 55% of drops at +0 to +3, 28% at +4 to +9, 12% at +10 to +15, 4% at +16 to +20 and "
        "1% at +21 to +25. legendary gives 70% at +0 to +2, 20% at +3 to +8, 7% at +9 to +14, 2.5% at +15 to "
        "+20 and 0.5% at +21 to +25. even makes every level equally likely. The curve scales to a somber "
        "weapon's +10.\n"
        "Example: common gave 3 drops at +21 or better out of 780.\n"
        "Risk: every drop row rolls the level again, so a generous drop setting produces more high levels.\n"
        "Needs: Random upgrade levels on loot."
    ),
    "loot_boss_bonus": (
        "Bosses roll their upgrade level from a better curve than ordinary enemies.\n\n"
        "same gives every enemy the chosen curve. better lets bosses use the next curve up (even to common, "
        "common to legendary). best makes bosses always use the legendary curve. A boss is an enemy with the "
        "isSoulGetByBoss flag set; --boss-min-runes adds every enemy worth at least that many runes on top.\n"
        "Example: with common and best, a boss can drop a +24 while a soldier drops a +2.\n"
        "Needs: Random upgrade levels on loot."
    ),
    "unique_drops": (
        "Allow unique weapons to appear in random enemy drops.\n\n"
        "Off by default: with it off, no random drop is ever a unique weapon, whatever the rate below says. "
        "Turn it on and every item that actually drops rolls the Unique weapon rate; a hit replaces the ordinary "
        "item with a unique weapon that cannot be infused or reinforced.\n"
        "Example: at Normal (3%) and the default 3 x 10% drop settings, about one unique per 111 kills.\n"
        "Risk: uniques are rare by design. If you want to see them, raise the rate or the drop chance; the "
        "rate alone cannot help when most kills drop nothing.\n"
        "Needs: Randomize enemy drops."
    ),
    "unique_rate": (
        "How often a dropped item is a unique weapon, when Rare unique weapons is on: a whole percent "
        "from 1 to 20, rolled on every item that drops - not on every roll. The roll happens per dropped "
        "item, so at the default 3 and the default 3 x 10% drops, about 0.3 items drop per kill and the "
        "default rate gives about 0.9 uniques per 100 kills. The field is greyed out unless the switch "
        "above is on. Upgrade material drops roll first, so with both on the effective rate is slightly "
        "lower.\n"
        "Example: at 10 with the default 3 x 10% drops, one unique shows up about every 33 kills; at 2 the "
        "same kills give about 0.6 uniques.\n"
        "Risk: at 20 uniques are common; they stop feeling special."
    ),
    "material_drops": (
        "Let enemies drop upgrade materials now and then.\n\n"
        "Each item that drops has an 8% chance to be smithing stones instead of the common draw, in a small "
        "stack of 1 to 5. Sparse by design, so materials stay something you go looking for rather than a "
        "guaranteed income.\n"
        "Example: with the default 3 x 10% drops, a kill has a 2.4% chance of a material - about one every 42 "
        "kills.\n"
        "Risk: the material roll happens before the unique roll, so a drop cannot be both, and the effective "
        "unique rate drops by 8% when both are on.\n"
        "Needs: Randomize enemy drops."
    ),
    "random_enemy_hp": (
        "Shuffle how much health enemies have.\n\n"
        "Every enemy with hit points gets a new value. shuffle permutes the existing values, so the world "
        "total is unchanged and a rat can end up with a dragon's health. range draws new values between two "
        "limits, and bands picks a band per enemy so most stay near their old toughness.\n"
        "Example: a soldier with 400 HP next to a boss with 1,200.\n"
        "Risk: shuffle can make a boss trivial and a rat a wall."
    ),
    "hp_mode": (
        "How enemy health is rolled.\n\n"
        "shuffle permutes the hit point values that exist. range draws a new value for every enemy between "
        "the two limits. bands picks a band per enemy - 50% at 0.5 to 1.5x, 35% at 1.5 to 2.5x, 15% at 2.5 "
        "to 4x of its vanilla value - so most enemies stay near their old toughness and a few become sponges. "
        "balanced keeps every enemy within 0.75 to 1.5x of its vanilla value - no bullet sponges, no pushovers.\n"
        "Example: range 0 to 200 means nothing has more than 200 HP, bosses included.\n"
        "Needs: Shuffle enemy HP."
    ),
    "hp_min": (
        "Range method: the lowest hit points to draw.\n\n"
        "Empty uses the lowest value that exists today.\n"
        "Example: 1 means every enemy can be killed.\n"
        "Needs: Shuffle enemy HP, range method."
    ),
    "hp_max": (
        "Range method: the highest hit points to draw.\n\n"
        "Empty uses the highest value that exists today.\n"
        "Example: 5000 means the hardest fight in the game is a 5,000 HP enemy.\n"
        "Needs: Shuffle enemy HP, range method."
    ),
    "random_runes": (
        "Shuffle how many runes enemies give.\n\n"
        "Every enemy's rune drop gets a new value. shuffle permutes the amounts that exist, so the world "
        "total is unchanged and a rat can be worth a dragon. range draws new amounts between two limits.\n"
        "Example: a rat worth 40,000 runes and a shardbearer worth 120.\n"
        "Risk: with shuffle the total stays the same, so a rich enemy means a poor one somewhere."
    ),
    "rune_mode": (
        "How rune drops are rolled.\n\n"
        "shuffle keeps the world's total runes the same and moves them between enemies. range ignores the "
        "existing values and draws new ones between the two limits. bands multiplies every enemy's own "
        "bounty by a band (50% 0.5-1.5x, 35% 1.5-2.5x, 15% 2.5-4x), so most enemies stay near their old "
        "worth and a few become rich.\n"
        "Example: range 1 to 99,999 means a boss and a rat can be worth the same.\n"
        "Needs: Shuffle enemy runes."
    ),
    "rune_min": (
        "Range method: the fewest runes an enemy can give.\n\n"
        "Empty uses the lowest amount that exists today.\n"
        "Example: 1 means every enemy gives something.\n"
        "Needs: Shuffle enemy runes, range method."
    ),
    "rune_max": (
        "Range method: the most runes an enemy can give.\n\n"
        "Empty uses the highest amount that exists today.\n"
        "Example: 500,000 means a single kill can fund several levels.\n"
        "Needs: Shuffle enemy runes, range method."
    ),
    "random_durations": (
        "Shuffle how long buffs last.\n\n"
        "Greases, meats, blessings and buff spells keep their effect but get a new duration: a grease that "
        "lasted 60 seconds may last 8, and a blessing may last 10 minutes. Timed effects under 5 seconds are "
        "treated as mechanics (holy water, cures, the frenzy seal) and are never touched.\n"
        "Example: a Fire Grease that lasts 40 seconds instead of 80."
    ),
    "duration_mode": (
        "How buff durations are rolled.\n\n"
        "shuffle keeps the set of durations and moves them between buffs. range draws a new duration for "
        "every buff between the two limits, in seconds.\n"
        "Example: range 10 to 600 means every buff lasts between ten seconds and ten minutes.\n"
        "Needs: Shuffle buff durations."
    ),
    "duration_min": (
        "Range method: the shortest buff duration, in seconds.\n\n"
        "Empty uses the shortest duration that exists today.\n"
        "Example: 10 means no buff is shorter than ten seconds.\n"
        "Needs: Shuffle buff durations, range method."
    ),
    "duration_max": (
        "Range method: the longest buff duration, in seconds.\n\n"
        "Empty uses the longest duration that exists today.\n"
        "Example: 600 means every buff lasts ten minutes at most.\n"
        "Needs: Shuffle buff durations, range method."
    ),
    "boss_hp_scale": (
        "Multiply every boss's HP by a factor drawn from this range.\n\n"
        "1.0,1.0 is off. Use it when Shuffle enemy HP can turn a boss into a pushover: a boss that the HP "
        "pass weakened is scaled back up, and it keeps the multiplier on top of whatever the HP pass rolled. "
        "A boss is an enemy worth 5000 runes or more in the unmodified game.\n"
        "Example: 1.5,2.0 makes every boss half again to twice as tough.\n"
        "Needs: nothing - it scales bosses on its own."
    ),
    "boss_rune_scale": (
        "Multiply every boss's rune bounty by a factor drawn from this range.\n\n"
        "1.0,1.0 is off. Use it to keep a boss worth the fight after Shuffle enemy runes moved its bounty "
        "around. A boss is an enemy worth 5000 runes or more in the unmodified game.\n"
        "Example: 1.5,2.0 pays a boss half again to twice its rolled runes.\n"
        "Needs: nothing - it scales bosses on its own."
    ),
    "couple_runes_to_hp": (
        "Make every enemy's rune bounty track its (randomized) hit points.\n\n"
        "Each enemy keeps its original worth-per-HP, but the bounty is recomputed from its new HP, so a "
        "tougher enemy gives more runes and a pushover fewer. It runs after the rune shuffle, so it "
        "overrides Shuffle enemy runes when both are on.\n"
        "Example: an enemy that rolled twice its old HP now gives about twice the runes.\n"
        "Needs: Shuffle enemy HP."
    ),
    "boss_min_runes": (
        "Also treat an enemy as a boss if its unmodified rune bounty is at least this.\n\n"
        "0 (default) uses the isSoulGetByBoss flag alone; a positive value adds high-rune enemies on top of "
        "it. Bosses are what the boss multipliers and the loot boss-bonus act on.\n"
        "Example: 5000 also treats every 5000-rune enemy as a boss.\n"
        "Needs: nothing."
    ),

    # ------------------------------------------------------------------ advanced
    "brief_reports": (
        "Write only the summary lines of each report.\n\n"
        "drops.txt and hp.txt list every enemy, which is about 500 KB each; with this on they keep only the "
        "summary lines and shrink to a couple of kilobytes. mapping.txt always stays complete, and the full "
        "detail is still printed to the console and the log.\n"
        "Example: drops.txt 509 KB becomes 688 bytes."
    ),
    "zstd_window": (
        "The window size of the zstd output: keep it at 16.\n\n"
        "16 (64 KB) is the only value the game accepts. The other values are kept for experiments.\n"
        "Risk: anything but 16 can crash the game.\n"
        "Only affects the zstd codec; kraken has no window."
    ),
}
