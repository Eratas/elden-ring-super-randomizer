"""Move one category of loot between the places it can drop.

The stat passes change what an item *is*; this one changes where you *find* it.  The item id of a drop
slot is replaced by another item id of the same category, so names, stats and icons stay exactly as the
game shipped them and only the source moves: the chest piece from one dungeon can end up on a soldier on
the other side of the map.

Categories: goods, weapons, armor, talismans, ashes of war.  Every slot the game actually uses takes part:

  enemy drops   the lots an NpcParam row points at (plus their consecutive rows)
  map lots      the rows in names/item_locations.txt (chests, boss rewards, gifts, pickups)
  shops         every shop slot of the matching equip type

One-time flag drops are never moved, and rows that hold a key item are left alone.

With `keep_sets` (armor only) the pieces of an armour set are moved as a unit: set A's four pieces are
replaced by set B's four pieces, so looting one piece of a set tells you what the rest of that set is.
"""
from __future__ import annotations

import random
from pathlib import Path

import erreg
from enemy_drops import EnemyDrops
from flasks import CATEGORY_NAMES, CATEGORY_OF_SHOP_TYPE, load_locations

HERE = Path(__file__).resolve().parent

SLOTS = 8
CATEGORIES = {"goods": 1, "weapon": 2, "armor": 3, "talisman": 4, "ashes": 5}
SHOP_FOR = {cat: shop for shop, cat in CATEGORY_OF_SHOP_TYPE.items() if cat in CATEGORIES.values()}
WORD = {1: "good", 2: "weapon", 3: "armor", 4: "talisman", 5: "ash of war"}
SLOT_WORDS = ("Armor", "Armour", "Helm", "Helmet", "Hat", "Crown", "Circlet", "Mask", "Robe",
              "Garb", "Vest", "Gauntlets", "Gauntlet", "Gloves", "Greaves", "Greave", "Boots",
              "Shoes", "Trousers")


def _set_key(name: str) -> str | None:
    for word in SLOT_WORDS:
        if name.endswith(" " + word):
            return name[:-(len(word) + 1)]
    return None


def _item_name(names: dict[int, str], iid: int, cat: int) -> str:
    if cat == 2:                                   # weapon: base + affinity*100 + level
        base, level = iid - iid % 10000, iid % 100
        return f"{names.get(base, f'weapon {base}')}" + (f" +{level}" if level else "")
    return names.get(iid, f"{WORD.get(cat, 'item')} {iid}")


def set_plan(iids: list[int], names: dict[int, str], rng: random.Random) -> list[int]:
    """Which original item each slot receives when armour sets move as a unit (keep_sets).

    Pure by design: it reads only `iids` (the ORIGINAL item id of every slot) and `names`, never the
    live param rows, so the result depends on the inputs and the seed alone and can be tested directly
    (test_logic.test_dropshuffle_sets drives this function, not a copy of it).

    Slots whose item belongs to a named set of two or more pieces are dealt out set by set, and groups
    of equal size are permuted among themselves: set A's helm, chest, gauntlets and greaves all become
    set B's pieces, so looting one piece still tells you what the rest of that set is.  A set that maps
    to itself keeps its own pieces and is held out of the loose shuffle, which would otherwise split it.
    Every remaining slot shuffles among itself.

    Returns `plan`, where `plan[n]` is the original item id that slot `n` ends up holding.
    """
    groups: dict[str, list[int]] = {}
    for n, iid in enumerate(iids):
        key = _set_key(names.get(iid, ""))
        if key:
            groups.setdefault(key, []).append(n)
    sets = [v for v in groups.values() if len(v) > 1]
    by_size: dict[int, list[list[int]]] = {}
    for group in sets:
        by_size.setdefault(len(group), []).append(group)
    moved: set[int] = set()
    plan = list(iids)
    for size in sorted(by_size):
        bucket = by_size[size]
        donors = bucket[:]
        rng.shuffle(donors)
        for group, donor in zip(bucket, donors):
            if group is donor:
                moved.update(group)
                continue
            data = [iids[t] for t in donor]
            for n, iid in zip(group, data):
                plan[n] = iid
                moved.add(n)
    rest = [n for n in range(len(iids)) if n not in moved]
    ids = [iids[n] for n in rest]
    rng.shuffle(ids)
    for n, iid in zip(rest, ids):
        plan[n] = iid
    return plan


