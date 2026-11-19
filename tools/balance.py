"""Post-run balance envelope: a short readout of how the randomised world turned out.

It reads the already-modified NpcParam and reports the spread of enemy HP and rune bounties, plus a
rough count of bullet sponges (HP above three times the median) and pushovers (below a third of it).
The point is a quick sanity check on a seed: if one number looks wrong, the whole run probably is.
"""
from __future__ import annotations

import statistics
from pathlib import Path

import erreg

HERE = Path(__file__).resolve().parent


def envelope(reg: erreg.Regulation) -> list[str]:
    N = reg.param("NpcParam", erreg.load_paramdef(HERE / "paramdef" / "NpcParam.xml"))
    hp = [N.get(r, "hp") for r in N.rows if N.get(r, "hp") > 0]
    runes = [N.get(r, "getSoul") for r in N.rows if N.get(r, "getSoul") > 0]
    lines = ["# balance envelope (this seed)"]
    if hp:
        med = statistics.median(hp)
        sponges = sum(1 for v in hp if v > 3 * med)
        pushovers = sum(1 for v in hp if v < med / 3)
        lines.append(f"# enemy HP: {len(hp)} enemies, {min(hp)}-{max(hp)} (median {med:.0f}); "
                     f"{sponges} sponges (>3x median), {pushovers} pushovers (<1/3 median)")
    if runes:
        med = statistics.median(runes)
        lines.append(f"# enemy runes: {len(runes)} enemies, {min(runes)}-{max(runes)} (median {med:.0f})")
    return lines
