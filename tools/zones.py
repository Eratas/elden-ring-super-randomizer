"""Map a location name to a difficulty zone (0 = early, 3 = Land of Shadow DLC).

The game's item_locations.txt names each lot's location (e.g. "[Stormveil - Godrick] ..."), and the
shops are named too.  --zone-loot-levels uses this to hand out weaker weapons in the early zones and
stronger ones late, so a Limgrave chest is not a +25 weapon.  Unknown / NPC locations fall back to the
middle tier, so the pass never crashes on an unfamiliar name.
"""
from __future__ import annotations

# (zone, keywords) - first match wins, most specific / latest first.  Zone 3 = Land of Shadow (DLC).
ZONE_KEYWORDS: tuple[tuple[int, tuple[str, ...]], ...] = (
    (3, ("Land of Shadow", "Shadow Keep", "Belurat", "Enir-Ilim", "Rauh", "Scadu", "Messmer", "Bayle", "Ymir")),
    (2, ("Farum Azula", "Mohgwyn", "Haligtree", "Miquella", "Mountaintops", "Snowfield", "Consecrated",
         "Ordina", "Deeproot", "Lake of Rot", "Nokron", "Nokstella", "Ainsel", "Siofra", "Crumbling")),
    (1, ("Liurnia", "Raya Lucaria", "Caelid", "Altus", "Leyndell", "Gelmir", "Volcano Manor",
         "Capital Outskirts", "Divine Tower", "Flame Peak", "Forbidden Lands", "Sage's Cave",
         "Millicent", "Greyoll")),
    (0, ("Limgrave", "Weeping", "Stormhill", "Stormveil", "Morne", "Agheel", "Stranded",
         "Chapel of Anticipation", "Tombs", "Murkwater", "Ruin-Strewn")),
)

# The fraction of a weapon's upgrade ceiling a drop in this zone may reach (0 early .. 3 DLC).
# Tuned from a 20-seed playtest so each zone's ceiling actually bites (the roll reaches it) and the
# early game stays close to vanilla:
#   zone 0 Limgrave/Stormveil      -> ~+3 of +25  (somber ~+1)
#   zone 1 Liurnia/Caelid/Altus    -> ~+7 of +25  (somber ~+3)
#   zone 2 Mountaintops/Haligtree  -> ~+13 of +25 (somber ~+5)
#   zone 3 Land of Shadow (DLC)    -> full ceiling (+25 / +10 somber)
ZONE_MAX_SHARE: dict[int, float] = {0: 0.15, 1: 0.3, 2: 0.55, 3: 1.0}
DEFAULT_ZONE = 1

# How many steps toward the "even" curve a zone shifts the rarity (0 = base, 2 = strongest).  A low
# cap collapses the "common" curve's first tier to +0 (floor(0.12*cap)==0), so the cap alone leaves the
# *average* flat; shifting later zones toward "even" (uniform, no collapse) makes the average climb with
# the zone.  CURVE_ORDER = ("even", "common", "legendary"); a shift lowers the index toward "even".
ZONE_CURVE_SHIFT: dict[int, int] = {0: 0, 1: 1, 2: 2, 3: 2}


def zone_of(name: str) -> int:
    """The progress zone (0 early .. 3 DLC) for a location name; 1 (mid) for anything unrecognised."""
    if not name:
        return DEFAULT_ZONE
    low = name.lower()
    for zone, keywords in ZONE_KEYWORDS:
        for kw in keywords:
            if kw.lower() in low:
                return zone
    return DEFAULT_ZONE


def max_share(zone: int) -> float:
    """The fraction of a weapon's upgrade ceiling a drop in this zone may reach."""
    return ZONE_MAX_SHARE.get(zone, 1.0)
