"""Reroll merchant stock: every shop slot gets a random item of its own category.

Prices (`ShopLineupParam.value`), the stock mask and the cost type stay as they are, so a slot keeps
selling at its vanilla price and the existing price passes still apply.

The pools are curated instead of "every named row": goods must have a real use effect and a sell
value (which keeps out the no-effect entries such as Depleted Ash), weapons are base rows only,
armour names must be actual names (the table's "Type 1" placeholders are dropped), and debug / NPC /
test rows are filtered by name.  Each shop keeps its own category mix, so a smith still sells weapons
and armour rather than suddenly selling only grease.

Small general shops are filled up to 40 slots by cloning a row of their own stock into the free row
ids directly after their last slot, before the next shop's block.  Only shops that already sell at
least two categories are filled (a spell scroll shop stays a spell scroll shop), and only when the
gap is large enough.  This is the static half of a rotating stock; a timer would need a runtime hook.

Slots are only rerolled when their `equipType` is in `kinds` (weapons 0, armor 1, talismans 2, goods 3,
ashes of war 4).  Rows with `equipId` 0 (empty slots) and progression-gated rows are skipped.
"""
from __future__ import annotations

import random
import re
from pathlib import Path

import erreg
from flasks import CATEGORY_OF_SHOP_TYPE
from loot_variants import fingerprint

HERE = Path(__file__).resolve().parent

SHOP_FOR = {shop: cat for shop, cat in CATEGORY_OF_SHOP_TYPE.items() if cat in (1, 2, 3, 4, 5)}
KIND_OF_CATEGORY = {1: "goods", 2: "weapons", 3: "armor", 4: "talismans", 5: "ashes"}
NAMES = {1: "EquipParamGoods", 2: "EquipParamWeapon", 3: "EquipParamProtector",
         4: "EquipParamAccessory", 5: "EquipParamGem"}
CATEGORY_OF_PARAM = {v: k for k, v in NAMES.items()}
BAD_NAME = re.compile(r"(?i)(^\s*$|\?|\[npc\]|^type \d+$|\b(?:dummy|test|debug|depleted|placeholder|unused)\b)")
TARGET_STOCK = 40          # a general merchant is filled up to the target (default 40 slots)
MAX_ADDED_PER_SHOP = 24    # a floor on fills, so a shop can always reach the default target
MAX_REPORT_LINES = 300
PERIODIC_MANIFEST = "shops_periodic.txt"   # the manifest mods/shops-periodic rerolls from


def _good_name(name: str) -> bool:
    return bool(name) and not BAD_NAME.search(name)


def _pools(reg: erreg.Regulation, kinds: set[int]) -> dict[int, list[int]]:
    """Curated item ids per category: things a merchant can sensibly sell."""
    out: dict[int, list[int]] = {}
    for cat in sorted(kinds):
        table = NAMES.get(cat)
        if not table:
            continue
        names = erreg.load_names(HERE / "names" / f"{table}.txt")
        ids: list[int] = []
        pd = HERE / "paramdef" / f"{table}.xml"
        if pd.is_file() and table != "EquipParamAccessory":
            P = reg.param(table, erreg.load_paramdef(pd))
            for r in P.rows:
                name = names.get(r.id)
                if not name or not _good_name(name):
                    continue
                if table == "EquipParamGoods":
                    # goodsType 0 = a normal consumable; without a use effect it is vendor trash
                    if P.get(r, "goodsType") != 0 or P.get(r, "sellValue") <= 0:
                        continue
                    if P.get(r, "refId_default") <= 0:
                        continue
                elif table == "EquipParamWeapon":
                    if r.id % 10000 or r.id == 110000:      # base rows, never "Unarmed"
                        continue
                    if not P.get(r, "wepType"):
                        continue
                ids.append(r.id)
        else:
            # talismans have no paramdef here; the names file is the authoritative row list
            ids = [i for i, name in names.items() if _good_name(name)]
        if ids:
            out[cat] = sorted(set(ids))
    return out


