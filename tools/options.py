#!/usr/bin/env python3
"""Every option of the randomizer in one table: the CLI flag, the label, the hover text, the default and
   the rules that tie options together.

Both front ends read this file:

  * randomize.py builds its argparse from it (so --help can never drift from the code),
  * the GUI builds its widgets from it (so a tooltip can never drift from the flag).

`values_from_args` turns parsed command line arguments into a plain dict, `argv_from_values` turns a
dict back into an argument list, and `validate` coerces and checks a dict that may come from the GUI
(everything a GUI holds is a string).  The round trip dict -> argv -> dict is the contract the GUI's
command preview and the worker thread share.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from tips import TIPS

# -------------------------------------------------------------------------------- helpers
# Groups, in the order the GUI lays them out.  "advanced" collects the knobs that only matter in
# unusual setups; it is collapsed by default.
GROUPS = (
    ("files", "Files and output"),
    ("goods", "Consumables and buffs"),
    ("spells", "Spells"),
    ("prices", "Prices and shops"),
    ("weapons", "Weapons"),
    ("gems", "Ashes of War"),
    ("gear", "Armour and talismans"),
    ("drops", "Enemies, drops and loot"),
    ("lootdrops", "Where loot drops"),
    ("world", "Flasks and starting items"),
    ("advanced", "Advanced"),
)


@dataclass(frozen=True)
class Opt:
    """One option.

    kind      bool | enum | int | pair | groups | str | path | paths
    flags     the command line flags that set it (the first is the one the GUI shows)
    neg       flags that clear a bool (--no-spells and friends); only for kind="bool"
    expands   bool option that switches a set of other keys on (the --weapons macro)
    needs     keys that must be on for this one to have any effect (the GUI greys it out)
    conflicts keys that are cleared when this one is switched on
    items     kind="groups": the values that can be ticked (rendered as small check boxes)
    advanced  show it in a collapsed "Advanced" section
    cli       build a command line flag for it (False = GUI-only)
    gui       show it in the window (False = command line only, e.g. the --weapons macro)
    """

    key: str
    flags: tuple[str, ...]
    kind: str = "bool"
    default: Any = None
    group: str = "advanced"
    label: str = ""
    tip: str = ""
    choices: tuple[str, ...] = ()
    items: tuple[str, ...] = ()
    metavar: str = ""
    neg: tuple[str, ...] = ()
    expands: tuple[str, ...] = ()
    needs: tuple[str, ...] = ()
    conflicts: tuple[str, ...] = ()
    advanced: bool = False
    cli: bool = True
    gui: bool = True
    help: str = ""                      # --help text; falls back to the tip

    @property
    def is_bool(self) -> bool:
        return self.kind == "bool"


def _o(key: str, *flags: str, **kw) -> Opt:
    # The long hover text lives in tips.py; the short one-liners below are only a fallback.
    tip = TIPS.get(key)
    if tip:
        kw["tip"] = tip
    return Opt(key, tuple(flags), **kw)


# -------------------------------------------------------------------------------- the table
OPTIONS: tuple[Opt, ...] = (
    # --- files -----------------------------------------------------------------------------
    _o("input", "--input", kind="str", default="regulation.bin", group="files",
       label="Input regulation.bin",
       tip="The regulation.bin to rewrite: the vanilla file, or one another randomizer (Item and Enemy "
           "Randomizer, Fog Gate Randomizer) already produced. It is only read, never modified."),
    _o("output", "--output", kind="str", default="randomized/regulation.bin", group="files",
       label="Output file",
       tip="Where the new regulation.bin is written. Give it a folder of its own: the reports (mapping.txt, "
           "weapons.txt, spells.txt ...) and, when weapon names are patched, a msg folder are written next "
           "to it, and an output named like the input would replace it."),
    _o("backup_replace", "--backup-replace", neg=("--no-backup-replace",), group="files", default=True,
       label="Backup and replace files",
       tip="On by default. Before the run touches anything, your input regulation.bin and msg archives are "
           "copied into a timestamped backup folder (backups/ next to the program), then the freshly "
           "generated files replace them - so one click on Randomize both backs up and installs.\n\n"
           "The randomized/ output folder is still written and keeps the reports. Turn it off to only "
           "write the output folder and leave your files alone; revert any time with the Revert button."),
    _o("seed", "--seed", kind="int", default=None, group="files",
       label="Seed",
       tip="Fix the seed to reproduce a run exactly. Leave it empty for a fresh one; the seed that was used "
           "is printed at the top of the log and in mapping.txt, so you can enter it here later."),
    _o("compression", "--compression", kind="enum", default="kraken", group="files",
       choices=("auto", "kraken", "zstd", "leviathan"), label="Compression",
       tip="kraken is the game's own Oodle format and gives the smallest file; it needs "
           "oo2core_6_win64.dll from the game's Game folder (Mod Engine 2 setups already have it). "
           "zstd needs no DLL but is about 35% larger, which can push the file over the game's size "
           "limit. auto picks kraken when the DLL is found. Leave it on kraken unless you have no DLL."),
    _o("compression_level", "--compression-level", kind="enum", default="max", group="files",
       choices=("fast", "max"), label="Effort",
       tip="max is the default and the safe one: Elden Ring Reforged's own regulation.bin is 3.03 MB, and "
           "only maximum effort brings the rewritten file back under the game's 2.36 MB limit. It costs "
           "one to four minutes and the window shows progress. fast is for quick experiments: seconds, "
           "about 20% larger, and it refuses to write a file that would not fit."),
    _o("oodle_dll", "--oodle-dll", kind="path", default=None, group="files", metavar="PATH",
       label="Oodle DLL",
       tip="oo2core_6_win64.dll, used to write the game's own Kraken format. It ships with the game (in "
           "Game\\ ), not with this tool. Without it the output is zstd and larger."),
    _o("archives", kind="paths", default=(), group="files", metavar="FOLDER", cli=False,
       label="Text archives folder",
       tip="Optional. The msg folder (or msg\\<language> folders, ';' separated) whose item_dlc02.msgbnd.dcx "
           "the weapon names are written into. Empty uses the copy shipped with the tool; pass the mod "
           "folder of the Item and Enemy Randomizer or the Fog Gate Randomizer when you run on top of them, "
           "so the names match the items that mod actually hands out."),
    _o("repack", "--repack", group="files",
       label="Repack only (change nothing)",
       tip="Read the input and write it out again with no randomization at all. This repairs a "
           "regulation.bin that another tool wrote in a form the game rejects (Fog Gate Randomizer v0.2.3 "
           "output crashes game 1.17.1 at startup)."),
    _o("dry_run", "--dry-run", group="advanced", advanced=True,
       label="Preview only (write nothing)",
       tip="Run every pass and print the reports, but write no file. Use it to try a seed or a set of "
           "options without producing a mod."),
    _o("no_reports", "--no-reports", group="advanced", advanced=True,
       label="Do not write the report files",
       tip="Skip mapping.txt, weapons.txt, spells.txt and the other plain-text reports next to the output. "
           "The console still shows the summary of every pass."),
    _o("max_size", "--max-size", kind="int", default=None, group="advanced", advanced=True,
       metavar="BYTES",
       label="Output size limit",
       tip="The game refuses a regulation.bin above 2,359,296 bytes (0x240000) and reports corrupted save "
           "data, so that is the default and the tool stops rather than write a file that will not load. "
           "Raise it only if you know your loader accepts more; Elden Ring Reforged itself ships 3.03 MB, "
           "so some setups do load bigger files than the vanilla limit."),

    _o("simulate", "--simulate", kind="int", default=None, group="advanced", advanced=True,
       metavar="N", gui=False,
       label="Simulate N drops instead of writing",
       tip="Build the randomized tables, then print N random kills and what they dropped, and write no "
           "file. This is the loot simulator: it uses the same tables and the same seed as a real run, so "
           "what it prints is what you would loot. Costs the passes but not the compression."),

    # --- consumables and spells -----------------------------------------------------------
    _o("goods", "--goods", neg=("--no-goods",), default=False, group="goods",
       label="Shuffle consumable effects",
       tip="Master switch for the consumable shuffle: every usable item (pots, greases, meats, boluses, "
           "tools, usable key items) receives the use effect of another item. Turn it off to leave "
           "EquipParamGoods exactly as it is."),
    _o("mode", "--mode", kind="enum", default="shuffle", group="goods", choices=("shuffle", "random"),
       needs=("goods",), label="Assignment",
       tip="shuffle deals the effects out like cards: every effect is used exactly once and no item keeps "
           "its own. random lets every item draw independently, so effects repeat and an item can keep "
           "what it had. This applies to spells as well."),
    _o("include_flasks", "--include-flasks", group="goods", needs=("goods",),
       label="Include the flasks",
       tip="Put the Flask of Crimson Tears and the Flask of Cerulean Tears into the pool, so a flask can "
           "end up with another item's effect. Off: the flasks keep their healing."),
    _o("include_remembrances", "--include-remembrances", group="goods", needs=("goods",),
       label="Include remembrances",
       tip="Put remembrances into the pool: using one for runes becomes a random effect, and some ordinary "
           "item can suddenly grant runes."),
    _o("goods_quantity", "--goods-quantity", group="goods",
       label="Shuffle stack sizes",
       tip="Moves the pair (how many a pickup gives, how many you can carry) from one item to another, so "
           "a fistful of pots can become a crate and a rune can become a single one. Only items that "
           "already stack take part; the two numbers always travel together, so no item ends up asking for "
           "more than it can hold."),
    _o("split_anim", "--split-anim", kind="enum", default="none", group="goods",
       choices=("none", "same", "any"), needs=("goods",), metavar="same|any",
       label="Use animation",
       tip="none: the animation travels with the effect, so a pot stays a pot. same: the animation is "
           "taken from another item of the same class (thrown stays thrown, applied stays applied). any: "
           "from any item at all, so a pot may be eaten and a fist may be thrown; that combination is "
           "untested in game. Also splits the cast animation of sorceries and incantations."),
    _o("spells", "--spells", neg=("--no-spells",), default=False, group="spells",
       label="Shuffle spell effects",
       tip="Shuffle the effect of every sorcery and incantation (Magic.param). Sorceries and incantations "
           "share one pool, so a glintstone spell can end up as an incantation and vice versa."),
    _o("spell_stats", "--spell-stats", group="spells", needs=("spells",),
       label="Randomize spell stats",
       tip="Randomize the FP and stamina cost and the stat requirements of every sorcery and incantation, "
           "independently of the weapon stats. Spells keep their own effects and animations."),

    # --- prices ----------------------------------------------------------------------------
    _o("random_prices", "--random-prices", group="prices",
       label="Shuffle shop prices",
       tip="Permute the rune price of every goods slot in every shop (ShopLineupParam.value) and the sell "
           "value of goods (EquipParamGoods.sellValue). Shops that an item randomizer filled with other "
           "items are included, because the slot is what is priced."),
    _o("price_mode", "--price-mode", kind="enum", default="shuffle", group="prices",
       choices=("shuffle", "range"), needs=("random_prices",), label="Method",
       tip="shuffle permutes the prices that already exist. range draws a new price for every entry between "
           "the two limits (log-uniform, rounded so prices still look like shop prices)."),
    _o("price_min", "--price-min", kind="int", default=None, group="prices",
       needs=("random_prices",), label="Minimum price",
       tip="range method: lowest price to draw. Empty uses the cheapest price that exists today."),
    _o("price_max", "--price-max", kind="int", default=None, group="prices",
       needs=("random_prices",), label="Maximum price",
       tip="range method: highest price to draw. Empty uses the most expensive price that exists today."),
    _o("sell_prices", "--sell-prices", neg=("--no-sell-prices",), default=False, group="prices",
       needs=("random_prices",),
       label="Shuffle sell prices too",
       tip="Also randomize what merchants pay you for goods. Buy and sell prices are drawn independently, "
           "so an item may sell for more than a shop asks for it; that is deliberate. Turn this off to "
           "change only the buy prices."),
    _o("sell_min", "--sell-min", kind="int", default=None, group="prices",
       needs=("random_prices", "sell_prices"), label="Minimum sell price",
       tip="range method: lowest sell price to draw. Empty uses the lowest that exists today."),
    _o("sell_max", "--sell-max", kind="int", default=None, group="prices",
       needs=("random_prices", "sell_prices"), label="Maximum sell price",
       tip="range method: highest sell price to draw. Empty uses the highest that exists today."),
    _o("random_shop_stock", "--random-shop-stock", group="prices",
       label="Randomize what shops sell",
       tip="Every merchant slot is filled with a random item of its own category instead of the item it "
           "always sold. Prices, stock and cost type stay as they are, so the slot keeps selling at its "
           "vanilla price. Each slot is drawn independently, nothing is swapped between merchants. A "
           "static file cannot make stock change on a timer - that would need a runtime mod - so this is "
           "the static half: every shop sells something else. It works with every other option."),
    _o("shop_stock_kinds", "--shop-stock-kinds", kind="groups", default="", group="prices",
       needs=("random_shop_stock",), items=("weapons", "armor", "talismans", "goods", "ashes"),
       label="Shop stock categories",
       tip="Which kinds of item merchants may sell. Empty means all of them. Untick weapons and no shop "
           "will sell one. It needs Randomize what shops sell."),
    _o("sell_equipment", "--sell-equipment", group="prices", needs=("random_prices",),
       label="Include weapons, armor and Ashes of War",
       tip="Extend the sell-price shuffle to equipment: one pool each for weapons, armor pieces and Ashes "
           "of War. Every affinity row of a weapon gets the same new price. Rows that cannot be sold "
           "(sellValue 0) are left alone."),

    # --- weapons ---------------------------------------------------------------------------
    _o("weapons", "--weapons", group="weapons", gui=False, label="All four weapon options",
       tip="Switch the four options below on or off together.",
       expands=("somber_infusable", "random_movesets", "random_default_ash", "random_stats")),
    _o("somber_infusable", "--somber-infusable", group="weapons",
       label="Make somber weapons infusable",
       tip="Give every somber and unique weapon the twelve affinities (Heavy through Occult) and let it "
           "mount Ashes of War. The rows this adds are named in the game's own text (Heavy Longsword and "
           "so on); without that patch the game shows ?WeaponName?."),
    _o("random_movesets", "--random-movesets", group="weapons",
       label="Shuffle movesets",
       tip="Give every melee weapon and shield the moveset of a random other weapon: the animation set and "
           "the attack behaviour. Shields only swap with shields and bows only with bows, so a shield in "
           "the left hand still blocks instead of swinging."),
    _o("moveset_mode", "--moveset-mode", kind="enum", default="affinity", group="weapons",
       choices=("affinity", "bound", "weapon"), needs=("random_movesets",), label="Moveset mode",
       tip="affinity: every affinity row of a weapon gets its own moveset. bound: rows draw from per-affinity "
           "clusters, and an Ash of War keeps only the affinities it can actually animate. weapon: one "
           "moveset per weapon, and the weapon type follows it so the smithing table only offers "
           "animations that exist."),
    _o("moveset_variety", "--moveset-variety", kind="int", default=3, group="weapons",
       needs=("random_movesets",), label="Bound variety",
       tip="bound mode: how many animation categories each affinity owns. 1 gives every weapon of an "
           "affinity the same moveset; higher numbers mix more, but leave fewer affinities per Ash of War."),
    _o("keep_standard", "--keep-standard-moveset", group="weapons", needs=("random_movesets",),
       label="Leave Standard rows alone",
       tip="affinity mode: keep each weapon's own moveset on its Standard row and randomize the other "
           "twelve. bound mode always does this."),
    _o("shield", "--shield-movesets", kind="enum", default="shields", group="weapons",
       choices=("shields", "none", "all"), needs=("random_movesets",), label="Shields",
       tip="shields: shields swap only among the four shield animation sets and weapons never get one, so "
           "a left-hand shield still guards. none: shields keep their moveset. all: shields and weapons "
           "swap freely, and a left-hand shield then attacks instead of guarding."),
    _o("bow", "--bow-movesets", kind="enum", default="bows", group="weapons",
       choices=("bows", "none"), needs=("random_movesets",), label="Bows",
       tip="bows: every bow, crossbow and ballista takes the moveset of a random other bow-class weapon, "
           "with its ammunition unchanged. none: bows are left alone."),
    _o("weptype", "--weptype-follows", group="weapons", needs=("random_movesets",),
       label="Weapon type follows the moveset",
       tip="affinity and bound modes: each randomized row also takes the donor's weapon type, so the "
           "smithing table lists exactly the Ashes of War that animate with that row. Untested against "
           "the game's save checks."),
    _o("random_weapon_effects", "--random-weapon-effects", group="weapons",
       label="Shuffle weapon properties",
       tip="Shuffles the properties a weapon carries: the status effects it inflicts on hit (blood loss, "
           "frostbite, rot) and the effects it grants while you hold it (for example a shield that costs "
           "less stamina to block with). The properties move as one bundle inside each weapon class, so "
           "two copies of the same weapon can behave differently. It works with every other option."),
    _o("random_weapon_holder_fx", "--random-weapon-holder-fx", group="weapons",
       label="Shuffle holder effects",
       tip="Shuffles the effects a weapon grants while you hold it - for example a shield that costs less "
           "stamina to block with. The on-hit properties (blood loss, frostbite, rot) are a separate "
           "switch, so you can shuffle one without the other. It works with every other option."),
    _o("random_default_ash", "--random-default-ash", group="weapons",
       label="Random default skill and affinity",
       tip="Roll a random default skill for every weapon and affinity row, chosen so that it animates with "
           "the row's moveset. Also gives the weapons handed out by pickups, shops and starting classes a "
           "random affinity, which is what makes two copies of the same weapon play differently."),
    _o("random_stats", "--random-stats", group="weapons",
       label="Randomize weapon stats",
       tip="Randomize attack values per element, critical damage, poise and stamina damage, guard negation, "
           "stat requirements, scaling, status build-up and stamina cost on every weapon and affinity row, "
           "bows and catalysts included. Every affinity gets its own numbers, so the same weapon at a "
           "different infusion really is a different weapon."),
    _o("req_mode", "--req-mode", kind="enum", default="tight", group="weapons",
       choices=("tight", "normal", "wild"), needs=("random_stats",), label="Requirement spread",
       tip="How far weapon requirements may wander from what the weapon needs in the vanilla game. "
           "tight (default) keeps a dagger needing a handful of points and a greatsword needing a lot, so "
           "a weapon you loot is almost always usable. normal is the widest band that still respects the "
           "weapon's own tier. wild can hand a starter weapon high requirements. It needs Randomize "
           "weapon stats."),
    _o("stat_groups", "--stat-groups", kind="groups", default="", group="weapons",
       needs=("random_stats",), items=("attack", "guard", "requirements", "scaling", "effects", "stamina"),
       label="Stat groups",
       tip="Which groups of numbers are randomized. Leave them all on for the full effect, or tick only "
           "the ones you care about (attack, guard, requirements, scaling, status effects, stamina). "
           "Everything you leave unticked stays exactly as the weapon had it."),
    _o("stamina_rate", "--stamina-rate", kind="pair", default="0.8,1.2", group="weapons",
       needs=("random_stats",), label="Stamina multiplier range",
       tip="The stamina multiplier of every weapon row is drawn from this range (low,high). The default "
           "0.8-1.2 keeps stamina close to what the weapon had; widen it (0,2.0) for wild costs. The cost "
           "is normalised so the first light attack costs the weapon's base cost times the multiplier, "
           "whatever moveset the row ended up with."),
    _o("weapon_names", "--weapon-names", kind="paths", default=None, group="weapons", metavar="FOLDER",
       needs=("somber_infusable",), label="Name the new affinity rows",
       tip="Write a name and description for every affinity row the somber patch added, into the item text "
           "archive (item_dlc02.msgbnd.dcx) of each language you give. Off: those rows show ?WeaponName? "
           "in game. Done automatically when somber weapons are made infusable."),
    _o("no_weapon_names", "--no-weapon-names", group="weapons", advanced=True,
       needs=("somber_infusable",), label="Do not patch weapon names",
       tip="Make somber weapons infusable without touching any text archive. The added rows then appear as "
           "?WeaponName? in game."),
    _o("random_armor", "--random-armor", group="gear",
       label="Shuffle armor stats",
       tip="Shakes every armor column (defenses, resistances, damage negation, weight) among the pieces of "
           "the same slot, so a helm ends up with another helm's numbers. Only the values the game already "
           "uses are dealt out, so nothing becomes absurd. Two copies of one piece are still identical: "
           "that would need a runtime mod, not a rewritten regulation.bin."),
    _o("random_armor_fresh", "--random-armor-fresh", group="gear",
       label="Randomize armor stats",
       tip="Rolls every piece's numbers again instead of swapping them: a knight's armor keeps knightly "
           "numbers, but no two pieces share a stat block, and a starter chest piece can roll like a "
           "late-game one. Values stay inside the range that slot uses in vanilla, so nothing becomes "
           "absurd. Use it together with Shuffle armor stats for the widest spread."),
    _o("armour_keep_sets", "--armor-keep-sets", neg=("--no-armor-keep-sets",), group="gear",
       needs=("random_armor_fresh",), default=True,
       label="Keep armor sets together",
       tip="Pieces that share a set name (Knight Helm, Knight Armor, Knight Gauntlets, Knight Greaves) are "
           "scaled by one factor instead of being rolled separately, so a set stays internally consistent "
           "while still being different from vanilla. Turn it off and every piece rolls on its own, which "
           "can make one piece of a set great and another useless."),
    _o("random_armor_drops", "--random-armor-drops", group="lootdrops",
       label="Move armor to random enemies",
       tip="Keeps every armor piece exactly as it is and only moves *where* it drops: the chest piece from "
           "one dungeon can end up on a soldier on the other side of the map. This is the loot shuffle the "
           "old version did, restricted to armor. One-time drops and key items are never moved."),
    _o("random_talisman_drops", "--random-talisman-drops", group="lootdrops",
       label="Move talismans to random enemies",
       tip="The same for talismans: every talisman keeps its name, effect and numbers, and only the place "
           "it is found changes. Combine it with Shuffle talismans for both a different effect and a "
           "different source."),
    _o("random_talismans", "--random-talismans", group="gear",
       label="Shuffle talismans",
       tip="Permutes whole talisman rows, so every talisman keeps its name and icon but receives another "
           "talisman's effect and numbers. This tool has no field table for EquipParamAccessory, so whole "
           "rows move rather than single stats."),

    # --- ashes of war ----------------------------------------------------------------------
    _o("random_goods_drops", "--random-goods-drops", group="lootdrops",
       label="Move goods to random enemies",
       tip="Keeps every consumable exactly as it is and only moves where it drops, so a grease that used to "
           "sit in a chest can end up on a soldier across the map. Enemy drop tables, map lots and goods "
           "shops are all included. It works with every other option. Combine it with Shuffle consumable "
           "effects to change both the item and where it is found."),
    _o("random_weapon_drops", "--random-weapon-drops", group="lootdrops",
       label="Move weapons to random enemies",
       tip="Every weapon stays exactly as it is - same affinity, same upgrade level, same stats - and only "
           "where it drops changes, so any enemy can drop any weapon. Enemy drop tables, map lots and weapon "
           "shops are included. It works with every other option: combine it with Randomize weapon stats "
           "and Random upgrade levels on loot to make every dropped weapon a different one."),
    _o("random_ashes_drops", "--random-ashes-drops", group="lootdrops",
       label="Move Ashes of War to random enemies",
       tip="Keeps every Ash of War exactly as it is and only moves where it drops, so any enemy can drop any "
           "ash. Enemy drop tables, map lots and the shops that sell ashes are included. It works with every "
           "other option."),
    _o("armour_drop_sets", "--armor-drop-sets", group="lootdrops", needs=("random_armor_drops",),
       label="Move armor sets as a set",
       tip="Pieces that share a set name are moved together: set A's helm, chest, gauntlets and greaves are "
           "replaced by set B's four pieces, so looting one piece tells you what the rest of that set is. "
           "Turn it off and each piece moves on its own. It needs Move armor to random enemies."),
    _o("random_gem_skills", "--random-gem-skills", group="gems",
       label="Shuffle skills",
       tip="Gives every Ash of War another ash's skill (EquipParamGem.swordArtsParamId): Lion's Claw may "
           "become Sky Shot. Donors are only drawn from ashes that can be mounted on the same weapon types, "
           "so a skill never lands on a weapon that could not use it. This is the one to switch on for "
           "'loot a different ash every time'."),
    _o("random_gem_effects", "--random-gem-effects", group="gems",
       label="Shuffle on-hit effects",
       tip="Gives every Ash of War another ash's on-hit effects (spEffectId0-2): bleed, frostbite, a buff. "
           "The three effects of one ash travel together, and donors come from ashes that fit the same "
           "weapons. Only a few dozen ashes have effects, so this changes less than Shuffle skills."),

    # --- enemies, drops, runes -------------------------------------------------------------
    _o("random_flask_locations", "--random-flask-locations", group="world",
       label="Move the two flasks",
       tip="Hide the Flask of Crimson Tears and the Flask of Cerulean Tears at a random pickup, boss "
           "reward, NPC gift or merchant, and put what was there at the first Site of Grace instead. "
           "Chance drops and map fragments are never used."),
    _o("flask_where", "--flask-where", kind="enum", default="anywhere", group="world",
       needs=("random_flask_locations",), choices=("anywhere", "overworld", "early"),
       label="Where the flasks may go",
       tip="anywhere (default) lets the two flasks go to any real location: pickups, boss rewards, NPC "
           "gifts and merchants. overworld keeps them out of dungeons, caves, catacombs, evergaols and "
           "the late-game regions. early keeps them in the regions you can reach first - Limgrave, the "
           "Weeping Peninsula, Stormveil, Murkwater, Agheel Lake, Liurnia - so they are never locked "
           "behind the end of the game. It needs Move the two flasks."),
    _o("start_bell", "--start-with-bell", group="world",
       label="Start with the Spirit Calling Bell",
       tip="Hand the bell out with the flasks at the very start. Useful with the Fog Gate Randomizer, where "
           "Renna in Limgrave may be out of reach early."),
    _o("start_lantern", "--start-with-lantern", group="world",
       label="Start with the Lantern",
       tip="Hand the Lantern out with the flasks at the start. In vanilla the nomadic merchants sell it in "
           "Liurnia and the Weeping Peninsula, which a fog gate run may not reach early."),
    _o("random_enemy_drops", "--random-enemy-drops", group="drops",
       label="Randomize enemy drops",
       tip="Every enemy drops something, and what it drops is random: weapons, armor, talismans, Ashes of "
           "War and goods (no key items). The first drop row of every enemy becomes guaranteed; later rows "
           "keep their chance. One-time drops and rows holding a key item are left alone."),
    _o("enemy_drop_rolls", "--enemy-drop-rolls", kind="int", default=None, group="drops",
       needs=("random_enemy_drops",), metavar="N",
       label="Rolls per enemy",
       tip="Give every enemy exactly N drop rolls instead of one guaranteed drop. Each roll drops a random "
           "item at the chance below, so a kill drops 0 to N items, N x chance / 100 on average."),
    _o("enemy_drop_chance", "--enemy-drop-chance", kind="int", default=50, group="drops",
       needs=("random_enemy_drops",), metavar="P",
       label="Chance per roll (%)",
       tip="How likely each of the rolls above is to drop something, in percent (1 to 100)."),
    _o("enemy_drop_kinds", "--enemy-drop-kinds", kind="groups", default="", group="drops",
       needs=("random_enemy_drops",), items=("weapons", "armor", "talismans", "goods", "ashes"),
       label="What enemies can drop",
       tip="Which kinds of item the random enemy drops can contain. Empty means all of them. Untick "
           "weapons and no enemy will ever drop one, for example. Key items are never dropped whatever "
           "this says. It needs Randomize enemy drops."),
    _o("random_loot_levels", "--random-loot-levels", group="drops",
       label="Random upgrade levels on loot",
       tip="Gives the weapons in enemy drop tables, chests, boss rewards and shops a random upgrade level: "
           "0-25 for a normal weapon, 0-10 for a somber one, +0 for a unique weapon that cannot be "
           "reinforced. Without this every weapon in the game is +0, exactly as in vanilla. Combine it "
           "with several rolls per enemy and one kill can drop a different weapon at a different level."),
    _o("loot_rarity", "--loot-rarity", kind="enum", default="common", group="drops",
       choices=("even", "common", "legendary"), needs=("random_loot_levels",), label="Upgrade rarity",
       tip="How the upgrade level is drawn, so that a +25 stays an event. common (default): 55% of drops "
           "are +0..+3, 28% +4..+9, 12% +10..+15, 4% +16..+20 and 1% +21..+25. legendary: 70% +0..+2, "
           "20% +3..+8, 7% +9..+14, 2.5% +15..+20, 0.5% +21..+25. even: every level equally likely (the "
           "old behaviour). The same curve scales to a somber weapon's +10."),
    _o("loot_boss_bonus", "--loot-boss-bonus", kind="enum", default="better", group="drops",
       choices=("same", "better", "best"), needs=("random_loot_levels",),
       label="Bosses roll better",
       tip="Bosses roll their upgrade level from a better curve than ordinary enemies. same: every enemy "
           "uses the chosen curve. better: bosses use the next curve up (even to common, common to "
           "legendary). best: bosses always use the legendary curve. A boss is an enemy worth 5000 runes "
           "or more in the unmodified game."),
    _o("loot_max_level", "--loot-max-level", kind="int", default=None, group="drops",
       needs=("random_loot_levels",), label="Max upgrade level",
       tip="Highest upgrade level a dropped weapon can roll.\n\n"
           "0 or empty means no cap: a weapon may reach its own ceiling (+25, or +10 for somber). "
           "Example: 10 keeps every drop at +10 or lower."),
    _o("zone_loot_levels", "--zone-loot-levels", group="drops", needs=("random_loot_levels",),
       label="Zone-aware loot levels",
       tip="Scales weapon upgrade levels by the area, so an early chest is not a +25 weapon: Limgrave / "
           "Weeping Peninsula stay low, Liurnia / Caelid / Altus mid, Mountaintops / Haligtree / Farum "
           "Azula high, the Land of Shadow at the full ceiling.\n\n"
           "Enemy drops are not tied to a place, so only chests, boss rewards and shops scale. Needs "
           "Random upgrade levels on loot."),
    _o("unique_drops", "--unique-drops", group="drops", needs=("random_enemy_drops",),
       label="Rare unique weapons",
       tip="Now and then an enemy drops a unique weapon - one that cannot be infused or reinforced - "
           "instead of the common draw. About one drop in thirty, so a kill is usually ordinary and a "
           "unique feels like an event. It needs Randomize enemy drops."),
    _o("material_drops", "--material-drops", group="drops", needs=("random_enemy_drops",),
       label="Upgrade material drops",
       tip="Now and then an enemy drops smithing stones instead of the common draw: about one drop in "
           "twelve, in a small stack. Sparse by design, so materials stay something you go looking for. "
           "It needs Randomize enemy drops."),
    _o("unique_rate", "--unique-rate", kind="enum", default="normal", group="drops",
       choices=("rare", "normal", "generous"), needs=("random_enemy_drops",),
       label="Unique weapon rate",
       tip="How often a drop is a unique weapon instead of the common draw. rare is 1%, normal 3% and "
           "generous 8%, rolled on every drop row - so an enemy with three rolls gets three chances. "
           "Uniques cannot be infused or reinforced, so they stay special at the low rates. It needs "
           "Randomize enemy drops."),
    _o("random_enemy_hp", "--random-enemy-hp", group="drops",
       label="Shuffle enemy HP",
       tip="Randomize the hit points of every enemy that has any (NpcParam.hp). shuffle permutes the "
           "existing values, so the world total is unchanged; range draws new ones between the two "
           "limits, spread evenly over orders of magnitude."),
    _o("hp_mode", "--hp-mode", kind="enum", default="shuffle", group="drops",
       choices=("shuffle", "range", "bands", "balanced"), needs=("random_enemy_hp",), label="HP method",
       tip="shuffle permutes the hit point values that exist. range draws a new value for every enemy "
           "between the two limits. bands picks a band per enemy - 50% at 0.5 to 1.5x, 35% at 1.5 to "
           "2.5x, 15% at 2.5 to 4x of its vanilla value - so most enemies stay near their old toughness "
           "and a few become sponges. balanced keeps every enemy within 0.75 to 1.5x of its vanilla "
           "value - no bullet sponges, no pushovers."),
    _o("hp_min", "--hp-min", kind="int", default=None, group="drops",
       needs=("random_enemy_hp",), label="Lowest HP",
       tip="range method: lowest hit point value to draw. Empty uses the lowest that exists today."),
    _o("hp_max", "--hp-max", kind="int", default=None, group="drops",
       needs=("random_enemy_hp",), label="Highest HP",
       tip="range method: highest hit point value to draw. Empty uses the highest that exists today."),
    _o("random_runes", "--random-runes", group="drops",
       label="Shuffle enemy runes",
       tip="Randomize the runes each enemy gives (NpcParam.getSoul). shuffle permutes the amounts that "
           "exist, so the world total is unchanged and a rat can be worth a dragon."),
    _o("rune_mode", "--rune-mode", kind="enum", default="shuffle", group="drops",
       choices=("shuffle", "range", "bands"), needs=("random_runes",), label="Rune method",
       tip="shuffle permutes the existing amounts over the enemies. range draws a new amount for every "
           "enemy between the two limits, spread evenly over orders of magnitude."),
    _o("rune_min", "--rune-min", kind="int", default=None, group="drops",
       needs=("random_runes",), label="Fewest runes",
       tip="range method: lowest amount to draw. Empty uses the lowest that exists today."),
    _o("rune_max", "--rune-max", kind="int", default=None, group="drops",
       needs=("random_runes",), label="Most runes",
       tip="range method: highest amount to draw. Empty uses the highest that exists today."),
    _o("boss_hp_scale", "--boss-hp-scale", kind="pair", default="1.0,1.0", group="drops",
       label="Boss HP multiplier range",
       tip="Multiply every boss's HP by a factor drawn from this range (low,high); 1.0,1.0 is off. Use "
           "it when Shuffle enemy HP can turn a boss into a pushover. Example: 1.5,2.0 makes bosses half "
           "again to twice as tough as the (possibly randomized) value. A boss is an enemy worth 5000 runes "
           "or more in the unmodified game."),
    _o("boss_rune_scale", "--boss-rune-scale", kind="pair", default="1.0,1.0", group="drops",
       label="Boss rune multiplier range",
       tip="Multiply every boss's rune bounty by a factor drawn from this range (low,high); 1.0,1.0 is "
           "off. Use it to keep a boss worth the fight after its runes were shuffled. Example: 1.5,2.0. A "
           "boss is an enemy worth 5000 runes or more in the unmodified game."),
    _o("couple_runes_to_hp", "--couple-runes-to-hp", group="drops", needs=("random_enemy_hp",),
       label="Couple runes to HP",
       tip="Recompute every enemy's rune bounty so it tracks its (randomized) HP: a tougher enemy gives "
           "more runes, a pushover fewer, keeping each enemy's original worth-per-HP. Runs after the rune "
           "shuffle, so it overrides it. Needs Shuffle enemy HP."),
    _o("boss_min_runes", "--boss-min-runes", kind="int", default=0, group="drops", metavar="N",
       label="Boss rune threshold",
       tip="Also treat an enemy as a boss if its unmodified rune bounty is at least this. 0 (default) uses "
           "the isSoulGetByBoss flag alone; a positive value adds high-rune enemies on top of it. Bosses are "
           "what the boss multipliers and the loot boss-bonus act on."),
    _o("random_durations", "--random-durations", group="goods",
       label="Shuffle buff durations",
       tip="Randomize how long buffs last (SpEffectParam.effectEndurance) for greases, meats, blessings "
           "and buff spells. Timed effects under 5 seconds are treated as mechanics, not buffs, and are "
           "left alone."),
    _o("duration_mode", "--duration-mode", kind="enum", default="shuffle", group="goods",
       choices=("shuffle", "range"), needs=("random_durations",), label="Duration method",
       tip="shuffle permutes the durations that exist over the buffs. range draws a new duration for every "
           "buff between the two limits, in seconds."),
    _o("duration_min", "--duration-min", kind="int", default=None, group="goods",
       needs=("random_durations",), label="Shortest buff (s)",
       tip="range method: shortest duration in seconds. Empty uses the shortest that exists today."),
    _o("duration_max", "--duration-max", kind="int", default=None, group="goods",
       needs=("random_durations",), label="Longest buff (s)",
       tip="range method: longest duration in seconds. Empty uses the longest that exists today."),

    # --- advanced --------------------------------------------------------------------------
    _o("brief_reports", "--brief-reports", group="advanced", advanced=True,
       label="Short reports (headers only)",
       tip="Write only the summary lines of each report and skip the per-row detail. drops.txt and hp.txt "
           "are the long ones (about 500 KB each); with this on they shrink to a couple of kilobytes. The "
           "full detail is still printed to the console and the log."),
    _o("zstd_window", "--zstd-window", kind="int", default=16, group="advanced", advanced=True,
       choices=(16, 17, 18, 19, 20, 21, 22), metavar="16..22",
       label="zstd window log",
       tip="Window size of the zstd output. 16 (64 KB) is the only value the game accepts; the others are "
           "kept for experiments and can crash it."),
)

BY_KEY: dict[str, Opt] = {o.key: o for o in OPTIONS}
BY_FLAG: dict[str, Opt] = {}
for _opt in OPTIONS:
    for _flag in _opt.flags + _opt.neg:
        BY_FLAG[_flag] = _opt


# -------------------------------------------------------------------------------- argparse
def build_argparse(prog: str | None = None, description: str = "", epilog: str = ""):
    """An ArgumentParser that produces exactly the options in OPTIONS."""
    import argparse

    ap = argparse.ArgumentParser(prog=prog, description=description, epilog=epilog,
                                 formatter_class=argparse.RawDescriptionHelpFormatter,
                                 argument_default=argparse.SUPPRESS)
    for o in OPTIONS:
        if not o.cli:
            continue
        # --help shows the first paragraph only; argparse runs help through %-formatting, so % is doubled
        first = (o.help or o.tip or "").split("\n\n")[0].strip() or o.label
        help_text = first.replace("%", "%%")
        kw: dict[str, Any] = {"help": help_text, "default": argparse.SUPPRESS}
        if o.kind == "bool":
            kw.update(action="store_true", dest=o.key)
            ap.add_argument(*o.flags, **kw)
            if o.neg:
                # the inverse flag stays for old command lines, but it does not deserve its own paragraph
                ap.add_argument(*o.neg, **dict(kw, action="store_false",
                                               help=f"Same as not passing {o.flags[0]}."))
        elif o.kind == "enum":
            kw.update(choices=o.choices, metavar=o.metavar or None)
            ap.add_argument(*o.flags, dest=o.key, **kw)
        elif o.kind in ("int", "float"):
            kw.update(type=int if o.kind == "int" else float, metavar=o.metavar or None)
            ap.add_argument(*o.flags, dest=o.key, **kw)
        elif o.kind == "pair":
            kw.update(metavar=o.metavar or "LO,HI")
            ap.add_argument(*o.flags, dest=o.key, **kw)
        elif o.kind == "paths":
            kw.update(nargs="*", metavar=o.metavar or "FOLDER", default=argparse.SUPPRESS)
            ap.add_argument(*o.flags, dest=o.key, **kw)
        else:                                            # str / path
            kw.update(metavar=o.metavar or None)
            ap.add_argument(*o.flags, dest=o.key, **kw)
    return ap


def values_from_args(args) -> dict:
    """Parsed arguments -> a full value dict (defaults filled in from the table)."""
    values = {o.key: o.default for o in OPTIONS}
    for o in OPTIONS:
        got = getattr(args, o.key, None)
        if got is None and o.default is None and o.kind in ("int", "float"):
            continue
        if got is not None:
            values[o.key] = got
    for key in ("weapon_names", "archives"):
        if values.get(key) is None:
            values[key] = ()
        elif isinstance(values[key], str):
            values[key] = tuple(values[key].split(";"))
    return values


# -------------------------------------------------------------------------------- validation
def _as_int(o: Opt, raw: Any) -> int | None:
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        return None
    try:
        return int(str(raw).strip())
    except ValueError:
        raise ValueError(f"{o.label} must be a whole number: {raw!r}") from None


def _as_float_pair(o: Opt, raw: Any) -> tuple[float, float] | None:
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        return None
    if isinstance(raw, (tuple, list)):              # already validated: validate() must be repeatable
        if len(raw) != 2:
            raise ValueError(f"{o.label} must be two numbers separated by a comma, for example 0,2.0")
        lo, hi = float(raw[0]), float(raw[1])
        if not 0 <= lo <= hi:
            raise ValueError(f"{o.label} must satisfy 0 <= low <= high")
        return (lo, hi)
    parts = [p.strip() for p in str(raw).replace(";", ",").split(",") if p.strip()]
    if len(parts) != 2:
        raise ValueError(f"{o.label} must be two numbers separated by a comma, for example 0,2.0")
    try:
        lo, hi = float(parts[0]), float(parts[1])
    except ValueError:
        raise ValueError(f"{o.label} must be two numbers separated by a comma, for example 0,2.0") from None
    if not 0 <= lo <= hi:
        raise ValueError(f"{o.label} must satisfy 0 <= low <= high, for example 0,2.0")
    return lo, hi


def _as_paths(o: Opt, raw: Any) -> tuple[str, ...]:
    if raw is None:
        return ()
    if isinstance(raw, str):
        raw = [p for p in raw.split(";") if p.strip()]
    return tuple(str(p).strip() for p in raw if str(p).strip())


def validate(values: dict) -> dict:
    """Coerce a value dict (the GUI holds strings) and check the rules.

    Raises ValueError with a message fit for a message box.  Returns a new dict; keys that are not
    options are ignored, keys missing from `values` are filled from their default."""
    import weapons  # local: avoids an import cycle at start-up

    out: dict[str, Any] = {}
    for o in OPTIONS:
        raw = values.get(o.key, o.default)
        if o.kind == "bool":
            out[o.key] = bool(raw)
        elif o.kind == "enum":
            v = str(raw) if raw is not None else o.default
            if v not in o.choices:
                raise ValueError(f"{o.label} must be one of: {', '.join(o.choices)}")
            out[o.key] = v
        elif o.kind == "int":
            if o.choices and raw not in (None, ""):
                n = _as_int(o, raw)
                if n not in o.choices:
                    raise ValueError(f"{o.label} must be one of: {', '.join(str(c) for c in o.choices)}")
                out[o.key] = n
            else:
                out[o.key] = _as_int(o, raw)
        elif o.kind == "pair":
            out[o.key] = _as_float_pair(o, raw)
        elif o.kind == "groups":
            out[o.key] = ",".join(str(x) for x in raw) if isinstance(raw, (list, tuple)) else str(raw or "").strip()
        elif o.kind == "paths":
            out[o.key] = _as_paths(o, raw)
        else:
            out[o.key] = None if raw is None else str(raw).strip()

    # cross-option rules -------------------------------------------------------------------
    # --weapons is a shorthand for the four weapon options; expand it before anything reads them
    if out["weapons"]:
        for key in BY_KEY["weapons"].expands:
            out[key] = True

    if out["enemy_drop_rolls"] is not None:
        if not out["random_enemy_drops"]:
            raise ValueError("Rolls per enemy needs \"Randomize enemy drops\"")
        if not 1 <= out["enemy_drop_rolls"] <= 32:
            raise ValueError("Rolls per enemy must be between 1 and 32")
        if out["enemy_drop_chance"] is None:
            out["enemy_drop_chance"] = 50
    if out["enemy_drop_chance"] is not None and not 1 <= out["enemy_drop_chance"] <= 100:
        raise ValueError("Chance per roll must be between 1 and 100 (percent)")

    for key, label in (("price_min", "Minimum price"), ("price_max", "Maximum price"),
                       ("sell_min", "Minimum sell price"), ("sell_max", "Maximum sell price"),
                       ("rune_min", "Fewest runes"), ("rune_max", "Most runes")):
        v = out[key]
        if v is not None and v < 0:
            raise ValueError(f"{label} cannot be negative")
    if out["max_size"] is not None and out["max_size"] < 1_000_000:
        raise ValueError("Output size limit must be at least 1,000,000 bytes (the game's own limit is "
                         "2,359,296)")
    if out["simulate"] is not None and out["simulate"] < 1:
        raise ValueError("Simulate must be at least 1 kill")
    if out["loot_max_level"] is not None and not 0 <= out["loot_max_level"] <= 25:
        raise ValueError("Max upgrade level must be between 0 and 25")
    if out["boss_min_runes"] is not None and out["boss_min_runes"] < 0:
        raise ValueError("Boss rune threshold cannot be negative")

    if out["random_prices"] and out["price_mode"] == "range":
        lo, hi = out["price_min"], out["price_max"]
        if lo is not None and hi is not None and lo > hi:
            raise ValueError("Minimum price cannot be larger than the maximum price")
    if out["random_runes"] and out["rune_mode"] == "range":
        lo, hi = out["rune_min"], out["rune_max"]
        if lo is not None and hi is not None and lo > hi:
            raise ValueError("Fewest runes cannot be larger than the most runes")
    if out["random_enemy_hp"] and out["hp_mode"] == "range":
        lo, hi = out["hp_min"], out["hp_max"]
        if lo is not None and hi is not None and lo > hi:
            raise ValueError("Lowest HP cannot be larger than the highest HP")
    if out["random_durations"] and out["duration_mode"] == "range":
        lo, hi = out["duration_min"], out["duration_max"]
        if lo is not None and hi is not None and lo > hi:
            raise ValueError("Shortest buff cannot be longer than the longest buff")

    if out["random_stats"]:
        o = BY_KEY["stat_groups"]
        picked = [g.strip() for g in str(out["stat_groups"] or "").split(",") if g.strip()]
        bad = [g for g in picked if g not in weapons.STAT_GROUPS]
        if bad:
            raise ValueError(f"Unknown stat groups: {', '.join(bad)} "
                             f"(choose from {', '.join(weapons.STAT_GROUPS)})")
        # an empty list means every group; "spells" is still accepted for old command lines
        groups = [g for g in o.items if g in picked] if picked else list(o.items)
        groups += [g for g in picked if g not in o.items]
        out["stat_groups"] = groups
    else:
        out["stat_groups"] = []

    for o in OPTIONS:
        if o.needs and not all(out.get(k) for k in o.needs):
            out[o.key] = o.default if o.kind == "bool" else out[o.key]

    return out


def is_active(o: Opt, values: dict) -> bool:
    """False when an option's own switch is off: the GUI uses it to grey dependent widgets out."""
    if o.key in ("enemy_drop_rolls", "enemy_drop_chance"):
        return bool(values.get("random_enemy_drops"))
    if o.needs:
        return all(values.get(k) for k in o.needs)
    return True


