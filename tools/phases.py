"""The passes a run makes, in the order randomize.py makes them.

One list, read by both front ends: randomize.py names each pass with the constants below, and the
window's progress bar walks PHASES.  A pass is added once, here, and the engine and the progress bar
stay in step.  check_packs.py fails if the order of the engine's say() calls and this tuple disagree.

The string values are the `phase:<value>` keys the language packs translate, so renaming one breaks
the translations on purpose: the packs and this tuple are the same contract.
"""
from __future__ import annotations

READING = "reading the input"
BUFF_DURATIONS = "buff durations"
CONSUMABLE_EFFECTS = "consumable effects"
STACK_SIZES = "stack sizes"
PRICES = "prices"
ENEMY_RUNES = "enemy runes"
ENEMY_HP = "enemy hit points"
ENEMY_DROPS = "enemy drops"
DROPPED_WEAPONS = "randomized weapons on pickups"
SHOP_STOCK = "shop stock"
WEAPONS = "weapons"
ASHES_OF_WAR = "ashes of war"
ARMOUR_TALISMANS = "armour and talismans"
LOOT_SHUFFLE = "loot shuffle"
LOOT_LEVELS = "loot levels"
WEAPON_NAMES = "weapon names"
SPELLS = "spells"
FLASK_LOCATIONS = "flask locations"
STARTING_ITEMS = "starting items"
LOOT_SIMULATION = "loot simulation"
COMPRESSING = "compressing (this is the slow part)"
DONE = "done"

# The order the window's progress bar walks.  DONE is last; the engine emits it in both the dry-run
# branch and after a real write.
PHASES: tuple[str, ...] = (
    READING,
    BUFF_DURATIONS,
    CONSUMABLE_EFFECTS,
    STACK_SIZES,
    PRICES,
    ENEMY_RUNES,
    ENEMY_HP,
    ENEMY_DROPS,
    DROPPED_WEAPONS,
    SHOP_STOCK,
    WEAPONS,
    ASHES_OF_WAR,
    ARMOUR_TALISMANS,
    LOOT_SHUFFLE,
    LOOT_LEVELS,
    WEAPON_NAMES,
    SPELLS,
    FLASK_LOCATIONS,
    STARTING_ITEMS,
    LOOT_SIMULATION,
    COMPRESSING,
    DONE,
)