def _runs(S) -> list[list]:
    """Consecutive rows of one shop block, in id order; a title row starts a new block."""
    rows = sorted(S.rows, key=lambda r: r.id)
    runs: list[list] = []
    for r in rows:
        title = S.get(r, "menuTitleMsgId")
        if title != -1 or not runs:
            runs.append([r])
        else:
            runs[-1].append(r)
    return runs


def _median(values: list[int]) -> int:
    values = sorted(v for v in values if v > 0)
    return values[len(values) // 2] if values else 100


def randomize(reg: erreg.Regulation, rng: random.Random, kinds: set[int] | None = None,
              target: int = TARGET_STOCK) -> list[str]:
    """Reroll merchant stock; small general shops are filled up to `target` slots.

    The fill is skipped when target <= 0, while the per-slot reroll still runs (that half is what
    --random-shop-stock buys; the fill is the extra bit the target adds).
    """
    wanted = set(kinds) if kinds else set(SHOP_FOR.values())
    wanted &= set(SHOP_FOR.values())
    if not wanted:
        return ["# shop stock: no category selected, nothing changed"]
    pools = _pools(reg, wanted)
    if not pools:
        return ["# shop stock: no named items to draw from, nothing changed"]
    S = reg.param("ShopLineupParam", erreg.load_paramdef(HERE / "paramdef" / "ShopLineupParam.xml"))
    names = {cat: erreg.load_names(HERE / "names" / f"{NAMES[cat]}.txt") for cat in pools}
    rows: list[tuple[int, int, int, int]] = []       # (slot id, category, old id, new id)
    changed = dict.fromkeys(pools, 0)
    used_by_run: list[set[int]] = []
    run_rows: list[list] = []
    for run in _runs(S):
        eligible = []
        for r in run:
            cat = SHOP_FOR.get(S.get(r, "equipType"))
            if cat not in pools or S.get(r, "equipId") <= 0:
                continue
            if (r.id < 10000 or S.get(r, "costType") != 0 or S.get(r, "eventFlag_forRelease")):
                continue                 # starting gifts, dragon-heart shops and quest rows stay as they are
            eligible.append((r, cat))
        used: set[int] = set()
        for r, cat in eligible:
            old = S.get(r, "equipId")
            pool = [i for i in pools[cat] if i not in used] or pools[cat]
            new = rng.choice(pool)
            used.add(new)
            rows.append((r.id, cat, old, new))
            if new != old:
                S.set(r, "equipId", new)
                changed[cat] += 1
        used_by_run.append(used)
        run_rows.append(eligible)

    added: list[tuple[int, int, int]] = []           # (new id, category, template id)
    for idx, (run, eligible) in enumerate(zip(_runs(S), run_rows)):
        if (not eligible or target <= 0 or len(run) >= target or len(eligible) >= target
                or len(eligible) < 4 or run[0].id >= 10_000_000):
            continue
        cats = {}
        for _r, cat in eligible:
            cats[cat] = cats.get(cat, 0) + 1
        if len(cats) < 2:                # a spell / ash / single-category specialist keeps its identity
            continue
        last_id = run[-1].id
        later = [r.id for r in S.rows if r.id > last_id]
        room = (min(later) - last_id - 1) if later else 999
        free = [last_id + i for i in range(1, min(room, target - len(run),
                                                  max(MAX_ADDED_PER_SHOP, target)) + 1)]
        free = [i for i in free if i not in S.by_id]
        if not free:
            continue
        cat_pool = [c for c, n in cats.items() for _ in range(n)]
        template = {cat: r for r, cat in eligible}
        used = used_by_run[idx]
        for new_id in free:
            cat = rng.choice(cat_pool)
            src = template.get(cat) or eligible[0][0]
            new = S.add_row(new_id, src)
            price = _median([S.get(r, "value") for r, c in eligible if c == cat])
            choices = [i for i in pools[cat] if i not in used] or pools[cat]
            item = rng.choice(choices)
            used.add(item)
            S.set(new, "equipId", item)
            S.set(new, "equipType", next(t for t, c in CATEGORY_OF_SHOP_TYPE.items() if c == cat))
            S.set(new, "value", price)
            S.set(new, "sellQuantity", 1)
            S.set(new, "setNum", 1)
            S.set(new, "eventFlag_forStock", 0)
            S.set(new, "eventFlag_forRelease", 0)
            S.set(new, "menuTitleMsgId", -1)
            S.set(new, "nameMsgId", -1)
            S.set(new, "iconId", -1)
            S.set(new, "menuIconId", -1)
            added.append((new_id, cat, src.id))

    total = sum(changed.values())
    total_items = sum(len(v) for v in pools.values())
    lines = [f"# shop stock: {total} of {len(rows)} slots rerolled; pools have {total_items} curated items "
             f"({', '.join(f'{len(pools[c])} {KIND_OF_CATEGORY[c]}' for c in sorted(pools))})",
             f"# shop stock: changed slots: "
             f"{', '.join(f'{changed.get(c, 0)} {KIND_OF_CATEGORY[c]}' for c in sorted(pools))}",
             f"# shop stock: {len(added)} slots added to small general shops (target {target})",
             "# slot  :  old item  ->  new item"]
    shown = 0
    for rid, cat, old, new in rows:
        if new == old:
            continue
        if shown >= MAX_REPORT_LINES:
            lines.append(f"# ... {total - shown} more changes in the table")
            break
        lines.append(f"{rid:>8}  {names[cat].get(old, str(old)):<40} ->  {names[cat].get(new, str(new))}")
        shown += 1
    for rid, cat, src in added[:20]:
        lines.append(f"{rid:>8}  (new)  {KIND_OF_CATEGORY[cat]:<12} (template row {src})")
    return lines


def periodic_manifest(reg: erreg.Regulation, kinds: set[int] | None = None, every: int = 15,
                      data: bytes | None = None) -> list[str]:
    """The manifest the optional periodic-shops DLL rerolls from (see mods/shops-periodic).

    One line per sellable slot of every shop block, so the runtime can pick a random item on each
    tick instead of repeating the same rows:

        bind <regulation size> <fnv1a64>        # the bytes of the written regulation.bin
        every <minutes>                         # the ini default interval
        pool <cat> <id> <id> ...                # the curated pool for one category (1 goods .. 5 ashes)
        shop <idx> <row_id> <cat> ...           # the sellable slots of shop block idx

    Categories match KIND_OF_CATEGORY.  The pool is the same `_pools` output the static pass
    rerolls, so static and periodic randomization share one definition of "a merchant can
    sensibly sell".  `data` must be the bytes actually written next to the manifest.
    """
    if data is None:
        raise ValueError("periodic_manifest needs the regulation bytes to bind the manifest")
    pools = _pools(reg, set(kinds) if kinds else set(SHOP_FOR.values()))
    lines = ["# generated by the Super Randomizer; see mods/shops-periodic/",
             f"bind {fingerprint(data)}",
             f"every {every}"]
    for cat in sorted(pools):
        lines.append("pool " + " ".join([str(cat), *(str(i) for i in pools[cat])]))
    S = reg.param("ShopLineupParam", erreg.load_paramdef(HERE / "paramdef" / "ShopLineupParam.xml"))
    for idx, run in enumerate(_runs(S)):
        slots = [(r.id, cat) for r in run if (cat := SHOP_FOR.get(S.get(r, "equipType"))) is not None
                 and S.get(r, "equipId") > 0 and S.get(r, "costType") == 0 and cat in pools]
        if slots:
            lines.append("shop " + " ".join([str(idx), *(f"{rid} {cat}" for rid, cat in slots)]))
    return lines
