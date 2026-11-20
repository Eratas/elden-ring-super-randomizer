#!/usr/bin/env python3
"""Elden Ring regulation.bin randomizer: the command line front end.

Every option lives in options.py (flag, label, hover text, default, rules); this file turns a value
dict into passes over the parameter tables and writes the reports.  gui.py builds its window from the
same table and runs this module in a worker thread, so the GUI and the command line can never disagree
about what an option does.

Passes, in the order they run (the order matters: the random generator is shared and some passes read
values another pass is about to change):

    goods      every usable item gets another item's use effect, stack sizes (EquipParamGoods)
    prices     shop prices and sell prices (ShopLineupParam, EquipParamGoods, equipment tables)
    durations  how long buffs last (SpEffectParam.effectEndurance)
    runes      the runes an enemy gives (NpcParam.getSoul)
    hp         the hit points of an enemy (NpcParam.hp)
    drops      what an enemy drops (ItemLotParam_enemy)
    weapons    somber affinities, movesets, default skills, per-row stats (EquipParamWeapon ...)
    ashes      skills and on-hit effects of Ashes of War (EquipParamGem)
    armour     armour stats (EquipParamProtector), talisman rows (EquipParamAccessory)
    levels     upgrade levels of the weapons in drop tables, chests and shops
    names      names for the affinity rows the somber pass added (item_dlc02.msgbnd.dcx)
    spells     spell effects and spell stats (Magic)
    world      flask locations, starting items (ItemLotParam_map, item lot 2000)
"""
from __future__ import annotations

import io
import math
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import balance  # noqa: E402
import boss_scale  # noqa: E402
import dropshuffle  # noqa: E402
import enemy_drops  # noqa: E402
import erreg  # noqa: E402
import flasks  # noqa: E402
import gear  # noqa: E402
import gems  # noqa: E402
import goods  # noqa: E402
import loot  # noqa: E402
import oodle  # noqa: E402
import options  # noqa: E402
import phases  # noqa: E402
import runes  # noqa: E402
import shops  # noqa: E402
import spells  # noqa: E402
import start_items  # noqa: E402
import textarchives  # noqa: E402
import weapon_names  # noqa: E402
import weapons  # noqa: E402

HERE = Path(__file__).resolve().parent

# Fields that travel together as "the effect" of a consumable item.
EFFECT_FIELDS = [
    "refCategory", "refId_default", "refId_1", "spEffectCategory", "refVirtualWepId",
    "behaviorId", "sfxVariationId",
    "goodsUseAnim", "castSfxId", "fireSfxId", "effectSfxId", "isDisableHand", "opmeMenuType",
    "isEnableFastUseItem", "canMultiUse", "isApplySpecialEffect", "isShieldEnchant",
    "consumeMP", "consumeHP", "consumeHeroPoint", "overDexterity",
    "useLimitCategory", "useLimitSpEffectType", "useEnableSpEffectType", "useLimitSummonBuddy",
    "enable_live", "enable_gray", "enable_white", "enable_black", "enable_multi",
    "disable_offline", "disableUseAtColiseum", "disableUseAtOutOfColiseum",
    "isUseMultiPlayPreparation", "isUseMultiPenaltyOnly", "isWarpProhibited",
    "enableRiding", "disableRiding", "isSummonHorse", "isUseNoAttackRegion",
    "isBonfireWarpItem", "enable_Ladder", "enable_ActiveBigRune",
    "useLevel", *[f"useLevel_vowType{i}" for i in range(16)],
    "aiUseJudgeId", "yesNoDialogMessageId", "replaceItemId", "replaceCategory",
    "appearanceReplaceItemId",
]

# Subset of EFFECT_FIELDS that is the use *animation* (motion, hand-held / release SFX, fast cancel).
# --split-anim takes these from a second donor: `same` = one whose vanilla refCategory equals the
# effect donor's (thrown items release a bullet, applied / eaten items apply a SpEffect; the TAE events
# differ), `any` = any pool item (cross-category triggering untested in-game).
ANIM_FIELDS = ["goodsUseAnim", "castSfxId", "fireSfxId", "sfxVariationId", "isEnableFastUseItem"]

GOODS_TYPE_NORMAL, GOODS_TYPE_KEY, GOODS_TYPE_REMEMBRANCE = 0, 1, 3
MENU_NONE, MENU_YES_NO = 0, 1          # opmeMenuType: 1 is only a yes/no confirmation, the rest open real menus
REF_BULLET, REF_SPEFFECT = 1, 2
SHOP_EQUIP_TYPE_GOODS = 3
SHOP_COST_RUNES = 0

# Goods that keep their vanilla effect whatever the options (by row id).
KEEP_GOODS = {
    2070,   # Lantern: an on / off toggle (refId_default / refId_1 = lit / unlit SpEffects), stays as is
}


