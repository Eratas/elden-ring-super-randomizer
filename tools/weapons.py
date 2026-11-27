"""Weapon-side randomization for Elden Ring regulation.bin.

Weapon ids are  base(…0000) + affinity*100 + upgrade level.  EquipParamWeapon holds one
row per (weapon, affinity); upgrade levels are applied at runtime through
ReinforceParamWeapon, so only affinity rows exist.

1. somber_infusable():  every single-affinity (somber / unique) weapon gets the 12 missing
   affinity rows (Heavy .. Occult) synthesized from a reference weapon of the same type,
   and gemMountType=2 so Ashes of War can be mounted.
2. random_movesets():   every (weapon, affinity) row receives the moveset bundle of a random
   other melee weapon or shield (animation set, attack behaviour block).
3. random_default_ash(): every (weapon, affinity) row gets a random default skill that is
   mountable on its weapon type, and every weapon handed out by item lots, shops and the
   starting classes gets a random affinity.
4. random_stats():      every (weapon, affinity) row (melee, shields, bows, crossbows, staves,
   seals) gets random attack power per element, critical, poise and stamina damage, guard
   negation, attribute requirements, scaling and status build-ups.
5. random_status_effects(): every weapon row draws 0-2 statuses from the input's own SpEffect
   table, with the effect text; random_loot_effects() is the same draw limited to weapons that
   appear in ItemLotParam_enemy / ItemLotParam_map.  random_effects() permutes whole on-hit or
   held-effect bundles inside a weapon class.
"""
from __future__ import annotations

import random
from pathlib import Path

import erreg

HERE = Path(__file__).resolve().parent
D, N = HERE / "paramdef", HERE / "names"

AFFINITY_NAMES = {0: "Standard", 1: "Heavy", 2: "Keen", 3: "Quality", 4: "Fire", 5: "Flame Art",
                  6: "Lightning", 7: "Sacred", 8: "Magic", 9: "Cold", 10: "Poison", 11: "Blood", 12: "Occult"}
# sortId offset of each affinity row relative to the Standard row (vanilla pattern)
SORT_DELTA = {0: 0, 1: 1, 2: 2, 3: 3, 4: 5, 5: 6, 6: 7, 7: 8, 8: 4, 9: 11, 10: 9, 11: 10, 12: 12}

MELEE_TYPES = {1, 3, 5, 7, 9, 11, 13, 14, 15, 16, 17, 19, 21, 23, 24, 25, 28, 29, 31, 35, 37, 39, 41,
               88, 89, 91, 92, 93, 94, 95}
MIN_ASHES_PER_CATEGORY = 30     # bound mode: an affinity never maps to a category with fewer animating ashes
SHIELD_TYPES = {65, 67, 69, 90}
# weapons that take part in affinity / moveset / default-ash randomization (staves, seals, torches do not)
INFUSABLE_TYPES = MELEE_TYPES | SHIELD_TYPES
# bows and crossbows: no affinities, movesets swapped only among themselves (never with the melee pool),
# wepType never changes so arrows stay arrows and bolts stay bolts
BOW_TYPES = {50, 51, 53, 55, 56}
BOW_ASH_TYPES = {50, 51, 53}        # crossbows / ballistas have no Ashes of War in vanilla
# wepType -> similar wepType, used to find a reference weapon when the type has no infusable weapon
REFERENCE_FALLBACK = {28: 25, 16: 15, 11: 9, 94: 13, 93: 5, 95: 37, 92: 9, 91: 1, 89: 35, 88: 35,
                      90: 67, 24: 21, 31: 29, 39: 9, 14: 3, 37: 35, 41: 23, 7: 5, 19: 17, 23: 21,
                      65: 67, 69: 67}
# wepType -> bit index inside EquipParamGem's 64-bit canMountWep block (bits 36+ are the DLC types)
WEPTYPE_BIT = {1: 0, 3: 1, 5: 2, 7: 3, 9: 4, 11: 5, 13: 6, 14: 7, 15: 8, 16: 9, 17: 10, 19: 11, 21: 12,
               23: 13, 24: 14, 25: 15, 28: 17, 29: 18, 31: 19, 35: 20, 37: 21, 39: 22, 41: 23,
               50: 24, 51: 25, 53: 26, 55: 27, 56: 28, 57: 29, 61: 31, 65: 32, 67: 33, 69: 34, 87: 35,
               88: 36, 89: 37, 90: 38, 91: 39, 92: 40, 93: 41, 94: 42, 95: 43}

# the "moveset": animation set + attack behaviour block.  wepType is handled separately: the
# game validates mounted Ashes of War against wepType when loading a save, so it may only
# change when every affinity row of a weapon gets the same type (mode "weapon").
MOVESET_FIELDS = ("weaponCategory", "wepmotionCategory", "guardmotionCategory",
                  "wepmotionOneHandId", "wepmotionBothHandId", "spAtkcategory",
                  "behaviorVariationId", "isDualBlade", "isThrustAttackType")
# Fields that belong to the item rather than to the attack moveset, so every row keeps its own:
# guardmotionCategory selects the guard (block) animation set, and weaponCategory is the item class
# the game maps inputs with (12 = shield: a left-hand shield guards on L1 instead of attacking).
# Found in-game 2026-10-17: with the donor's weaponCategory a left-hand shield attacked on L1.
# They stay in MOVESET_FIELDS so pool keys and weapons.txt donor names are unchanged.
KEEP_OWN_FIELDS = ("guardmotionCategory", "weaponCategory")

TYPE_NAMES = {1: "Dagger", 3: "Straight Sword", 5: "Greatsword", 7: "Colossal Sword", 9: "Curved Sword",
              11: "Curved Greatsword", 13: "Katana", 14: "Twinblade", 15: "Thrusting Sword",
              16: "Heavy Thrusting Sword", 17: "Axe", 19: "Greataxe", 21: "Hammer", 23: "Great Hammer",
              24: "Flail", 25: "Spear", 28: "Great Spear", 29: "Halberd", 31: "Reaper", 35: "Fist",
              37: "Claw", 39: "Whip", 41: "Colossal Weapon", 50: "Light Bow", 51: "Bow", 53: "Greatbow",
              55: "Crossbow", 56: "Ballista", 57: "Glintstone Staff", 61: "Sacred Seal", 65: "Small Shield",
              67: "Medium Shield", 69: "Greatshield", 87: "Torch", 88: "Hand-to-Hand", 89: "Perfume Bottle",
              90: "Thrusting Shield", 91: "Throwing Blade", 92: "Backhand Blade", 93: "Light Greatsword",
              94: "Great Katana", 95: "Beast Claw"}

ATTACK_FIELDS = ("attackBasePhysics", "attackBaseMagic", "attackBaseFire", "attackBaseThunder", "attackBaseDark")
SCALING_FIELDS = ("correctStrength", "correctAgility", "correctMagic", "correctFaith", "correctLuck")
COPY_IF_CHANGED = ("attackElementCorrectId", "correctType_Physics", "correctType_Magic", "correctType_Fire",
                   "correctType_Thunder", "correctType_Dark", "correctType_Poison", "correctType_Blood",
                   "correctType_Sleep", "correctType_Madness", "spAttribute", "isEnhance")
EFFECT_SLOTS = ("spEffectBehaviorId0", "spEffectBehaviorId1", "spEffectBehaviorId2")
MSG_SLOTS = ("spEffectMsgId0", "spEffectMsgId1", "spEffectMsgId2")

# --- 4. per-row stats (random_stats) -----------------------------------------------------
STAT_GROUPS = ("attack", "guard", "requirements", "scaling", "effects", "stamina", "spells")   # spells: see spells.py
STAMINA_RATE_RANGE = (0.0, 2.0)      # group "stamina": the multiplier of every row, uniform in this range
PC_BEHAVIOR = 100_000_000            # BehaviorParam_PC row id = PC_BEHAVIOR + behaviorVariationId * 1000 + judge id
LIGHT_ATTACK = 0                     # judge id of the first one-handed light attack: its stamina = the moveset's base cost
STAT_TYPES = INFUSABLE_TYPES | BOW_TYPES | {57, 61}       # + staves and seals (torches untouched)
ELEMENTS = ("Physics", "Magic", "Fire", "Thunder", "Dark")      # attackBase* / correctType_* suffixes
STATS = ("Strength", "Agility", "Magic", "Faith", "Luck")        # correct* / proper* suffixes
AEC_STAT = {"Strength": "Strength", "Agility": "Dexterity", "Magic": "Magic", "Faith": "Faith", "Luck": "Luck"}
AEC_BASE = 10000                     # vanilla default AttackElementCorrectParam row, template for new rows
AEC_NEW = 90000000                   # new rows: AEC_NEW + stat_mask (every scaling attribute raises every damage type)
GUARD_CUT = ("physGuardCutRate", "magGuardCutRate", "fireGuardCutRate", "thunGuardCutRate", "darkGuardCutRate")
GUARD_RESIST = ("poisonGuardResist", "diseaseGuardResist", "bloodGuardResist", "curseGuardResist",
                "freezeGuardResist", "sleepGuardResist", "madnessGuardResist")
SP_ATTRIBUTE = {"Magic": 10, "Fire": 11, "Thunder": 12, "Dark": 13}
# On-hit properties a weapon carries: "can inflict rot", "blocking costs less stamina", and the like.
# The behaviour ids are the status effects the weapon applies on hit; the resident ids are the effects it
# grants while it is held.  Both are shuffled as one bundle among weapons of the same class.
WEAPON_EFFECT_FIELDS = ("spEffectBehaviorId0", "spEffectBehaviorId1", "spEffectBehaviorId2",
                        "residentSpEffectId", "residentSpEffectId1", "residentSpEffectId2")
