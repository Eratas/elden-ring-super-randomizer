"""Which NpcParam rows are bosses - one definition for every pass that cares.

The official signal is NpcParam.isSoulGetByBoss (a 1-bit flag). A rune threshold is only an extra:
in a real regulation.bin the old `getSoul >= 5000` test caught 10 of 6915 rows while the flag marks
384, so both the boss multipliers and the loot boss-bonus use the flag, and --boss-min-runes adds an
optional rune threshold on top of it.
"""
from __future__ import annotations


def boss_ids(N, min_runes: int = 0) -> set[int]:
    """Row ids that count as bosses: the isSoulGetByBoss flag, or (optionally) a rune threshold.

    `min_runes` of 0 means "the flag alone"; a positive value also includes enemies worth at least that
    many runes in the unmodified game.
    """
    out: set[int] = set()
    for r in N.rows:
        if N.get(r, "isSoulGetByBoss") or (min_runes > 0 and N.get(r, "getSoul") >= min_runes):
            out.add(r.id)
    return out
