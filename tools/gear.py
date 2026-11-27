"""Armour and talisman stats.

Both passes answer the same complaint: two copies of the same armour piece are the same armour piece,
because a row is shared by every copy.  Neither can invent per-copy values in a static file (that needs
the runtime DLL), but each *column* of the table can be shaken, and then every armour piece / talisman
in the game is a different one:

  armour     every stat column (defences, resistances, damage negation, weight) is permuted among the
             rows of the same slot (head / body / arms / legs), so a helm ends up with another helm's
             numbers.  A column keeps the set of vanilla values, so nothing becomes absurd and the
             balance stays where the game put it.
  talismans  whole rows are permuted among the named talismans (this tool has no paramdef for
             EquipParamAccessory, so fields cannot be addressed - see erreg.Param.loose).  Every
             talisman keeps its name and icon and receives another one's effect and numbers.

Rows without a name (cut content) and rows without weight (the "Type N" placeholders) are left alone.
"""
from __future__ import annotations

import random
from pathlib import Path

import erreg

HERE = Path(__file__).resolve().parent

# EquipParamProtector columns that make up a piece's numbers.  Elden Ring armour has no flat defence
# (defensePhysics / defenseSlash / ... are all zero in 1.17.1): what the equipment screen shows is the
# damage negation rate per damage type, plus the status resistances, the weight and the poise values.
ARMOR_COLUMNS = (
    # damage negation shown on the equipment screen (0-1, 0.796 to 0.999 in vanilla)
    "neutralDamageCutRate", "slashDamageCutRate", "blowDamageCutRate", "thrustDamageCutRate",
    "magicDamageCutRate", "fireDamageCutRate", "thunderDamageCutRate", "darkDamageCutRate",
    # status resistances
    "resistPoison", "resistDisease", "resistBlood", "resistCurse", "resistFreeze",
    "resistSleep", "resistMadness",
    # poise and how heavy the piece is
    "saDurability", "toughnessCorrectRate", "weight",
)
ARMOR_SUMMARY = ("neutralDamageCutRate", "weight")

# Piece words that end an armour name ("Knight Helm", "Knight Armor", "Knight Gauntlets").  Used to
# group the four pieces of a set so a set can be rolled as a whole; a name that ends in none of them is
# treated as a set of its own.
SLOT_WORDS = ("Armor", "Armour", "Helm", "Helmet", "Hat", "Crown", "Circlet", "Mask", "Robe",
              "Garb", "Vest", "Gauntlets", "Gauntlet", "Gloves", "Greaves", "Greave", "Boots",
              "Shoes", "Trousers")
TALISMAN_TABLE = "EquipParamAccessory"