# Options that are not on/off switches even though they are booleans: a run mode, a report switch, or
# a refinement of another option.  Everything else is a master switch, and at least one of them has to be
# on for a run to change anything.
_NOT_A_SWITCH = {"repack", "dry_run", "no_reports", "sell_prices", "keep_standard", "weptype",
                 "no_weapon_names", "spell_stats", "include_flasks", "include_remembrances"}


def master_switches() -> tuple[Opt, ...]:
    """The booleans that turn a randomisation pass on: they stand alone, everything else hangs off one."""
    return tuple(o for o in OPTIONS
                 if o.kind == "bool" and not o.needs and o.key not in _NOT_A_SWITCH)


# -------------------------------------------------------------------------------- argv
def _unless_default(a: list[str], values: dict, key: str, flag: str) -> None:
    """Append `flag value` when `key` differs from its own default in the option table.

    The CLI's fallback is the table default, so a value equal to it needs no flag - and every other
    value must be passed, or the run silently uses the default instead.  Comparing against the option's
    real default (rather than a hard-coded sibling value) is the whole point: "fast" compression once
    meant "max" and "auto" compression once meant "kraken" because the test was inverted here.
    """
    value = values.get(key)
    if value in (None, ""):
        return
    if value == BY_KEY[key].default:
        return
    a += [flag, str(value)]


