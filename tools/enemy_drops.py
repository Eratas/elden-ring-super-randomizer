"""--random-enemy-drops: every enemy drops something, and what it drops is random.

ItemLotParam_enemy holds the enemy drop tables.  An enemy (NpcParam.itemLotId_enemy) points at one row and the
game rolls that row and every row after it with a consecutive id (300000000-300000005: the Castle Exile's
crossbow, hood, armor, gauntlets, greaves and feather are six independent rolls).  A row is up to eight weighted
slots; in vanilla nearly every row is "nothing" (lotItemId 0, weight 950-990) against one item (weight 10-50).
The Item and Enemy Randomizer swaps the two slots around and clears most one-time flags, but keeps the shape.

For every lot an NpcParam row points at (1361 in vanilla 1.17.1; rows nothing points at are cut content and
stay as they are):
  - the lot is given exactly `rolls` rows, each holding one random item at `chance` percent and otherwise
    "nothing", so every kill rolls that many independent dice and can give 0 to `rolls` items.  Rows are
    filled, emptied or appended as needed; `rolls` of 0 (or an empty field) means one guaranteed item per
    kill instead, which is the same as one roll at 100 percent;
  - a row with a getItemFlagId is a one-time drop (the Alabaster Lord's sword, the Banished Knight's Dragon
    Communion Seal, the Silver Tear Orbs' Larval Tears; the item randomizer's own placements) and is left
    alone, item and chance, as is a row holding a key item (belt and braces: the item randomizer may put a key
    item into an enemy drop).  Such a row is not one of the lot's dice, so the lot keeps its full number of
    rolls around it.

The pool is every item the input hands out somewhere: the pickups, rewards and gifts of names/item_locations.txt,
the shops listed there and the enemy drops themselves -- weapons (upgrade level dropped), armor, talismans, Ashes
of War and goods, except key items, Great Runes, info items (letters), the Flask of Wondrous Physick and the
Flasks of Crimson / Cerulean Tears.  Each distinct item is in the pool once, so a weapon is as likely as a Rowa
Fruit; the quantity is one the game gives that item somewhere (a stack of 5 arrows, 1 sword).  --mode has no
effect here.  Items of the Land of Shadow are in the pool whenever the input hands them out.
"""
from __future__ import annotations

import random
import re
from pathlib import Path

import erreg
from flasks import (
    CATEGORY_NAMES,
    CATEGORY_OF_SHOP_TYPE,
    CATEGORY_WORD,
    SHOP_TYPE_OF_CATEGORY,
    load_locations,
)

HERE = Path(__file__).resolve().parent
SLOTS = 8
BRACKET = re.compile(r"^\[(.+?)\]")                 # "[Crab] Crab Eggs" -> the enemy's name
UNIQUE_CHANCE = 0.03                 # a drop is a unique weapon instead of the common draw
MATERIAL_CHANCE = 0.08               # ... or an upgrade stone, with a small stack
CATEGORY_GOODS, CATEGORY_WEAPON = 1, 2
POOL_CATEGORIES = (1, 2, 3, 4, 5)                     # goods, weapon, armor, talisman, ash of war
# A drop should look like loot, not like a uniform draw over every row in the game: consumables stay
# common, equipment is the reason to kill something, ashes are the rare find.
CATEGORY_WEIGHT = {1: 40, 2: 25, 3: 20, 4: 10, 5: 5}
DEFAULT_ROLLS = 3
DEFAULT_CHANCE = 25
# EquipParamGoods.goodsType values that never drop: 1 key item, 9 Flask of Wondrous Physick, 12 info item
# (letters, notes), 13 (unused), 15 Great Rune.  Flasks of Crimson / Cerulean Tears are goodsType 0 with a suppleType.
KEEP_GOODS_TYPES = {1, 9, 12, 13, 15}
CERTAIN = 1000                                        # weight of the only slot of a guaranteed drop
SLOT_FIELDS = ("lotItemId", "lotItemCategory", "lotItemBasePoint", "lotItemNum", "enableLuck",
               "cumulateLotPoint", "getItemFlagId", "cumulateReset")


