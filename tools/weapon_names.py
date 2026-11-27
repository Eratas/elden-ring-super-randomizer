"""Names for the affinity rows of somber weapons (--somber-infusable), in the game's own text.

The game shows "?WeaponName?" for a weapon whose id has no entry in WeaponName.fmg (msg/<language>/item_dlc02.msgbnd.dcx:
WeaponName.fmg holds the base game, WeaponName_dlc01.fmg Shadow of the Erdtree).  Vanilla names every affinity row of an
infusable weapon on its own (1000000 Dagger, 1000100 Heavy Dagger ... 1001200 Occult Dagger), but a
somber weapon has only its base row and so only one name.  --somber-infusable adds the 12 affinity rows; a weapon handed
out with one of them (--random-default-ash gives the weapons of lots / shops / classes random affinities) or infused at the
smith is then nameless (reported 2026-11-07: the Crystal Sword, 2150000).  Its description (WeaponCaption.fmg) is looked up
by the same id and is missing as well; WeaponInfo / WeaponEffect are not keyed by weapon id and need nothing.

This pass gives every affinity row of the output a name and a description when the archive has none for its id but has
them for the base weapon: the name is the base name with the language's own affinity affix, learned from the archive
itself (the most common prefix / suffix that turns a base name into its affinity name over every weapon named at all 13
ids: English "Heavy " ... "Occult "; the game uses "Bloody" / "Sharp" for a few weapons, the
majority pattern is taken; a gendered language gets the majority form), the description is the base weapon's.  Nothing
else in the archive changes.  A new id goes into the FMG that holds its base weapon (WeaponName.fmg / WeaponName_dlc01.fmg).
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path

import erreg
import talkmsg
from constants import AFFINITY_IDS as AFFINITIES
from textarchives import ITEM_ARCHIVE as ARCHIVE
from textarchives import MSG_DIR

HERE = Path(__file__).resolve().parent
FMG_NAME, FMG_CAPTION = "WeaponName", "WeaponCaption"
ERROR_MARK = "[ERROR]"                            # cut weapons are named "[ERROR]Heavy ...": not a pattern to learn from
# English fallback, in the game's own order.  A modded archive that does not name one weapon at all 13
# affinities used to abort the whole run; an English affinity plus the Paramdex name is readable in
# game, while "?WeaponName?" is not.
FALLBACK_AFFIX = {1: ("Heavy ", ""), 2: ("Keen ", ""), 3: ("Quality ", ""), 4: ("Fire ", ""),
                  5: ("Flame Art ", ""), 6: ("Lightning ", ""), 7: ("Sacred ", ""), 8: ("Magic ", ""),
                  9: ("Cold ", ""), 10: ("Poison ", ""), 11: ("Blood ", ""), 12: ("Occult ", "")}


def shipped_archives() -> list[Path]:
    """The item text archives shipped with the tool: MSG_DIR/<language>/item_dlc02.msgbnd.dcx."""
    return sorted(p for p in MSG_DIR.glob(f"*/{ARCHIVE}") if p.is_file())


def read_fmgs(path: Path) -> dict[str, dict[int, str]]:
    """{FMG prefix: the entries of <prefix>.fmg and <prefix>_dlc*.fmg together} for the two FMGs used here."""
    raw = path.read_bytes()
    bnd = erreg.read_bnd4(erreg.read_dcx(raw).data if raw[:4] == b"DCX\0" else raw)
    out: dict[str, dict[int, str]] = {FMG_NAME: {}, FMG_CAPTION: {}}
    for f in bnd.files:
        n = talkmsg.fmg_name(f)
        for prefix in out:
            if n == f"{prefix}.fmg" or (n.startswith(f"{prefix}_") and n.endswith(".fmg")):
                out[prefix].update(talkmsg.read_fmg(bnd.datas[f.index]))
    if not out[FMG_NAME]:
        raise SystemExit(f"{path}: no {FMG_NAME}*.fmg inside (the weapon names are in msg/<language>/{ARCHIVE})")
    return out


def affixes(names: dict[int, str]) -> dict[int, tuple[str, str]]:
    """affinity -> (prefix, suffix) that turns a base name into the affinity name in this language, learned from the
       weapons the archive names at all 13 ids (the most common pattern per affinity).  Missing patterns are left
       out: the caller fills them from FALLBACK_AFFIX instead of stopping the run."""
    bases = [b for b in names if b % 10000 == 0 and ERROR_MARK not in names[b]
             and all(b + a * 100 in names for a in AFFINITIES)]
    out: dict[int, tuple[str, str]] = {}
    for a in AFFINITIES:
        pats: Counter = Counter()
        for b in bases:
            base, var = names[b], names[b + a * 100]
            k = var.find(base)
            if k >= 0 and var != base and ERROR_MARK not in var:
                pats[(var[:k], var[k + len(base):])] += 1
        if pats:
            out[a] = pats.most_common(1)[0][0]
    return out


class WeaponNames:
    def __init__(self, reg: erreg.Regulation, archives: list[str]) -> None:
        self.W = reg.param("EquipParamWeapon", erreg.load_paramdef(HERE / "paramdef" / "EquipParamWeapon.xml"))
        self.base_names = erreg.load_names(HERE / "names" / "EquipParamWeapon.txt")
        self.archives = [Path(a) for a in archives]
        self.langs = [a.parent.name.lower() for a in self.archives]
        self.patches: list[tuple[Path, dict[str, dict[int, str]], dict[int, int]]] = []   # (archive, texts, anchor)

    def rows(self) -> list[int]:
        """Every affinity row of the weapon table (affinity 1-12, upgrade level 0)."""
        return [r.id for r in self.W.rows if r.id % 10000 and r.id % 100 == 0]

    def texts_for(self, archive: Path) -> tuple[dict[str, dict[int, str]], dict[int, int], str]:
        """What to write into `archive`: {WeaponName: {id: name}, WeaponCaption: {id: text}}, the base weapon of every id
           (where the new entry goes) and a one-line summary."""
        fm = read_fmgs(archive)
        names, caps = fm[FMG_NAME], fm[FMG_CAPTION]
        learned = affixes(names)
        affix = {a: learned.get(a, FALLBACK_AFFIX[a]) for a in AFFINITIES}
        new_names: dict[int, str] = {}
        new_caps: dict[int, str] = {}
        anchor: dict[int, int] = {}
        for rid in self.rows():
            b, a = rid - rid % 10000, rid % 10000 // 100
            base = names.get(b) or self.base_names.get(b)
            if rid in names or not base or a not in affix:
                continue
            pre, suf = affix[a]
            new_names[rid] = pre + base + suf
            anchor[rid] = b
            if rid not in caps and b in caps:
                new_caps[rid] = caps[b]
        example = next(iter(new_names.values()), "")
        detail = (f"{len(new_names)} affinity rows of {len(set(anchor.values()))} weapons get a name"
                  + (f" ({example!r}, ...)" if example else "") + f", {len(new_caps)} a description; affixes: "
                  + ", ".join(f"{a}={pre!r}+name+{suf!r}" if suf else f"{a}={pre!r}+name" for a, (pre, suf) in affix.items())
                  + (f" (fallback for {sorted(set(AFFINITIES) - set(learned))})" if learned.keys() != affix.keys() else ""))
        return {FMG_NAME: new_names, FMG_CAPTION: new_caps}, anchor, detail

    def prepare(self) -> list[str]:
        """Compute the texts for every archive (after every change to the weapon table); report lines."""
        lines = []
        self.patches = []
        for src in self.archives:
            texts, anchor, detail = self.texts_for(src)
            self.patches.append((src, texts, anchor))
            lines.append(f"# weapon names: {src}: {detail}")
        return lines
