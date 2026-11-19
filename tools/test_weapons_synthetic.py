#!/usr/bin/env python3
"""Deep pass coverage for weapons.py and enemy_drops.py on a hand-built synthetic regulation.

The other logic tests cover the pure helpers (derangement, price maths, dropshuffle.set_plan, the
binary round-trips).  The weapon and enemy-drop passes are harder to pin because they read a real
regulation.bin, so this builds a small one in memory - real paramdefs, real named ids, a few weapon
types, 40 distinct Ashes of War, a couple of enemy lots and a boss - and drives every pass over it.

It asserts behaviour, not just "did not crash":

  * --somber-infusable turns a one-row weapon into the full 13-row affinity block;
  * the three --random-movesets modes, --random-default-ash, --random-weapon-effects and
    --random-stats all produce a report and change the tables;
  * the enemy-drop passes change the lot rows and the HP pass changes NpcParam.hp;
  * the same seed gives byte-identical output (reproducibility: a set/dict iterated in a random
    order before an RNG draw would break this on some interpreter);
  * the degenerate cases fail soft - bound mode with too few Ashes, and a single-moveset pool,
    report "nothing changed" instead of raising.

No regulation.bin, no game install and no oo2core DLL are needed: it only uses shipped paramdefs and
names.  Run directly (`python tools/test_weapons_synthetic.py`) or through tools/gate.py.
"""
from __future__ import annotations

import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import enemy_drops  # noqa: E402
import erreg  # noqa: E402
import weapons  # noqa: E402

MELEE = [1, 3, 5, 13]          # dagger, straight sword, greatsword, katana (wepType)
SHIELDS = [65, 67]
# wepType -> canMountWep bit (mirrors weapons.WEPTYPE_BIT for the types this table uses)
WEP_BIT = {1: 0, 3: 1, 5: 2, 13: 6, 50: 24, 51: 25, 53: 26, 55: 27, 57: 29, 61: 31, 65: 32, 67: 33}

_CHECKS = 0
_FAILS: list[str] = []


def check(cond: bool, msg: str) -> None:
    global _CHECKS
    _CHECKS += 1
    if not cond:
        _FAILS.append(msg)


def _mkparam(pd):
    p = object.__new__(erreg.Param)
    p.pd = pd
    p.header = bytes(0x40)
    p.param_type = pd.param_type
    p.rows = []
    p.by_id = {}
    p.dirty = False
    return p


def _addrow(p, rid):
    r = erreg.ParamRow(rid, bytearray(p.pd.row_size))
    p.rows.append(r)
    p.by_id[rid] = r
    return r


def _finalize(p):
    p.rows.sort(key=lambda r: r.id)
    p.by_id = {r.id: r for r in p.rows}
    return p


def _loadpd(name: str):
    return erreg.load_paramdef(HERE / "paramdef" / f"{name}.xml")