def _pair(raw, default: tuple[float, float]) -> tuple[float, float]:
    """A (lo, hi) pair from either form of the value dict.

    A validated dict carries a tuple; a raw dict (a preset, a test) still carries the option's own
    default, which is the string "1.0,1.0".  Unpacking the string raises "too many values to unpack",
    so the raw form is parsed here instead of being handed to `lo, hi = ...`.
    """
    if raw in (None, ""):
        return default
    if isinstance(raw, (list, tuple)):
        return (float(raw[0]), float(raw[1])) if len(raw) == 2 else default
    parts = [p.strip() for p in str(raw).replace(";", ",").split(",") if p.strip()]
    return (float(parts[0]), float(parts[1])) if len(parts) == 2 else default


def _groups_value(values: dict, key: str) -> list[str]:
    """The selected items of a `groups` option, in canonical order (empty selection = every item).

    Accepts the comma string the GUI holds and the list a validated dict carries.  `g in "<string>"`
    would be a substring test, which is wrong as soon as one item name is contained in another.
    """
    every = list(BY_KEY[key].items)
    raw = values.get(key)
    if isinstance(raw, (list, tuple)):
        picked = [str(g).strip() for g in raw if str(g).strip()]
    else:
        picked = [g.strip() for g in str(raw or "").split(",") if g.strip()]
    return [g for g in every if not picked or g in picked]


