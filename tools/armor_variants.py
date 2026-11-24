"""Same-looking armour, different stats: extra EquipParamProtector rows the runtime can pick from.

Armour has no affinity rows and no second live row with the same model and slot, so a per-pickup
stat reroll needs somewhere to put the numbers.  This pass clones a few rows per piece, changes only
the selected stat columns, and leaves every appearance field (model, icons, category, name id) alone.
The loot-variants manifest then lists the generated ids, and the runtime chooses one on each pickup.

~416 bytes per row; a +4 variant run adds ~1.3 MB of raw table data (a few tens of KB compressed),
well inside the regulation budget.  Every clone uses the same reinforce type as its source, so the
ordinary +0..+10 roll still composes with the variant roll.
"""
from __future__ import annotations

import random
from pathlib import Path

import erreg

HERE = Path(__file__).resolve().parent

# The stat columns are the same ones gear.py already treats as armour numbers, grouped so a run can
# ask for "just resistances" without changing weight or poise.
STAT_GROUPS: dict[str, tuple[str, ...]] = {
    "negation": ("neutralDamageCutRate", "slashDamageCutRate", "blowDamageCutRate",
                 "thrustDamageCutRate", "magicDamageCutRate", "fireDamageCutRate",
                 "thunderDamageCutRate", "darkDamageCutRate"),
    "resistance": ("resistPoison", "resistDisease", "resistBlood", "resistCurse",
                   "resistFreeze", "resistSleep", "resistMadness"),
    "poise": ("saDurability", "toughnessCorrectRate"),
    "weight": ("weight",),
}
MAX_VARIANTS = 8


class ArmorVariants:
    def __init__(self, reg: erreg.Regulation, rng: random.Random, count: int = 0,
                 groups: tuple[str, ...] | list[str] = ("negation", "resistance")) -> None:
        self.P = reg.param("EquipParamProtector",
                           erreg.load_paramdef(HERE / "paramdef" / "EquipParamProtector.xml"))
        self.count = max(0, min(MAX_VARIANTS, int(count)))
        self.groups = tuple(g for g in STAT_GROUPS if not groups or g in groups)
        self.fields = tuple(f for group in self.groups for f in STAT_GROUPS[group])
        self.variants: dict[int, tuple[int, ...]] = {}
        if self.count:
            self._build(rng)

    def _build(self, rng: random.Random) -> None:
        P = self.P
        names = erreg.load_names(HERE / "names" / "EquipParamProtector.txt")
        sources = [r for r in P.rows
                   if r.id in names and P.get(r, "weight") > 0 and P.get(r, "materialSetId") != -1]
        if not sources:
            return
        # Vanilla ranges per slot keep a heavy helm heavy and a light helm light.
        ranges: dict[int, dict[str, tuple[float, float, bool]]] = {}
        for row in sources:
            slot = P.get(row, "protectorCategory")
            per = ranges.setdefault(slot, {})
            for field in self.fields:
                if field not in per:
                    lo, hi = P.get(row, field), P.get(row, field)
                    per[field] = (float(lo), float(hi), isinstance(lo, float))
                else:
                    old = per[field]
                    v = float(P.get(row, field))
                    per[field] = (min(old[0], v), max(old[1], v), old[2])

        next_id = ((max(r.id for r in P.rows) // 10000) + 1) * 10000
        for source in sources:
            slot = P.get(source, "protectorCategory")
            ids: list[int] = []
            for _ in range(self.count):
                clone = P.add_row(next_id, source)
                for field in self.fields:
                    lo, hi, is_float = ranges[slot][field]
                    value = lo if hi <= lo else rng.uniform(lo, hi)
                    P.set(clone, field, round(value, 3) if is_float else int(round(value)))
                ids.append(next_id)
                next_id += 1
            self.variants[source.id] = tuple(ids)

    def lines(self) -> list[str]:
        n = sum(len(v) for v in self.variants.values())
        return [f"# armour variants: {n} extra rows for {len(self.variants)} pieces, "
                f"stats: {','.join(self.groups)} (appearance fields copied unchanged)",
                "# each variant is one more silhouette-free stat block the runtime may hand out"]
