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

The hover text lives in tips.py and is looked up by key; this table only holds the structure (kind,
default, limits and dependencies), so a label can be translated without touching the rules.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from tips import TIPS

# -------------------------------------------------------------------------------- helpers
# Groups, in the order the GUI lays them out.  Loot lives in one section on purpose: the drop table,
# the upgrade level of what drops and the places loot can be found are one subject, not three.
# "advanced" collects the knobs that only matter in unusual setups; it is collapsed by default.
GROUPS = (
    ("files", "Files and output"),
    ("loot", "Loot and upgrade levels"),
    ("prices", "Prices and shops"),
    ("weapons", "Weapons"),
    ("weapon_effects", "Chaotic Weapon Effects"),
    ("gems", "Ashes of War"),
    ("gear", "Armour and talismans"),
    ("drops", "Enemies: health and runes"),
    ("goods", "Consumables and buffs"),
    ("spells", "Spells"),
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
    # The long hover text lives in tips.py; a key with no entry there falls back to the label.
    tip = TIPS.get(key)
    if tip:
        kw["tip"] = tip
    return Opt(key, tuple(flags), **kw)


# -------------------------------------------------------------------------------- the table
OPTIONS: tuple[Opt, ...] = (
    # --- files -----------------------------------------------------------------------------
    _o("input", "--input", kind="str", default="regulation.bin", group="files",
       label="Input regulation.bin"),
    _o("output", "--output", kind="str", default="randomized/regulation.bin", group="files",
       label="Output file"),
    _o("backup_replace", "--backup-replace", neg=("--no-backup-replace",), group="files", default=True,
       label="Backup and replace files"),
    _o("oodle_dll", "--oodle-dll", kind="path", default=None, group="files", metavar="PATH",
       label="Oodle DLL"),
    _o("archives", kind="paths", default=(), group="files", metavar="FOLDER", cli=False,
       label="Text archives folder"),
    _o("seed", "--seed", kind="int", default=None, group="files", label="Seed"),
    _o("compression", "--compression", kind="enum", default="kraken", group="files",
       choices=("auto", "kraken", "zstd", "leviathan"), label="Compression"),
    _o("compression_level", "--compression-level", kind="enum", default="max", group="files",
       choices=("fast", "max"), label="Effort"),
    _o("repack", "--repack", group="files", label="Repack only (change nothing)"),

    # --- loot: what drops, how good it is, and where it is found -----------------------------
    _o("random_enemy_drops", "--random-enemy-drops", group="loot",
       label="Randomize enemy drops"),
    _o("enemy_drop_rolls", "--enemy-drop-rolls", kind="int", default=3, group="loot",
       needs=("random_enemy_drops",), metavar="N", label="Rolls per enemy"),
    _o("enemy_drop_chance", "--enemy-drop-chance", kind="int", default=25, group="loot",
       needs=("random_enemy_drops",), metavar="P", label="Chance per roll (%)"),
    _o("enemy_drop_kinds", "--enemy-drop-kinds", kind="groups", default="", group="loot",
       needs=("random_enemy_drops",), items=("weapons", "armor", "talismans", "goods", "ashes"),
       label="What enemies can drop"),
    _o("unique_drops", "--unique-drops", group="loot", needs=("random_enemy_drops",),
       label="Rare unique weapons"),
    _o("unique_rate", "--unique-rate", kind="int", default=3, metavar="PERCENT", group="loot",
       needs=("random_enemy_drops", "unique_drops"), label="Unique weapon rate"),
    _o("material_drops", "--material-drops", group="loot", needs=("random_enemy_drops",),
       label="Upgrade material drops"),
    _o("random_dropped_weapons", "--random-dropped-weapons", group="loot",
       label="Randomize dropped weapons"),
    _o("random_dropped_shop_weapons", "--random-dropped-shop-weapons", group="loot",
       needs=("random_dropped_weapons",), label="Reroll weapons in shop stock"),
    _o("random_loot_levels", "--random-loot-levels", group="loot",
       label="Random upgrade levels on loot"),
    _o("loot_rarity", "--loot-rarity", kind="enum", default="common", group="loot",
       choices=("even", "common", "legendary"), needs=("random_loot_levels",), label="Upgrade rarity"),
    _o("loot_max_level", "--loot-max-level", kind="int", default=None, group="loot",
       needs=("random_loot_levels",), label="Max upgrade level"),
    _o("loot_boss_bonus", "--loot-boss-bonus", kind="enum", default="better", group="loot",
       choices=("same", "better", "best"), needs=("random_loot_levels",),
       label="Bosses roll better"),
    _o("zone_loot_levels", "--zone-loot-levels", group="loot", needs=("random_loot_levels",),
       label="Zone-aware loot levels"),
    _o("random_weapon_drops", "--random-weapon-drops", group="loot",
       label="Move weapons to random enemies"),
    _o("random_armor_drops", "--random-armor-drops", group="loot",
       label="Move armor to random enemies"),
    _o("armour_drop_sets", "--armor-drop-sets", group="loot", needs=("random_armor_drops",),
       label="Move armor sets as a set"),
    _o("random_talisman_drops", "--random-talisman-drops", group="loot",
       label="Move talismans to random enemies"),
    _o("random_goods_drops", "--random-goods-drops", group="loot",
       label="Move goods to random enemies"),
    _o("random_ashes_drops", "--random-ashes-drops", group="loot",
       label="Move Ashes of War to random enemies"),

    # --- prices ----------------------------------------------------------------------------
    _o("random_shop_stock", "--random-shop-stock", group="prices",
       label="Randomize what shops sell"),
    _o("shop_stock_kinds", "--shop-stock-kinds", kind="groups", default="", group="prices",
       needs=("random_shop_stock",), items=("weapons", "armor", "talismans", "goods", "ashes"),
       label="Shop stock categories"),
    _o("random_prices", "--random-prices", group="prices", label="Shuffle shop prices"),
    _o("price_mode", "--price-mode", kind="enum", default="shuffle", group="prices",
       choices=("shuffle", "range"), needs=("random_prices",), label="Method"),
    _o("price_min", "--price-min", kind="int", default=None, group="prices",
       needs=("random_prices",), label="Minimum price"),
    _o("price_max", "--price-max", kind="int", default=None, group="prices",
       needs=("random_prices",), label="Maximum price"),
    _o("sell_prices", "--sell-prices", neg=("--no-sell-prices",), default=False, group="prices",
       needs=("random_prices",), label="Shuffle sell prices too"),
    _o("sell_min", "--sell-min", kind="int", default=None, group="prices",
       needs=("random_prices", "sell_prices"), label="Minimum sell price"),
    _o("sell_max", "--sell-max", kind="int", default=None, group="prices",
       needs=("random_prices", "sell_prices"), label="Maximum sell price"),
    _o("sell_equipment", "--sell-equipment", group="prices", needs=("random_prices",),
       label="Include weapons, armor and Ashes of War"),

    # --- weapons ---------------------------------------------------------------------------
    _o("weapons", "--weapons", group="weapons", gui=False, label="All four weapon options",
       expands=("somber_infusable", "random_movesets", "random_default_ash", "random_stats")),
    _o("somber_infusable", "--somber-infusable", group="weapons",
       label="Make somber weapons infusable"),
    _o("random_movesets", "--random-movesets", group="weapons", label="Shuffle movesets"),
    _o("moveset_mode", "--moveset-mode", kind="enum", default="affinity", group="weapons",
       choices=("affinity", "bound", "weapon"), needs=("random_movesets",), label="Moveset mode"),
    _o("moveset_variety", "--moveset-variety", kind="int", default=3, group="weapons",
       needs=("random_movesets",), label="Bound variety"),
    _o("keep_standard", "--keep-standard-moveset", group="weapons", needs=("random_movesets",),
       label="Leave Standard rows alone"),
    _o("shield", "--shield-movesets", kind="enum", default="shields", group="weapons",
       choices=("shields", "none", "all"), needs=("random_movesets",), label="Shields"),
    _o("bow", "--bow-movesets", kind="enum", default="bows", group="weapons",
       choices=("bows", "none"), needs=("random_movesets",), label="Bows"),
    _o("weptype", "--weptype-follows", group="weapons", needs=("random_movesets",),
       label="Weapon type follows the moveset"),
    _o("random_default_ash", "--random-default-ash", group="weapons",
       label="Random default skill and affinity"),
    _o("random_stats", "--random-stats", group="weapons", label="Randomize weapon stats"),
    _o("req_mode", "--req-mode", kind="enum", default="tight", group="weapons",
       choices=("tight", "normal", "wild"), needs=("random_stats",), label="Requirement spread"),
    _o("stat_groups", "--stat-groups", kind="groups", default="", group="weapons",
       needs=("random_stats",), items=("attack", "guard", "requirements", "scaling", "effects", "stamina"),
       label="Stat groups"),
    _o("stamina_rate", "--stamina-rate", kind="pair", default="0.8,1.2", group="weapons",
       needs=("random_stats",), label="Stamina multiplier range"),
    _o("weapon_names", "--weapon-names", kind="paths", default=None, group="weapons", metavar="FOLDER",
       needs=("somber_infusable",), label="Name the new affinity rows"),
    _o("no_weapon_names", "--no-weapon-names", group="weapons", advanced=True,
       label="Use placeholder names (no text patch)"),

    # --- chaotic weapon effects ------------------------------------------------------------
    _o("random_weapon_onhit_shuffle", "--random-weapon-onhit-shuffle", group="weapon_effects",
       label="Shuffle on-hit bundles"),
    _o("random_weapon_holder_shuffle", "--random-weapon-holder-shuffle", group="weapon_effects",
       label="Shuffle held-effect bundles"),
    _o("random_weapon_status_roll", "--random-weapon-status-roll", group="weapon_effects",
       label="Roll chaotic statuses"),
    _o("random_loot_effects", "--random-loot-effects", group="weapon_effects",
       needs=("random_weapon_status_roll",), label="Loot weapons only"),

    # --- ashes of war ----------------------------------------------------------------------
    _o("random_gem_skills", "--random-gem-skills", group="gems", label="Shuffle skills"),
    _o("random_gem_effects", "--random-gem-effects", group="gems", label="Shuffle on-hit effects"),

    # --- armour and talismans --------------------------------------------------------------
    _o("random_armor_fresh", "--random-armor-fresh", group="gear", label="Randomize armor stats"),
    _o("armour_keep_sets", "--armor-keep-sets", neg=("--no-armor-keep-sets",), group="gear",
       needs=("random_armor_fresh",), default=True, label="Keep armor sets together"),
    _o("random_armor", "--random-armor", group="gear", label="Shuffle armor stats"),
    _o("random_talismans", "--random-talismans", group="gear", label="Shuffle talismans"),

    # --- enemies: health and runes ---------------------------------------------------------
    _o("random_enemy_hp", "--random-enemy-hp", group="drops", label="Shuffle enemy HP"),
    _o("hp_mode", "--hp-mode", kind="enum", default="shuffle", group="drops",
       choices=("shuffle", "range", "bands", "balanced"), needs=("random_enemy_hp",), label="HP method"),
    _o("hp_min", "--hp-min", kind="int", default=None, group="drops",
       needs=("random_enemy_hp",), label="Lowest HP"),
    _o("hp_max", "--hp-max", kind="int", default=None, group="drops",
       needs=("random_enemy_hp",), label="Highest HP"),
    _o("random_runes", "--random-runes", group="drops", label="Shuffle enemy runes"),
    _o("rune_mode", "--rune-mode", kind="enum", default="shuffle", group="drops",
       choices=("shuffle", "range", "bands"), needs=("random_runes",), label="Rune method"),
    _o("rune_min", "--rune-min", kind="int", default=None, group="drops",
       needs=("random_runes",), label="Fewest runes"),
    _o("rune_max", "--rune-max", kind="int", default=None, group="drops",
       needs=("random_runes",), label="Most runes"),
    _o("boss_hp_scale", "--boss-hp-scale", kind="pair", default="1.0,1.0", group="drops",
       label="Boss HP multiplier range"),
    _o("boss_rune_scale", "--boss-rune-scale", kind="pair", default="1.0,1.0", group="drops",
       label="Boss rune multiplier range"),
    _o("couple_runes_to_hp", "--couple-runes-to-hp", group="drops", needs=("random_enemy_hp",),
       label="Couple runes to HP"),
    _o("boss_min_runes", "--boss-min-runes", kind="int", default=0, group="drops", metavar="N",
       label="Boss rune threshold"),

    # --- consumables and buffs -------------------------------------------------------------
    _o("goods", "--goods", neg=("--no-goods",), default=False, group="goods",
       label="Shuffle consumable effects"),
    _o("goods_name_gaps", "--goods-name-gaps", group="goods",
       label="Warn about goods without names"),
    _o("mode", "--mode", kind="enum", default="shuffle", group="goods", choices=("shuffle", "random"),
       needs=("goods",), label="Assignment"),
    _o("include_flasks", "--include-flasks", group="goods", needs=("goods",),
       label="Include the flasks"),
    _o("include_remembrances", "--include-remembrances", group="goods", needs=("goods",),
       label="Include remembrances"),
    _o("goods_quantity", "--goods-quantity", group="goods", label="Shuffle stack sizes"),
    _o("split_anim", "--split-anim", kind="enum", default="none", group="goods",
       choices=("none", "same", "any"), needs=("goods",), metavar="same|any",
       label="Use animation"),
    _o("random_durations", "--random-durations", group="goods", label="Shuffle buff durations"),
    _o("duration_mode", "--duration-mode", kind="enum", default="shuffle", group="goods",
       choices=("shuffle", "range"), needs=("random_durations",), label="Duration method"),
    _o("duration_min", "--duration-min", kind="int", default=None, group="goods",
       needs=("random_durations",), label="Shortest buff (s)"),
    _o("duration_max", "--duration-max", kind="int", default=None, group="goods",
       needs=("random_durations",), label="Longest buff (s)"),

    # --- spells ----------------------------------------------------------------------------
    _o("spells", "--spells", neg=("--no-spells",), default=False, group="spells",
       label="Shuffle spell effects"),
    _o("spell_stats", "--spell-stats", group="spells", label="Randomize spell stats"),

    # --- flasks and starting items ---------------------------------------------------------
    _o("random_flask_locations", "--random-flask-locations", group="world",
       label="Move the two flasks"),
    _o("flask_where", "--flask-where", kind="enum", default="anywhere", group="world",
       needs=("random_flask_locations",), choices=("anywhere", "overworld", "early"),
       label="Where the flasks may go"),
    _o("start_bell", "--start-with-bell", group="world", label="Start with the Spirit Calling Bell"),
    _o("start_lantern", "--start-with-lantern", group="world", label="Start with the Lantern"),

    # --- advanced --------------------------------------------------------------------------
    _o("dry_run", "--dry-run", group="advanced", advanced=True,
       label="Preview only (write nothing)"),
    _o("no_reports", "--no-reports", group="advanced", advanced=True,
       label="Do not write the report files"),
    _o("brief_reports", "--brief-reports", group="advanced", advanced=True,
       label="Short reports (headers only)"),
    _o("max_size", "--max-size", kind="int", default=None, group="advanced", advanced=True,
       metavar="BYTES", label="Output size limit"),
    _o("simulate", "--simulate", kind="int", default=None, group="advanced", advanced=True,
       metavar="N", gui=False, label="Simulate N drops instead of writing"),
    _o("zstd_window", "--zstd-window", kind="int", default=16, group="advanced", advanced=True,
       choices=(16, 17, 18, 19, 20, 21, 22), metavar="16..22", label="zstd window log"),
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
    # --version is not an option: argparse prints it and exits before anything runs, so it never
    # reaches values_from_args() and never appears in the window (which is generated from OPTIONS).
    import version
    ap.add_argument("--version", action="version", version=f"%(prog)s {version.__version__}")
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
        if not 0 <= out["enemy_drop_rolls"] <= 32:
            raise ValueError("Rolls per enemy must be between 0 and 32 (0 = one guaranteed item per kill)")
        if out["enemy_drop_rolls"] == 0:
            out["enemy_drop_rolls"] = None       # 0 and an empty field mean the guaranteed mode
    if out["enemy_drop_chance"] is None:
        out["enemy_drop_chance"] = BY_KEY["enemy_drop_chance"].default
    if not 1 <= out["enemy_drop_chance"] <= 100:
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
    if out["unique_rate"] is None:
        out["unique_rate"] = BY_KEY["unique_rate"].default
    if not 1 <= out["unique_rate"] <= 20:
        raise ValueError("Unique weapon rate must be between 1 and 20 (percent)")

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
    if o.key == "enemy_drop_rolls":
        return bool(values.get("random_enemy_drops"))
    if o.key == "enemy_drop_chance":
        # chance only means something when there is at least one roll; 0 is the guaranteed-row mode
        return bool(values.get("random_enemy_drops")) and values.get("enemy_drop_rolls") not in (None, "", 0, "0")
    if o.needs:
        return all(values.get(k) for k in o.needs)
    return True


# Options that are not on/off switches even though they are booleans: a run mode, a report switch, or
# a refinement of another option.  Everything else is a master switch, and at least one of them has to be
# on for a run to change anything.
_NOT_A_SWITCH = {"repack", "dry_run", "no_reports", "sell_prices", "keep_standard", "weptype",
                 "no_weapon_names", "include_flasks", "include_remembrances"}


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
                       ("goods_name_gaps", "--goods-name-gaps"),
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
                      ("random_weapon_onhit_shuffle", "--random-weapon-onhit-shuffle"),
                      ("random_weapon_holder_shuffle", "--random-weapon-holder-shuffle"),
                      ("random_weapon_status_roll", "--random-weapon-status-roll"),
                      ("random_loot_effects", "--random-loot-effects"),
                      ("brief_reports", "--brief-reports"),
                      ("random_runes", "--random-runes"),
                      ("random_enemy_hp", "--random-enemy-hp"),
                      ("spell_stats", "--spell-stats"),
                      ("random_durations", "--random-durations"),
                      ("random_flask_locations", "--random-flask-locations"),
                      ("start_bell", "--start-with-bell"),
                      ("start_lantern", "--start-with-lantern"),
                      ("random_dropped_weapons", "--random-dropped-weapons"),
                      ("random_dropped_shop_weapons", "--random-dropped-shop-weapons"),
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

    if values.get("random_enemy_drops"):
        rolls = values.get("enemy_drop_rolls")
        # 0 (or an empty field) is the guaranteed mode: pass it explicitly so the round trip does not
        # silently turn it back into the table default of 3 rolls.
        a += ["--enemy-drop-rolls", "0" if rolls in (None, "") else str(rolls)]
        if rolls not in (None, "", 0, "0"):
            a += ["--enemy-drop-chance", str(values.get("enemy_drop_chance")
                                         or BY_KEY["enemy_drop_chance"].default)]
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
    if values.get("unique_drops") and values.get("unique_rate") \
            and str(values["unique_rate"]) != str(BY_KEY["unique_rate"].default):
        a += ["--unique-rate", str(values["unique_rate"])]
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