# The two groups can be shuffled separately: what the weapon does when it hits, and what it grants while held.
ONHIT_FIELDS = WEAPON_EFFECT_FIELDS[:3]
HOLDER_FIELDS = WEAPON_EFFECT_FIELDS[3:]
CRIT_VALUES = (0, 10, 20, 30, 40, 50, 60)                   # throwAtkRate: critical = 100 + value
REQ_MAX = 60                         # attribute requirements never exceed this, singly or summed
# Requirement bands per mode: (multiplier band for the attributes the weapon already needs, the range a
# brand-new attribute may add, the floor of the total cap, the total cap as a multiple of the weapon's own
# vanilla total).  Tying the roll to the weapon's own profile is what keeps a dagger a dagger: the old
# global pool could hand a starter dagger 50 Int.
REQ_BANDS = {
    "tight": ((0.75, 1.25), (1, 6), 12, 1.5, 0.08),
    "normal": ((0.60, 1.60), (1, 10), 20, 1.8, 0.15),
    "wild": ((0.40, 2.20), (1, 20), 40, 2.5, 0.25),
}
# Each drawn requirement is a vanilla value of the same attribute (the non-zero proper* values of the base
# rows, one per weapon); spells draw a whole vanilla INT / FAI / ARC set (spells.py).  No weighted tiers
# since 2026-10-30; both share the sum cap below.
REQ_TOTAL_MAX = REQ_MAX              # sum over all attributes; scaled down proportionally when above


def tiered(rng: random.Random, tiers) -> int:
    """Pick a tier by weight, then a uniform integer inside it (spell FP / stamina costs, spells.py)."""
    (lo, hi), = rng.choices([t[0] for t in tiers], [t[1] for t in tiers])
    return rng.randint(lo, hi)


def cap_total(req: dict, cap: int) -> dict:
    """Scale every value down proportionally (rounded down) when their sum exceeds cap."""
    tot = sum(req.values())
    if tot <= cap:
        return req
    return {k: int(v * cap / tot) for k, v in req.items()}


def _weighted_sample(rng: random.Random, items, weights, k: int) -> list:
    """k distinct items, drawn without replacement in proportion to their weights."""
    pool = [(item, max(0.0, float(weight))) for item, weight in zip(items, weights)]
    out = []
    for _ in range(min(k, len(pool))):
        total = sum(w for _, w in pool) or 1.0
        point = rng.random() * total
        upto = 0.0
        for i, (item, weight) in enumerate(pool):
            upto += weight
            if point < upto:
                out.append(item)
                pool.pop(i)
                break
        else:
            out.append(pool.pop()[0])
    return out
CRIT_WEIGHTS = (35, 25, 15, 10, 8, 5, 2)
PHYS_CURVES = (0, 1, 2, 7, 8)        # CalcCorrectGraph ids vanilla weapons use for physical scaling
ELEM_CURVES = (0, 4)                 # ... for elemental scaling
CATALYST_CURVES = (12, 14, 15, 16)   # ... staves / seals (spell scaling)
# status build-ups: SpEffect ids used by vanilla weapons.  "flat" ids keep their strength at every
# upgrade level; "series" ids are the affinity ones that grow with the level (id + level) and may only
# sit in the slot that the row's ReinforceParamWeapon type offsets (Blood: slot 0, Poison/Cold: slot 1).
STATUS_FLAT = {"blood": (6400, 6401, 6402, 6403, 6404, 6405, 6406),
               "poizon": (6500, 6501, 6502, 6503, 6505),
               "disease": (6600, 6601, 6602, 6603, 6605),
               "freeze": (6700, 6701, 6702),
               "sleep": (6451, 6452, 6454, 6455, 6456),
               "madness": (6750, 6751, 6752, 6753)}
STATUS_SERIES = {"blood": (105000, 105100, 105200), "poizon": (106000, 106100, 106200),
                 "freeze": (107500, 107600, 107700)}
STATUS_MSG = {"blood": 6501, "poizon": 6401, "disease": 6451, "freeze": 6601, "sleep": 6651, "madness": 6701}
STATUS_MSG_IDS = frozenset(range(6400, 6900))       # effect-text ids of status build-ups (6401, 6500, 6501, ...)
STATUS_LABEL = {"blood": "bleed", "poizon": "poison", "disease": "rot", "freeze": "frost",
                "sleep": "sleep", "madness": "madness"}
# Flat statuses random_loot_effects draws into the on-hit slots of loot weapons: the statuses
# every vanilla weapon carries, valid in any slot.  The level-growing series of STATUS_SERIES
# sit in their reinforce-type slots and are deliberately not drawn.
# crossbows / ballistas use reinforce types whose scaling rates are 0; to give them scaling they take
# the regular (25 levels) or somber (10 levels) type with the same materials and level count
CROSSBOW_REINFORCE = {3100: 0, 3500: 0, 3200: 2200, 3300: 2200, 3400: 2200}


def base_id(i: int) -> int:
    return i - i % 10000


def affinity(i: int) -> int:
    return i % 10000 // 100


def level(i: int) -> int:
    return i % 100