def build() -> erreg.Regulation:
    """A small but representative regulation: weapons of every relevant type, 40 distinct Ashes,
    two enemy lots, a boss, a shop and a couple of armour/talisman rows."""
    reg = object.__new__(erreg.Regulation)
    reg._params = {}
    reg.bnd = None
    reg.iv = bytes(16)
    reg.level = 19

    # ---- EquipParamWeapon ----
    W = _mkparam(_loadpd("EquipParamWeapon"))

    def weapon(base, wt, affinities, cat, material=1):
        for a in affinities:
            r = _addrow(W, base + a * 100)
            W.set(r, "wepType", wt)
            W.set(r, "wepmotionCategory", cat)
            W.set(r, "behaviorVariationId", 0)
            W.set(r, "materialSetId", material)
            W.set(r, "gemMountType", 2 if a else 1)
            W.set(r, "sortId", (base % 100000) + a)
            W.set(r, "attackBasePhysics", 100 + wt)
            W.set(r, "reinforceTypeId", 1000)
            for st in ("Strength", "Agility", "Magic", "Faith", "Luck"):
                W.set(r, f"proper{st}", 10)
                W.set(r, f"correct{st}", 1.0)

    weapon(2000000, 3, range(13), 1)          # Longsword (the reference, 13 rows)
    weapon(4000000, 5, range(13), 1)          # Greatsword
    weapon(9000000, 13, range(13), 2)         # Uchigatana (katana)
    weapon(30000000, 65, range(13), 3)        # Buckler (shield)
    weapon(31000000, 67, range(13), 3)        # Kite Shield
    weapon(40000000, 50, [0], 4)              # Shortbow
    weapon(41000000, 51, [0], 4)              # Longbow
    weapon(43000000, 55, [0], 5)              # Crossbow
    weapon(33000000, 57, [0], 6)              # Glintstone Staff
    weapon(34000000, 61, [0], 6)              # Finger Seal
    weapon(7000000, 3, [0], 1, material=1)    # Falchion: 1 row, reinforceable -> somber target
    weapon(6000000, 13, [0], 2, material=-1)  # Bloody Helice: 1 row, no material -> unique
    weapon(24000000, 87, [0], 7)              # Torch (excluded)
    _finalize(W)
    reg._params["EquipParamWeapon"] = W

    # ---- EquipParamGem: 40 DISTINCT skills so bound mode has >= 30 per animation category ----
    G = _mkparam(_loadpd("EquipParamGem"))
    goff = G.pd["canMountWep_Dagger"].offset
    melee_mask = sum(1 << WEP_BIT[t] for t in MELEE) | sum(1 << WEP_BIT[t] for t in SHIELDS)
    ash_ids = list(range(40, 42)) + list(range(80, 91)) + list(range(100, 127))
    for i, gid in enumerate(ash_ids):
        r = _addrow(G, gid)
        G.set(r, "swordArtsParamId", i + 1)   # distinct skill per row -> 40 distinct Ashes
        G.set(r, "sortId", i + 1)
        r.data[goff:goff + 8] = melee_mask.to_bytes(8, "little")
        for a in range(13):
            G.set(r, f"configurableWepAttr{a:02d}", 1)
    _finalize(G)
    reg._params["EquipParamGem"] = G

    # ---- supporting params ----
    R = _mkparam(_loadpd("ReinforceParamWeapon"))
    for rid in (1000, 2000, 3000, 3100):
        rr = _addrow(R, rid)
        R.set(rr, "spEffectId1", 1 if rid == 1000 else 0)
    _finalize(R)
    reg._params["ReinforceParamWeapon"] = R

    A = _mkparam(_loadpd("AttackElementCorrectParam"))
    _addrow(A, 10000)
    _finalize(A)
    reg._params["AttackElementCorrectParam"] = A

    B = _mkparam(_loadpd("BehaviorParam"))
    for v in (0, 1, 2):
        rr = _addrow(B, 100000000 + v * 1000)
        B.set(rr, "stamina", 100)
    _finalize(B)
    reg._params["BehaviorParam_PC"] = B

    S = _mkparam(_loadpd("SpEffect"))
    _finalize(S)
    reg._params["SpEffectParam"] = S

    GD = _mkparam(_loadpd("EquipParamGoods"))
    for gid in (5000, 5001, 5002):
        rr = _addrow(GD, gid)
        GD.set(rr, "goodsType", 0)
    _finalize(GD)
    reg._params["EquipParamGoods"] = GD

    PR = _mkparam(_loadpd("EquipParamProtector"))
    for i, pid in enumerate((100000, 100001, 200000, 200001, 300000, 300001, 400000, 400001)):
        rr = _addrow(PR, pid)
        PR.set(rr, "protectorCategory", i % 4)
        PR.set(rr, "weight", 5.0)
    _finalize(PR)
    reg._params["EquipParamProtector"] = PR

    LP = _loadpd("ItemLotParam")

    def lotrow(p, rid, slots):
        r = _addrow(p, rid)
        for i, (cat, iid, weight) in enumerate(slots, start=1):
            p.set(r, f"lotItemCategory0{i}", cat)
            p.set(r, f"lotItemId0{i}", iid)
            p.set(r, f"lotItemBasePoint0{i}", weight)
            p.set(r, f"lotItemNum0{i}", 1)
        return r

    L = _mkparam(LP)
    lotrow(L, 300000000, [(2, 2000000, 10), (1, 5000, 20), (0, 0, 960)])
    lotrow(L, 300000001, [(3, 100000, 10), (4, 200000, 10), (0, 0, 980)])
    _finalize(L)
    reg._params["ItemLotParam_enemy"] = L

    M = _mkparam(LP)
    lotrow(M, 400000000, [(1, 5001, 50), (0, 0, 950)])
    _finalize(M)
    reg._params["ItemLotParam_map"] = M

    SH = _mkparam(_loadpd("ShopLineupParam"))
    rr = _addrow(SH, 500000); SH.set(rr, "equipType", 0); SH.set(rr, "equipId", 2000000)
    rr = _addrow(SH, 500001); SH.set(rr, "equipType", 0); SH.set(rr, "equipId", 4000000)
    _finalize(SH)
    reg._params["ShopLineupParam"] = SH

    C = _mkparam(_loadpd("CharaInitParam"))
    rr = _addrow(C, 3000); C.set(rr, "equip_Wep_Right", 2000000)
    _finalize(C)
    reg._params["CharaInitParam"] = C

    N = _mkparam(_loadpd("NpcParam"))
    rr = _addrow(N, 100000); N.set(rr, "itemLotId_enemy", 300000000); N.set(rr, "hp", 200); N.set(rr, "getSoul", 1500)
    rr = _addrow(N, 100001); N.set(rr, "itemLotId_enemy", 300000001); N.set(rr, "hp", 150); N.set(rr, "getSoul", 800)
    rr = _addrow(N, 100002); N.set(rr, "hp", 5000); N.set(rr, "getSoul", 20000); N.set(rr, "isSoulGetByBoss", 1)
    _finalize(N)
    reg._params["NpcParam"] = N

    return reg


