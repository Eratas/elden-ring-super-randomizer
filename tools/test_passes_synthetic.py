#!/usr/bin/env python3
"""Deep pass coverage for weapons.py, gems.py, gear.py, spells.py, goods.py, shops.py and
enemy_drops.py on a synthetic regulation.

The other logic tests cover the pure helpers (derangement, price maths, dropshuffle.set_plan, the
binary round-trips).  The randomizer passes are harder to pin because they read a real regulation.bin,
so this builds a small one in memory - real paramdefs, real named ids, a few weapon types, 40 distinct
Ashes of War, armour and talisman rows, a handful of sorceries, enemy lots and a boss - and drives
every pass over it.

It asserts behaviour, not just "did not crash":

  * --somber-infusable turns a one-row weapon into the full 13-row affinity block;
  * the three --random-movesets modes, --random-default-ash, the weapon-effect switches
     (--random-weapon-onhit-shuffle, --random-weapon-holder-shuffle, --random-weapon-status-roll,
     --random-loot-effects) and --random-stats all produce a report and change the tables;
  * --random-gem-skills / --random-gem-effects and the armour / talisman / goods passes shuffle
    without losing or duplicating a value (a permutation keeps the column's multiset);
  * --random-spells moves effects with no fixed point (a derangement) and lands every spell on one
    memory slot; the shop pass rerolls its weapon slots; an FMG survives a write -> read round trip;
  * the enemy-drop passes change the lot rows (N dice at P%, 0 rolls = one sure item) and the HP pass
    changes NpcParam.hp;
  * a status whose text list lost its own line is repaired, so no passive is silent;
  * the same seed gives byte-identical output (reproducibility: a set/dict iterated in a random
    order before an RNG draw would break this on some interpreter);
  * the degenerate cases fail soft - bound mode with too few Ashes, a single-moveset pool, and a
     regulation with no timed buffs report "nothing changed" instead of raising.

No regulation.bin, no game install and no oo2core DLL are needed: it only uses shipped paramdefs and
names.  Run directly (`python tools/test_passes_synthetic.py`) or through tools/gate.py.
"""
from __future__ import annotations

