"""Borderlands-style loot: the manifest the runtime mod reads to reroll a weapon on every pickup.

The static tool cannot change an item after the game has loaded the regulation: a lot row names one
weapon id, and every pickup of that row gives the same id.  A weapon id is
`base + affinity * 100 + upgrade level`, the affinity row carries the stats, scaling and status
effects, and the upgrade level is applied through ReinforceParamWeapon, so the game can be handed any
(affinity, level) of a weapon that has a row at `base + affinity * 100`.  The runtime mod
(`mods/loot-variants`) intercepts the game's item-give call and rewrites that id per pickup, then
attaches a random Ash of War that the row can actually use.

This pass writes the manifest that makes those choices safe.  Five record kinds:

    bind     <regulation size> <fnv1a64>
    defaults <ash chance %> <level curve> <reroll affinity 0|1> <reroll level 0|1>
    weapon   <base> <max level> <affinity mask> <gem class for affinity 0> ... <gem class for 12>
    armor    <base> <max level>
    gems     <class> <gem id> <gem id> ...

`bind` is a cheap consistency tag over the exact bytes of the regulation this manifest was made
for.  The DLL hashes the regulation.bin it finds and stays inert on a mismatch, so a manifest left
over from a different run (e.g. one with --somber-infusable) cannot hand out ids whose rows do not
exist.  FNV-1a is deliberately not cryptographic: this is a mismatch check, not a trust boundary.

`affinity mask` is the set of affinity rows that exist for the weapon (bit 0 = Standard), so the mod
never asks for a row the table does not have.  `max level` is the weapon's own ceiling (25 for a
standard weapon, 10 for a somber one, 0 for a unique one that cannot be reinforced) - the same rule
--random-loot-levels rolls against, and it is read from the pristine table because
--somber-infusable adds twelve affinity rows to a weapon that still tops out at +10.

A gem class is the Ash pool of one weapon row at one affinity: the Ashes of War whose `canMountWep`
bit covers the row's weapon type *and* whose `configurableWepAttr` bit is set for that affinity.
Those are the two flags the smithing table itself checks, so a rerolled weapon never gets a skill it
cannot play; `-1` means no Ash.  `--random-movesets` keeps `configurableWepAttr` in sync with the new
animations (weapons.py `_restrict_ash_affinities`), so the pool follows the moveset shuffle.

A weapon where nothing can change (one affinity, no upgrades, no Ash) is left out of the manifest, so
the mod keeps unique quest weapons exactly as the table has them.

Armour has no affinity rows: the same helmet can only be +0..+10.  Those levels are real stats (damage
negation and resistances scale through ReinforceParamProtector), so the runtime mod rerolls just the
level while keeping the piece - and therefore the appearance - identical.  Only pieces that can be
reinforced are listed; the give id is `0x10000000 | level << 24 | base`, the layout the game uses for
upgraded armour (and the same `level << 24` field ReinforceParamProtector stores).

The mod is optional.  Without it the regulation is still a complete run and this option only writes
the manifest; with it, `loot_variants.txt` has to sit next to `loot_variants.dll` or next to
regulation.bin.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import erreg
import loot
import weapons

HERE = Path(__file__).resolve().parent
MANIFEST_NAME = "loot_variants.txt"
REPORT_NAME = "variants.txt"
MAGIC = "MADLOVE-LOOT-VARIANTS"
FORMAT_VERSION = 2                  # v2 adds `armor` lines; v1 manifests stay readable
NO_ASH = -1
AFFINITIES = 13                     # Standard, Heavy .. Occult: the only ids the game resolves
ASH_CHANCE = 50                     # default of the runtime mod; the ini can override it
CURVES = ("even", "common", "legendary")
FNV_OFFSET, FNV_PRIME, MASK64 = 0xCBF29CE484222325, 0x100000001B3, 0xFFFFFFFFFFFFFFFF


def fingerprint(data: bytes) -> str:
    """`bind` value for one regulation: its byte length and 64-bit FNV-1a, in one string."""
    value = FNV_OFFSET
    for byte in data:
        value = ((value ^ byte) * FNV_PRIME) & MASK64
    return f"{len(data)} {value:016x}"


@dataclass(frozen=True)
class Gem:
    """One Ash of War row: the gem id, the skill it grants, its mount bits and its affinity bits."""

    id: int
    skill: int
    bits: int                       # canMountWep_* : weapon types the ash fits
    attr: int                       # configurableWepAttr00..12 : affinities the ash may be applied at


@dataclass(frozen=True)
class Entry:
    """One weapon the runtime mod may reroll."""

    base: int
    max_level: int
    affinity_mask: int
    gem_class: tuple[int, ...]      # index = affinity 0..12, -1 = no Ash for that row

    @property
    def affinities(self) -> int:
        return self.affinity_mask.bit_count()

    @property
    def ash_rows(self) -> int:
        return sum(1 for c in self.gem_class if c != NO_ASH)

    @property
    def rollable(self) -> bool:
        """False for a weapon the mod would hand back unchanged."""
        return self.affinities > 1 or self.max_level > 0 or self.ash_rows > 0


class Variants:
    def __init__(self, reg: erreg.Regulation, wp: weapons.Weapons | None = None,
                 ceilings: dict[int, int] | None = None, curve: str = "common") -> None:
        self.reg = reg
        self.W = reg.param("EquipParamWeapon",
                           erreg.load_paramdef(HERE / "paramdef" / "EquipParamWeapon.xml"))
        # `Weapons` owns the moveset knowledge (which row got which animation category and, with
        # --weptype-follows, which type); reuse the instance the weapon pass already built.
        self.wp = wp or weapons.Weapons(reg)
        # The ceilings have to come from the table as it was before --somber-infusable added rows to
        # somber weapons: a 13-row somber weapon is still a +10 weapon.  randomize.py snapshots them
        # before the weapon pass and passes them in; a standalone run has no pass to worry about.
        self.ceilings = ceilings if ceilings is not None else loot.ceilings(self.W)
        self.curve = curve if curve in CURVES else "common"
        self.gems = self._gems()
        self._class_of: dict[tuple[int, ...], int] = {}
        self.class_gems: list[tuple[int, ...]] = []
        self.entries = self._build()
        self.armor = self._build_armor()

    # ------------------------------------------------------------ the armour
    def _build_armor(self) -> dict[int, int]:
        """base id -> highest reinforcement level, for named pieces the smith can actually upgrade.

        Armour ids are all below 0x1000000 and every row uses reinforceTypeId 0, whose
        ReinforceParamProtector table runs +0..+10.  The 45 rows with materialSetId -1 are cut or
        unreinforceable placeholders and stay exactly as dropped.
        """
        import gear
        P = gear.Armour(self.reg).P
        out: dict[int, int] = {}
        for row in P.rows:
            if P.get(row, "weight") <= 0 or P.get(row, "materialSetId") == -1:
                continue
            out[row.id] = 10
        return out

    # ------------------------------------------------------------ the Ash pool
    def _gems(self) -> list[Gem]:
        """Every real Ash of War row: a named skill, a mount mask and no test/NPC row."""
        G = self.wp.G
        off = G.pd["canMountWep_Dagger"].offset
        attr = [f"configurableWepAttr{a:02d}" for a in range(AFFINITIES)]
        out: list[Gem] = []
        for r in G.rows:
            name = self.wp.gem_names.get(r.id, "")
            if not name.startswith("Ash of War:"):
                continue
            skill = G.get(r, "swordArtsParamId")
            if skill == -1 or G.get(r, "sortId") == 999999:
                continue
            if name.split(":", 1)[1].strip() in ("", "No Skill"):
                continue
            bits = int.from_bytes(bytes(r.data[off:off + 8]), "little")
            mask = 0
            for a, field in enumerate(attr):
                if G.get(r, field):
                    mask |= 1 << a
            if bits and mask:
                out.append(Gem(r.id, skill, bits, mask))
        return out

    def _intern(self, ids: tuple[int, ...]) -> int:
        """A stable class id for a gem set, so the manifest stores each distinct pool once."""
        key = tuple(sorted(set(ids)))
        if key not in self._class_of:
            self._class_of[key] = len(self.class_gems)
            self.class_gems.append(key)
        return self._class_of[key]

    def _class_for(self, row, affinity: int) -> int:
        """The Ash pool of one weapon row at one affinity, or NO_ASH when it cannot take one."""
        if self.W.get(row, "gemMountType") != 2:
            return NO_ASH                     # fixed skill or no Ash at all
        bit = weapons.WEPTYPE_BIT.get(self.W.get(row, "wepType"))
        if bit is None:
            return NO_ASH
        # One Ash per skill: two gem rows that grant the same skill are one choice, not two.
        by_skill: dict[int, int] = {}
        for g in self.gems:
            if (g.bits >> bit) & 1 and (g.attr >> affinity) & 1:
                by_skill.setdefault(g.skill, g.id)
        allowed = tuple(sorted(by_skill.values()))
        return self._intern(allowed) if allowed else NO_ASH

    # ------------------------------------------------------------ the weapons
    def _build(self) -> list[Entry]:
        out: list[Entry] = []
        for base in self.wp.bases():
            if not self.wp.named(base):
                continue
            mask = 0
            classes = [NO_ASH] * AFFINITIES
            for a in self.wp.variants(base):
                mask |= 1 << a
                classes[a] = self._class_for(self.W.by_id[base + a * 100], a)
            entry = Entry(base, self.ceilings.get(base, 0), mask, tuple(classes))
            if entry.rollable:
                out.append(entry)
        return out

    def name(self, base: int) -> str:
        return self.wp.names.get(base, f"weapon {base}")

    # ------------------------------------------------------------ the files
    def manifest(self, bind: str | None = None) -> list[str]:
        """The machine-readable file the DLL parses."""
        out = [f"{MAGIC} {FORMAT_VERSION}",
               "# generated by the Elden Ring Super Randomizer: keep this file next to loot_variants.dll"]
        if bind is not None:
            out += ["# bind <regulation size> <fnv1a64>: refuse a manifest from another run",
                    f"bind {bind}"]
        out += ["# defaults <ash chance %> <level curve> <reroll affinity> <reroll level>",
                f"defaults {ASH_CHANCE} {self.curve} 1 1",
                "# weapon <base> <max level> <affinity mask> <gem class for affinity 0..12>"]
        for e in self.entries:
            cells = " ".join(str(e.gem_class[a]) if (e.affinity_mask >> a) & 1 else "-"
                             for a in range(AFFINITIES))
            out.append(f"weapon {e.base} {e.max_level} {e.affinity_mask} {cells}")
        out.append("# armor <base> <max level> (same piece, different reinforcement)")
        for base, top in sorted(self.armor.items()):
            out.append(f"armor {base} {top}")
        out.append("# gems <class> <gem id> ...")
        for i, ids in enumerate(self.class_gems):
            out.append(f"gems {i} " + " ".join(str(g) for g in ids))
        return out

    def write(self, path: Path, bind: str | None = None) -> int:
        """Write the manifest and return its size in bytes (UTF-8, LF line endings)."""
        body = "\n".join(self.manifest(bind)) + "\n"
        path.write_text(body, encoding="utf-8", newline="\n")
        return len(body.encode("utf-8"))

    def lines(self) -> list[str]:
        """The human report: what the runtime mod may roll, weapon by weapon."""
        rollable = sum(1 for e in self.entries if e.affinities > 1)
        ash_rows = sum(e.ash_rows for e in self.entries)
        choices = sum(len(self.class_gems[c]) for e in self.entries for c in e.gem_class if c != NO_ASH)
        return [f"# loot variants: {len(self.entries)} weapons the runtime mod rerolls "
                f"({rollable} with more than one affinity), {ash_rows} rows with an Ash pool "
                f"({choices} weapon/Ash pairs in {len(self.class_gems)} distinct pools); "
                f"{len(self.armor)} armour pieces reroll their +0..+10 level",
                f"# ash chance {ASH_CHANCE}%, level curve {self.curve}, ids stay inside "
                f"base + affinity*100 + level (weapons) / category+level+base (armour)",
                "# base      weapon                                   levels  affinities  ashes",
                *[f"{e.base:>9}  {self.name(e.base):<40} 0-{e.max_level:<4} {e.affinities:>2}          "
                  f"{e.ash_rows:>2}" for e in self.entries]]


def main(argv: list[str]) -> int:
    """python tools/loot_variants.py <regulation.bin> [out.txt] - regenerate a manifest by hand."""
    if len(argv) < 2:
        print("usage: loot_variants.py <regulation.bin> [loot_variants.txt]")
        return 2
    source = Path(argv[1])
    reg = erreg.Regulation(source)
    v = Variants(reg)
    out = Path(argv[2]) if len(argv) > 2 else Path(MANIFEST_NAME)
    size = v.write(out, bind=fingerprint(source.read_bytes()))
    print("\n".join(v.lines()))
    print(f"# wrote {out} ({size} bytes)")
    return 0


if __name__ == "__main__":
    import sys

    raise SystemExit(main(sys.argv))
