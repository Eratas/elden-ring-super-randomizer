"""Random upgrade levels on the weapons the game hands out.

A weapon id is `base + affinity * 100 + upgrade`.  In vanilla every weapon in a drop table, a chest or a
shop is +0 (measured on 1.17.1: 947 weapon slots in ItemLotParam_enemy, all +0), so "loot a Longsword +7"
does not exist.  This pass rewrites the level part of those ids:

  * enemy drop tables (ItemLotParam_enemy, the rows an NpcParam row points at),
  * map lots: chests, boss rewards, gifts, pickups (ItemLotParam_map, the rows in names/item_locations.txt),
  * shops (ShopLineupParam, weapon slots),
  * starting classes are left alone: a +10 class weapon would break the early game's balance.

The level is drawn between 0 and the ceiling of the weapon: 25 for a weapon with affinity rows, 10 for a
somber weapon (one row and `materialSetId != -1`), 0 for a unique weapon that cannot be reinforced.  The
ceiling is read once, before --somber-infusable adds its rows, so construct this before the weapon pass.

### Curves

A tier is (from, to, share) as fractions of what the weapon can take, so the same curve works for a +25
weapon and a +10 somber one.  `even` is every level equally likely; `common` and `legendary` make a high
roll an event.  Bosses can roll one curve higher (see --loot-boss-bonus), and a drop at 90% or more of
its weapon's ceiling is announced as LEGENDARY.
"""
from __future__ import annotations

import math
import random
from pathlib import Path

import bosses
import erreg
from enemy_drops import EnemyDrops
from flasks import load_locations

HERE = Path(__file__).resolve().parent

CATEGORY_WEAPON = 2
SHOP_TYPE_WEAPON = 0
SOMBER_MAX, STANDARD_MAX = 10, 25
SLOTS = 8

TIERS: dict[str, tuple[tuple[float, float, float], ...]] = {
    "even": ((0.0, 1.0, 1.0),),
    "common": ((0.00, 0.12, 0.55), (0.12, 0.36, 0.28), (0.36, 0.60, 0.12),
               (0.60, 0.80, 0.04), (0.80, 1.00, 0.01)),
    "legendary": ((0.00, 0.10, 0.70), (0.10, 0.32, 0.20), (0.32, 0.56, 0.07),
                  (0.56, 0.80, 0.025), (0.80, 1.00, 0.005)),
}
CURVE_ORDER = ("even", "common", "legendary")
TOP_SHARE = 0.80                    # at or above this share of the ceiling a drop counts as a top roll
LEGENDARY_SHARE = 0.90              # at or above this share it is announced as a legendary drop