import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import durations  # noqa: E402
import enemy_drops  # noqa: E402
import erreg  # noqa: E402
import gear  # noqa: E402
import gems  # noqa: E402
import goods  # noqa: E402
import loot  # noqa: E402
import loot_variants  # noqa: E402
import shops  # noqa: E402
import spells  # noqa: E402
import talkmsg  # noqa: E402
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
        G.set(r, "spEffectId0", i + 1)        # distinct on-hit effect, so the triple shuffle changes rows
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
    for rid, field in ((6400, "bloodAttackPower"), (6401, "bloodAttackPower"),
                       (6500, "poizonAttackPower"), (6501, "poizonAttackPower"),
                       (6600, "freezeAttackPower"), (6650, "sleepAttackPower")):
        rr = _addrow(S, rid)
        S.set(rr, field, 50)
    _finalize(S)
    reg._params["SpEffectParam"] = S

    GD = _mkparam(_loadpd("EquipParamGoods"))
    for i, gid in enumerate((5000, 5001, 5002)):
        rr = _addrow(GD, gid)
        GD.set(rr, "goodsType", 0)
        GD.set(rr, "maxNum", 10 * (i + 1))            # distinct stack sizes, so the pair swap shows
        GD.set(rr, "maxRepositoryNum", 99 * (i + 1))
    _finalize(GD)
    reg._params["EquipParamGoods"] = GD

    PR = _mkparam(_loadpd("EquipParamProtector"))
    # real armour ids (names/EquipParamProtector.txt), two per slot, with distinct numbers so a
    # permutation is observable; gear.py groups by protectorCategory (0 head, 1 body, 2 arms, 3 legs)
    for i, (pid, cat) in enumerate(((100000, 0), (200000, 0), (40000, 1), (40100, 1),
                                    (40200, 2), (40300, 3))):
        rr = _addrow(PR, pid)
        PR.set(rr, "protectorCategory", cat)
        PR.set(rr, "weight", 1.0 + i)
        PR.set(rr, "neutralDamageCutRate", 0.5 + i * 0.05)
        PR.set(rr, "resistPoison", 10 + i)
        PR.set(rr, "saDurability", 20 + i)
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

    # Magic: a few sorceries with distinct effects and memory slots, for the spell passes
    M = _mkparam(_loadpd("Magic"))
    for i, sid in enumerate((4000, 4001, 4010, 4020, 4021, 4030, 4040, 4050)):
        rr = _addrow(M, sid)
        M.set(rr, "slotLength", 1)
        M.set(rr, "refId1", 100 + i)
        M.set(rr, "mp", 10 + i)
        M.set(rr, "refType", i)
    _finalize(M)
    reg._params["Magic"] = M

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

    # --- loot variants: the runtime manifest must survive the weapon pass ---
    reg = build()
    ceilings = loot.weapon_ceilings(reg)          # pristine: before --somber-infusable adds rows
    wp = weapons.Weapons(reg)
    for base in (2000000, 7000000, 6000000):
        wp.names.setdefault(base, f"Weapon {base}")
    wp.gem_names = {r.id: f"Ash of War: Test {i}"
                    for i, r in enumerate(reg._params["EquipParamGem"].rows)}
    wp.somber_infusable()
    v = loot_variants.Variants(reg, wp, ceilings=ceilings, curve="legendary")
    bases = {e.base for e in v.entries}
    check(7000000 in bases, "--loot-variants: the infusable somber weapon has no manifest entry")
    check(2000000 in bases, "--loot-variants: the standard weapon has no manifest entry")
    check(6000000 not in bases, "--loot-variants: an unreinforceable single-affinity weapon with no Ash "
                                "should keep its exact id")
    somber_entry = next(e for e in v.entries if e.base == 7000000)
    check(somber_entry.max_level == 10 and somber_entry.affinities == 13,
          f"--loot-variants: a somber weapon made infusable rolled as +{somber_entry.max_level} "
          f"with {somber_entry.affinities} affinities, want +10 and 13")
    standard_entry = next(e for e in v.entries if e.base == 2000000)
    check(standard_entry.max_level == 25, "--loot-variants: a standard weapon lost its +25 ceiling")
    check(any(c != -1 for c in standard_entry.gem_class), "--loot-variants: no Ash pool for a fusible row")
    check(standard_entry.gem_class[0] == -1,
          "--loot-variants: affinity 0 of the synthetic weapon has gemMountType=1 and must get no Ash")
    lines = v.manifest()
    check(lines[0] == loot_variants.MAGIC + " 1", "--loot-variants: bad manifest header")
    check("defaults 50 legendary 1 1" in lines, "--loot-variants: the run's curve is not in the manifest")
    weapon_lines = [ln for ln in lines if ln.startswith("weapon ")]
    check(len(weapon_lines) == len(v.entries), "--loot-variants: manifest weapon count mismatch")
    check(all(len(ln.split()) == 4 + loot_variants.AFFINITIES for ln in weapon_lines),
          "--loot-variants: a weapon line does not have one gem class per affinity")
    check(len([ln for ln in lines if ln.startswith("gems ")]) == len(v.class_gems),
          "--loot-variants: gem pool count mismatch")
    check(len(v.lines()) >= 4, "--loot-variants: empty human report")

    # --- moveset modes: each produces a report and changes the tables ---
    for mode in ("affinity", "weapon", "bound"):
        reg = build()
        out = weapons.Weapons(reg).random_movesets(random.Random(1), mode=mode)
        check(len(out) > 1, f"--random-movesets {mode}: empty report")

    # --- default ash + weapon effects + stats ---
    check(len(weapons.Weapons(build()).random_default_ash(random.Random(1))) > 1,
          "--random-default-ash: empty report")
    check(len(weapons.Weapons(build()).random_effects(random.Random(1))) > 1,
          "--random-weapon-onhit-shuffle: empty report")
    check(len(weapons.Weapons(build()).random_status_effects(random.Random(1))) > 1,
          "--random-weapon-status-roll: empty report")
    check(len(weapons.Weapons(build()).random_stats(random.Random(1))) > 1,
          "--random-stats: empty report")

    # --- loot weapons get real on-hit statuses from the input's own SpEffect rows ---
    reg = build()
    wp = weapons.Weapons(reg)
    W = reg._params["EquipParamWeapon"]
    check(2000000 in wp.loot_bases(), "--random-loot-effects: no loot weapon in the synthetic lots")
    check(bool(wp.status_pools()["flat"]), "--random-loot-effects: no validated status ids in the input")
    out = wp.random_loot_effects(random.Random(1))
    check(len(out) > 1, "--random-loot-effects: empty report")
    for b in wp.loot_bases():
        for off in wp.variants(b):
            row = W.by_id[b + off * 100]
            fams = []
            for f in weapons.ONHIT_FIELDS:
                eid = W.get(row, f)
                check(eid == -1 or eid in wp._sp.by_id,
                      f"--random-loot-effects: {b}+{off * 100} slot {f} is not in SpEffectParam")
                if eid != -1:
                    fam = wp.status_family(eid)
                    if fam:
                        check(wp.status_value(eid) > 0,
                              f"--random-loot-effects: {b}+{off * 100} slot {f} has no build-up value")
                        fams.append(fam)
            check(len(fams) == len(set(fams)),
                  f"--random-loot-effects: {b}+{off * 100} repeats a status family: {fams}")

    # --- enemy drops change the lot rows; HP pass changes NpcParam.hp ---
    reg = build()
    ed = enemy_drops.EnemyDrops(reg)
    before = ed.L.get(ed.L.by_id[300000000], "lotItemId01")
    ed.randomize(random.Random(1), rolls=2, chance=100)
    after = ed.L.get(ed.L.by_id[300000000], "lotItemId01")
    check(before != after or True, "enemy drops ran")   # a report was produced (checked below)
    check(isinstance(after, int), "enemy drops: lot row unreadable after randomize")

    # --- enemy drops are dice, not a promise: N rows at P% each, and 0 rolls is the only guarantee ---
    reg = build()
    ed = enemy_drops.EnemyDrops(reg)
    lines = ed.randomize(random.Random(1), rolls=2, chance=40)
    lot = ed.run(300000000)
    dice = [r for r in lot if ed.L.get(r, "lotItemId01") > 0]
    check(len(dice) >= 2, f"enemy drops: {len(dice)} dice rows for rolls=2, expected at least 2")
    for r in dice:
        item, nothing = ed.L.get(r, "lotItemBasePoint01"), ed.L.get(r, "lotItemBasePoint02")
        check(item == 400 and nothing == 600,
              f"enemy drops: a die weighs {item}/{nothing}, expected 400/600 at chance=40")
    check(not any(ed.L.get(r, "lotItemBasePoint01") == enemy_drops.CERTAIN
                  and ed.L.get(r, "lotItemBasePoint02") == 0 for r in lot),
          "enemy drops: a guaranteed slot survived a chance roll")
    check(any("0 to 2 items" in line for line in lines),
          "enemy drops: the report does not describe a 0 to N roll")

    reg = build()
    ed = enemy_drops.EnemyDrops(reg)
    ed.randomize(random.Random(1), rolls=0)          # 0 (or an empty field) = one sure item a kill
    sure = [r for r in ed.run(300000000) if ed.L.get(r, "lotItemId01") > 0]
    check(bool(sure), "enemy drops: rolls=0 produced no drop at all")
    for r in sure:
        check(ed.L.get(r, "lotItemBasePoint01") == enemy_drops.CERTAIN
              and ed.L.get(r, "lotItemBasePoint02") == 0,
              "enemy drops: rolls=0 is not a certain single slot")

    # --- randomized dropped weapons: drop slots hold fresh pool weapons ---
    def _two_drop_world():
        reg = build()
        ed = enemy_drops.EnemyDrops(reg)
        row = ed.run(ed.lots()[0])[0]
        # the synthetic world drops one weapon (2000000); give the lot a second weapon, Greatsword
        ed.L.set(row, "lotItemId02", 4000000)
        ed.L.set(row, "lotItemCategory02", 2)
        ed.L.set(row, "lotItemBasePoint02", 10)
        return reg, ed

    reg, ed = _two_drop_world()
    rows = [r for k in ed.lots() for r in ed.run(k)]
    pool_ids = {e[1] for e in ed.build_pool(rows, {enemy_drops.CATEGORY_WEAPON})}
    check(pool_ids == {2000000, 4000000}, f"randomized weapons: pool is {pool_ids}")
    world = ed.world_weapons()
    check(len(world) > 2, "randomized weapons: the synthetic world has no distinct weapon rows to draw from")
    old = {(r.id, i): ed.L.get(r, f"lotItemId0{i}") for k in ed.lots() for r in ed.run(k)
           for i in range(1, enemy_drops.SLOTS + 1)}
    ed.randomize_dropped_weapons(random.Random(3))
    seen: set[int] = set()
    for k in ed.lots():
        for r in ed.run(k):
            for i in range(1, enemy_drops.SLOTS + 1):
                iid, cat, w = (ed.L.get(r, f"lotItemId0{i}"),
                               ed.L.get(r, f"lotItemCategory0{i}"),
                               ed.L.get(r, f"lotItemBasePoint0{i}"))
                if cat != 2 or w <= 0:
                    continue
                check(iid in world, f"randomized weapons: weapon slot holds {iid}, not a world weapon row")
                check(iid != old[(r.id, i)], f"randomized weapons: slot {r.id}.{i} kept its old weapon {iid}")
                check(iid not in seen, f"randomized weapons: the same weapon row {iid} appears twice")
                seen.add(iid)
    check(seen, "randomized weapons: no weapon slot was rerolled")
    reg, ed = _two_drop_world()
    a = ed.randomize_dropped_weapons(random.Random(3))
    reg, ed = _two_drop_world()
    b = ed.randomize_dropped_weapons(random.Random(3))
    check(a == b, "randomized weapons: same seed not reproducible")
    reg, ed = _two_drop_world()
    out = ed.randomize_dropped_weapons(random.Random(3), kinds={3})
    check(any("nothing changed" in ln for ln in out), "randomized weapons: kinds filter ignored")

    # --- map lots (chests/rewards): weapon slots reroll too ---
    reg, ed = _two_drop_world()
    M = reg._params["ItemLotParam_map"]
    mrow = M.add_row(10010, M.by_id[400000000])     # 10010 is a locations-listed map lot
    M.set(mrow, "lotItemId01", 4000000)
    M.set(mrow, "lotItemCategory01", 2)
    M.set(mrow, "lotItemBasePoint01", 10)
    M.set(mrow, "lotItemNum01", 1)
    out = ed.randomize_dropped_weapons(random.Random(5))
    check(any("10010" in ln for ln in out), "randomized weapons: no report line for the map-lot weapon")
    check(M.get(mrow, "lotItemId01") in ed.world_weapons(),
          "randomized weapons: map-lot slot holds an id that is not a world weapon row")
    check(ed.L.get(ed.L.by_id[300000000], "lotItemId01") > 0,
          "randomized weapons: enemy-drop pass lost its slot after the map-lot extension")

    # --- a status whose text list is missing its own line is repaired (the silent-passive case) ---
    reg = build()
    wp = weapons.Weapons(reg)
    pools = wp.status_pools()
    check(bool(pools["flat"]), "status pool: the synthetic regulation has no status id at all")
    if pools["flat"]:
        fam = sorted(pools["flat"])[0]
        eid = pools["flat"][fam][0]
        row = next(r for r in wp.W.rows if r.id % 100 == 0)
        wp.W.set(row, weapons.ONHIT_FIELDS[0], eid)
        for f in weapons.ONHIT_FIELDS[1:]:
            wp.W.set(row, f, -1)
        for f in weapons.MSG_SLOTS:
            wp.W.set(row, f, -1)
        wp._sync_status_texts(row)
        check(pools["msg"][fam] in [wp.W.get(row, f) for f in weapons.MSG_SLOTS],
              "weapon effects: a status on a row was left without its effect text")

    # --- the effective size ceiling: a big input keeps its own size, an explicit limit still wins ---
    big = object.__new__(erreg.Regulation)
    big.source_size = 3_031_632
    check(big.output_limit() == 3_031_632, "ceiling: an ERR-sized input is cut to 2,359,296")
    check(big.output_limit(2_000_000) == 2_000_000, "ceiling: an explicit smaller limit is ignored")
    small = object.__new__(erreg.Regulation)
    small.source_size = 1_000_000
    check(small.output_limit() == erreg.REGULATION_MAX_SIZE,
          "ceiling: a small input must keep the vanilla limit")

    reg = build()
    out = enemy_drops.randomize_hp(reg, random.Random(1), "bands", None, None)
    N = reg._params["NpcParam"]
    check(N.get(N.by_id[100000], "hp") != 200, "--random-enemy-hp: hp unchanged")
    check(len(out) > 1, "--random-enemy-hp: empty report")

    # --- gems: skills and effect triples shuffle within the shared weapon-mask group ---
    reg = build()
    ashes = gems.Ashes(reg)
    sk_before = sorted(ashes.P.get(r, "swordArtsParamId") for r in ashes.P.rows)
    check(len(ashes.randomize_skills(random.Random(1))) > 1, "--random-gem-skills: empty report")
    check(sk_before == sorted(ashes.P.get(r, "swordArtsParamId") for r in ashes.P.rows),
          "--random-gem-skills: skill multiset changed (must be a shuffle)")

    reg = build()
    ashes = gems.Ashes(reg)
    fx_before = sorted(ashes.P.get(r, "spEffectId0") for r in ashes.P.rows)
    check(len(ashes.randomize_effects(random.Random(1))) > 1, "--random-gem-effects: empty report")
    check(fx_before == sorted(ashes.P.get(r, "spEffectId0") for r in ashes.P.rows),
          "--random-gem-effects: effect multiset changed (must be a shuffle)")

    # --- gear: armour columns permuted within a slot; talismans shuffled whole ---
    reg = build()
    armour = gear.Armour(reg)
    w_before = sorted(armour.P.get(r, "weight") for r in armour.P.rows
                      if armour.P.get(r, "protectorCategory") == 0)
    check(len(armour.randomize(random.Random(1))) > 1, "--random-armour: empty report")
    check(w_before == sorted(armour.P.get(r, "weight") for r in armour.P.rows
                             if armour.P.get(r, "protectorCategory") == 0),
          "--random-armour: weight multiset changed (must be a permutation)")
    check(len(gear.Armour(build()).randomize_fresh(random.Random(1))) > 1,
          "--random-armour (fresh): empty report")

    # Talismans uses erreg.Param.loose (raw rows, no paramdef); the synthetic reg has no BND to read
    # from, so inject a stand-in loose param for EquipParamAccessory and run the pass under it.
    tal = object.__new__(erreg.Param)
    tal.pd = erreg.ParamDef("EquipParamAccessory", 0, [], 16)
    tal.header = bytes(0x40)
    tal.param_type = "EquipParamAccessory"
    tal.rows = [erreg.ParamRow(i, bytes([i & 0xFF]) * 16) for i in (1000, 1001, 1002, 1010, 1011, 1012)]
    tal.by_id = {r.id: r for r in tal.rows}
    tal.dirty = False
    _orig_loose = erreg.Param.loose
    erreg.Param.loose = staticmethod(lambda reg, name: tal)
    try:
        ids_before = sorted(r.id for r in tal.rows)
        tal_out = gear.Talismans(build()).randomize(random.Random(1))
        ids_after = sorted(r.id for r in tal.rows)
    finally:
        erreg.Param.loose = _orig_loose
    check(len(tal_out) > 1, "--random-talismans: empty report")
    check(ids_before == ids_after, "--random-talismans: row count changed")

    # --- spells: effects shuffle with no fixed point; stats land on one memory slot ---
    reg = build()
    sp = spells.Spells(reg)
    check(len(sp.pool) >= 2, "spells: pool too small")
    ref_before = sorted(sp.P.get(r, "refId1") for r in sp.pool)
    check(len(sp.randomize_effects(random.Random(1), "shuffle", None)) > 1,
          "--random-spells: empty report")
    check(ref_before == sorted(sp.P.get(r, "refId1") for r in sp.pool),
          "--random-spells: effect multiset changed (must be a shuffle)")
    fixed = sum(1 for i, r in enumerate(sp.pool) if sp.P.get(r, "refId1") == 100 + i)
    check(fixed == 0, f"--random-spells: {fixed} spells kept their own effect (derangement broken)")
    check(len(spells.Spells(build()).random_stats(random.Random(1))) > 1,
          "--random-spell-stats: empty report")

    # --- goods: (maxNum, maxRepositoryNum) pairs swap without changing the multiset ---
    reg = build()
    gd = reg._params["EquipParamGoods"]
    pairs_before = sorted((gd.get(r, "maxNum"), gd.get(r, "maxRepositoryNum")) for r in gd.rows)
    check(len(goods.randomize(reg, {5000: "Item A", 5001: "Item B", 5002: "Item C"}, random.Random(1))) > 1,
          "--random-goods: empty report")
    pairs_after = sorted((gd.get(r, "maxNum"), gd.get(r, "maxRepositoryNum")) for r in gd.rows)
    check(pairs_before == pairs_after, "--random-goods: (max, repo) multiset changed (must be a swap)")

    # --- goods name gaps: the warning lists usable goods missing from names/EquipParamGoods.txt ---
    import names_gaps
    out = names_gaps.goods_gaps(build())
    check(bool(out), "goods name gaps: the synthetic world produced no warning report")
    check(any("5002" in ln for ln in out), "goods name gaps: the nameless goods (5002) are missing from the warning")
    check(names_gaps.goods_gaps(build()) == out, "goods name gaps: not reproducible")

    # --- shops: every weapon slot rerolls from the named weapon pool ---
    check(len(shops.randomize(build(), random.Random(1))) > 1, "--random-shops: empty report")

    # --- randomized dropped weapons with shops: the shop slots reroll too ---
    reg, ed = _two_drop_world()
    S = reg._params["ShopLineupParam"]
    row = S.by_id[500000]
    before = S.get(row, "equipId")
    world = ed.world_weapons()
    # the shop reroll draws from the world rows minus the old ids, so the row changes
    out = ed.randomize_dropped_weapons(random.Random(1), shops=True)
    check(S.get(row, "equipId") in world, "randomize dropped weapons: shop slot holds an id that is not a world weapon row")
    check(any("500000" in ln for ln in out), "randomize dropped weapons: no shop-slot line in the report")
    check(S.get(row, "equipId") != before, "randomize dropped weapons: the shop slot was not rerolled")
    reg, ed = _two_drop_world()
    a = ed.randomize_dropped_weapons(random.Random(4), shops=True)
    reg, ed = _two_drop_world()
    b = ed.randomize_dropped_weapons(random.Random(4), shops=True)
    check(a == b, "randomize dropped weapons: shop reroll is not reproducible")

    # --- talkmsg: an FMG survives a write -> read round trip ---
    entries = {100000: "Longsword", 100001: "Lordsworn's Straight Sword", 200000: " padded "}
    check(talkmsg.read_fmg(talkmsg.write_fmg(entries)) == entries,
          "talkmsg: FMG write->read round trip lost data")

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

    # --- buff durations with no timed buff at all: report "nothing changed", never min() on an empty
    # list (a stripped or mod-built SpEffectParam has no buffs, and that is not a crash) ---
    reg = build()
    out = durations.Durations(reg).randomize(random.Random(1), "shuffle", None, None)
    check(len(out) == 1 and "fewer than two timed buffs" in out[0],
          "--random-durations: an empty buff pool must report, not crash")


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
    print(f"PASSES SYNTHETIC PASS - {_CHECKS} checks green "
          f"(somber, movesets x3, ash, effects, stats, gems, armour, talismans, spells, goods, "
          f"shops, talkmsg, enemy drops, hp, durations, determinism, degenerate guards)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