class EnemyDrops:
    def __init__(self, reg: erreg.Regulation) -> None:
        self.reg = reg
        pd = erreg.load_paramdef(HERE / "paramdef" / "ItemLotParam.xml")
        self.L = reg.param("ItemLotParam_enemy", pd)
        self.M = reg.param("ItemLotParam_map", pd)
        self.S = reg.param("ShopLineupParam", erreg.load_paramdef(HERE / "paramdef" / "ShopLineupParam.xml"))
        self.N = reg.param("NpcParam", erreg.load_paramdef(HERE / "paramdef" / "NpcParam.xml"))
        self.G = reg.param("EquipParamGoods", erreg.load_paramdef(HERE / "paramdef" / "EquipParamGoods.xml"))
        self.W = reg.param("EquipParamWeapon", erreg.load_paramdef(HERE / "paramdef" / "EquipParamWeapon.xml"))
        self.lot_names = erreg.load_names(HERE / "names" / "ItemLotParam_enemy.txt")
        self._names: dict[int, dict[int, str]] = {}

    # ------------------------------------------------------------ names
    def names(self, cat: int) -> dict[int, str]:
        if cat not in self._names:
            p = HERE / "names" / f"{CATEGORY_NAMES.get(cat, '')}.txt"
            self._names[cat] = erreg.load_names(p) if cat in CATEGORY_NAMES and p.is_file() else {}
        return self._names[cat]

    def item_name(self, iid: int, cat: int, num: int = 1) -> str:
        names = self.names(cat)
        if cat == CATEGORY_WEAPON:                     # weapon id = base + affinity * 100 + upgrade level
            base, level = iid - iid % 10000, iid % 100
            nm = names.get(base, f"weapon {base}") + (f" +{level}" if level else "")
        else:
            nm = names.get(iid, f"{CATEGORY_WORD.get(cat, f'category {cat}')} {iid}")
        return f"{nm} x{num}"

    # ------------------------------------------------------------ the lots
    def lots(self) -> list[int]:
        """The first rows of the enemy drop lots: every ItemLotParam_enemy row an NpcParam row points at."""
        L = self.L
        refs = {self.N.get(r, "itemLotId_enemy") for r in self.N.rows}
        return sorted(k for k in refs if k > 0 and k in L.by_id)

    def run(self, first: int) -> list:
        """The rows the game rolls for a lot: the first row and every row after it with a consecutive id."""
        rows, rid = [], first
        while rid in self.L.by_id:
            rows.append(self.L.by_id[rid])
            rid += 1
        return rows

    def slots(self, r) -> list[tuple[int, int, int, int]]:
        """(item id, category, weight, quantity) of every slot of a row."""
        L = self.L
        return [(L.get(r, f"lotItemId0{i}"), L.get(r, f"lotItemCategory0{i}"), L.get(r, f"lotItemBasePoint0{i}"),
                 L.get(r, f"lotItemNum0{i}")) for i in range(1, SLOTS + 1)]

    def is_key(self, iid: int, cat: int) -> bool:
        if cat != CATEGORY_GOODS:
            return False
        g = self.G.by_id.get(iid)
        return g is None or self.G.get(g, "goodsType") in KEEP_GOODS_TYPES or self.G.get(g, "suppleType") != 0

    def protected(self, r) -> str:
        """Why a row is left alone: a one-time drop (flag) or a key item in a weighted slot; '' otherwise."""
        if self.L.get(r, "getItemFlagId"):
            return "one-time drop"
        if any(w > 0 and iid > 0 and self.is_key(iid, cat) for iid, cat, w, _ in self.slots(r)):
            return "key item"
        return ""

    def describe(self, r) -> str:
        """'Crab Eggs x1 3% / Strip of White Flesh x1 3%', 'nothing' for an empty row."""
        slots = self.slots(r)
        total = sum(w for _, _, w, _ in slots)
        parts = [f"{self.item_name(iid, cat, num)} {100 * w / total:g}%" for iid, cat, w, num in slots if w > 0 and iid > 0]
        return " / ".join(parts) if parts else "nothing"

    # ------------------------------------------------------------ the pool
    def build_pool(self, lot_rows: list, kinds: set[int] | None = None) -> list[tuple[int, int, tuple[int, ...]]]:
        """(category, item id, quantities seen) of every item handed out by the real pickups / rewards / gifts and
           shops of names/item_locations.txt and by the enemy drop rows given; one entry per item, in table order.
           `kinds` restricts the categories (empty or None = all of them)."""
        seen: dict[tuple[int, int], set[int]] = {}
        allowed = set(kinds) if kinds else set(POOL_CATEGORIES)

        def add(cat: int, iid: int, num: int) -> None:
            if iid <= 0 or cat not in allowed or cat not in POOL_CATEGORIES or self.is_key(iid, cat):
                return
            if cat == CATEGORY_WEAPON:
                iid -= iid % 100                       # the drop is +0; the affinity (if any) stays
            seen.setdefault((cat, iid), set()).add(max(1, min(num, 255)))

        locations = load_locations()
        for P, rows in ((self.M, [self.M.by_id[k] for k in locations.get("ItemLotParam_map", {}) if k in self.M.by_id]),
                        (self.L, lot_rows)):
            for r in rows:
                for i in range(1, SLOTS + 1):
                    if P.get(r, f"lotItemBasePoint0{i}") > 0:
                        add(P.get(r, f"lotItemCategory0{i}"), P.get(r, f"lotItemId0{i}"), P.get(r, f"lotItemNum0{i}"))
        for k in locations.get("ShopLineupParam", {}):
            r = self.S.by_id.get(k)
            if r is not None and self.S.get(r, "equipType") in CATEGORY_OF_SHOP_TYPE:
                add(CATEGORY_OF_SHOP_TYPE[self.S.get(r, "equipType")], self.S.get(r, "equipId"), 1)
        return [(cat, iid, tuple(sorted(nums))) for (cat, iid), nums in seen.items()]

    def world_weapons(self) -> list[int]:
        """(one entry per row of EquipParamWeapon) the weapon rows the world can drop.
        Rows of one appearance are different instances - different stats - so the reroll hands
        out distinct rows per slot and the same appearance can be found twice with different
        stats."""
        return [r.id for r in self.W.rows]

    # ------------------------------------------------------------ rare drop pools
    def _named_bases(self, param: str, names_file: str, one_row_only: bool = False,
                     material_set: int | None = None) -> list[int]:
        """Named base rows of a param, optionally only the ones with a single row and a given material set."""
        P = self.reg.param(param, erreg.load_paramdef(HERE / "paramdef" / f"{param}.xml"))
        names = erreg.load_names(HERE / "names" / names_file)
        counts: dict[int, int] = {}
        for r in P.rows:
            counts[r.id - r.id % 10000] = counts.get(r.id - r.id % 10000, 0) + 1
        out = []
        for r in P.rows:
            if r.id % 10000 or r.id not in names:
                continue
            if one_row_only and counts.get(r.id, 0) != 1:
                continue
            if material_set is not None and P.get(r, "materialSetId") != material_set:
                continue
            out.append(r.id)
        return out

    def build_rare_pools(self) -> None:
        """Unique weapons (one row, no smithing material set) and upgrade stones, for the rare-drop options."""
        self.uniques = self._named_bases("EquipParamWeapon", "EquipParamWeapon.txt", True, -1)
        G = self.reg.param("EquipParamGoods",
                           erreg.load_paramdef(HERE / "paramdef" / "EquipParamGoods.xml"))
        gnames = erreg.load_names(HERE / "names" / "EquipParamGoods.txt")
        self.materials = [r.id for r in G.rows
                          if "Smithing Stone" in gnames.get(r.id, "") and G.get(r, "goodsType") == 0]

    # ------------------------------------------------------------ the change
    def room_after(self, run: list) -> int:
        """How many rows can be appended to a lot: the free ids after its last row, less one that must stay free so
           the lot does not run on into the next one (the game rolls every row with a consecutive id)."""
        n, rid = 0, run[-1].id + 1
        while rid not in self.L.by_id and n < 64:
            n, rid = n + 1, rid + 1
        return max(0, n - 1)

    def randomize(self, rng: random.Random, rolls: int | None = DEFAULT_ROLLS, chance: int = DEFAULT_CHANCE,
                  kinds: set[int] | None = None, unique_drops: bool = False,
                  material_drops: bool = False, unique_rate: float = UNIQUE_CHANCE) -> list[str]:
        """Every lot gets exactly `rolls` dice, each one a random item at `chance` percent and nothing otherwise, so a
           kill drops 0 to `rolls` items.  `rolls` of 0 or None gives one guaranteed item per kill instead, which is
           one die at 100 percent.  Nothing is ever forced to drop unless that guaranteed mode is chosen.  `kinds`
           restricts the item categories."""
        L = self.L
        rolls = max(0, int(rolls or 0))
        chance = max(1, min(100, int(chance)))
        guaranteed = rolls == 0
        count = 1 if guaranteed else rolls
        rolls = count                       # one path below: every lot is filled to exactly `count` dice
        lots = self.lots()
        rows: dict[int, object] = {}
        for k in lots:
            for r in self.run(k):
                rows.setdefault(r.id, r)
        pool = self.build_pool(list(rows.values()), kinds)
        if unique_drops or material_drops:
            self.build_rare_pools()
        by_cat = {c: sum(1 for cat, _, _ in pool if cat == c) for c in POOL_CATEGORIES}
        cat_items = {c: [entry for entry in pool if entry[0] == c] for c in POOL_CATEGORIES}
        cats = [c for c in POOL_CATEGORIES if cat_items[c]]
        cat_weights = [CATEGORY_WEIGHT[c] for c in cats]
        mode = (f"every lot rolls {count} die/dice at {chance}% each: 0 to {count} items per kill, "
                f"{count * chance / 100:g} on average" if not guaranteed else
                "every lot drops one item for certain (rolls 0)")
        lines = [f"# enemy drops: lots={len(lots)} (ItemLotParam_enemy rows NpcParam.itemLotId_enemy points at, with the "
                 f"consecutive rows after them: {len(rows)} rows), pool={len(pool)} items ({by_cat[1]} goods, {by_cat[2]} weapons, "
                 f"{by_cat[3]} armor pieces, {by_cat[4]} talismans, {by_cat[5]} ashes of war: every item the input hands out "
                 f"somewhere, each once); {mode} (one-time drops and rows with a key item stay and do not count)",
                 "# lot row  [enemy] vanilla content (Paramdex name)  :  before  ->  after   (chance per item; 'kept' = left alone, "
                 "'+ row' = row appended to the lot)"]
        if len(pool) < 2:
            lines.append("# pool too small, nothing changed")
            return lines
        done: set[int] = set()
        n_empty: set[int] = set()        # rows that are no roll of their lot: emptied or left alone
        n = {"rows": 0, "kept": 0, "added": 0, "emptied": 0, "short": 0}
        old: dict[int, str] = {}

        def draw(used: set[tuple[int, int]] | None = None) -> tuple[int, int, int]:
            # rare overrides: a unique weapon or an upgrade stone now and then, instead of the common draw
            if material_drops and self.materials and rng.random() < MATERIAL_CHANCE:
                iid = rng.choice([i for i in self.materials if (1, i) not in (used or ())] or self.materials)
                if used is not None:
                    used.add((1, iid))
                return iid, 1, rng.choice((1, 2, 3, 4, 5))
            if unique_drops and self.uniques and rng.random() < unique_rate:
                iid = rng.choice([i for i in self.uniques if (2, i) not in (used or ())] or self.uniques)
                if used is not None:
                    used.add((2, iid))
                return iid, 2, 1
            for _ in range(25):
                cat = rng.choices(cats, cat_weights)[0]
                entries = cat_items[cat]
                fresh = [e for e in entries if (e[0], e[1]) not in (used or ())]
                entry = rng.choice(fresh or entries)
                key = (entry[0], entry[1])
                if used is None or key not in used or not fresh:
                    if used is not None:
                        used.add(key)
                    return entry[1], entry[0], rng.choice(entry[2])
            entry = rng.choice(pool)
            if used is not None:
                used.add((entry[0], entry[1]))
            return entry[1], entry[0], rng.choice(entry[2])

        def set_slot(r, i: int, iid: int, cat: int, weight: int, num: int) -> None:
            for f, v in (("lotItemId", iid), ("lotItemCategory", cat), ("lotItemBasePoint", weight), ("lotItemNum", num),
                         ("enableLuck", 0), ("cumulateLotPoint", 0), ("getItemFlagId", 0), ("cumulateReset", 0)):
                L.set(r, f"{f}{i:02d}", v)

        def clear(r) -> None:
            for i in range(1, SLOTS + 1):
                set_slot(r, i, 0, 0, 0, 0)

        def set_roll(r, used: set[tuple[int, int]], certain: bool = False) -> None:
            """One random item at `chance` percent (or for certain), nothing otherwise."""
            clear(r)
            iid, cat, num = draw(used)
            set_slot(r, 1, iid, cat, CERTAIN if certain else chance * 10, num)
            if not certain and chance < 100:
                set_slot(r, 2, 0, 0, CERTAIN - chance * 10, 0)

        def empty(r) -> None:
            clear(r)
            set_slot(r, 1, 0, 0, CERTAIN, 0)

        def append_row(run: list) -> erreg.ParamRow | None:
            """A new row after the lot's last one (None when the next id is taken or the lot would run on into the
               next lot), copied from the last row and emptied."""
            if self.room_after(run) < 1:
                return None
            row = L.add_row(run[-1].id + 1, run[-1])
            clear(row)
            L.set(row, "getItemFlagId", 0)
            L.set(row, "cumulateNumFlagId", 0)
            L.set(row, "cumulateNumMax", 0)
            run.append(row)
            return row

        def name(r) -> str:
            return self.lot_names.get(r.id) or "?"

        for k in lots:
            run = self.run(k)
            used: set[tuple[int, int]] = set()
            for r in run:
                if r.id not in old:
                    old[r.id] = self.describe(r)
            active = [r for r in run if r.id in done and r.id not in n_empty]
            need = count - len(active)
            for r in run:
                if r.id in done:
                    continue
                why = self.protected(r)
                if why:
                    done.add(r.id)
                    n_empty.add(r.id)              # not a die of this lot: a one-time drop or a key item
                    n["kept"] += 1
                    lines.append(f"{r.id:>10}  {name(r)}  :  {old[r.id]}  kept ({why})")
                    continue
                done.add(r.id)
                if need > 0:
                    set_roll(r, used, certain=guaranteed)
                    n["rows"] += 1
                    need -= 1
                    lines.append(f"{r.id:>10}  {name(r)}  :  {old[r.id]}  ->  {self.describe(r)}")
                else:
                    empty(r)
                    n_empty.add(r.id)
                    n["emptied"] += 1
                    lines.append(f"{r.id:>10}  {name(r)}  :  {old[r.id]}  ->  nothing (beyond the {count} rolls)")
            while need > 0:
                row = append_row(run)
                if row is None:
                    n["short"] += 1
                    lines.append(f"{'':>10}  lot {k}: only {count - need} of {count} rolls, no free id before the next lot")
                    break
                set_roll(row, used, certain=guaranteed)
                done.add(row.id)
                n["added"] += 1
                need -= 1
                lines.append(f"{row.id:>10}  + row for lot {k}  :  nothing  ->  {self.describe(row)}")
        summary = (f"# rows set to a roll={n['rows']}, rows emptied={n['emptied']}, rows appended={n['added']}, rows left alone={n['kept']}"
                   + (f", lots short of rolls (no free id)={n['short']}" if n["short"] else ""))
        lines.insert(2, summary)
        return lines

    def randomize_dropped_weapons(self, rng: random.Random, kinds: set[int] | None = None,
                                  shops: bool = False) -> list[str]:
        """Every weapon slot in the enemy drop lots and the map lots (chest pickups, boss rewards,
        gifts) holds a random weapon from the pool.

        The game awards the enemy lots when an enemy dies and the map lots at area events; this
        rewrites the weapon id of every weapon slot to a fresh draw from the pool - the weapons the
        input hands out somewhere.  Slots take distinct world weapon rows where the world has
        them: two rows of one appearance are two instances (different stats), so the same
        appearance can be found in two loot spots with different stats; where the world has no
        other row, the repeat is forced.  It changes what you find when you pick up a drop, not
        where loot drops and not what a weapon is; rows with a one-time flag stay as they are.
        `shops` additionally rerolls the weapon slots of the weapon shops (ShopLineupParam): the
        per-run reroll of what merchants sell (--random-dropped-shop-weapons)."""
        L = self.L
        rows: dict[int, object] = {}
        for k in self.lots():
            for r in self.run(k):
                rows.setdefault(r.id, r)
        for k in load_locations().get("ItemLotParam_map", {}):
            r = self.M.by_id.get(k)
            if r is not None:
                rows.setdefault(r.id, r)
        pool = [e[1] for e in self.build_pool(list(rows.values()), kinds) if e[0] == CATEGORY_WEAPON]
        slots = [(r, i) for r in rows.values() if not self.protected(r)
                 for i in range(1, SLOTS + 1)
                 if L.get(r, f"lotItemCategory0{i}") == CATEGORY_WEAPON
                 and L.get(r, f"lotItemId0{i}") > 0
                 and L.get(r, f"lotItemBasePoint0{i}") > 0]
        world = self.world_weapons()
        if len(pool) < 2 or not slots or not world:
            return [f"# randomize dropped weapons: {len(pool)} pool weapons, {len(slots)} weapon slots, nothing changed"]
        lines = [f"# randomize dropped weapons: rerolled {len(slots)} slot(s) over the {len(pool)}-weapon pool",
                 "# lot row  [enemy or map lot]  old weapon -> new weapon"]
        used = {L.get(r, f"lotItemId0{i}") for r, i in slots}
        for r, i in slots:
            lname = self.lot_names.get(r.id) or "?"
            old = L.get(r, f"lotItemId0{i}")
            fresh = [w for w in world if w not in used]
            new = rng.choice(fresh) if fresh else rng.choice(world)
            used.add(new)
            L.set(r, f"lotItemId0{i}", new)
            lines.append(f"{r.id:>10}  {lname:<40}  {self.item_name(old, CATEGORY_WEAPON)} -> "
                         f"{self.item_name(new, CATEGORY_WEAPON)}")
        if shops and pool:
            lines.extend(self._reroll_shop_weapons(rng, world))
        return lines

    def _reroll_shop_weapons(self, rng: random.Random, world: list[int]) -> list[str]:
        """Shop slots of weapons (ShopLineupParam): per-run reroll of what merchants sell, one
        distinct world weapon row per slot (the same distinctness rule as the lot reroll)."""
        names = erreg.load_names(HERE / "names" / "ShopLineupParam.txt")
        lines = []
        used = set()
        for r in self.S.rows:
            if self.S.get(r, "equipType") != SHOP_TYPE_OF_CATEGORY[CATEGORY_WEAPON] \
                    or self.S.get(r, "equipId") <= 0:
                continue
            old = self.S.get(r, "equipId")
            used.add(old)
            fresh = [w for w in world if w not in used]
            new = rng.choice(fresh) if fresh else rng.choice(world)
            used.add(new)
            self.S.set(r, "equipId", new)
            lines.append(f"{r.id:>10}  {names.get(r.id, '?'):<40}  "
                         f"{self.item_name(old, CATEGORY_WEAPON)} -> {self.item_name(new, CATEGORY_WEAPON)}")
        return lines