def utf8_stdio() -> None:
    """Never let a console code page kill a run over one character.

    The reports carry item names from the game's text archives, which are Chinese, Japanese, Korean ...
    on an English Windows console (cp1252) a plain print() raises UnicodeEncodeError half way through
    the report (found 2026-11-16).  Keep the console's encoding, but replace what it cannot show."""
    for stream in (getattr(sys, "stdout", None), getattr(sys, "stderr", None)):
        if stream is None:
            continue
        try:
            stream.reconfigure(errors="replace")          # type: ignore[attr-defined]
        except (AttributeError, ValueError, OSError):
            pass


# ---------------------------------------------------------------- goods
def build_pool(P: erreg.Param, names: dict[int, str], include_flasks: bool = False,
               include_remembrances: bool = False):
    """Every item the player can use from the inventory: consumables (Golden / Shadow Realm Runes
       included), reusable tools (shackles, bairns, Miquella's Great Rune...), usable key items;
       flasks and remembrances only on request."""
    types = {GOODS_TYPE_NORMAL, GOODS_TYPE_KEY} | ({GOODS_TYPE_REMEMBRANCE} if include_remembrances else set())
    pool = []
    for r in P.rows:
        name = names.get(r.id)
        if not name or name == "?":
            continue                                   # unnamed / cut rows
        if r.id in KEEP_GOODS:
            continue                                   # fixed by design (Lantern)
        if P.get(r, "goodsType") not in types:
            continue                                   # materials, spells, spirit ashes, crystal tears...
        if P.get(r, "refCategory") not in (REF_BULLET, REF_SPEFFECT) or P.get(r, "refId_default") == -1:
            continue                                   # no usable effect
        if P.get(r, "opmeMenuType") not in (MENU_NONE, MENU_YES_NO):
            continue                                   # opens a real menu (fingers, effigies, whistle)
        if P.get(r, "disable_offline"):
            continue                                   # multiplayer-only (fingers, phantom items)
        if P.get(r, "isSummonHorse"):
            continue                                   # Spectral Steed Whistle (both states): Torrent stays as is
        if P.get(r, "iconId") == 0 or P.get(r, "sortId") in (0, 999999):
            continue                                   # unused / placeholder rows
        if not include_flasks and P.get(r, "suppleType") != 0:
            continue                                   # Flask of Crimson/Cerulean Tears
        pool.append(r)
    return pool


def anim_sources(P: erreg.Param, pool: list, src: list[int], mode: str, rng: random.Random,
                 any_category: bool = False) -> list[int]:
    """Per item, the index of the pool item whose use animation it gets: drawn among the items whose
       vanilla refCategory equals that of the item's effect donor src[i], or among the whole pool with
       any_category.  shuffle: every animation of a category is used once (a permutation of that
       category's items); random: free draw."""
    cat = [0 if any_category else P.get(r, "refCategory") for r in pool]
    by_cat: dict[int, list[int]] = {}
    for j, c in enumerate(cat):
        by_cat.setdefault(c, []).append(j)
    anim = [0] * len(pool)
    if mode == "shuffle":
        receivers: dict[int, list[int]] = {}
        for i in range(len(pool)):
            receivers.setdefault(cat[src[i]], []).append(i)
        for c, idx in receivers.items():
            donors = by_cat[c][:]
            while len(donors) < len(idx):            # only in random mode; shuffle keeps the multiset
                donors += by_cat[c]
            rng.shuffle(donors)
            for i, j in zip(idx, donors):
                anim[i] = j
    else:
        for i in range(len(pool)):
            anim[i] = rng.choice(by_cat[cat[src[i]]])
    return anim


def derangement(n: int, rng: random.Random) -> list[int]:
    """Permutation with no fixed point (every item gets a *different* item's effect).

    n < 2 has no fixed-point-free permutation (a single item can only keep its own effect), so the
    identity is returned instead of looping forever - callers treat a pool smaller than two as
    "nothing to shuffle"."""
    if n < 2:
        return list(range(n))
    while True:
        perm = list(range(n))
        rng.shuffle(perm)
        if all(i != p for i, p in enumerate(perm)):
            return perm


# ---------------------------------------------------------------- prices
def round_price(v: float) -> int:
    """Round to 2 significant digits so prices look like shop prices (1234 -> 1200)."""
    v = max(1, int(round(v)))
    digits = int(math.log10(v))
    step = 10 ** max(0, digits - 1)
    return max(1, int(round(v / step)) * step)


def new_prices(old: list[int], rng: random.Random, mode: str, lo: int | None, hi: int | None,
               what: str) -> list[int]:
    """shuffle: a permutation of the existing prices (an entry may land on its own price again);
       range: log-uniform draws between lo and hi (default: the lowest / highest existing price),
       rounded to 2 significant digits.

    An empty pool has neither an entry to permute nor a lowest/highest to draw between, so it yields an
    empty list.  Every caller that passes a pool the regulation.bin may not fill (a shop table with no
    priced goods) would otherwise die on `min()` of nothing with "min() iterable argument is empty",
    which names neither the pass nor the file.
    """
    if not old:
        return []
    if mode == "shuffle":
        new = old[:]
        rng.shuffle(new)
        return new
    lo = lo if lo is not None else min(old)
    hi = hi if hi is not None else max(old)
    if lo < 1 or hi < lo:
        raise SystemExit(f"bad {what} range {lo}..{hi}")
    return [round_price(math.exp(rng.uniform(math.log(lo), math.log(hi)))) for _ in old]