def argv_from_values(values: dict) -> list[str]:
    """A value dict -> the argument list randomize.py takes.  The GUI shows this and runs it verbatim."""
    a: list[str] = []
    if values.get("repack"):
        a += ["--input", str(values.get("input") or "regulation.bin"),
              "--output", str(values.get("output") or "randomized/regulation.bin"),
              "--repack"]
        _unless_default(a, values, "compression", "--compression")
        _unless_default(a, values, "compression_level", "--compression-level")
        if values.get("oodle_dll"):
            a += ["--oodle-dll", str(values["oodle_dll"])]
        if not values.get("backup_replace", True):
            a.append("--no-backup-replace")
        return a

    a += ["--input", str(values.get("input") or "regulation.bin"),
          "--output", str(values.get("output") or "randomized/regulation.bin")]
    if values.get("seed") not in (None, ""):
        a += ["--seed", str(values["seed"])]
    _unless_default(a, values, "compression", "--compression")
    _unless_default(a, values, "compression_level", "--compression-level")
    if values.get("oodle_dll"):
        a += ["--oodle-dll", str(values["oodle_dll"])]
    if values.get("max_size"):
        a += ["--max-size", str(values["max_size"])]
    if values.get("simulate"):
        a += ["--simulate", str(values["simulate"])]
    zw = values.get("zstd_window")
    if zw not in (None, "", 16, "16"):
        a += ["--zstd-window", str(zw)]
    if not values.get("backup_replace", True):
        a.append("--no-backup-replace")

    if values.get("goods"):
        a.append("--goods")
        if values.get("mode") and values["mode"] != "shuffle":
            a += ["--mode", values["mode"]]
        if values.get("include_flasks"):
            a.append("--include-flasks")
        if values.get("include_remembrances"):
            a.append("--include-remembrances")
        if values.get("split_anim") and values["split_anim"] != "none":
            a += ["--split-anim", values["split_anim"]]

    if values.get("spells"):
        a.append("--spells")

    for key, flag in (("random_prices", "--random-prices"),
                      ("random_shop_stock", "--random-shop-stock"),
                      ("goods_quantity", "--goods-quantity"),
                      ("random_armor", "--random-armor"),
                      ("random_armor_fresh", "--random-armor-fresh"),
                      ("random_armor_drops", "--random-armor-drops"),
                      ("random_talismans", "--random-talismans"),
                      ("random_goods_drops", "--random-goods-drops"),
                      ("random_weapon_drops", "--random-weapon-drops"),
                      ("random_ashes_drops", "--random-ashes-drops"),
                      ("random_talisman_drops", "--random-talisman-drops"),
                      ("armour_drop_sets", "--armor-drop-sets"),
                      ("random_gem_skills", "--random-gem-skills"),
                      ("random_gem_effects", "--random-gem-effects"),
                      ("random_weapon_effects", "--random-weapon-effects"),
                      ("random_weapon_holder_fx", "--random-weapon-holder-fx"),
                      ("brief_reports", "--brief-reports"),
                      ("random_runes", "--random-runes"),
                      ("random_enemy_hp", "--random-enemy-hp"),
                      ("spell_stats", "--spell-stats"),
                      ("random_durations", "--random-durations"),
                      ("random_flask_locations", "--random-flask-locations"),
                      ("start_bell", "--start-with-bell"),
                      ("start_lantern", "--start-with-lantern"),
                      ("random_enemy_drops", "--random-enemy-drops"),
                      ("unique_drops", "--unique-drops"),
                      ("material_drops", "--material-drops"),
                      ("couple_runes_to_hp", "--couple-runes-to-hp")):
        if values.get(key):
            a.append(flag)
    for key, flag in (("boss_hp_scale", "--boss-hp-scale"), ("boss_rune_scale", "--boss-rune-scale")):
        lo, hi = _pair(values.get(key), (1.0, 1.0))
        if (lo, hi) != (1.0, 1.0):
            a += [flag, f"{lo:g},{hi:g}"]
    if values.get("boss_min_runes"):
        a += ["--boss-min-runes", str(values["boss_min_runes"])]
    if values.get("random_loot_levels"):
        a.append("--random-loot-levels")
        # these three hang off --random-loot-levels, not off --zone-loot-levels: the boss bonus and the
        # level cap describe how a drop is rolled, zone scaling only changes the cap it rolls against.
        if values.get("loot_rarity") and values["loot_rarity"] != "common":
            a += ["--loot-rarity", values["loot_rarity"]]
        if values.get("loot_boss_bonus") and values["loot_boss_bonus"] != "better":
            a += ["--loot-boss-bonus", values["loot_boss_bonus"]]
        if values.get("loot_max_level"):
            a += ["--loot-max-level", str(values["loot_max_level"])]
    if values.get("zone_loot_levels"):
        a.append("--zone-loot-levels")
    if values.get("random_armor_fresh") and not values.get("armour_keep_sets", True):
        a.append("--no-armor-keep-sets")

    if values.get("random_prices"):
        if values.get("price_mode") and values["price_mode"] != "shuffle":
            a += ["--price-mode", values["price_mode"]]
            if values["price_mode"] == "range":
                for key, flag in (("price_min", "--price-min"), ("price_max", "--price-max")):
                    if values.get(key) not in (None, ""):
                        a += [flag, str(values[key])]
        if values.get("sell_prices"):
            a.append("--sell-prices")
        if values.get("sell_equipment"):
            a.append("--sell-equipment")
        if values.get("price_mode") == "range" and values.get("sell_prices"):
            for key, flag in (("sell_min", "--sell-min"), ("sell_max", "--sell-max")):
                if values.get(key) not in (None, ""):
                    a += [flag, str(values[key])]

    for on_key, mode_key, prefix, lo_key, hi_key in (
            ("random_runes", "rune_mode", "rune", "rune_min", "rune_max"),
            ("random_enemy_hp", "hp_mode", "hp", "hp_min", "hp_max"),
            ("random_durations", "duration_mode", "duration", "duration_min", "duration_max")):
        if not values.get(on_key):
            continue
        mode = values.get(mode_key)
        if not mode or mode == "shuffle":            # shuffle is the default, no flag needed
            continue
        a += [f"--{prefix}-mode", mode]
        if mode == "range":
            for key in (lo_key, hi_key):
                if values.get(key) not in (None, ""):
                    a += [f"--{key.replace('_', '-')}", str(values[key])]

    if values.get("random_enemy_drops") and values.get("enemy_drop_rolls") not in (None, ""):
        a += ["--enemy-drop-rolls", str(values["enemy_drop_rolls"]),
              "--enemy-drop-chance", str(values.get("enemy_drop_chance") or 50)]
    if values.get("random_enemy_drops"):
        o = BY_KEY["enemy_drop_kinds"]
        have = _groups_value(values, "enemy_drop_kinds")
        if len(have) != len(o.items):
            a += ["--enemy-drop-kinds", ",".join(have)]
    if values.get("random_shop_stock"):
        o = BY_KEY["shop_stock_kinds"]
        have = _groups_value(values, "shop_stock_kinds")
        if len(have) != len(o.items):
            a += ["--shop-stock-kinds", ",".join(have)]

    # weapons: --weapons when all four are on, else the individual flags
    four = ("somber_infusable", "random_movesets", "random_default_ash", "random_stats")
    if all(values.get(k) for k in four):
        a.append("--weapons")
    else:
        for key, flag in zip(four, ("--somber-infusable", "--random-movesets",
                                    "--random-default-ash", "--random-stats")):
            if values.get(key):
                a.append(flag)

    if values.get("somber_infusable"):
        if not values.get("no_weapon_names"):
            paths = list(values.get("weapon_names") or ()) or list(values.get("archives") or ())
            a += ["--weapon-names", *paths]
        if values.get("no_weapon_names"):
            a.append("--no-weapon-names")

    if values.get("random_movesets"):
        if values.get("moveset_mode") and values["moveset_mode"] != "affinity":
            a += ["--moveset-mode", values["moveset_mode"]]
        if values.get("moveset_mode") == "bound" and str(values.get("moveset_variety", 3)) != "3":
            a += ["--moveset-variety", str(values["moveset_variety"])]
        if values.get("keep_standard"):
            a.append("--keep-standard-moveset")
        if values.get("shield") and values["shield"] != "shields":
            a += ["--shield-movesets", values["shield"]]
        if values.get("bow") and values["bow"] != "bows":
            a += ["--bow-movesets", values["bow"]]
        if values.get("weptype"):
            a.append("--weptype-follows")

    if values.get("random_stats"):
        o = BY_KEY["stat_groups"]
        every = list(o.items)
        raw = values.get("stat_groups")
        # A comma list may arrive as a string (the GUI var) or a list (a validated dict); list() on a
        # string splits it into single characters, so "attack,guard" would become a,t,t,a,c,k,...
        have = ([str(g).strip() for g in raw if str(g).strip()] if isinstance(raw, (list, tuple))
                else [g.strip() for g in str(raw or "").split(",") if g.strip()]) or every
        groups = [g for g in every if g in have]
        extras = [g for g in have if g not in every]
        if len(groups) != len(every) or extras:
            a += ["--stat-groups", ",".join(groups + extras)]
        if values.get("req_mode") and values["req_mode"] != "tight":
            a += ["--req-mode", values["req_mode"]]
        lo, hi = _pair(values.get("stamina_rate"), (0.8, 1.2))
        if (lo, hi) != (0.8, 1.2):
            a += ["--stamina-rate", f"{lo:g},{hi:g}"]

    if values.get("flask_where") and values["flask_where"] != "anywhere":
        a += ["--flask-where", values["flask_where"]]
    if values.get("unique_rate") and values["unique_rate"] != "normal":
        a += ["--unique-rate", values["unique_rate"]]
    if values.get("no_reports"):
        a.append("--no-reports")
    if values.get("dry_run"):
        a.append("--dry-run")
    return a


def all_stat_groups() -> tuple[str, ...]:
    """The stat groups --random-stats can roll, in their canonical order."""
    import weapons
    return tuple(weapons.STAT_GROUPS)


def stat_groups_value(raw) -> list[str]:
    """--stat-groups from the GUI (a string) or the CLI: the explicit list, or every group."""
    groups = [g.strip() for g in str(raw or "").split(",") if g.strip()]
    return groups or list(all_stat_groups())