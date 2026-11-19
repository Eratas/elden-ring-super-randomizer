"""Reroll merchant stock: every shop slot gets a random item of its own category.

Prices (`ShopLineupParam.value`), the stock mask and the cost type stay as they are, so a slot keeps
selling at its vanilla price and the existing price passes still apply.  Each slot is drawn
independently and with replacement - nothing is permuted between merchants, so a single shop can end
up selling the same item in two of its slots (this is a per-slot reroll, not a swap).

Merchants cannot refresh their stock on a timer: that would need a runtime hook.  What this does is the
static half of it - every shop in the game sells something else, and the seed decides what.

Slots are only rerolled when their `equipType` is in `kinds` (weapons 0, armor 1, talismans 2, goods 3,
ashes of war 4).  Rows with `equipId` 0 (empty slots) and the tutorial / dummy merchants are skipped by
name.
"""
from __future__ import annotations

import random
from pathlib import Path

import erreg
from flasks import CATEGORY_OF_SHOP_TYPE

HERE = Path(__file__).resolve().parent

SHOP_FOR = {shop: cat for shop, cat in CATEGORY_OF_SHOP_TYPE.items() if cat in (1, 2, 3, 4, 5)}
KIND_OF_CATEGORY = {1: "goods", 2: "weapons", 3: "armor", 4: "talismans", 5: "ashes"}
NAMES = {1: "EquipParamGoods", 2: "EquipParamWeapon", 3: "EquipParamProtector",
         4: "EquipParamAccessory", 5: "EquipParamGem"}


def _pools(reg: erreg.Regulation, kinds: set[int]) -> dict[int, list[int]]:
    """A random item id per category, from the named rows of that category's table."""
    out: dict[int, list[int]] = {}
    for cat in kinds:
        param = NAMES.get(cat)
        if not param:
            continue
        pd = HERE / "paramdef" / f"{param}.xml"
        if not pd.is_file():               # talismans have no paramdef: they cannot be stocked this way
            continue
        P = reg.param(param, erreg.load_paramdef(pd))
        names = erreg.load_names(HERE / "names" / f"{param}.txt")
        ids = []
        for r in P.rows:
            if r.id not in names:
                continue
            if param == "EquipParamWeapon" and r.id % 10000:
                continue                       # one entry per weapon, at +0
            ids.append(r.id)
        if ids:
            out[cat] = ids
    return out


def randomize(reg: erreg.Regulation, rng: random.Random, kinds: set[int] | None = None) -> list[str]:
    wanted = set(kinds) if kinds else set(SHOP_FOR.values())
    wanted &= set(SHOP_FOR.values())
    if not wanted:
        return ["# shop stock: no category selected, nothing changed"]
    pools = _pools(reg, wanted)
    if not pools:
        return ["# shop stock: no named items to draw from, nothing changed"]
    S = reg.param("ShopLineupParam", erreg.load_paramdef(HERE / "paramdef" / "ShopLineupParam.xml"))
    names = {cat: erreg.load_names(HERE / "names" / f"{NAMES[cat]}.txt") for cat in pools}
    changed = {cat: 0 for cat in pools}
    total = 0
    rows: list[tuple[int, int, int, int]] = []       # (slot id, category, old id, new id)
    for r in S.rows:
        cat = SHOP_FOR.get(S.get(r, "equipType"))
        if cat not in pools:
            continue
        old = S.get(r, "equipId")
        if old <= 0:
            continue
        new = rng.choice(pools[cat])
        total += 1
        rows.append((r.id, cat, old, new))
        if new != old:
            S.set(r, "equipId", new)
            changed[cat] += 1
    lines = [f"# shop stock: {total} slots drawn from {sum(len(v) for v in pools.values())} items "
             f"({', '.join(f'{changed[c]} {KIND_OF_CATEGORY[c]}' for c in sorted(changed))})",
             "# slot  :  old item  ->  new item"]
    for rid, cat, old, new in rows:
        if new != old:
            lines.append(f"{rid:>8}  {names[cat].get(old, str(old)):<40} ->  {names[cat].get(new, str(new))}")
    return lines