EQUIPMENT_SELL = (("EquipParamWeapon", "weapon"), ("EquipParamProtector", "armor"), ("EquipParamGem", "ash of war"))


def randomize_equipment_sell(reg: erreg.Regulation, rng: random.Random, mode: str,
                             smin: int | None, smax: int | None) -> list[str]:
    """--sell-equipment: sellValue of weapons, armor pieces and Ashes of War, one pool per table.
    A weapon is one entry (its base row, id % 10000 == 0) and every affinity row of it gets the same
    new price.  Rows with sellValue <= 0 (unsellable, dummies) stay as they are; unnamed rows (cut
    content, DLC pieces Paramdex has no name for) take part and are listed by id."""
    lines: list[str] = []
    for param, what in EQUIPMENT_SELL:
        P = reg.param(param, erreg.load_paramdef(HERE / "paramdef" / f"{param}.xml"))
        names = erreg.load_names(HERE / "names" / f"{param}.txt")
        weapon = param == "EquipParamWeapon"
        heads = [r for r in P.rows if P.get(r, "sellValue") > 0 and (not weapon or r.id % 10000 == 0)]
        members: dict[int, list] = {}
        for r in P.rows:
            members.setdefault(r.id - r.id % 10000 if weapon else r.id, []).append(r)
        old = [P.get(r, "sellValue") for r in heads]
        new = new_prices(old, rng, mode, smin, smax, f"{what} sell price")
        lines += ["", f"# {what} sell prices: mode={mode} entries={len(heads)}  ({param}.sellValue"
                  + ("; every affinity row of a weapon gets its price)" if weapon else ")")
                  + ("" if old else "  (no sellable rows, left alone)"),
                  "# item  old -> new (runes)"]
        for r, o, n in zip(heads, old, new):
            for m in members[r.id]:
                P.set(m, "sellValue", n)
            lines.append(f"{r.id:>8}  {names.get(r.id, f'{what} {r.id}'):<40} {o:>7} -> {n}")
    return lines


def randomize_prices(reg: erreg.Regulation, rng: random.Random, mode: str,
                     pmin: int | None, pmax: int | None,
                     sell: bool = True, smin: int | None = None, smax: int | None = None) -> list[str]:
    """Shop prices: ShopLineupParam.value of every goods entry priced in runes (whatever the slot sells,
    so items an item randomizer put into shops are included).  Sell prices (unless sell is False):
    EquipParamGoods.sellValue of every named goods row that can be sold (sellValue > 0; -1 = unsellable).
    Shop prices and sell prices are drawn independently, so an item may well sell back for more
    than a merchant asks for it; the user prefers that to a cap."""
    pd = erreg.load_paramdef(HERE / "paramdef" / "ShopLineupParam.xml")
    slots = erreg.load_names(HERE / "names" / "ShopLineupParam.txt")     # vanilla "[merchant] item" per slot
    goods = erreg.load_names(HERE / "names" / "EquipParamGoods.txt")
    Sh = reg.param("ShopLineupParam", pd)
    rows = [r for r in Sh.rows
            if Sh.get(r, "equipType") == SHOP_EQUIP_TYPE_GOODS
            and Sh.get(r, "costType") == SHOP_COST_RUNES
            and Sh.get(r, "value") > 0]            # free (0) and non-rune entries are left alone
    old = [Sh.get(r, "value") for r in rows]
    new = new_prices(old, rng, mode, pmin, pmax, "price")
    lines = [f"# prices: mode={mode} entries={len(rows)}" + ("" if old else "  (no shop slot sells goods for runes, left alone)"),
             "# shop entry  [merchant] item sold  old -> new (runes)   (slot: what the slot sells in vanilla,"
             " shown when an item randomizer put something else there)"]
    for r, o, n in zip(rows, old, new):
        Sh.set(r, "value", n)
        eid = Sh.get(r, "equipId")
        slot = slots.get(r.id, "")
        merchant, _, slot_item = slot.rpartition("] ") if slot.startswith("[") else ("", "", slot)
        merchant = merchant + "]" if merchant else ""
        item = goods.get(eid, f"goods {eid}")
        note = f"   (slot: {slot_item})" if slot_item and slot_item != item else ""
        lines.append(f"{r.id:>8}  {merchant:<44} {item:<40} {o:>7} -> {n:<6}{note}".rstrip())
    if not sell:
        return lines
    G = reg.param("EquipParamGoods", erreg.load_paramdef(HERE / "paramdef" / "EquipParamGoods.xml"))
    srows = [r for r in G.rows if G.get(r, "sellValue") > 0 and r.id in goods]   # named rows only: ids 23-99 are debug items
    sold = [G.get(r, "sellValue") for r in srows]
    snew = new_prices(sold, rng, mode, smin, smax, "sell price")
    lines += ["", f"# sell prices: mode={mode} entries={len(srows)}  (EquipParamGoods.sellValue)"
              + ("" if sold else "  (no named sellable goods, left alone)"),
              "# item  old -> new (runes)"]
    for r, o, n in zip(srows, sold, snew):
        G.set(r, "sellValue", n)
        lines.append(f"{r.id:>8}  {goods.get(r.id, '?'):<40} {o:>7} -> {n}")
    return lines