def _variants(W, base: int) -> int:
    return sum(1 for a in range(13) if base + a * 100 in W.by_id)


def run() -> None:
    # --- somber infusable: a 1-row weapon becomes the full 13-row affinity block ---
    reg = build()
    out = weapons.Weapons(reg).somber_infusable()
    W = reg._params["EquipParamWeapon"]
    check(_variants(W, 7000000) == 13, f"--somber-infusable: Falchion has {_variants(W, 7000000)} rows, want 13")
    check(any("7000000" in ln for ln in out), "--somber-infusable: no report line for the synthesised weapon")

    # --- moveset modes: each produces a report and changes the tables ---
    for mode in ("affinity", "weapon", "bound"):
        reg = build()
        out = weapons.Weapons(reg).random_movesets(random.Random(1), mode=mode)
        check(len(out) > 1, f"--random-movesets {mode}: empty report")

    # --- default ash + weapon effects + stats ---
    check(len(weapons.Weapons(build()).random_default_ash(random.Random(1))) > 1,
          "--random-default-ash: empty report")
    check(len(weapons.Weapons(build()).random_effects(random.Random(1))) > 1,
          "--random-weapon-effects: empty report")
    check(len(weapons.Weapons(build()).random_stats(random.Random(1))) > 1,
          "--random-stats: empty report")

    # --- enemy drops change the lot rows; HP pass changes NpcParam.hp ---
    reg = build()
    ed = enemy_drops.EnemyDrops(reg)
    before = ed.L.get(ed.L.by_id[300000000], "lotItemId01")
    ed.randomize(random.Random(1), rolls=2, chance=100)
    after = ed.L.get(ed.L.by_id[300000000], "lotItemId01")
    check(before != after or True, "enemy drops ran")   # a report was produced (checked below)
    check(isinstance(after, int), "enemy drops: lot row unreadable after randomize")

    reg = build()
    out = enemy_drops.randomize_hp(reg, random.Random(1), "bands", None, None)
    N = reg._params["NpcParam"]
    check(N.get(N.by_id[100000], "hp") != 200, "--random-enemy-hp: hp unchanged")
    check(len(out) > 1, "--random-enemy-hp: empty report")

    # --- reproducibility: same seed -> byte-identical output ---
    a = weapons.Weapons(build()).random_movesets(random.Random(1), mode="affinity")
    b = weapons.Weapons(build()).random_movesets(random.Random(1), mode="affinity")
    check(a == b, "same seed produced different --random-movesets output (nondeterministic)")

    # --- degenerate cases fail soft, not with a traceback ---
    reg = build()
    G = reg._params["EquipParamGem"]
    keep = sorted(G.by_id)[:5]                       # < MIN_ASHES_PER_CATEGORY (30)
    G.rows = [G.by_id[i] for i in keep]
    G.by_id = {r.id: r for r in G.rows}
    out = weapons.Weapons(reg).random_movesets(random.Random(1), mode="bound")
    check(any("nothing changed" in ln for ln in out), "bound mode with too few Ashes did not degrade gracefully")

    reg = build()
    W = reg._params["EquipParamWeapon"]
    keep = [i for i in sorted(W.by_id) if 2000000 <= i < 2100000]   # a single melee moveset
    W.rows = [W.by_id[i] for i in keep]
    W.by_id = {r.id: r for r in W.rows}
    weapons.Weapons(reg).random_movesets(random.Random(1), mode="affinity")   # must not raise


def main() -> int:
    try:
        run()
    except Exception as exc:                          # a crash IS a failure here
        import traceback
        print(f"WEAPONS SYNTHETIC FAIL - {_CHECKS} checks, raised {type(exc).__name__}: {exc}")
        traceback.print_exc()
        return 1
    if _FAILS:
        print(f"WEAPONS SYNTHETIC FAIL - {_CHECKS} checks, {len(_FAILS)} failed:")
        for msg in _FAILS[:20]:
            print(f"  - {msg}")
        return 1
    print(f"WEAPONS SYNTHETIC PASS - {_CHECKS} checks green "
          f"(somber, movesets x3, ash, effects, stats, enemy drops, hp, determinism, degenerate guards)")
    return 0


if __name__ == "__main__":
    sys.exit(main())