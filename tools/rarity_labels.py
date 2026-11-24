"""Append a textual rarity tag to item names in the patched msg archives.

The game's FMG strings contain no verified colour markup, so this pass uses an honest label instead:
``Iron Helmet [RARE]``.  The tag comes from the row's own ``rarity`` field (0..3 in the shipped
regulation), and is only added to names that already exist in the archive, so it composes with the
affinity names weapon_names.py generates in the same run.  A second run does not double-tag.

If a real in-game colour code is confirmed later, change LABELS to wrap the tag in it - the plumbing
here and in the reports does not need to change.
"""
from __future__ import annotations

from pathlib import Path

import erreg
import talkmsg

HERE = Path(__file__).resolve().parent
LABELS = {0: "COMMON", 1: "UNCOMMON", 2: "RARE", 3: "LEGENDARY"}
PREFIXES = ("WeaponName", "ProtectorName")


def read_names(path: Path) -> dict[str, dict[int, str]]:
    """{prefix: {id: text}} for the name FMGs, the same way weapon_names.read_fmgs works."""
    raw = path.read_bytes()
    bnd = erreg.read_bnd4(erreg.read_dcx(raw).data if raw[:4] == b"DCX\0" else raw)
    out: dict[str, dict[int, str]] = {prefix: {} for prefix in PREFIXES}
    for f in bnd.files:
        name = talkmsg.fmg_name(f)
        for prefix in PREFIXES:
            if name == f"{prefix}.fmg" or (name.startswith(f"{prefix}_") and name.endswith(".fmg")):
                out[prefix].update(talkmsg.read_fmg(bnd.datas[f.index]))
    return out


class RarityLabels:
    def __init__(self, reg: erreg.Regulation) -> None:
        rarity: dict[int, str] = {}
        for table_name in ("EquipParamWeapon", "EquipParamProtector"):
            table = reg.param(table_name, erreg.load_paramdef(HERE / "paramdef" / f"{table_name}.xml"))
            for row in table.rows:
                label = LABELS.get(table.get(row, "rarity"))
                if label is not None:
                    rarity[row.id] = label
        self.rarity = rarity

    def apply_to(self, src: Path, texts: dict) -> tuple[int, int]:
        """Add tags to `texts` for one archive; returns (names tagged, rows with a rarity)."""
        current = read_names(src)
        for prefix, entries in texts.items():
            if prefix in current:
                current[prefix].update(entries)
        touched = 0
        for prefix in PREFIXES:
            target = texts.setdefault(prefix, {})
            for tid, label in self.rarity.items():
                text = current[prefix].get(tid)
                if text is None or text.startswith("["):
                    continue
                suffix = f" [{label}]"
                if text.endswith(suffix):
                    continue
                target[tid] = text + suffix
                touched += 1
        return touched, len(self.rarity)