class Armour:
    def __init__(self, reg: erreg.Regulation) -> None:
        self.reg = reg
        self.P = reg.param("EquipParamProtector", erreg.load_paramdef(HERE / "paramdef" / "EquipParamProtector.xml"))
        self.names = erreg.load_names(HERE / "names" / "EquipParamProtector.txt")

    def rows(self) -> dict[int, list]:
        """Named, non-placeholder rows grouped by slot (protectorCategory: 0 head, 1 body, 2 arms,
           3 legs).  Rows with weight 0 are the "Type N" placeholders and never appear in game."""
        groups: dict[int, list] = {}
        for r in self.P.rows:
            if r.id not in self.names or self.P.get(r, "weight") <= 0:
                continue
            groups.setdefault(self.P.get(r, "protectorCategory"), []).append(r)
        return groups

    def randomize(self, rng: random.Random) -> list[str]:
        P, names = self.P, self.names
        groups = self.rows()
        n_rows = sum(len(v) for v in groups.values())
        lines = [f"# armour: {n_rows} pieces in {len(groups)} slots, {len(ARMOR_COLUMNS)} columns permuted "
                 f"within each slot (EquipParamProtector; head / body / arms / legs never mix)",
                 "# row  piece  |  " + "  |  ".join(ARMOR_SUMMARY) + "   (old -> new)"]
        before = {r.id: tuple(P.get(r, f) for f in ARMOR_SUMMARY) for g in groups.values() for r in g}
        for cat in sorted(groups):
            rows = groups[cat]
            for f in ARMOR_COLUMNS:
                values = [P.get(r, f) for r in rows]
                rng.shuffle(values)
                for r, v in zip(rows, values):
                    P.set(r, f, v)
        for cat in sorted(groups):
            for r in groups[cat]:
                old = "  ".join(f"{f} {o:g}" for f, o in zip(ARMOR_SUMMARY, before[r.id]))
                new = "  ".join(f"{f} {P.get(r, f):g}" for f in ARMOR_SUMMARY)
                lines.append(f"{r.id:>8}  {names.get(r.id, '?'):<40} |  {old}  ->  {new}")
        return lines

    def randomize_fresh(self, rng: random.Random, keep_sets: bool = True) -> list[str]:
        """Roll every piece's numbers again instead of swapping them.

        Each column is drawn uniformly between the lowest and highest value that column has inside the
        piece's own slot, so a helm's numbers stay in the range helms use, but no two pieces share a stat
        block and no piece can be recognised from its vanilla set.  With keep_sets the four pieces of a set
        are scaled by one factor instead, so a set stays internally consistent while still being different
        from vanilla."""
        P, names = self.P, self.names
        groups = self.rows()
        all_rows = [r for g in groups.values() for r in g]
        n_rows = len(all_rows)
        lines = [f"# armour: {n_rows} pieces, {len(ARMOR_COLUMNS)} columns rolled again inside each slot's "
                 f"vanilla range (EquipParamProtector)",
                 "# row  piece  |  " + "  |  ".join(ARMOR_SUMMARY) + "   (old -> new)"]
        before = {r.id: tuple(P.get(r, f) for f in ARMOR_SUMMARY) for r in all_rows}
        # the vanilla range of every column per slot, taken before anything is changed
        ranges: dict[int, dict] = {}
        for cat, rows in groups.items():
            per_slot = {}
            for f in ARMOR_COLUMNS:
                values = [P.get(r, f) for r in rows]
                if max(values) > min(values):
                    per_slot[f] = (min(values), max(values), isinstance(values[0], float))
            ranges[cat] = per_slot
        # a set is a name without its trailing piece word; its pieces can sit in different slots, so the
        # factor is drawn once per set and column and every piece of the set gets the same one
        sets = self._sets(all_rows, names) if keep_sets else {}
        factors = {(name, f): rng.uniform(0.8, 1.2)
                   for name in sets for f in ARMOR_COLUMNS}
        slot_of = {r.id: cat for cat, rows in groups.items() for r in rows}
        done: set[int] = set()
        for name, members in sets.items():
            for r in members:
                per_slot = ranges.get(slot_of.get(r.id, -1), {})
                for f, (lo, hi, is_float) in per_slot.items():
                    v = P.get(r, f) * factors[(name, f)]
                    v = round(v, 3) if is_float else int(round(v))
                    P.set(r, f, max(lo, min(hi, v)))
                done.add(r.id)
        for cat, rows in groups.items():
            for f, (lo, hi, is_float) in ranges[cat].items():
                for r in rows:
                    if r.id in done:
                        continue
                    v = rng.uniform(lo, hi)
                    P.set(r, f, round(v, 3) if is_float else int(round(v)))
        for r in all_rows:
            old = "  ".join(f"{f} {o:g}" for f, o in zip(ARMOR_SUMMARY, before[r.id]))
            new = "  ".join(f"{f} {P.get(r, f):g}" for f in ARMOR_SUMMARY)
            lines.append(f"{r.id:>8}  {names.get(r.id, '?'):<40} |  {old}  ->  {new}")
        return lines

    @staticmethod
    def _sets(rows: list, names: dict[int, str]) -> dict[str, list]:
        """Pieces that belong to the same named set: the name without its trailing piece word."""
        sets: dict[str, list] = {}
        for r in rows:
            name = names.get(r.id, "")
            key = None
            for word in SLOT_WORDS:
                if name.endswith(" " + word):
                    key = name[:-(len(word) + 1)]
                    break
            if key:
                sets.setdefault(key, []).append(r)
        return {k: v for k, v in sets.items() if len(v) > 1}


class Talismans:
    """Whole-row shuffle over EquipParamAccessory (no paramdef, so no field-level work)."""

    def __init__(self, reg: erreg.Regulation) -> None:
        self.reg = reg
        self.P = erreg.Param.loose(reg, TALISMAN_TABLE)
        self.names = erreg.load_names(HERE / "names" / "EquipParamAccessory.txt")

    def randomize(self, rng: random.Random) -> list[str]:
        rows = [r for r in self.P.rows if r.id in self.names]
        if len(rows) < 2:
            return ["# talismans: fewer than two named rows, nothing changed"]
        data_of = {r.id: r.data for r in rows}          # snapshot: assignment never mutates a row's bytes
        donors = rows[:]
        rng.shuffle(donors)
        for r, donor in zip(rows, donors):
            r.data = data_of[donor.id]
        self.P.dirty = True
        names = self.names
        lines = [f"# talismans: {len(rows)} rows shuffled (EquipParamAccessory; this tool has no paramdef "
                 f"for the table, so whole rows move and every talisman keeps its name)",
                 "# row  talisman                                <-  row the numbers came from"]
        for r, donor in zip(rows, donors):
            lines.append(f"{r.id:>8}  {names.get(r.id, '?'):<42} <-  {names.get(donor.id, '?')} ({donor.id})")
        return lines