def shuffle(reg: erreg.Regulation, rng: random.Random, kind: str,
            keep_sets: bool = False) -> list[str]:
    if kind not in CATEGORIES:
        raise ValueError(f"unknown loot kind: {kind}")
    cat = CATEGORIES[kind]
    ed = EnemyDrops(reg)
    names = erreg.load_names(HERE / "names" / f"{CATEGORY_NAMES[cat]}.txt")
    lots = erreg.load_names(HERE / "names" / "ItemLotParam_enemy.txt")

    # every slot that can hold this category, as (param, row, index, item id)
    found: list[tuple[erreg.Param, object, int, int]] = []
    rows: dict[int, object] = {}
    for k in ed.lots():
        for r in ed.run(k):
            rows.setdefault(r.id, r)
    for r in rows.values():
        if ed.protected(r):                 # one-time flag drops and rows holding a key item are never moved
            continue
        for i in range(1, SLOTS + 1):
            iid = ed.L.get(r, f"lotItemId0{i}")
            if ed.L.get(r, f"lotItemCategory0{i}") == cat and iid > 0 and ed.L.get(r, f"lotItemBasePoint0{i}") > 0:
                found.append((ed.L, r, i, iid))
    here = load_locations()
    for k in here.get("ItemLotParam_map", {}):
        r = ed.M.by_id.get(k)
        if r is None:
            continue
        if ed.protected(r):                 # one-time / key-item map slots stay where they are
            continue
        for i in range(1, SLOTS + 1):
            iid = ed.M.get(r, f"lotItemId0{i}")
            if ed.M.get(r, f"lotItemCategory0{i}") == cat and iid > 0 and ed.M.get(r, f"lotItemBasePoint0{i}") > 0:
                found.append((ed.M, r, i, iid))
    # every shop slot of this type, not only the ones the item randomizer rewrote: a merchant selling
    # armor is a live slot whether or not another tool touched it
    for r in ed.S.rows:
        if ed.S.get(r, "equipType") != SHOP_FOR.get(cat, -1):
            continue
        iid = ed.S.get(r, "equipId")
        if iid > 0:
            found.append((ed.S, r, 0, iid))

    if len(found) < 2:
        return [f"# {WORD[cat]} drops: fewer than two slots, nothing moved"]

    # set-aware mode for armour: the pieces of an armour set are moved as a unit
    if keep_sets and cat == 3:
        plan = set_plan([f[3] for f in found], names, rng)
        for (P, r, i, _old), new in zip(found, plan):
            _write(P, r, i, new)
        unit = "; sets move as a unit"
    else:
        donors = [f[3] for f in found]
        rng.shuffle(donors)
        for (P, r, i, _old), new in zip(found, donors):
            _write(P, r, i, new)
        unit = ""

    changes = []
    for (P, r, i, old) in found:
        new = P.get(r, "equipId") if i == 0 else P.get(r, f"lotItemId0{i}")
        if old != new:
            changes.append((r, i, old, new))
    lines = [f"# {WORD[cat]} drops: {len(changes)} of {len(found)} slots changed, the items themselves are "
             f"unchanged{unit}",
             "# slot  :  old item  ->  new item"]
    for r, i, old, new in changes:
        if i == 0:
            lines.append(f"{r.id:>9}  shop    {_item_name(names, old, cat):<44} ->  {_item_name(names, new, cat)}")
        else:
            lot = lots.get(r.id, "")
            where = lot[1:].split("]")[0] if lot.startswith("[") and "]" in lot else (lot or f"lot {r.id}")
            lines.append(f"{r.id:>9}  {where[:34]:<34}  {_item_name(names, old, cat):<34} ->  "
                         f"{_item_name(names, new, cat)}")
    return lines


def _write(P: erreg.Param, r, i: int, iid: int) -> None:
    if i == 0:
        P.set(r, "equipId", iid)
    else:
        P.set(r, f"lotItemId0{i}", iid)