class Loot:
    def __init__(self, reg: erreg.Regulation, boss_min_runes: int = 0) -> None:
        self.reg = reg
        self.W = reg.param("EquipParamWeapon", erreg.load_paramdef(HERE / "paramdef" / "EquipParamWeapon.xml"))
        self.L = reg.param("ItemLotParam_enemy",
                           erreg.load_paramdef(HERE / "paramdef" / "ItemLotParam.xml"))
        self.M = reg.param("ItemLotParam_map",
                           erreg.load_paramdef(HERE / "paramdef" / "ItemLotParam.xml"))
        self.S = reg.param("ShopLineupParam",
                           erreg.load_paramdef(HERE / "paramdef" / "ShopLineupParam.xml"))
        N = reg.param("NpcParam", erreg.load_paramdef(HERE / "paramdef" / "NpcParam.xml"))
        self.weapon_names = erreg.load_names(HERE / "names" / "EquipParamWeapon.txt")
        self._ceilings: dict[int, int] = {}
        variants: dict[int, int] = {}
        for r in self.W.rows:
            variants[r.id - r.id % 10000] = variants.get(r.id - r.id % 10000, 0) + 1
        for base, count in variants.items():
            row = self.W.by_id.get(base)
            if row is None:
                continue
            if count > 1:
                self._ceilings[base] = STANDARD_MAX
            elif self.W.get(row, "materialSetId") == -1:
                self._ceilings[base] = 0            # unique weapon: cannot be reinforced
            else:
                self._ceilings[base] = SOMBER_MAX   # somber weapon
        # which enemy drop lots belong to a boss-tier enemy (isSoulGetByBoss, optionally widened)
        boss = bosses.boss_ids(N, boss_min_runes)
        self.lot_boss: dict[int, bool] = {}
        for r in N.rows:
            lot = N.get(r, "itemLotId_enemy")
            if lot > 0 and lot not in self.lot_boss:
                self.lot_boss[lot] = r.id in boss
        self.drop_rows = self._drop_rows()

    # ------------------------------------------------------------------ where
    def _drop_rows(self) -> list:
        """Every ItemLotParam_enemy row the game can roll (the lots NpcParam points at, with their
           consecutive rows)."""
        ed = EnemyDrops(self.reg)
        rows: dict[int, object] = {}
        for k in ed.lots():
            for r in ed.run(k):
                rows.setdefault(r.id, r)
        return list(rows.values())

    def max_level(self, base: int) -> int:
        return self._ceilings.get(base, STANDARD_MAX)

    def _top(self, base: int, cap: int | None) -> int:
        """The ceiling a drop may reach: the weapon's own, lowered by the optional global cap."""
        top = self.max_level(base)
        return min(top, cap) if cap else top

    def curve_for(self, rarity: str, boss: bool, bonus: str) -> str:
        """The curve a drop uses: the chosen one, or one step higher for a boss with the bonus on."""
        if not boss or bonus == "same":
            return rarity
        if bonus == "best":
            return "legendary"
        i = CURVE_ORDER.index(rarity) if rarity in CURVE_ORDER else 1
        return CURVE_ORDER[min(i + 1, len(CURVE_ORDER) - 1)]

    # ------------------------------------------------------------------ the change
    def _roll(self, iid: int, rng: random.Random, rarity: str = "common",
              cap: int | None = None) -> tuple[int, int]:
        """A new id for a weapon and the level it got: the same weapon and affinity, a new upgrade level.

        The level is drawn from a tier first (most drops land in the first tier) and then uniformly inside
        that tier, so +25 stays rare instead of being one chance in 26."""
        base = iid - iid % 10000
        affinity = (iid % 10000) // 100
        top = self._top(base, cap)
        if top <= 0:
            return iid, 0
        tiers = TIERS.get(rarity, TIERS["common"])
        roll = rng.random()
        upto = 0.0
        chosen = tiers[-1]
        for tier in tiers:
            upto += tier[2]
            if roll <= upto:
                chosen = tier
                break
        lo = int(math.ceil(chosen[0] * top))
        hi = int(math.floor(chosen[1] * top))
        level = max(0, min(top, rng.randint(min(lo, hi), max(lo, hi))))
        return base + affinity * 100 + level, level

    def _weapon_name(self, iid: int) -> str:
        base, level = iid - iid % 10000, iid % 100
        return f"{self.weapon_names.get(base, f'weapon {base}')}" + (f" +{level}" if level else "")

    def randomize(self, rng: random.Random, rarity: str = "common", boss_bonus: str = "better",
                  max_level: int | None = None) -> list[str]:
        base_curve = rarity if rarity in TIERS else "common"
        boss_note = ("# every enemy rolls the same curve" if boss_bonus == "same"
                     else f"# boss enemies roll one curve higher ({boss_bonus})")
        cap_note = f"# levels capped at +{max_level}" if max_level else ""
        lines = [f"# loot levels: every weapon in the drop tables, map lots and shops gets a random upgrade "
                 f"level ({base_curve} curve; 0-25, somber 0-10, unique 0)",
                 boss_note,
                 "# \u2605 = 80% or more of the weapon's ceiling, LEGENDARY = 90% or more",
                 "# source  :  old item  ->  new item"]
        if cap_note:
            lines.insert(2, cap_note)
        n = {"enemy": 0, "map": 0, "shop": 0}
        top_drops: list[tuple[float, int, str, int, bool]] = []
        legendary: list[str] = []

        def note(iid: int, new: int, level: int, top: int, where: str) -> None:
            share = (level / top) if top else 0.0
            mark = "LEGENDARY" if share >= LEGENDARY_SHARE else ("\u2605" if share >= TOP_SHARE else " ")
            lines.append(f"{mark:>9} {where:<12} {self._weapon_name(iid):<44} ->  {self._weapon_name(new)}")
            if share >= TOP_SHARE:
                top_drops.append((share, level, self._weapon_name(new), top, share >= LEGENDARY_SHARE))
            if share >= LEGENDARY_SHARE:
                legendary.append(f"# LEGENDARY drop: {self._weapon_name(new)} (+{level} of +{top})")

        def do_lot(P: erreg.Param, rows: list, tag: str) -> None:
            for r in rows:
                boss = tag == "enemy" and self.lot_boss.get(r.id, False)
                curve = self.curve_for(base_curve, boss, boss_bonus)
                for i in range(1, SLOTS + 1):
                    if P.get(r, f"lotItemCategory0{i}") != CATEGORY_WEAPON:
                        continue
                    iid = P.get(r, f"lotItemId0{i}")
                    if iid <= 0 or P.get(r, f"lotItemBasePoint0{i}") <= 0:
                        continue
                    new, level = self._roll(iid, rng, curve, max_level)
                    if new != iid:
                        P.set(r, f"lotItemId0{i}", new)
                        n[tag] += 1
                        note(iid, new, level, self._top(iid - iid % 10000, max_level),
                             f"{r.id} {'boss' if boss else tag}")

        do_lot(self.L, self.drop_rows, "enemy")
        here = load_locations()
        do_lot(self.M, [self.M.by_id[k] for k in here.get("ItemLotParam_map", {}) if k in self.M.by_id], "map")
        shops = [self.S.by_id[k] for k in here.get("ShopLineupParam", {}) if k in self.S.by_id]
        for r in shops:
            if self.S.get(r, "equipType") != SHOP_TYPE_WEAPON:
                continue
            iid = self.S.get(r, "equipId")
            if iid <= 0:
                continue
            new, level = self._roll(iid, rng, base_curve, max_level)
            if new != iid:
                self.S.set(r, "equipId", new)
                n["shop"] += 1
                note(iid, new, level, self._top(iid - iid % 10000, max_level), f"{r.id} shop")

        summary = (f"# loot levels: {n['enemy']} enemy drop slots, {n['map']} map lots and {n['shop']} shop "
                   f"entries changed ({len(self._ceilings)} upgradeable weapons; 0-25, somber 0-10, unique 0)")
        lines = [lines[0], lines[1], summary] + lines[2:]
        if legendary:
            lines = legendary + lines
        if top_drops:
            top_drops.sort(reverse=True)
            lines += ["", f"# best {min(len(top_drops), 12)} drops of this seed (by share of the ceiling):"]
            for _share, level, name, top, is_legendary in top_drops[:12]:
                tag = "LEGENDARY" if is_legendary else "top"
                lines.append(f"#   {tag:<9} {name:<44} +{level}  (of +{top})")
        return lines