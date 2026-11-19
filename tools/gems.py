"""Ashes of War: what a gem *does* when it is mounted on a weapon.

An Ash of War is an `EquipParamGem` row.  Two things on that row matter in play:

  swordArtsParamId   the skill itself (Lion's Claw, Sky Shot, ...) – the animation and the hit logic
  spEffectId0..2     the on-hit effects (blood loss, frostbite, a buff, ...) – up to three, fired together

Both can be shaken.  To stay compatible the donors are only drawn from gems that can be mounted on the
same weapon types: the `configurableWepAttr` bitfield says which weapon attributes a gem may be applied
to, and two gems with the same mask accept the same weapons.  Shuffling inside those groups means a
skill never ends up on a weapon that could not use it.

The effect triple moves as a unit (slot 0 is the primary effect, 1 and 2 the secondary ones), and the
skill moves on its own, so the two can be switched on separately.
"""
from __future__ import annotations

import random
from pathlib import Path

import erreg

HERE = Path(__file__).resolve().parent


class Ashes:
    def __init__(self, reg: erreg.Regulation) -> None:
        self.reg = reg
        self.P = reg.param("EquipParamGem", erreg.load_paramdef(HERE / "paramdef" / "EquipParamGem.xml"))
        self.names = erreg.load_names(HERE / "names" / "EquipParamGem.txt")
        self.attr_fields = [f.name for f in self.P.pd.fields
                            if f.name.startswith("configurableWepAttr")]

    def _mask(self, r) -> int:
        mask = 0
        for i, f in enumerate(self.attr_fields):
            if self.P.get(r, f):
                mask |= 1 << i
        return mask

    def _groups(self, what: str) -> dict[int, list]:
        """Rows that have something to give, grouped by the weapon types they accept."""
        groups: dict[int, list] = {}
        for r in self.P.rows:
            if r.id not in self.names:
                continue
            has = (self.P.get(r, "swordArtsParamId") != -1) if what == "skill" else \
                  any(self.P.get(r, f"spEffectId{i}") != -1 for i in range(3))
            if has:
                groups.setdefault(self._mask(r), []).append(r)
        return groups

    def randomize_skills(self, rng: random.Random) -> list[str]:
        """Shuffle swordArtsParamId (the skill) among gems that accept the same weapon types."""
        P, names = self.P, self.names
        groups = self._groups("skill")
        n = sum(len(v) for v in groups.values())
        if n < 2:
            return ["# ashes: fewer than two gems with a skill, nothing changed"]
        lines = [f"# ashes: {n} gems with a skill, shuffled inside {len(groups)} weapon-type groups "
                 f"(EquipParamGem.swordArtsParamId)",
                 "# gem                                             <-  skill of"]
        for mask in sorted(groups):
            rows = groups[mask]
            old = {r.id: P.get(r, "swordArtsParamId") for r in rows}
            donors = rows[:]
            rng.shuffle(donors)
            for r, donor in zip(rows, donors):
                P.set(r, "swordArtsParamId", old[donor.id])
            for r, donor in zip(rows, donors):
                lines.append(f"{r.id:>8}  {names.get(r.id, '?'):<44} <-  {names.get(donor.id, '?')}")
        return lines

    def randomize_effects(self, rng: random.Random) -> list[str]:
        """Shuffle the spEffectId0-2 triple among gems that accept the same weapon types."""
        P, names = self.P, self.names
        groups = self._groups("effect")
        n = sum(len(v) for v in groups.values())
        if n < 2:
            return ["# ashes: fewer than two gems with an effect, nothing changed"]
        lines = [f"# ashes: {n} gems with an on-hit effect, the (spEffectId0,1,2) triple shuffled inside "
                 f"{len(groups)} weapon-type groups",
                 "# gem                                             <-  effect of"]
        for mask in sorted(groups):
            rows = groups[mask]
            old = {r.id: tuple(P.get(r, f"spEffectId{i}") for i in range(3)) for r in rows}
            donors = rows[:]
            rng.shuffle(donors)
            for r, donor in zip(rows, donors):
                for i in range(3):
                    P.set(r, f"spEffectId{i}", old[donor.id][i])
            for r, donor in zip(rows, donors):
                lines.append(f"{r.id:>8}  {names.get(r.id, '?'):<44} <-  {names.get(donor.id, '?')}")
        return lines