# ---------------------------------------------------------------- output
DLL_HELP = f"""
# {oodle.DLL_NAME} not found, so the output cannot be compressed with the game's own Oodle (KRAK format).
# It is only looked for in the current directory (randomize.sh / .bat switch to the project directory first,
# so that is er_mod/{oodle.DLL_NAME}).  The file is in the game folder (Steam\\steamapps\\common\\ELDEN RING\\Game\\)
# and in the mod folders of the fog gate / item randomizers (mod/fog/, mod/randomizer/); copy it next to the tool,
# enter its full path below, or pass --oodle-dll PATH / set the OODLE_DLL environment variable.
# Press Enter without a path to go without it: the output is then zstd (64 KB window), about 35% larger,
# and may exceed the game's size limit."""


def choose_codec(wanted: str, level: str = "fast") -> str:
    """Resolve --compression: kraken needs the game's Oodle DLL.  When it is missing, ask the user
    for it before falling back to zstd (and never fall back silently)."""
    if wanted == erreg.CODEC_ZSTD:
        return wanted
    why = oodle.available()
    while why and oodle.missing_dll():
        print(DLL_HELP)
        if sys.stdin is None or not sys.stdin.isatty():
            raise SystemExit(f"# {oodle.DLL_NAME} not found and no terminal to ask for it. Pass --oodle-dll PATH or "
                             "set OODLE_DLL, or add --compression zstd explicitly to use zstd instead.")
        try:
            answer = input(f"Path to {oodle.DLL_NAME} (Enter = I do not have it): ").strip().strip('"').strip("'")
        except EOFError:
            answer = ""
        if not answer:
            if wanted != "auto":
                raise SystemExit(f"--compression {wanted} needs {oodle.DLL_NAME}; cancelled.")
            print("# no DLL given, falling back to zstd (64 KB window, larger file).")
            return erreg.CODEC_ZSTD
        if not oodle.use_dll(answer):
            print(f"# file not found: {answer}")
        why = oodle.available()
    if why:                                   # liblinoodle.so missing or the DLL unusable
        if wanted != "auto":
            raise SystemExit(f"--compression {wanted} unavailable: {why}")
        print(f"# note: {why}; falling back to zstd (64 KB window, larger file).")
        return erreg.CODEC_ZSTD
    return erreg.CODEC_KRAKEN if wanted == "auto" else wanted


def archive_guard(flag: str, src: Path, output: Path, dry_run: bool) -> None:
    """The patched text archives go to <output folder>/msg/<language>/; never on top of their own source or the
       archives shipped next to the program (an output written into the program's folder would do that)."""
    dst = output.resolve().parent / "msg" / src.parent.name / src.name
    if dst.resolve() == src.resolve() or textarchives.MSG_DIR.resolve() in dst.resolve().parents:
        what = ("its own source" if dst.resolve() == src.resolve()
                else f"the text archives shipped with the program ({textarchives.MSG_DIR})")
        msg = (f"{flag}: the patched {dst} would overwrite {what}. Create a new folder for the output; that also "
               "keeps the mods easy to manage.")
        if dry_run:
            print("# warning: " + msg)
            return
        raise SystemExit(msg)


def shipped_warning(flag: str, archives: list[Path]) -> list[str]:
    """What an option prints (and puts into weapons.txt) when it falls back to the shipped text archives."""
    return [f"# {flag.lstrip('-')}: using the shipped text archives: " + ", ".join(str(a) for a in archives),
            "# warning: using the msg/ files provided by this program could cause the disagreement between "
            "the name and the actual items"]


# ---------------------------------------------------------------- the run


def _kinds(text) -> set[int] | None:
    """The enemy drop pool filter from --enemy-drop-kinds (a comma list); empty means every category."""
    picked = [k.strip().lower() for k in str(text or "").split(",") if k.strip()]
    if not picked:
        return None
    known = {"goods": 1, "weapons": 2, "armor": 3, "talismans": 4, "ashes": 5}
    return {known[k] for k in picked if k in known}


