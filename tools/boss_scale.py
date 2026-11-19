"""--boss-hp-scale / --boss-rune-scale / --couple-runes-to-hp.

A boss is an NpcParam row flagged isSoulGetByBoss (optionally widened by --boss-min-runes); see
bosses.py.  hp_scale and rune_scale multiply a boss's HP / rune bounty by a factor drawn from
U(lo,hi) (1.0,1.0 = off), so a boss that a shuffle turned weak can be kept scary.  couple recomputes
every enemy's bounty from its final HP (its original worth-per-HP), so a tougher enemy gives more runes
and a pushover fewer - the bounty tracks the rolled hit points.
"""
from __future__ import annotations

import random
from pathlib import Path

import bosses
import erreg

HERE = Path(__file__).resolve().parent


def boss_ids(N, min_runes: int = 0) -> set[int]:
    """The rows that count as bosses - one definition, shared with the loot boss-bonus (bosses.py)."""
    return bosses.boss_ids(N, min_runes)


def apply(reg: erreg.Regulation, rng: random.Random, boss: set[int], orig: dict,
          hp_scale, rune_scale, couple: bool) -> list[str]:
    """Scale boss HP/runes and/or couple runes to HP.  `orig` maps row id -> (vanilla hp, vanilla soul)."""
    from randomize import round_price  # local: randomize imports this module

    N = reg.param("NpcParam", erreg.load_paramdef(HERE / "paramdef" / "NpcParam.xml"))
    lines: list[str] = []
    if hp_scale and tuple(hp_scale) != (1.0, 1.0):
        lo, hi = hp_scale
        for r in N.rows:
            if r.id in boss:
                N.set(r, "hp", round(N.get(r, "hp") * rng.uniform(lo, hi)))
        lines.append(f"# boss HP x U({lo:g},{hi:g}): {len(boss)} bosses scaled")
    if couple and orig:
        # reads the CURRENT hp (already multiplied above when boss HP scaling ran first), so a scaled
        # boss also yields more runes; a later rune_scale then multiplies the coupled bounty on top
        for r in N.rows:
            oh, os_ = orig.get(r.id, (0, 0))
            if oh > 0:
                N.set(r, "getSoul", round(N.get(r, "hp") * os_ / oh))
        lines.append("# runes coupled to HP (each enemy's bounty tracks its hit points)")
    if rune_scale and tuple(rune_scale) != (1.0, 1.0):
        lo, hi = rune_scale
        for r in N.rows:
            if r.id in boss:
                N.set(r, "getSoul", round_price(N.get(r, "getSoul") * rng.uniform(lo, hi)))
        lines.append(f"# boss runes x U({lo:g},{hi:g}): {len(boss)} bosses scaled")
    return lines