def randomize_hp(reg: erreg.Regulation, rng: random.Random, mode: str, lo: int | None,
                 hi: int | None) -> list[str]:
    """--random-enemy-hp: the hit points of every enemy that has any (NpcParam.hp).

    shuffle permutes the values that exist over the enemies, so the world total is unchanged (a boss can
    end up with a rat's hit points); range draws a new value for every enemy between lo and hi
    (default: the lowest / highest that exist), spread evenly over orders of magnitude and rounded to
    two significant digits, the same draw the rune and price passes use; bands picks a band per enemy
    with the weights of the runtime mod (50% 0.5-1.5x, 35% 1.5-2.5x, 15% 2.5-4x of the vanilla
    value), so most enemies stay near their old toughness and a few become sponges; balanced keeps
    every enemy within 0.75-1.5x of its vanilla value, so there are no bullet sponges and no pushovers."""
    from randomize import new_prices, round_price
    N = reg.param("NpcParam", erreg.load_paramdef(HERE / "paramdef" / "NpcParam.xml"))
    enemy = erreg.load_names(HERE / "names" / "ItemLotParam_enemy.txt")
    boss = erreg.load_names(HERE / "names" / "ItemLotParam_map.txt")
    rows = [r for r in N.rows if N.get(r, "hp") > 0]
    old = [N.get(r, "hp") for r in rows]
    if len(rows) < 2:
        return ["# enemy hp: fewer than two enemies with hit points, nothing changed"]
    if mode == "bands":
        bands = ((0.5, 1.5, 50), (1.5, 2.5, 35), (2.5, 4.0, 15))
        new = []
        for value in old:
            low, high = rng.choices([(b[0], b[1]) for b in bands], [b[2] for b in bands])[0]
            new.append(max(1, round_price(value * rng.uniform(low, high))))
    elif mode == "balanced":
        # a fair band: every enemy stays near its vanilla toughness, so no bullet sponges and no pushovers
        new = [max(1, round_price(value * rng.uniform(0.75, 1.5))) for value in old]
    else:
        new = new_prices(old, rng, mode, lo, hi, "HP")
    lines = [f"# enemy hp: mode={mode} enemies={len(rows)} (NpcParam rows with hp > 0; vanilla {min(old)}-{max(old)})",
             "# npc row  [enemy of its drop table]  old -> new (hp)"]
    for r, o, n in zip(rows, old, new):
        N.set(r, "hp", n)
        nm = enemy.get(N.get(r, "itemLotId_enemy")) or boss.get(N.get(r, "itemLotId_map")) or ""
        m = BRACKET.match(nm)
        lines.append(f"{r.id:>9}  {(m.group(0) if m else nm):<44} {o:>7} -> {n}")
    return lines


