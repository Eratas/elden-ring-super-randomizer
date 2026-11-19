"""Consumable stack sizes.

`EquipParamGoods.maxNum` is how many of an item one pickup or one purchase gives, and
`maxRepositoryNum` is how many fit in the inventory.  Vanilla uses a handful of values (1, 10, 20, 99,
999), so a "stack of 99" is always the same 99.

Shuffling the two together moves the *pair* from one item to another, which keeps every row internally
consistent: an item that suddenly gives 999 also has the repository cap that goes with it.  Only rows
that already stack (`maxNum > 1`) take part, so a key item that gives exactly one stays exactly one.
"""
from __future__ import annotations

import random
from pathlib import Path

import erreg

HERE = Path(__file__).resolve().parent


def randomize(reg: erreg.Regulation, names: dict[int, str], rng: random.Random) -> list[str]:
    P = reg.param("EquipParamGoods", erreg.load_paramdef(HERE / "paramdef" / "EquipParamGoods.xml"))
    rows = [r for r in P.rows if r.id in names and P.get(r, "maxNum") > 1]
    if len(rows) < 2:
        return ["# goods quantity: fewer than two stackable items, nothing changed"]
    old = {r.id: (P.get(r, "maxNum"), P.get(r, "maxRepositoryNum")) for r in rows}
    donors = rows[:]
    rng.shuffle(donors)
    for r, donor in zip(rows, donors):
        P.set(r, "maxNum", old[donor.id][0])
        P.set(r, "maxRepositoryNum", old[donor.id][1])
    lines = [f"# goods quantity: {len(rows)} stackable items swapped "
             f"(EquipParamGoods.maxNum + maxRepositoryNum)",
             "# item                                     |  old (max, repository)  ->  new"]
    for r, donor in zip(rows, donors):
        lines.append(f"{r.id:>8}  {names.get(r.id, '?'):<40} |  {old[r.id][0]:>4} {old[r.id][1]:>4}"
                     f"  ->  {old[donor.id][0]:>4} {old[donor.id][1]:>4}")
    return lines
