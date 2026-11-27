"""Append a textual rarity tag to item names in the patched msg archives.

The game's FMG strings contain no verified colour markup, so this pass uses an honest label instead:
``Iron Helmet [RARE]``.  The tag comes from that row's own ``rarity`` field (0..3 in the shipped
regulation), and is only added to names that already exist in the archive, so it composes with the
affinity names weapon_names.py generates in the same run.  A second run does not stack labels.

If a real in-game colour code is confirmed later, change LABELS to wrap the tag in it - the plumbing
here and in the reports does not need to change.
"""
from __future__ import annotations

import re
from pathlib import Path

import erreg
import talkmsg

HERE = Path(__file__).resolve().parent
LABELS = {0: "COMMON", 1: "UNCOMMON", 2: "RARE", 3: "LEGENDARY"}
# Weapon and protector ids overlap in the shipped tables, so the rarity map must stay per FMG.
TABLES = {"WeaponName": "EquipParamWeapon", "ProtectorName": "EquipParamProtector"}
PREFIXES = tuple(TABLES)
TAG_RE = re.compile(r" \[(?:" + "|".join(LABELS.values()) + r")\]$")


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
        self.rarity: dict[str, dict[int, str]] = {prefix: {} for prefix in PREFIXES}
        for prefix, table_name in TABLES.items():
            table = reg.param(table_name, erreg.load_paramdef(HERE / "paramdef" / f"{table_name}.xml"))
            for row in table.rows:
                label = LABELS.get(table.get(row, "rarity"))
                if label is not None:
                    self.rarity[prefix][row.id] = label

    def apply_to(self, src: Path, texts: dict) -> tuple[int, int]:
        """Add tags to `texts` for one archive; returns (names tagged, total rarity rows)."""
        current = read_names(src)
        for prefix, entries in texts.items():
            if prefix in current:
                current[prefix].update(entries)
        touched = 0
        for prefix in PREFIXES:
            if not current[prefix]:             # archive has no FMG with this prefix
                continue
            target = texts.setdefault(prefix, {})
            for tid, label in self.rarity[prefix].items():
                text = current[prefix].get(tid)
                if text is None or "[ERROR]" in text or "dummy" in text.lower():
                    continue
                base = TAG_RE.sub("", text)    # replace an old tag if the row's rarity changed
                tagged = f"{base} [{label}]"
                if current[prefix].get(tid) != tagged:
                    target[tid] = tagged
                    touched += 1
        return touched, sum(len(rows) for rows in self.rarity.values())


def add_armor_clone_names(src: Path, texts: dict, anchor: dict, names: dict) -> int:
    """Give cloned EquipParamProtector rows a name, anchored where their base id lives."""
    current = read_names(src)
    if not current["ProtectorName"]:
        return 0
    target = texts.setdefault("ProtectorName", {})
    for clone_id, (base_id, name) in names.items():
        target[clone_id] = name
        anchor[clone_id] = base_id
    return len(names)
