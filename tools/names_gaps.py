"""--goods-name-gaps: warn about usable goods that have no entry in the names file.

The tool reads goods names from tools/names/EquipParamGoods.txt.  Where the game has an item the
tool reports but the file has no name for it, the reports show the id where a name would go - the
'?'-style names the game itself uses for undiscovered items.  The pass lists those rows: it
changes nothing (a warning, not a rewrite).
"""
from __future__ import annotations

from pathlib import Path

import erreg

HERE = Path(__file__).resolve().parent


def goods_gaps(reg: erreg.Regulation) -> list[str]:
    """The report: usable goods rows (goodsType 0) with no name in tools/names/EquipParamGoods.txt."""
    G = reg.param("EquipParamGoods", erreg.load_paramdef(HERE / "paramdef" / "EquipParamGoods.xml"))
    names = erreg.load_names(HERE / "names" / "EquipParamGoods.txt")
    missing = [r for r in G.rows if G.get(r, "goodsType") == 0 and r.id not in names]
    lines = [f"# goods name gaps: {len(missing)} usable goods have no entry in tools/names/EquipParamGoods.txt "
             f"(their reports show the id instead of a name)",
             "# id  [goods]  iconId  sortId  maxNum"]
    for r in missing:
        lines.append(f"{r.id:>9}  [goods {r.id % 100000}]  icon={G.get(r, 'iconId')}  sort={G.get(r, 'sortId')}"
                     f"  num={G.get(r, 'maxNum')}")
    return lines