class Weapons:
    def __init__(self, reg: erreg.Regulation) -> None:
        self.reg = reg
        self.W = reg.param("EquipParamWeapon", erreg.load_paramdef(D / "EquipParamWeapon.xml"))
        self.names = erreg.load_names(N / "EquipParamWeapon.txt")
        self.orig_type = {}      # base id -> wepType
        self.orig_variation = {}  # base id -> vanilla behaviorVariationId (random_movesets replaces it on the rows)
        for r in self.W.rows:
            if r.id >= 1000000 and r.id % 10000 == 0:
                self.orig_type[r.id] = self.W.get(r, "wepType")
                self.orig_variation[r.id] = self.W.get(r, "behaviorVariationId")
        self.moveset_type: dict[int, int] = {}   # row id -> wepType of the weapon whose moveset it got
        self.row_cat: dict[int, int] = {}        # row id -> wepmotionCategory after randomization
        self.G = reg.param("EquipParamGem", erreg.load_paramdef(D / "EquipParamGem.xml"))
        self.gem_names = erreg.load_names(N / "EquipParamGem.txt")
        self.ashes = self._ashes()               # vanilla mount bits, read before any gem edit
        # weapon type -> animation category (wepmotionCategory) used by its weapons (majority vote)
        votes: dict[int, dict[int, int]] = {}
        for b in self.bases():
            if self.named(b):
                c = self.W.get(self.W.by_id[b], "wepmotionCategory")
                votes.setdefault(self.orig_type[b], {})[c] = votes.get(self.orig_type[b], {}).get(c, 0) + 1
        self.cat_of_type = {t: max(v, key=v.get) for t, v in votes.items()}
        self._animated_cache: dict[int, set[int]] = {}
        self._profile = self._build_profile()
        self._status: dict | None = None
        self._offset_series: list[tuple[str, int, int]] | None = None
        self._offset_map: dict[int, int] = {}
        self._status_warned = False

    def _build_profile(self) -> dict[int, list[float]]:
        """Per-affinity scaling shares, learned from what the affinity adds over Standard.

        Absolute coefficients hide the affinity: Elden Ring Reforged keeps the weapon's Strength and
        Dexterity and *adds* 147 Intelligence to a Magic row, so summing whole rows made Magic look
        Strength-first.  The difference from the same weapon's Standard row is the affinity's actual
        identity (Heavy adds Strength, Keen adds Dexterity, Magic adds Intelligence, ...), and each
        weapon contributes one equal vote, so a colossal does not drown out a dagger.  When a mod
        only redistributes (vanilla) or adds nothing (Fire in some tables), the row's own shares are
        the fallback.
        """
        raw = {a: [0.0] * len(STATS) for a in range(13)}
        votes = dict.fromkeys(range(13), 0)
        for b in self.bases():
            if not self.named(b) or self.orig_type[b] not in INFUSABLE_TYPES or b not in self.W.by_id:
                continue
            std = [self.W.get(self.W.by_id[b], f"correct{st}") for st in STATS]
            for a in self.variants(b):
                row = self.W.by_id[b + a * 100]
                cur = [self.W.get(row, f"correct{st}") for st in STATS]
                if a:
                    add = [max(0.0, cur[i] - std[i]) for i in range(len(STATS))]
                else:
                    add = []
                if not any(add):
                    add = cur
                total = sum(add)
                if total <= 0:
                    continue
                for i in range(len(STATS)):
                    raw[a][i] += add[i] / total
                votes[a] += 1
        return {a: ([v / votes[a] for v in vals] if votes[a] else [0.0] * len(STATS))
                for a, vals in raw.items()}

    def animated(self, cat: int) -> set[int]:
        """swordArts ids of ashes whose animations exist in animation category `cat`
        (= ashes mountable on some weapon type that uses that category)."""
        if cat not in self._animated_cache:
            types = [t for t, c in self.cat_of_type.items() if c == cat and t in WEPTYPE_BIT]
            self._animated_cache[cat] = {sa for sa, (_, bits) in self.ashes.items()
                                         if any(bits >> WEPTYPE_BIT[t] & 1 for t in types)}
        return self._animated_cache[cat]

    # --- helpers --------------------------------------------------------------
    def variants(self, b: int) -> list[int]:
        return [a for a in range(13) if b + a * 100 in self.W.by_id]

    def bases(self) -> list[int]:
        return sorted(self.orig_type)

    def named(self, b: int) -> bool:
        n = self.names.get(b, "?")
        return n != "?" and not n.startswith("[NPC]")

    def name(self, rid: int) -> str:
        b, a = base_id(rid), affinity(rid)
        n = self.names.get(b, f"#{b}")
        # a DLC / cut row can carry an affinity outside 0-12; a report must never die on it
        return n if a == 0 else f"{AFFINITY_NAMES.get(a, f'#{a}')} {n}"

    # --- 1. somber weapons: add affinity rows ------------------------------------------
    def somber_infusable(self) -> list[str]:
        W, g, s = self.W, self.W.get, self.W.set
        refs: dict[int, int] = {}
        for b in self.bases():
            if len(self.variants(b)) == 13 and self.named(b):
                wt = self.orig_type[b]
                innate = sum(1 for f in EFFECT_SLOTS if g(W.by_id[b], f) != -1)
                if wt not in refs or innate < refs[wt][0]:
                    refs[wt] = (innate, b)
        refs = {wt: v[1] for wt, v in refs.items()}
        # a vanilla / Reforged table always has a Longsword; fall back to the first base row so a
        # table that lacks one still works instead of raising StopIteration from next()
        clean_ref = next((b for b in self.bases() if self.names.get(b) == "Longsword"), self.bases()[0])
        lines = ["# somber/unique weapons made infusable (12 affinity rows added, gemMountType=2)",
                 "# weapon  <-  stats derived from reference weapon"]
        for b in self.bases():
            wt = self.orig_type[b]
            if wt not in INFUSABLE_TYPES or len(self.variants(b)) != 1 or not self.named(b):
                continue
            base = W.by_id[b]
            if g(base, "materialSetId") == -1:
                continue                                   # cannot be reinforced at all
            ref = refs.get(wt) or refs.get(REFERENCE_FALLBACK.get(wt, -1)) or clean_ref
            eff_ref = ref if all(g(W.by_id[ref], f) == -1 for f in EFFECT_SLOTS) else clean_ref
            s(base, "gemMountType", 2)
            for a in range(1, 13):
                new = W.add_row(b + a * 100, base)
                self._synthesize(new, base, W.by_id[ref], W.by_id[ref + a * 100],
                                 W.by_id[eff_ref], W.by_id[eff_ref + a * 100])
                if g(base, "sortId") != -1:
                    s(new, "sortId", g(base, "sortId") + SORT_DELTA[a])
            lines.append(f"{b:>9}  {self.names[b]:<40} <-  {self.names.get(ref, ref)}")
        lines.insert(0, f"# {len(lines) - 2} weapons")
        return lines

    def _synthesize(self, new, base, ref0, refa, eref0, erefa) -> None:
        g, s = self.W.get, self.W.set
        scale = g(base, "attackBasePhysics") / g(ref0, "attackBasePhysics") if g(ref0, "attackBasePhysics") else 1.0
        for f in ATTACK_FIELDS:
            r0, ra, bv = g(ref0, f), g(refa, f), g(base, f)
            nv = bv * ra / r0 if r0 else (bv + ra * scale if ra else bv)
            s(new, f, max(0, min(65535, int(round(nv)))))
        for f in SCALING_FIELDS:
            r0, ra, bv = g(ref0, f), g(refa, f), g(base, f)
            nv = bv * ra / r0 if r0 else (bv + ra if ra else bv)
            s(new, f, float(round(nv, 1)))
        for f in COPY_IF_CHANGED:
            if g(ref0, f) != g(refa, f):
                s(new, f, g(refa, f))
        # status effects: the affinity's bleed/poison/frost replaces an innate effect of the
        # same kind (vanilla: Blood Uchigatana swaps its innate bleed for the stronger one).
        # Effect-text ids (spEffectMsgId*) are an unordered list, handled separately.
        eff = [g(base, f) for f in EFFECT_SLOTS]
        msg = [g(base, f) for f in MSG_SLOTS]
        ref_msgs0 = {g(eref0, f) for f in MSG_SLOTS} - {-1}
        added_msgs = [m for f in MSG_SLOTS if (m := g(erefa, f)) != -1 and m not in ref_msgs0]
        removed_msgs = [m for m in ref_msgs0 if m not in {g(erefa, f) for f in MSG_SLOTS}]
        added = removed = False
        for i, fe in enumerate(EFFECT_SLOTS):
            r0, ra = g(eref0, fe), g(erefa, fe)
            if r0 == ra:
                continue
            if ra == -1:                           # affinity removes the reference's innate effect
                if eff[i] == r0:
                    eff[i], removed = -1, True
                continue
            fam = self.status_family(ra)
            same = [j for j, e in enumerate(eff) if e != -1 and (e == r0 or (fam and self.status_family(e) == fam))]
            if same:
                eff[same[0]] = ra
            else:
                empty = [j for j in ([i] + list(range(3))) if eff[j] == -1]
                eff[empty[0] if empty else i], added = ra, True
        if removed:
            msg = [-1 if m in removed_msgs else m for m in msg]
        if added:
            for m in added_msgs:
                if m not in msg and -1 in msg:
                    msg[msg.index(-1)] = m
        for f, v in zip(EFFECT_SLOTS, eff):
            s(new, f, v)
        for f, v in zip(MSG_SLOTS, msg):
            s(new, f, v)

    def status_family(self, sp_id: int) -> str | None:
        """'blood', 'poizon', 'freeze', ... for a status build-up SpEffect, else None.

        Only the six status families a weapon can inflict count.  A buff SpEffect also carries an
        ``*AttackPower`` field (physics / magic), and treating that as a status was how a damage buff
        could be moved into an on-hit slot.
        """
        if not hasattr(self, "_sp"):
            try:
                self._sp = self.reg.param("SpEffectParam", erreg.load_paramdef(D / "SpEffect.xml"))
                self._sp_fields = [f.name for f in self._sp.pd.fields if f.name.endswith("AttackPower")]
            except ValueError:                 # a synthetic / cut table without SpEffect rows
                self._sp = None
                self._sp_fields = []
            self._fam_cache = {}
        if self._sp is None:
            return None
        if sp_id not in self._fam_cache:
            r = self._sp.by_id.get(sp_id)
            fam = None
            if r is not None:
                for f in self._sp_fields:
                    if self._sp.get(r, f) > 0 and f[:-len("AttackPower")] in STATUS_LABEL:
                        fam = f[: -len("AttackPower")]
                        break
            self._fam_cache[sp_id] = fam
        return self._fam_cache[sp_id]

    def status_value(self, sp_id: int) -> int:
        """The build-up strength of a status SpEffect row, 0 when the row is missing or empty."""
        if self.status_family(sp_id) is None:
            return 0
        r = self._sp.by_id[sp_id]
        return max((self._sp.get(r, f) for f in self._sp_fields
                    if f[:-len("AttackPower")] in STATUS_LABEL), default=0)

    def _reinforce(self) -> list[tuple[str, int, int]]:
        """(family, base SpEffect id, slot index) read from ReinforceParamWeapon, plus the slot map.

        The game adds the upgrade level to the id in that slot, so only the base id may ever be
        written there: writing 105100 and then upgrading to +2 would ask for 105300.
        """
        if self._offset_series is not None:
            return self._offset_series
        self._offset_series = []
        try:
            R = self.reg.param("ReinforceParamWeapon",
                              erreg.load_paramdef(D / "ReinforceParamWeapon.xml"))
        except ValueError:
            return self._offset_series
        for r in R.rows:
            base = r.id - r.id % 100
            for i, f in enumerate(("spEffectId1", "spEffectId2", "spEffectId3")):
                v = R.get(r, f)
                if not v:
                    continue
                self._offset_map.setdefault(base, i)
                fam = self.status_family(v)
                if fam:
                    self._offset_series.append((fam, v, i))
        self._offset_series = list(dict.fromkeys(self._offset_series))
        return self._offset_series

    def offset_slot(self, rt: int) -> int | None:
        """The effect slot a reinforce type adds the upgrade level to, or None."""
        self._reinforce()
        return self._offset_map.get(rt - rt % 100) if rt else None

    def status_pools(self) -> dict:
        """Status ids that actually exist in this regulation, plus the reinforce offsets.

        The hard-coded vanilla ids are only a starting point: Elden Ring Reforged renumbers
        SpEffect rows, and a status id that is valid in vanilla can be missing there.  A missing id
        is exactly what produced the ``Poison (0)`` passive in game, so every id is checked against
        the input and the ids its own weapons already use are always accepted.
        """
        if self._status is not None:
            return self._status
        flat: dict[str, set[int]] = {fam: set() for fam in STATUS_LABEL}
        series: dict[str, int] = {}
        for fam, ids in STATUS_FLAT.items():
            flat[fam].update(i for i in ids if self.status_value(i) > 0)
        for b in self.bases():
            if not self.named(b):
                continue
            for a in self.variants(b):
                row = self.W.by_id[b + a * 100]
                for f in ONHIT_FIELDS:
                    eid = self.W.get(row, f)
                    fam = self.status_family(eid) if eid != -1 else None
                    if fam and self.status_value(eid) > 0:
                        flat[fam].add(eid)
        for fam, base, _slot in self._reinforce():
            if self.status_value(base) > 0:
                series.setdefault(fam, base)
        # a series base is also a valid flat id; keep it out of the flat pool so a slot with an
        # upgrade offset never receives an id the game would add the level to
        for fam, base in series.items():
            flat[fam].discard(base)
        self._status = {
            "flat": {f: tuple(sorted(ids)) for f, ids in flat.items() if ids},
            "series": series,
            "msg": dict(STATUS_MSG),
        }
        return self._status

    def _profile_for(self, row, vanilla_corr: list[float]) -> list[float]:
        """The scaling share to use for one row: its affinity's profile, or its own for Standard."""
        a = affinity(row.id)
        prof = list(self._profile.get(a, [0.0] * len(STATS)))
        if a == 0 or not any(prof):
            prof = [float(v) for v in vanilla_corr]
        if not any(prof):
            prof = [1.0] * len(STATS)
        total = sum(prof)
        return [v / total for v in prof]

    def _sync_status_texts(self, row) -> None:
        """Rewrite the three effect texts so every status on the row is described.

        A row can carry three texts and no more, and a status without its text is a passive the player
        cannot see (the "it does nothing" case).  The status texts therefore come first and the texts of
        real non-status effects fill whatever is left.  Called after every pass that moves a status, so a
        bundle inherited from a row whose own text list was incomplete is repaired on arrival.
        """
        g, s = self.W.get, self.W.set
        self.status_pools()
        fams: list[str] = []
        for f in ONHIT_FIELDS:
            eid = g(row, f)
            if eid != -1:
                fam = self.status_family(eid)
                if fam and fam not in fams:
                    fams.append(fam)
        status_msgs = set(STATUS_MSG.values())
        out = [STATUS_MSG[f] for f in fams if f in STATUS_MSG]
        for m in (g(row, f) for f in MSG_SLOTS):
            if m != -1 and m not in status_msgs and m not in out and len(out) < len(MSG_SLOTS):
                out.append(m)
        out = (out + [-1] * len(MSG_SLOTS))[:len(MSG_SLOTS)]
        for f, v in zip(MSG_SLOTS, out):
            s(row, f, v)

    def _assign_statuses(self, row, rng: random.Random) -> list[str]:
        """Give a weapon row 0-2 real statuses, with the matching passive text.

        Only ids present in the input are drawn (no more ``(0)`` build-ups), no family is repeated,
        a real non-status on-hit effect is never overwritten, and a reinforce offset slot receives
        only the base id of a growing series.  Returns the families written.
        """
        g, s = self.W.get, self.W.set
        pools = self.status_pools()
        flat = pools["flat"]
        if not flat:
            if not self._status_warned:
                self._status_warned = True
            return []
        eff = [g(row, f) for f in ONHIT_FIELDS]
        for i, e in enumerate(eff):
            if e != -1 and self.status_family(e):
                eff[i] = -1
        protected = {i for i, e in enumerate(eff) if e != -1 and e in self._sp.by_id}
        offset_slot = self.offset_slot(g(row, "reinforceTypeId"))
        n = rng.choices((0, 1, 2), (25, 55, 20))[0]
        free = [i for i, e in enumerate(eff)
                if e == -1 or (i not in protected and e not in self._sp.by_id)]
        for i in free:              # a dead id (a placeholder from a modded table) is not a status
            eff[i] = -1
        chosen: list[tuple[int, str, int]] = []       # (slot, family, id)
        series = {fam: base for fam, base in pools["series"].items() if fam in flat}
        if offset_slot is not None and offset_slot in free and series and n:
            fam = rng.choice(sorted(series))
            chosen.append((offset_slot, fam, series[fam]))
            n -= 1
        if offset_slot is not None and offset_slot in free:
            # the game adds the upgrade level to whatever sits in this slot, so a flat status
            # would silently become a different (usually missing) id as the weapon is upgraded
            free.remove(offset_slot)
        fams = [f for f in sorted(flat) if f not in {c[1] for c in chosen}]
        rng.shuffle(fams)
        for fam in fams[:max(0, n)]:
            if not free:
                break
            slot = free.pop(0)
            chosen.append((slot, fam, rng.choice(flat[fam])))
        for slot, _fam, eid in chosen:
            eff[slot] = eid
        for f, v in zip(ONHIT_FIELDS, eff):
            s(row, f, v)
        self._sync_status_texts(row)      # the status texts go in first, other texts fill the rest
        return [fam for _slot, fam, _eid in chosen]

    # --- 2. movesets ------------------------------------------------------------------
    def random_movesets(self, rng: random.Random, mode: str = "affinity", variety: int = 3,
                        keep_standard: bool = False, weptype_follows: bool = False,
                        shield_movesets: str = "shields", bow_movesets: str = "bows") -> list[str]:
        """mode="affinity": (default) a different moveset per affinity row (Standard included),
                          wepType untouched, every melee/shield ash unlocked on every melee weapon
                          and shield (the player must pick fitting ones from weapons.txt).
           mode="bound":    per weapon per affinity movesets from per-affinity clusters, ashes keep
                          only the affinities that animate them (see _movesets_bound).
           mode="weapon":   one random moveset per weapon, shared by all its affinity rows, and
                          wepType follows the moveset -> the smithing table only offers Ashes of
                          War whose animations exist for that moveset.  Shields do not take part
                          (their wepType must stay a shield type).
           The pool holds the movesets of all named melee weapons and shields; in modes affinity
           and bound shields receive movesets too.  Every row gets the donor's complete bundle;
           the only hard limit found so far is the regulation.bin size (erreg.REGULATION_MAX_SIZE).
           keep_standard: in mode affinity leave the Standard row of every weapon untouched (bound
           already does; weapon cannot).  weptype_follows (affinity / bound): every randomized row
           also takes the donor's wepType, so the smithing table lists exactly the ashes that
           animate with that row's moveset and the ash unlock is skipped.  Untested against the
           game's save validation: a mounted ash may become invalid after an affinity change.
           shield_movesets: "shields" (default) = shields only swap among the four shield animation
           sets and weapons never get a shield set (a left-hand shield still guards on L1: the
           guard/attack choice for L1 lives in the animation set itself, found in-game 2026-10-17);
           "none" = shields keep their own moveset; "all" = everything swaps with everything.
           bow_movesets: "bows" (default) = every bow / crossbow / ballista takes the moveset of a
           random other bow-class weapon (all modes, wepType and ammo unchanged); "none" = untouched."""
        W, g, s = self.W, self.W.get, self.W.set
        lines_bows = self._bow_movesets(rng) if bow_movesets == "bows" else []
        recipients = MELEE_TYPES if mode == "weapon" else INFUSABLE_TYPES
        pool: dict[tuple, tuple[str, int]] = {}
        for b in self.bases():
            if self.named(b) and self.orig_type[b] in recipients:
                key = (self.orig_type[b],) + tuple(g(W.by_id[b], f) for f in MOVESET_FIELDS)
                pool.setdefault(key, (self.names[b], self.orig_type[b]))
        pool_items = sorted(pool.items())
        n_shield = sum(1 for _, (_, t) in pool_items if t in SHIELD_TYPES)
        shield_help = {"shields": "swap only among shield movesets", "none": "keep their own moveset",
                       "all": "swap with everything"}
        lines = [f"# movesets: mode={mode}, {len(pool_items)} distinct movesets in the pool ({n_shield} from shields); "
                 f"shields: {shield_help[shield_movesets]}"]
        if mode == "bound":
            return lines + self._movesets_bound(rng, pool_items, variety, weptype_follows, shield_movesets) + lines_bows
        if mode == "weapon":
            lines += ["# weapon  <-  moveset of (new weapon type; ashes of war offered at the smithing table follow it)",
                      "#           safe = ashes mountable on both the old and the new type (mount one of these on",
                      "#           weapons you already own BEFORE switching regulation.bin, or the save will not load)",
                      "# shields are left alone in this mode"]
        else:
            lines += ["# every affinity row of every melee weapon and shield gets its own moveset"
                      + (" (Standard rows keep their own)" if keep_standard else " (Standard included)")
                      + ("; wepType follows the moveset" if weptype_follows else ""),
                      "# weapon row  <-  moveset of (weapon type whose ashes of war animate with it)"]
        shield_items = [p for p in pool_items if p[1][1] in SHIELD_TYPES]
        weapon_items = [p for p in pool_items if p[1][1] not in SHIELD_TYPES]
        for b in self.bases():
            if not self.named(b) or self.orig_type[b] not in recipients:
                continue
            is_shield = self.orig_type[b] in SHIELD_TYPES
            if is_shield and shield_movesets == "none":
                continue
            own = (self.orig_type[b],) + tuple(g(W.by_id[b], f) for f in MOVESET_FIELDS)
            vs = self.variants(b)
            cand = pool_items if shield_movesets == "all" else (shield_items if is_shield else weapon_items)
            others = [p for p in cand if p[0] != own]
            if not others:
                continue                            # degenerate pool (only this moveset exists): keep the row as is
            if mode == "weapon":
                key, (donor, dtype) = rng.choice(others)
                for a in vs:
                    row = W.by_id[b + a * 100]
                    for f, v in zip(MOVESET_FIELDS, key[1:]):
                        if f not in KEEP_OWN_FIELDS:
                            s(row, f, v)
                    s(row, "wepType", dtype)
                    self.moveset_type[row.id] = dtype
                    self.row_cat[row.id] = key[2]
                old_t, new_t = self.orig_type[b], dtype
                safe = sorted(nm for nm, bits in self.ashes.values()
                              if bits >> WEPTYPE_BIT[old_t] & 1 and bits >> WEPTYPE_BIT[new_t] & 1)
                lines.append(f"{b:>9}  {self.names[b]:<36} <-  {donor} ({TYPE_NAMES.get(dtype, dtype)})"
                             f"   safe[{len(safe)}]: {', '.join(safe[:6])}{', ...' if len(safe) > 6 else ''}")
            else:
                if keep_standard:
                    vs = [a for a in vs if a]
                    self.row_cat[b] = own[2]
                picks = rng.sample(others, len(vs)) if len(others) >= len(vs) else [rng.choice(others) for _ in vs]
                for a, (key, (donor, dtype)) in zip(vs, picks):
                    row = W.by_id[b + a * 100]
                    for f, v in zip(MOVESET_FIELDS, key[1:]):
                        if f not in KEEP_OWN_FIELDS:
                            s(row, f, v)
                    if weptype_follows:
                        s(row, "wepType", dtype)
                    self.moveset_type[row.id] = dtype
                    self.row_cat[row.id] = key[2]
                    lines.append(f"{row.id:>9}  {self.name(row.id):<48} <-  {donor} ({TYPE_NAMES.get(dtype, dtype)})")
        if mode == "affinity" and weptype_follows:
            lines += ["", "# wepType follows each row's moveset: the smithing table lists exactly the ashes that",
                      "# animate with the current affinity's moveset (EquipParamGem mount lists untouched)"]
        elif mode == "affinity":
            lines += [""] + self._unlock_ashes(cross_shields=(shield_movesets == "all"))
        lines += lines_bows
        lines += [""] + self._ash_lists()
        return lines

    def _bow_movesets(self, rng: random.Random) -> list[str]:
        """Every named bow / crossbow / ballista takes the complete moveset bundle of a random other
        bow-class weapon (light bow, bow, greatbow, crossbow, ballista animation sets).  wepType is
        never touched, so the ammunition type stays the weapon's own."""
        W, g, s = self.W, self.W.get, self.W.set
        pool: dict[tuple, tuple[str, int]] = {}
        for b in self.bases():
            if self.named(b) and self.orig_type[b] in BOW_TYPES:
                key = (self.orig_type[b],) + tuple(g(W.by_id[b], f) for f in MOVESET_FIELDS)
                pool.setdefault(key, (self.names[b], self.orig_type[b]))
        items = sorted(pool.items())
        lines = ["", f"# bows / crossbows / ballistas: {len(items)} distinct movesets swapped only among themselves "
                     "(wepType and ammunition unchanged)",
                 "# weapon  <-  moveset of"]
        for b in self.bases():
            if not self.named(b) or self.orig_type[b] not in BOW_TYPES:
                continue
            row = W.by_id[b]
            own = (self.orig_type[b],) + tuple(g(row, f) for f in MOVESET_FIELDS)
            others = [p for p in items if p[0] != own]
            if not others:
                continue
            key, (donor, dtype) = rng.choice(others)
            for f, v in zip(MOVESET_FIELDS, key[1:]):
                if f not in KEEP_OWN_FIELDS:
                    s(row, f, v)
            self.moveset_type[row.id] = dtype
            self.row_cat[row.id] = key[2]
            lines.append(f"{b:>9}  {self.names[b]:<36} <-  {donor} ({TYPE_NAMES.get(dtype, dtype)})")
        return lines

    def _movesets_bound(self, rng: random.Random, pool_items, variety: int = 3,
                        weptype_follows: bool = False, shield_movesets: str = "shields") -> list[str]:
        """Every (weapon, affinity>0) row gets its own random moveset:
           * each affinity owns a cluster of `variety` animation categories chosen so that as many
             ashes as possible animate in all of them (e.g. straight sword / katana / light greatsword);
           * every weapon draws, per affinity, one category of that affinity's cluster (all 12
             affinities of a weapon get different categories where possible, never its own) and a
             random concrete moveset of that category;
           * afterwards each Ash of War keeps only the affinities for which *every* weapon it can be
             mounted on uses a category that animates it (EquipParamGem.configurableWepAttr), so the
             smithing table never offers an ash/affinity pair without an animation.
           Standard keeps each weapon's own moveset; wepType stays vanilla.  Shields take part
           like weapons; weapon ashes that keep at least one affinity on the shield rows become
           mountable on shields (bits only added, never removed)."""
        W, g, s = self.W, self.W.get, self.W.set
        by_cat: dict[int, list] = {}
        for key, (donor, dtype) in pool_items:
            by_cat.setdefault(key[2], []).append((key, donor, dtype))   # key[2] = wepmotionCategory
        shield_items = [(key, donor, dtype) for key, (donor, dtype) in pool_items if dtype in SHIELD_TYPES]
        if shield_movesets != "all":      # weapons never take a shield animation set
            by_cat = {c: [d for d in ds if d[2] not in SHIELD_TYPES] for c, ds in by_cat.items()}
            by_cat = {c: ds for c, ds in by_cat.items() if ds}
        # skip perfume / hand-to-hand / plain shield style sets with few skill animations
        elig = sorted(c for c in by_cat if len(self.animated(c)) >= MIN_ASHES_PER_CATEGORY)
        if not elig:
            return [f"# bound mode: no animation category has at least {MIN_ASHES_PER_CATEGORY} ashes, "
                    "nothing changed"]
        variety = max(1, min(variety, len(elig)))
        anim = {c: self.animated(c) for c in elig}
        # clusters: first category = least used so far, then greedily the ones sharing most ashes
        clusters: dict[int, list[int]] = {}
        used: dict[int, int] = dict.fromkeys(elig, 0)
        for a in range(1, 13):
            least = min(used.values())
            first = rng.choice([c for c in elig if used[c] == least])
            pool, common = [first], set(anim[first])
            while len(pool) < variety:
                rest = [c for c in elig if c not in pool]
                score = {c: (len(common & anim[c]), -used[c]) for c in rest}
                top = max(score.values())
                best = rng.choice([c for c in rest if score[c] == top])
                pool.append(best)
                common &= anim[best]
            for c in pool:
                used[c] += 1
            clusters[a] = pool
        lines = [f"# bound mode (variety={variety}): each affinity owns a cluster of animation categories; every",
                 "# weapon draws its own category per affinity from that cluster. Ashes of war then keep only the",
                 "# affinities whose categories (on every weapon they can be mounted on) animate them.",
                 "# Standard keeps each weapon's own moveset. Shields take part; weapon ashes that still animate",
                 "# on the shield rows at some affinity become mountable on shields (Standard shields keep the",
                 "# shield moveset, so a weapon ash on a Standard shield has no animation)."]
        for a in range(1, 13):
            desc = ", ".join(f"{c} ({'/'.join(sorted({TYPE_NAMES.get(d[2], str(d[2])) for d in by_cat[c]}))})" for c in clusters[a])
            lines.append(f"#   {AFFINITY_NAMES[a]:<9} -> {desc}")
        lines.append("# weapon row  <-  moveset of")
        for b in self.bases():
            if not self.named(b) or self.orig_type[b] not in INFUSABLE_TYPES:
                continue
            own = g(W.by_id[b], "wepmotionCategory")
            is_shield = self.orig_type[b] in SHIELD_TYPES
            if is_shield and shield_movesets != "all":
                for a in self.variants(b):
                    row = W.by_id[b + a * 100]
                    self.row_cat[row.id] = own
                    if a == 0 or shield_movesets == "none":
                        continue
                    key, donor, dtype = rng.choice([d for d in shield_items if d[0][2] != own] or shield_items)
                    for f, v in zip(MOVESET_FIELDS, key[1:]):
                        if f not in KEEP_OWN_FIELDS:
                            s(row, f, v)
                    if weptype_follows:
                        s(row, "wepType", dtype)
                    self.row_cat[row.id] = key[2]
                    self.moveset_type[row.id] = dtype
                    lines.append(f"{row.id:>9}  {self.name(row.id):<48} <-  {donor} ({TYPE_NAMES.get(dtype, dtype)})")
                continue
            taken = {own}
            for a in rng.sample(self.variants(b), len(self.variants(b))):
                row = W.by_id[b + a * 100]
                if a == 0:
                    self.row_cat[row.id] = own
                    continue
                opts = ([c for c in clusters[a] if c not in taken]
                        or [c for c in clusters[a] if c != own] or clusters[a])
                c = rng.choice(opts)
                taken.add(c)
                key, donor, dtype = rng.choice([d for d in by_cat[c] if d[1] != self.names[b]] or by_cat[c])
                for f, v in zip(MOVESET_FIELDS, key[1:]):
                    if f not in KEEP_OWN_FIELDS:
                        s(row, f, v)
                if weptype_follows:
                    s(row, "wepType", dtype)
                self.row_cat[row.id] = c
                self.moveset_type[row.id] = dtype
            for a in self.variants(b):
                if a:
                    row = W.by_id[b + a * 100]
                    lines.append(f"{row.id:>9}  {self.name(row.id):<48} <-  "
                                 f"{TYPE_NAMES.get(self.moveset_type[row.id], '?')} moveset (category {self.row_cat[row.id]})")
        lines += [""] + self._restrict_ash_affinities(weptype_follows)
        return lines

    def _restrict_ash_affinities(self, weptype_follows: bool = False) -> list[str]:
        """Clear configurableWepAttr bits of every real Ash of War for the affinities where some
        weapon it can be mounted on uses an animation category without that ash's animation.
        An ash not yet mountable on every shield type is opened to all shield types when at least
        one affinity animates on every shield row (shields got weapon movesets)."""
        G = self.G
        attr = [f"configurableWepAttr{a:02d}" for a in range(13)]
        off = G.pd["canMountWep_Dagger"].offset
        shield_mask = 0
        for t in SHIELD_TYPES:
            shield_mask |= 1 << WEPTYPE_BIT[t]
        # (wepType, affinity) -> categories actually used by weapons of that type at that affinity
        cats_used: dict[tuple[int, int], set[int]] = {}
        for b in self.bases():
            if not self.named(b) or self.orig_type[b] not in INFUSABLE_TYPES:
                continue
            for a in self.variants(b):
                if a:
                    cats_used.setdefault((self.orig_type[b], a), set()).add(self.row_cat[b + a * 100])

        # weptype_follows: every row's smithing list follows its own moveset, so an ash can be
        # reached on nearly every weapon -> an affinity survives only if every weapon's row at that
        # affinity animates the ash (the cluster rule), whatever the weapon's original type.
        cats_all: dict[int, set[int]] = {}
        for (_t, a), cs in cats_used.items():
            cats_all.setdefault(a, set()).update(cs)

        def kept_for(r, sa, types) -> list[int]:
            if weptype_follows:
                return [a for a in range(1, 13) if G.get(r, attr[a])
                        and all(sa in self.animated(c) for c in cats_all.get(a, ()))]
            return [a for a in range(1, 13) if G.get(r, attr[a])
                    and all(sa in self.animated(c) for t in types for c in cats_used.get((t, a), ()))]

        removed = standard_only = opened = 0
        lines = ["# ash of war -> affinities still offered (others removed because some weapon that can mount",
                 "# the ash uses an animation category without the ash's animation at that affinity)",
                 "# [+shields] = now mountable on every shield type; its default affinity is the first one listed"]
        for r in G.rows:
            nm = self.gem_names.get(r.id, "")
            sa = G.get(r, "swordArtsParamId")
            if not nm.startswith("Ash of War:") or sa not in self.ashes or G.get(r, "sortId") == 999999:
                continue
            bits = self.ashes[sa][1]
            types = sorted(t for t in INFUSABLE_TYPES if bits >> WEPTYPE_BIT[t] & 1)
            kept = kept_for(r, sa, types)
            tag = ""
            if weptype_follows:
                tag = "  [row types]" if kept else ""
            elif bits & shield_mask != shield_mask:
                with_shields = kept_for(r, sa, sorted(set(types) | SHIELD_TYPES))
                if with_shields:
                    kept = with_shields
                    rb = int.from_bytes(bytes(r.data[off:off + 8]), "little")
                    r.data[off:off + 8] = (rb | shield_mask).to_bytes(8, "little")
                    G.dirty = True
                    opened += 1
                    tag = "  [+shields]"
            for a in range(1, 13):
                if G.get(r, attr[a]) and a not in kept:
                    G.set(r, attr[a], 0)
                    removed += 1
            if G.get(r, "defaultWepAttr") not in (0, *kept):
                G.set(r, "defaultWepAttr", 0)
            if tag and G.get(r, "defaultWepAttr") == 0:
                G.set(r, "defaultWepAttr", kept[0])   # Standard rows keep their own moveset: no animation there
            standard_only += not kept
            lines.append(f"{r.id:>7}  {nm.split(':', 1)[1].strip():<34} "
                         f"{', '.join(AFFINITY_NAMES[a] for a in [0] + kept)}{tag}")
        lines.insert(3, f"# {removed} (ash, affinity) combinations removed; {standard_only} ashes are Standard-only; "
                        f"{opened} ashes opened to shields")
        return lines

    def _unlock_ashes(self, cross_shields: bool = False) -> list[str]:
        """Every Ash of War mountable on some melee type becomes mountable on all melee types, and
        every ash mountable on some shield type on all shield types (one shared group when
        cross_shields), so a weapon can take the ashes that animate with its new moveset and save
        validation never fails because of a moveset change (bits are only ever added)."""
        G = self.G
        off = G.pd["canMountWep_Dagger"].offset
        groups = ([INFUSABLE_TYPES] if cross_shields else [MELEE_TYPES, SHIELD_TYPES]) + [BOW_ASH_TYPES]
        masks = []
        for ts in groups:
            m = 0
            for wt in ts:
                m |= 1 << WEPTYPE_BIT[wt]
            masks.append(m)
        n = 0
        for r in G.rows:
            bits = int.from_bytes(bytes(r.data[off:off + 8]), "little")
            new = bits
            for m in masks:
                if new & m:
                    new |= m
            if new != bits:
                r.data[off:off + 8] = new.to_bytes(8, "little")
                G.dirty = True
                n += 1
        what = ("every melee weapon and shield type, bow ashes on every bow type" if cross_shields
                else "every type of their own group (melee weapons / shields / bows)")
        return [f"# {n} ash of war rows made mountable on {what} (EquipParamGem canMountWep_*)"]

    def _ash_lists(self) -> list[str]:
        lines = ["# ashes of war that have animations for each weapon type (pick from the list of the",
                 "# type named after '<-' above; other ashes can be mounted but may not animate)"]
        for wt in sorted(INFUSABLE_TYPES | BOW_ASH_TYPES):
            names = sorted(nm for nm, bits in self.ashes.values() if bits >> WEPTYPE_BIT[wt] & 1)
            lines.append(f"{TYPE_NAMES.get(wt, wt)}: " + ", ".join(names))
        return lines

    # --- 3. default ash + affinity -----------------------------------------------------
    def _ashes(self) -> dict[int, tuple[str, int]]:
        G, gn = self.G, self.gem_names
        off = G.pd["canMountWep_Dagger"].offset
        ashes: dict[int, tuple[str, int]] = {}
        for r in G.rows:
            nm = gn.get(r.id, "")
            sa = G.get(r, "swordArtsParamId")
            if not nm.startswith("Ash of War:") or sa == -1 or G.get(r, "sortId") == 999999:
                continue                               # sortId 999999 = NPC/test rows mountable on everything
            nm = nm.split(":", 1)[1].strip()
            if nm in ("", "No Skill"):             # unnamed rows are unused test gems
                continue
            bits = int.from_bytes(bytes(r.data[off:off + 8]), "little")
            prev = ashes.get(sa, ("", 0))
            ashes[sa] = (prev[0] or nm, prev[1] | bits)
        return ashes

    def random_default_ash(self, rng: random.Random) -> list[str]:
        W, g, s = self.W, self.W.get, self.W.set
        ashes = self.ashes
        lines = [f"# default skills: {len(ashes)} ashes of war in the pool (chosen to match the row's moveset)",
                 "# weapon row  <-  default skill"]
        for b in self.bases():
            if not self.named(b) or self.orig_type[b] not in INFUSABLE_TYPES | BOW_ASH_TYPES:
                continue
            for a in self.variants(b):
                row = W.by_id[b + a * 100]
                if row.id in self.moveset_type:          # moveset came from another weapon type
                    bit = WEPTYPE_BIT[self.moveset_type[row.id]]
                    cands = [sa for sa, (_, bits) in ashes.items() if bits >> bit & 1]
                    if self.orig_type[b] in BOW_ASH_TYPES:   # bows: must also be mountable on the bow's own type
                        own_bit = WEPTYPE_BIT[self.orig_type[b]]
                        cands = [sa for sa in cands if ashes[sa][1] >> own_bit & 1]
                else:                                   # own moveset: anything that animates in its category
                    cands = sorted(self.animated(self.row_cat.get(row.id, g(row, "wepmotionCategory"))))
                if not cands:
                    continue
                sa = rng.choice(sorted(cands))
                s(row, "swordArtsParamId", sa)
                lines.append(f"{row.id:>9}  {self.name(row.id):<48} <-  {ashes[sa][0]}")
        lines += [""] + self._random_affinity_sources(rng)
        return lines

    def _random_affinity_sources(self, rng: random.Random) -> list[str]:
        lines = ["# affinity of weapons given by item lots / shops / starting classes",
                 "# source  :  old weapon id -> new weapon id"]
        var_cache = {b: self.variants(b) for b in self.bases()}

        def reroll(wid: int) -> int | None:
            b = base_id(wid)
            vs = var_cache.get(b)
            if wid <= 0 or not vs or len(vs) < 2:
                return None
            return b + rng.choice(vs) * 100 + level(wid)

        pdl = erreg.load_paramdef(D / "ItemLotParam.xml")
        for pn in ("ItemLotParam_map", "ItemLotParam_enemy"):
            L = self.reg.param(pn, pdl)
            ln = erreg.load_names(N / f"{pn}.txt")
            for r in L.rows:
                for i in range(1, 9):
                    if L.get(r, f"lotItemCategory0{i}") != 2:
                        continue
                    old = L.get(r, f"lotItemId0{i}")
                    new = reroll(old)
                    if new is not None and new != old:
                        L.set(r, f"lotItemId0{i}", new)
                        lines.append(f"{pn} {r.id} [{ln.get(r.id, '?')}] : {old} -> {new}  ({self.name(new - level(new))})")
        Sh = self.reg.param("ShopLineupParam", erreg.load_paramdef(D / "ShopLineupParam.xml"))
        sn = erreg.load_names(N / "ShopLineupParam.txt")
        for r in Sh.rows:
            if Sh.get(r, "equipType") != 0:
                continue
            old = Sh.get(r, "equipId")
            new = reroll(old)
            if new is not None and new != old:
                Sh.set(r, "equipId", new)
                lines.append(f"ShopLineupParam {r.id} [{sn.get(r.id, '?')}] : {old} -> {new}  ({self.name(new - level(new))})")
        C = self.reg.param("CharaInitParam", erreg.load_paramdef(D / "CharaInitParam.xml"))
        cn = erreg.load_names(N / "CharaInitParam.txt")
        for r in C.rows:
            rid = r.id
            if not 3000 <= rid < 3100:      # 3000-3009 the ten base classes, 3010-3011 Idus / Heavy Knight (1.17)
                continue
            for f in ("equip_Wep_Right", "equip_Subwep_Right", "equip_Subwep_Right3",
                      "equip_Wep_Left", "equip_Subwep_Left", "equip_Subwep_Left3"):
                if f not in C.pd:
                    continue
                old = C.get(r, f)
                new = reroll(old)
                if new is not None and new != old:
                    C.set(r, f, new)
                    lines.append(f"CharaInitParam {rid} [{cn.get(rid, '?')}] {f} : {old} -> {new}  ({self.name(new - level(new))})")
        return lines

    # --- 4. per-row stats ---------------------------------------------------------------
    @staticmethod
    def stat_group(wt: int) -> str:
        if wt in INFUSABLE_TYPES:
            return "hand"
        if wt in (55, 56):
            return "xbow"
        if wt in BOW_TYPES:
            return "bow"
        return "catalyst"

    def random_effects(self, rng: random.Random, fields=ONHIT_FIELDS) -> list[str]:
        """Permute the given on-hit / holder bundle among the rows of the same weapon class.

        The unit is a row, not a weapon: a Blood Dagger's bleed bundle and a plain Dagger's empty
        bundle are different, and collapsing every affinity onto the base row's bundle erased the
        difference the game shows.  An on-hit bundle carries its effect-text ids with it; holder
        bundles are only exchanged between rows that already have one, so a weapon never gains an
        always-on effect it was not designed to hold.
        """
        fields = tuple(fields)
        onhit = fields == ONHIT_FIELDS
        bundle = fields + (MSG_SLOTS if onhit else ())
        W, g, s = self.W, self.W.get, self.W.set
        by_class: dict[int, list] = {}
        for r in W.rows:
            b = base_id(r.id)
            if b not in self.orig_type or not self.named(b) or r.id % 100:
                continue                       # named rows, affinity level 0 only
            if not onhit and all(g(r, f) == -1 for f in fields):
                continue                       # nothing to exchange: leave the weapon's own state
            by_class.setdefault(self.orig_type[b], []).append(r)
        groups = {k: v for k, v in by_class.items() if len(v) > 1}
        total = sum(len(v) for v in groups.values())
        if total < 2:
            return ["# weapon effects: fewer than two rows of a class carry one, nothing changed"]
        lines = [f"# weapon effects: {total} rows in {len(groups)} classes, {len(fields)} fields shuffled "
                 f"inside each class" + (" (+ effect text ids)" if onhit else ""),
                 "# weapon  <-  bundle of"]
        shown = 0
        for cls in sorted(groups):
            rows = groups[cls]
            old = {r.id: tuple(g(r, f) for f in bundle) for r in rows}
            if onhit:
                self.status_pools()
                if self._sp is not None:
                    clean = {}
                    for rid, vals in old.items():
                        eff = [e if e == -1 or e in self._sp.by_id else -1 for e in vals[:len(fields)]]
                        msg = list(vals[len(fields):])
                        clean[rid] = tuple(eff + (msg if any(e != -1 for e in eff) else [-1] * len(msg)))
                    old = clean
            donors = rows[:]
            rng.shuffle(donors)
            for r, donor in zip(rows, donors):
                for f, v in zip(bundle, old[donor.id]):
                    s(r, f, v)
                if onhit:
                    self._sync_status_texts(r)      # a donor's incomplete text list is repaired here
                if shown < 12:
                    lines.append(f"{self.name(r.id):<48} <-  {self.name(donor.id)}")
                    shown += 1
        return lines

    def clean_dead_effects(self) -> list[str]:
        """Clear on-hit ids that do not exist in this regulation's SpEffectParam.

        ERR uses 109900 as a missing-row placeholder; other mods leave old ids behind when they
        renumber rows.  Such an id shows a broken passive in game, so it is replaced by -1.  The three
        text ids are an unordered list, not one per slot, so they are rebuilt from what is left rather
        than cleared slot-by-slot (which used to delete a live status's own text).
        """
        self.status_pools()
        if self._sp is None:
            return []
        changed = 0
        for row in self.W.rows:
            dead = False
            for f in ONHIT_FIELDS:
                e = self.W.get(row, f)
                if e != -1 and e not in self._sp.by_id:
                    self.W.set(row, f, -1)
                    changed += 1
                    dead = True
            if dead:
                self._sync_status_texts(row)
        return [f"# weapon effects: cleared {changed} dead on-hit ids that do not exist in this "
                f"regulation's SpEffectParam"]

    def random_status_effects(self, rng: random.Random, loot_only: bool = False) -> list[str]:
        """Give every weapon row 0-2 real statuses drawn from the input's own status pools.

        A draw, not a permutation: the same status may appear on two weapons.  Only ids present in
        the regulation are used, the text id matches the status family, and a row never carries the
        same family twice.  With loot_only the draw is restricted to the weapons the game hands out
        from a drop lot or map lot.
        """
        pools = self.status_pools()
        if not pools["flat"]:
            return ["# weapon statuses: no status SpEffect ids in this regulation, nothing changed"]
        bases = self.loot_bases() if loot_only else self.bases()
        changed = 0
        examples: list[str] = []
        for b in bases:
            if not self.named(b):
                continue
            for a in self.variants(b):
                row = self.W.by_id[b + a * 100]
                before = tuple(self.W.get(row, f) for f in ONHIT_FIELDS)
                fams = self._assign_statuses(row, rng)
                if tuple(self.W.get(row, f) for f in ONHIT_FIELDS) != before:
                    changed += 1
                    if len(examples) < 12:
                        examples.append(f"{self.name(row.id):<48} {', '.join(fams) or 'no status'}")
        total = sum(len(v) for v in pools["flat"].values())
        return [f"# weapon statuses: {changed} rows redrawn from {total} status ids that exist in this "
                f"regulation" + (" (loot weapons only)" if loot_only else "")] + examples

    def loot_bases(self) -> list[int]:
        """Weapon bases that appear in the game's drop lots: a lotItemId slot of an ItemLotParam_enemy
        or ItemLotParam_map row with category 2 holds the weapon, so every enemy or map loot this
        randomizer can move is a loot weapon (matches how _random_affinity_sources reads the lots)."""
        have: set[int] = set()
        pdl = erreg.load_paramdef(D / "ItemLotParam.xml")
        for pn in ("ItemLotParam_map", "ItemLotParam_enemy"):
            L = self.reg.param(pn, pdl)
            for r in L.rows:
                for i in range(1, 9):
                    if L.get(r, f"lotItemCategory0{i}") == 2:
                        wid = L.get(r, f"lotItemId0{i}")
                        if wid > 0:
                            have.add(base_id(wid))
        return sorted(b for b in self.bases() if b in have and self.named(b))

    def random_loot_effects(self, rng: random.Random) -> list[str]:
        """The same draw as random_status_effects, limited to weapons that appear in loot lots."""
        return self.random_status_effects(rng, loot_only=True)

    def random_stats(self, rng: random.Random, groups=STAT_GROUPS,
                     stamina_rate: tuple[float, float] = STAMINA_RATE_RANGE,
                     req_mode: str = "tight") -> list[str]:
        """Random stats for every (weapon, affinity) row of melee weapons, shields, bows, crossbows,
           ballistas, staves and seals (torches untouched):
           attack:       the five attackBase* values of a random donor row of the same class (hand
                         weapons / bows / crossbows / catalysts), elements shuffled (50%: the biggest
                         value stays physical), each +-15%; critical (throwAtkRate), poise damage
                         (saWeaponDamage) and stamina damage (attackBaseStamina) drawn separately;
                         spAttribute follows the main element.
           guard:        physical / elemental guard negation, guard boost (staminaGuardDef) and the
                         seven status resists, shields in the shield range, everything else in the
                         weapon range (bows and crossbows cannot guard and are skipped).
           scaling:      1-4 random attributes share a budget taken from a donor row (+-15%), random
                         CalcCorrectGraph curves, and an AttackElementCorrectParam row (one per attribute
                         set, 31 at most) in which every scaling attribute raises every damage type, so
                         the displayed letters always matter and spell scaling of catalysts follows.
                         Every attribute is available on every row (since 2026-10-30 Heavy rows may
                         draw Dexterity too, although the Heavy reinforce table multiplies its rate by
                         0, so that share of the budget shows and does nothing); crossbows switch to
                         the regular / somber reinforce type so their scaling rates are not 0.
           requirements: every scaling attribute (and 15% of the others) draws a vanilla value of that
                         attribute: the non-zero proper* values of the base rows (one per weapon, the
                         affinity rows repeat them), so common values come up as often as in the game;
                         when the sum exceeds 60 all values are scaled down proportionally.
           effects:      0-2 status build-ups (bleed, poison, scarlet rot, frost, sleep, madness) from
                         the SpEffect ids vanilla weapons use; rows whose reinforce type raises an effect
                         with the upgrade level (vanilla Blood / Poison / Cold) always carry a growing
                         bleed / poison / frost series in that slot.  Unique non-status on-hit effects
                         are kept.
           stamina:      every row draws a base cost (the vanilla stamina of the first one-handed light
                         attack of a random weapon of the same class: BehaviorParam_PC row
                         PC_BEHAVIOR + behaviorVariationId * 1000 + LIGHT_ATTACK, falling back to the
                         x00 default variation like the game does; hand weapons and shields 5-20,
                         catalysts 8 / 12) and a multiplier uniform in stamina_rate (default 0-2.0);
                         staminaConsumptionRate = multiplier * base / own, where own is that light
                         attack's cost in the moveset the row carries now, so the first light attack
                         costs base * multiplier whatever moveset --random-movesets gave the row and
                         the other attacks keep the moveset's proportions (since 2026-10-30; before,
                         the base followed the moveset).  Bows and crossbows have no stamina in
                         BehaviorParam_PC (0), they only get the multiplier.
           greases:      isEnhance is 1 on every row, so greases / weapon buffs can be applied whatever
                         the element or status build-up (vanilla sets 0 on elemental and status rows and
                         on most unique weapons; bows and shields use their own greases, gated elsewhere)."""
        W, g, s = self.W, self.W.get, self.W.set
        groups = set(groups)
        A = self.reg.param("AttackElementCorrectParam", erreg.load_paramdef(D / "AttackElementCorrectParam.xml"))
        targets = [(b, W.by_id[b + a * 100]) for b in self.bases()
                   if self.named(b) and self.orig_type[b] in STAT_TYPES for a in self.variants(b)]
        donors: dict[str, list[dict]] = {}
        for b, row in targets:                      # vanilla values, read before anything is changed
            donors.setdefault(self.stat_group(self.orig_type[b]), []).append({
                "atk": [g(row, f"attackBase{e}") for e in ELEMENTS],
                "stamina": g(row, "attackBaseStamina"), "poise": g(row, "saWeaponDamage"),
                "corr": sum(g(row, f"correct{st}") for st in STATS)})
        stam_pool: dict[str, list[int]] = {}         # stat group -> vanilla light-attack costs, one per weapon
        if "stamina" in groups:
            Bh = self.reg.param("BehaviorParam_PC", erreg.load_paramdef(D / "BehaviorParam.xml"))

            def light_cost(v: int) -> int:
                r = (Bh.by_id.get(PC_BEHAVIOR + v * 1000 + LIGHT_ATTACK)
                     or Bh.by_id.get(PC_BEHAVIOR + v // 100 * 100 * 1000 + LIGHT_ATTACK))
                return Bh.get(r, "stamina") if r is not None else 0
            for b in sorted({b for b, _ in targets}):
                c = light_cost(self.orig_variation[b])
                if c > 0:
                    stam_pool.setdefault(self.stat_group(self.orig_type[b]), []).append(c)
        lines = [f"# stats: {len(targets)} weapon rows, groups: {', '.join(x for x in STAT_GROUPS if x in groups)}"
                 + (f", stamina: vanilla light-attack base x multiplier {stamina_rate[0]:g}-{stamina_rate[1]:g}"
                    if "stamina" in groups else ""),
                 "# row  name  |  atk phys/mag/fire/ltng/holy  crit  poise  stam  |  guard phys/mag/fire/ltng/holy"
                 "  boost  |  req str/dex/int/fai/arc  |  scaling str/dex/int/fai/arc  |  status build-ups"
                 "  |  stamina rate (base x multiplier, moveset base)"]
        n_aec = 0
        for b, row in targets:
            wt = self.orig_type[b]
            grp = self.stat_group(wt)
            pool = donors[grp]
            vanilla_corr = [g(row, f"correct{st}") for st in STATS]
            vanilla_req = [g(row, f"proper{st}") for st in STATS]
            rt = g(row, "reinforceTypeId")
            if "scaling" in groups and rt in CROSSBOW_REINFORCE:
                rt = CROSSBOW_REINFORCE[rt]
                s(row, "reinforceTypeId", rt)
            # attack ---------------------------------------------------------------
            if "attack" in groups:
                vals = list(rng.choice(pool)["atk"])
                if rng.random() < 0.5:                      # biggest value stays physical
                    i = max(range(5), key=lambda k: vals[k])
                    vals[0], vals[i] = vals[i], vals[0]
                    rest = vals[1:]
                    rng.shuffle(rest)
                    vals = [vals[0]] + rest
                else:
                    rng.shuffle(vals)
                vals = [max(0, min(65535, int(round(v * rng.uniform(0.85, 1.15))))) for v in vals]
                if not any(vals):
                    vals[0] = 1
                for e, v in zip(ELEMENTS, vals):
                    s(row, f"attackBase{e}", v)
                s(row, "attackBaseStamina", max(5, min(65535, 5 * int(round(rng.choice(pool)["stamina"] * rng.uniform(0.85, 1.15) / 5)))))
                s(row, "saWeaponDamage", rng.choice(pool)["poise"])
                s(row, "throwAtkRate", rng.choices(CRIT_VALUES, CRIT_WEIGHTS)[0])
                main = max(ELEMENTS[1:], key=lambda e: g(row, f"attackBase{e}"))
                s(row, "spAttribute", SP_ATTRIBUTE[main] if g(row, f"attackBase{main}") else 0)
            atk = [g(row, f"attackBase{e}") for e in ELEMENTS]
            # guard ----------------------------------------------------------------
            if "guard" in groups and grp in ("hand", "catalyst"):
                r5 = lambda lo, hi: 5 * rng.randint(lo // 5, hi // 5)      # multiples of 5 compress better
                if wt in SHIELD_TYPES:
                    phys = 100 if rng.random() < 0.35 else r5(60, 95)
                    elem, boost, resist = (15, 90), (35, 85), (15, 50)
                else:
                    phys, elem, boost, resist = r5(10, 90), (10, 70), (15, 60), (9, 29)
                s(row, GUARD_CUT[0], float(phys))
                for f in GUARD_CUT[1:]:
                    s(row, f, float(r5(*elem)))
                s(row, "staminaGuardDef", r5(*boost))
                resist = rng.randint(*resist)              # one value for all seven, as in vanilla
                for f in GUARD_RESIST:
                    s(row, f, resist)
            # scaling --------------------------------------------------------------
            scaling_weights = [g(row, f"correct{st}") for st in STATS]   # vanilla until this block
            if "scaling" in groups:
                profile = self._profile_for(row, vanilla_corr)
                count = rng.choices((1, 2, 3), (25, 50, 25))[0]
                chosen = _weighted_sample(rng, list(range(len(STATS))),
                                          [max(p, 0.02) for p in profile], count)
                top = max(range(len(STATS)), key=lambda i: profile[i])
                if chosen and top not in chosen and rng.random() < 0.85:
                    chosen[0] = top
                chosen = list(dict.fromkeys(chosen))
                share = [profile[i] * rng.uniform(0.75, 1.25) if i in chosen else 0.0
                         for i in range(len(STATS))]
                tw = sum(share) or 1.0
                share = [x / tw for x in share]
                for i in chosen:                       # every chosen attribute must show on the page
                    share[i] = max(share[i], 0.08)
                tw = sum(share) or 1.0
                share = [x / tw for x in share]
                base_total = sum(vanilla_corr)
                total = (max(15.0, base_total * rng.uniform(0.85, 1.15)) if base_total
                         else rng.uniform(40, 90))
                for i, st in enumerate(STATS):
                    s(row, f"correct{st}", float(round(total * share[i])) if share[i] else 0.0)
                scaling_weights = share
                if grp == "catalyst":
                    c = rng.choice(CATALYST_CURVES)
                    for e in ELEMENTS:
                        s(row, f"correctType_{e}", c)
                else:
                    s(row, "correctType_Physics", rng.choice(PHYS_CURVES))
                    for e in ELEMENTS[1:]:
                        s(row, f"correctType_{e}", rng.choice(ELEM_CURVES))
                smask = sum(1 << i for i in chosen)
                aid = AEC_NEW + smask       # bits for damage types the row lacks are harmless (0 attack)
                if aid not in A.by_id:
                    ar = A.add_row(aid, A.by_id[AEC_BASE])
                    for i, st in enumerate(STATS):
                        for e in ELEMENTS:
                            A.set(ar, f"is{AEC_STAT[st]}Correct_by{e}", smask >> i & 1)
                    n_aec += 1
                s(row, "attackElementCorrectId", aid)
            # requirements ---------------------------------------------------------
            # The old pass rolled requirements from the row's vanilla profile and ignored what the
            # scaling had just rolled, which could produce "30 Dexterity, S Intelligence".  Here the
            # requirement is the scaling budget: only the attributes the weapon actually scales with
            # get points, in proportion to their share, so the two pages always agree.
            if "requirements" in groups:
                weights = list(scaling_weights)
                if not any(weights):
                    weights = [g(row, f"correct{st}") for st in STATS]   # scaling group switched off
                tw = sum(weights)
                if tw > 0:
                    shares = [w / tw for w in weights]
                    tier = max(sum(vanilla_req), REQ_BANDS[req_mode][2])
                    budget = max(REQ_BANDS[req_mode][2],
                                 min(REQ_MAX, round(tier * rng.uniform(0.9, REQ_BANDS[req_mode][3]))))
                    raw = {st: (shares[i] * rng.uniform(0.85, 1.15) if shares[i] > 0.02 else 0.0)
                           for i, st in enumerate(STATS)}
                    total_share = sum(raw.values()) or 1.0
                    req = {st: (max(1, round(budget * v / total_share)) if v else 0)
                           for st, v in raw.items()}
                    req = cap_total(req, REQ_MAX)
                    for st in STATS:
                        s(row, f"proper{st}", req[st])
            # status build-ups -----------------------------------------------------
            if "effects" in groups:
                self._assign_statuses(row, rng)
            s(row, "isEnhance", 1)                  # greases / buffs on every row, whatever it rolled
            # stamina consumption ----------------------------------------------------
            stam_note = ""
            if "stamina" in groups:
                own = light_cost(g(row, "behaviorVariationId"))
                base = rng.choice(stam_pool[grp]) if stam_pool.get(grp) else 0
                mult = rng.uniform(*stamina_rate)
                if own and base:
                    s(row, "staminaConsumptionRate", round(mult * base / own, 3))
                    stam_note = f" (base {base} x {mult:.2f}, moveset {own})"
                else:                                   # bows / crossbows: the multiplier alone
                    s(row, "staminaConsumptionRate", round(mult, 3))
            # report ---------------------------------------------------------------
            effs = [self.status_family(e) for e in (g(row, f) for f in EFFECT_SLOTS) if e != -1]
            effs = [STATUS_LABEL.get(x, "unique") for x in effs]
            guard = "-" if grp in ("bow", "xbow") else ("/".join(str(int(g(row, f))) for f in GUARD_CUT)
                                                           + f" boost {g(row, 'staminaGuardDef')}")
            lines.append(f"{row.id:>9}  {self.name(row.id):<44} | atk {'/'.join(map(str, atk))} "
                         f"crit {100 + g(row, 'throwAtkRate')} poise {g(row, 'saWeaponDamage'):g} "
                         f"stam {g(row, 'attackBaseStamina')} | guard {guard} | req "
                         + "/".join(str(g(row, f"proper{st}")) for st in STATS) + " | scl "
                         + "/".join(f"{g(row, f'correct{st}'):g}" for st in STATS)
                         + " | " + (", ".join(effs) if effs else "-")
                         + f" | rate {g(row, 'staminaConsumptionRate'):.3f}{stam_note}")
        lines.insert(1, f"# {n_aec} AttackElementCorrectParam rows added (ids {AEC_NEW}+)")
        return lines