def main(argv: list[str] | None = None, progress=None, quiet: bool = False) -> int:
    """Run the passes.  `progress` is called with a short phase name ("weapons", "compressing", ...)
    whenever the run moves on; the window uses it for its status line and progress bar, the command line
    ignores it."""
    say = progress or (lambda _phase: None)
    utf8_stdio()
    ap = options.build_argparse(prog="randomize.py", description=__doc__,
                                epilog="Every option is documented in options.py; the GUI is generated from the "
                                       "same table, so `randomize.py --help` and the hover text always agree.")
    args = ap.parse_args(argv)
    try:
        v = options.validate(options.values_from_args(args))
    except ValueError as e:
        raise SystemExit(str(e)) from None      # user-facing validation error, not a crash

    dll = getattr(args, "oodle_dll", None)
    if dll is not None and not oodle.use_dll(dll):
        raise SystemExit(f"--oodle-dll: {dll} does not exist")
    # Guard: the output folder also receives the reports and (with weapon names) a msg folder, so an output
    # in the input's folder would litter or overwrite a mod folder, and an output named like the input would
    # replace it.
    if not v["simulate"] and Path(v["input"]).resolve().parent == Path(v["output"]).resolve().parent:
        msg = (f"the output {v['output']} is in the same folder as the input {v['input']}. The output folder also "
               "gets mapping.txt & co. and the msg folder of the weapon names, which would land in the input's "
               "(mod) folder, and an output named regulation.bin would replace the input. Create a new folder "
               "for the output; that also keeps the mods easy to manage.")
        if v["dry_run"]:
            print("# warning: " + msg)
        else:
            raise SystemExit(msg)
    codec = erreg.CODEC_ZSTD if (v["dry_run"] or v["simulate"]) else choose_codec(v["compression"], v["compression_level"])
    oodle_level = oodle.LEVELS.get(v["compression_level"], oodle.LEVEL_FAST)
    if v["repack"]:
        if v["dry_run"]:
            print("# --repack with --dry-run: nothing to do")
            return 0
        reg = erreg.Regulation(v["input"])
        out = Path(v["output"])
        out.parent.mkdir(parents=True, exist_ok=True)
        size = reg.save(out, max_size=v["max_size"] or erreg.REGULATION_MAX_SIZE,
                        window_log=v["zstd_window"], codec=codec, level=oodle_level)
        print(f"# repacked {v['input']} -> {out} ({codec}, {size} bytes, "
              f"limit {v['max_size'] or erreg.REGULATION_MAX_SIZE}; content unchanged)")
        if v["backup_replace"]:
            import backup
            bdir = backup.backup_and_replace(Path(v["input"]), out, list(v["archives"] or ()))
            if bdir is not None:
                print(f"# backup and replace: original files copied to {bdir} before replacing them")
        return 0

    real_stdout = sys.stdout if quiet else None
    if quiet:
        sys.stdout = io.StringIO()      # the window shows only the loot sample, not every pass
    try:
        say(phases.READING)
        stat_groups = v["stat_groups"]
        spell_stats = bool(v["spell_stats"] or "spells" in stat_groups)
        stamina_rate = v["stamina_rate"] or (0.8, 1.2)

        seed = v["seed"] if v["seed"] is not None else random.randrange(1, 2**31)
        rng = random.Random(seed)

        pd = erreg.load_paramdef(HERE / "paramdef" / "EquipParamGoods.xml")
        names = erreg.load_names(HERE / "names" / "EquipParamGoods.txt")
        reg = erreg.Regulation(v["input"])
        Npc = reg.param("NpcParam", erreg.load_paramdef(HERE / "paramdef" / "NpcParam.xml"))
        boss = boss_scale.boss_ids(Npc, v.get("boss_min_runes") or 0)   # bosses, before any pass runs
        orig = {r.id: (Npc.get(r, "hp"), Npc.get(r, "getSoul")) for r in Npc.rows}
        P = reg.param("EquipParamGoods", pd)

        lines: list[str] = []
        if v["goods"]:
            pool = build_pool(P, names, v["include_flasks"], v["include_remembrances"])
            if len(pool) < 2:
                # stdout, not stderr: the GUI captures stdout, so in a quiet run (loot sim) this
                # message still reaches the log instead of vanishing into a console nobody sees
                print("pool too small: not enough items to randomize", file=sys.stdout)
                return 1
        else:
            pool = []

        dur_lines: list[str] = []
        if v["random_durations"]:                      # before the effect shuffle: the report names the vanilla owner of each effect
            say(phases.BUFF_DURATIONS)
            import durations
            dur_lines = durations.Durations(reg).randomize(rng, v["duration_mode"], v["duration_min"], v["duration_max"])
            print("\n".join(l for l in dur_lines if l.startswith("#")))

        if pool:
            say(phases.CONSUMABLE_EFFECTS)
            bundles = [{f: P.get(r, f) for f in EFFECT_FIELDS} for r in pool]
            if v["mode"] == "shuffle":
                src = derangement(len(pool), rng)
            else:
                src = [rng.randrange(len(pool)) for _ in pool]
            anim = anim_sources(P, pool, src, v["mode"], rng, v["split_anim"] == "any") if v["split_anim"] != "none" else src
            reusable = sum(1 for r in pool if not P.get(r, "isConsume"))

            lines = [f"# seed={seed} mode={v['mode']} pool={len(pool)} items ({reusable} reusable tools)"
                     + (f" anim split ({v['split_anim']} category)" if v["split_anim"] != "none" else ""),
                     "# item  <-  effect taken from" + ("  |  animation taken from" if v["split_anim"] != "none" else "")]
            for i, r in enumerate(pool):
                s, a = pool[src[i]], pool[anim[i]]
                lines.append(f"{r.id:>8}  {names[r.id]:<40} <-  {names[s.id]} ({s.id})"
                             + (f"  |  {names[a.id]} ({a.id})" if v["split_anim"] != "none" else ""))
                for f in EFFECT_FIELDS:
                    P.set(r, f, bundles[src[i]][f])
                for f in ANIM_FIELDS:
                    P.set(r, f, bundles[anim[i]][f])
        qlines: list[str] = []
        if v["goods_quantity"]:
            say(phases.STACK_SIZES)
            qlines = goods.randomize(reg, names, rng)
            print("\n".join(l for l in qlines if l.startswith("#")))
        if v["random_prices"]:
            say(phases.PRICES)
            lines += [""] + randomize_prices(reg, rng, v["price_mode"], v["price_min"], v["price_max"],
                                             v["sell_prices"], v["sell_min"], v["sell_max"])
            if v["sell_equipment"]:
                lines += randomize_equipment_sell(reg, rng, v["price_mode"], v["sell_min"], v["sell_max"])
        if dur_lines:
            lines += [""] + dur_lines
        report = "\n".join(lines)
        print(report)

        rlines: list[str] = []
        if v["random_runes"]:
            say(phases.ENEMY_RUNES)
            rlines = [f"# seed={seed}"] + runes.randomize(reg, rng, v["rune_mode"], v["rune_min"], v["rune_max"])
            print("\n".join(l for l in rlines if l.startswith("#")))

        hlines: list[str] = []
        if v["random_enemy_hp"]:
            say(phases.ENEMY_HP)
            hlines = [f"# seed={seed}"] + enemy_drops.randomize_hp(reg, rng, v["hp_mode"], v["hp_min"], v["hp_max"])
            print("\n".join(l for l in hlines if l.startswith("#")))

        elines: list[str] = []         # enemy drops: before the weapons pass, so --random-default-ash rerolls the dropped weapons too
        if v["random_enemy_drops"]:
            say(phases.ENEMY_DROPS)
            elines.append(f"# seed={seed}")
            elines += enemy_drops.EnemyDrops(reg).randomize(
                rng, v["enemy_drop_rolls"], v["enemy_drop_chance"], _kinds(v["enemy_drop_kinds"]),
                v["unique_drops"], v["material_drops"], v["unique_rate"] / 100)
            print("\n".join(l for l in elines if l.startswith("#")))

        if v["random_shop_stock"]:
            say(phases.SHOP_STOCK)
            shop_lines = shops.randomize(reg, rng, _kinds(v["shop_stock_kinds"]))
            print("\n".join(l for l in shop_lines if l.startswith("#")))
        else:
            shop_lines = []

        wlines: list[str] = []
        # The level ceilings are read from the pristine weapon table, so this is built before the weapon pass
        # adds the somber affinity rows.
        loot_levels = loot.Loot(reg, v.get("boss_min_runes") or 0) if v["random_loot_levels"] else None
        if (v["somber_infusable"] or v["random_movesets"] or v["random_default_ash"] or v["random_stats"]
                or v["random_weapon_onhit_shuffle"] or v["random_weapon_holder_shuffle"]
                or v["random_weapon_status_roll"] or v["random_loot_effects"]):
            say(phases.WEAPONS)
            wp = weapons.Weapons(reg)
            wlines.append(f"# seed={seed}")
            if v["somber_infusable"]:
                wlines += [""] + wp.somber_infusable()
            if v["random_movesets"]:
                wlines += [""] + wp.random_movesets(rng, v["moveset_mode"], v["moveset_variety"],
                                                     v["keep_standard"], v["weptype"],
                                                     v["shield"], v["bow"])
            if v["random_default_ash"]:
                wlines += [""] + wp.random_default_ash(rng)
            if v["random_stats"]:
                wlines += [""] + wp.random_stats(rng, stat_groups, stamina_rate, v["req_mode"])
            if v["random_weapon_onhit_shuffle"]:
                wlines += [""] + wp.random_effects(rng, weapons.ONHIT_FIELDS)
            if v["random_weapon_holder_shuffle"]:
                wlines += [""] + wp.random_effects(rng, weapons.HOLDER_FIELDS)
            if v["random_weapon_status_roll"]:
                wlines += [""] + wp.random_status_effects(rng)
            if v["random_loot_effects"]:
                # after the shuffles: loot weapons keep the random draws where a shuffle also ran
                wlines += [""] + wp.random_loot_effects(rng)
            print("\n".join(l for l in wlines if l.startswith("#")))

        glines: list[str] = []
        if v["random_gem_skills"] or v["random_gem_effects"]:
            say(phases.ASHES_OF_WAR)
            glines.append(f"# seed={seed}")
            ashes = gems.Ashes(reg)
            if v["random_gem_skills"]:
                glines += [""] + ashes.randomize_skills(rng)
            if v["random_gem_effects"]:
                glines += [""] + ashes.randomize_effects(rng)
            print("\n".join(l for l in glines if l.startswith("#")))

        alines: list[str] = []
        if v["random_armor"] or v["random_armor_fresh"] or v["random_talismans"]:
            say(phases.ARMOUR_TALISMANS)
            alines.append(f"# seed={seed}")
            armour = gear.Armour(reg)
            if v["random_armor"]:
                alines += [""] + armour.randomize(rng)
            if v["random_armor_fresh"]:
                alines += [""] + armour.randomize_fresh(rng, v["armour_keep_sets"])
            if v["random_talismans"]:
                alines += [""] + gear.Talismans(reg).randomize(rng)
            print("\n".join(l for l in alines if l.startswith("#")))

        dlines: list[str] = []
        shuffle_kinds = (("goods", "random_goods_drops"), ("weapon", "random_weapon_drops"),
                         ("armor", "random_armor_drops"), ("talisman", "random_talisman_drops"),
                         ("ashes", "random_ashes_drops"))
        if any(v[key] for _kind, key in shuffle_kinds):
            say(phases.LOOT_SHUFFLE)
            dlines.append(f"# seed={seed}")
            for kind, key in shuffle_kinds:
                if not v[key]:
                    continue
                dlines += [""] + dropshuffle.shuffle(reg, rng, kind, v["armour_drop_sets"])
            print("\n".join(l for l in dlines if l.startswith("#")))

        llines: list[str] = []
        if loot_levels is not None:
            say(phases.LOOT_LEVELS)
            llines = [f"# seed={seed}"] + loot_levels.randomize(rng, v["loot_rarity"], v["loot_boss_bonus"],
                                                              v.get("loot_max_level"), v.get("zone_loot_levels", False))
            print("\n".join(l for l in llines if l.startswith("#")))

        wnames = None
        if v["somber_infusable"] and not v["no_weapon_names"]:
            say(phases.WEAPON_NAMES)
            given = list(v["weapon_names"] or ())
            archives = (textarchives.expand_archives("--weapon-names", given, weapon_names.ARCHIVE)
                        or [str(p) for p in weapon_names.shipped_archives()])
            if not archives:
                raise SystemExit(f"--weapon-names: the shipped item text archives are missing: "
                                 f"{textarchives.MSG_DIR}/<language>/{weapon_names.ARCHIVE}. "
                                 + ("Put the msg folder from the Release zip next to the executable, "
                                    if getattr(sys, "frozen", False) else "Restore tools/msg/ from the repository, ")
                                 + "or pass the path(s) of the game's msg/<language>/item_dlc02.msgbnd.dcx (or --no-weapon-names).")
            if not given:
                for line in shipped_warning("--weapon-names", [Path(a) for a in archives]):
                    print(line)
                    wlines.append(line)
            wnames = weapon_names.WeaponNames(reg, archives)
            for src in wnames.archives:
                archive_guard("--weapon-names", src, Path(v["output"]), v["dry_run"])
            for line in wnames.prepare():
                print(line)
                wlines.append(line)

        slines: list[str] = []
        if v["spells"] or spell_stats:
            say(phases.SPELLS)
            sp = spells.Spells(reg)
            slines.append(f"# seed={seed} mode={v['mode']} spells={len(sp.pool)} (sorceries + incantations in one pool)"
                          + (f" anim split ({v['split_anim']} signature)" if v["split_anim"] != "none" else ""))
            if v["spells"]:
                slines += sp.randomize_effects(rng, v["mode"], v["split_anim"] if v["split_anim"] != "none" else None)
            if spell_stats:
                slines += [""] + sp.random_stats(rng)
            print("\n".join(l for l in slines if l.startswith("#")))

        if v["random_flask_locations"]:
            say(phases.FLASK_LOCATIONS)
            flines = flasks.Flasks(reg).randomize(rng, v["flask_where"])
            print("\n".join(flines))
            report += "\n\n" + "\n".join(flines)

        starting = [k for k, on in (("bell", v["start_bell"]), ("lantern", v["start_lantern"])) if on]
        tlines: list[str] = []
        if starting:
            say(phases.STARTING_ITEMS)
            tlines = start_items.give(reg, starting)
            print("\n".join(tlines))
            report += "\n\n" + "\n".join(tlines)

        blines = boss_scale.apply(reg, rng, boss, orig, v.get("boss_hp_scale"), v.get("boss_rune_scale"),
                                  v.get("couple_runes_to_hp"))
        if blines:
            print("\n".join(blines))
            report += "\n\n" + "\n".join(blines)

        if v["random_enemy_hp"] or v["random_runes"]:      # a quick read on how the seed turned out
            env = balance.envelope(reg)
            print("\n".join(env))
            report += "\n\n" + "\n".join(env)

    finally:
        if quiet:
            sys.stdout = real_stdout
    if v["dry_run"] or v["simulate"]:
        if v["simulate"]:
            say(phases.LOOT_SIMULATION)
            print("\n".join(enemy_drops.sample(reg, rng, v["simulate"], v["enemy_drop_rolls"],
                                                   v["enemy_drop_chance"] or 10)))
        say(phases.DONE)
        return 0
    out = Path(v["output"])
    out.parent.mkdir(parents=True, exist_ok=True)
    say(phases.COMPRESSING)
    size = reg.save(out, max_size=v["max_size"] or erreg.REGULATION_MAX_SIZE,
                    window_log=v["zstd_window"], codec=codec, level=oodle_level)
    print(f"# wrote {out} ({codec}, {size} bytes, limit {v['max_size'] or erreg.REGULATION_MAX_SIZE}; "
          f"{(v['max_size'] or erreg.REGULATION_MAX_SIZE) - size} bytes to spare)")
    # the patched text archives are content, not a report: they are always written
    if wnames is not None:
        for src, texts, anchor in wnames.patches:
            dst = out.parent / "msg" / src.parent.name / src.name
            dst.parent.mkdir(parents=True, exist_ok=True)
            data, written = textarchives.patch_fmgs(src, texts, anchor)
            dst.write_bytes(data)
            note = (f"# weapon names: {dst} <- {src}: "
                    + ", ".join(f"{n} entries in {name}" for name, n in written.items())
                    + "; put the msg folder next to regulation.bin in the mod folder")
            print(note)
            wlines.append(note)
    if v["no_reports"]:
        print("# --no-reports: the report files were not written")
    else:
        def dump(name: str, lines, full: bool = False) -> None:
            """One report file.  With --brief-reports only the summary lines are kept, which is what
               makes drops.txt and hp.txt small enough to read.  mapping.txt is always kept in full:
               it is the one report you actually read item by item."""
            trim = v["brief_reports"] and not full
            body = [l for l in lines if l.startswith("#")] if trim else list(lines)
            out.with_name(name).write_text("\n".join(body) + "\n", encoding="utf-8")

        dump("mapping.txt", report.splitlines(), full=True)
        if wlines:
            dump("weapons.txt", wlines)
        if slines:
            dump("spells.txt", slines)
        if elines:
            dump("drops.txt", elines)
        if glines:
            dump("ashes.txt", glines)
        if alines:
            dump("gear.txt", alines)
        if llines:
            dump("loot.txt", llines)
        if hlines:
            dump("hp.txt", hlines)
        if tlines:
            dump("start.txt", tlines)
        if qlines:
            dump("goods.txt", qlines)
        if shop_lines:
            dump("shops.txt", shop_lines)
        if dlines:
            dump("loot-shuffle.txt", dlines)
        if rlines:
            dump("runes.txt", rlines)
    print(f"\nwritten: {out}  (seed={seed}"
          + ("" if v["no_reports"] else
             f", mapping: {out.with_name('mapping.txt')}"
             + (f", weapons: {out.with_name('weapons.txt')}" if wlines else "")
             + (f", gear: {out.with_name('gear.txt')}" if alines else "")
             + (f", ashes: {out.with_name('ashes.txt')}" if glines else "")
             + (f", stack sizes: {out.with_name('goods.txt')}" if qlines else "")
              + (f", shops: {out.with_name('shops.txt')}" if shop_lines else "")
              + (f", loot shuffle: {out.with_name('loot-shuffle.txt')}" if dlines else "")
             + (f", loot levels: {out.with_name('loot.txt')}" if llines else "")
             + (f", spells: {out.with_name('spells.txt')}" if slines else "")
             + (f", enemy drops: {out.with_name('drops.txt')}" if elines else "")
             + (f", enemy hp: {out.with_name('hp.txt')}" if hlines else "")
             + (f", runes: {out.with_name('runes.txt')}" if rlines else "")) + ")")
    if v["backup_replace"] and not v["dry_run"]:
        import backup
        bdir = backup.backup_and_replace(Path(v["input"]), out, list(v["archives"] or ()))
        if bdir is not None:
            print(f"# backup and replace: original files copied to {bdir} before replacing them")
        else:
            print("# backup and replace: input file not found, nothing was backed up")
    say(phases.DONE)
    return 0


if __name__ == "__main__":
    sys.exit(main())