def sample(reg: erreg.Regulation, rng: random.Random, count: int, rolls: int | None = None,
           chance: int = DEFAULT_CHANCE) -> list[str]:
    """The loot simulator: `count` random kills, each drop row rolled at its own chance.

    The roll mirrors what the game does with a lot - every row is independent and a row drops one of its
    slots, weighted by the chance printed in drops.txt - so a kill shows what it would really have given,
    "nothing" included.  It reads whatever the passes left in the tables, so it reports the drop settings
    of the run it is attached to."""
    ed = EnemyDrops(reg)
    lots = ed.lots()
    if not lots or count < 1:
        return ["# loot simulation: no enemy drop lots"]
    model = (f"the roll settings were {rolls} rolls at {chance}% each, so 0 to {rolls} items per kill"
             if rolls else "the roll settings were one guaranteed item per kill")
    lines = [f"# loot simulation: {count} random kills. {model}.",
             "# Each line is one kill, exactly as the game would roll it - nothing is forced to drop.",
             "# enemy  :  what dropped"]
    total = 0
    for n in range(1, count + 1):
        first = rng.choice(lots)
        got: list[str] = []
        for r in ed.run(first):
            slots = [s for s in ed.slots(r) if s[2] > 0 and s[0] > 0]
            total_slots = sum(s[2] for s in slots)
            if not total_slots:
                continue
            roll = rng.randrange(total_slots)
            upto = 0
            for iid, cat, w, num in slots:
                upto += w
                if roll < upto:
                    got.append(ed.item_name(iid, cat, num or 1))
                    break
        total += len(got)
        lot = ed.lot_names.get(first, "")
        enemy = lot[1:].split("]")[0] if lot.startswith("[") and "]" in lot else f"lot {first}"
        lines.append(f"{n:>3}. {enemy[:40]:<40}  {', '.join(got) if got else 'nothing'}")
    avg = total / count if count else 0
    lines += ["", f"# {count} kills -> {total} items ({avg:.1f} per kill)"]
    return lines
