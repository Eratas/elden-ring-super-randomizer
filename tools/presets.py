"""Plug-and-play presets: one choice, a whole coherent set of options.

A preset is a bundle of option values, nothing more: picking one writes those values into the window, so
the player sees exactly what was switched on and can change anything afterwards.  The window marks itself
"Custom" as soon as a value is changed by hand.

Keep them few and meaningful.  Each one must work on a vanilla regulation.bin and on an Elden Ring
Reforged one, and each one must leave the output under the game's 2.36 MB limit at the default
compression (kraken, maximum effort).

Values use the option keys from options.py; a key that is not listed keeps whatever the player had.
"""
from __future__ import annotations

PRESETS: tuple[dict, ...] = (
    {
        "key": "borderlands",
        "label": "Borderlands loot",
        "tip": "Weapons become loot boxes: any enemy drops any weapon, at a random affinity and a random "
               "upgrade level, with randomized stats. Three rolls per enemy at 100%, so a kill drops three "
               "things. With the loot-variants runtime DLL installed, every pickup rolls its own affinity, "
               "level and Ash of War, so five copies of one sword are five different swords.",
        "values": {
            "goods": False, "spells": False, "random_prices": False,
            "somber_infusable": True, "random_movesets": False, "random_default_ash": True,
            "random_stats": True, "stat_groups": "", "stamina_rate": "0,2.0",
            "random_enemy_drops": True, "enemy_drop_rolls": 3, "enemy_drop_chance": 100,
            "enemy_drop_kinds": "", "random_loot_levels": True, "loot_rarity": "common",
            "loot_boss_bonus": "better", "unique_drops": True, "material_drops": True,
            "random_weapon_drops": True, "random_goods_drops": True, "random_armor_drops": True,
            "random_talisman_drops": True, "random_ashes_drops": True, "armour_drop_sets": False,
            "random_runes": False, "random_enemy_hp": False, "random_durations": False,
            "random_flask_locations": False, "random_armor": False, "random_armor_fresh": False,
            "random_talismans": False, "random_gem_skills": False, "random_gem_effects": False,
            "loot_variants": True,
        },
    },
    {
        "key": "classic",
        "label": "Classic randomizer",
        "tip": "The traditional set: what consumables and spells do, and what shops charge. Weapons keep "
               "their movesets and stats, so the game still feels like itself.",
        "values": {
            "goods": True, "mode": "shuffle", "split_anim": "none", "include_flasks": False,
            "include_remembrances": False, "goods_quantity": False,
            "spells": True, "spell_stats": False,
            "random_prices": True, "price_mode": "shuffle", "sell_prices": True,
            "somber_infusable": False, "random_movesets": False, "random_default_ash": False,
            "random_stats": False, "random_enemy_drops": False, "random_loot_levels": False,
            "random_runes": False, "random_enemy_hp": False, "random_durations": True,
            "random_flask_locations": False, "random_armor": False, "random_armor_fresh": False,
            "random_talismans": False, "random_gem_skills": False, "random_gem_effects": False,
            "random_weapon_drops": False, "random_goods_drops": False, "random_armor_drops": False,
            "random_talisman_drops": False, "random_ashes_drops": False,
        },
    },
    {
        "key": "gentle",
        "label": "Gentle start",
        "tip": "A little of everything that cannot break the game: consumables and spells swap, prices move, "
               "buffs last a different time. Weapons, armour and drops are untouched, so it is a safe first run.",
        "values": {
            "goods": True, "mode": "shuffle", "split_anim": "none", "include_flasks": False,
            "include_remembrances": False, "goods_quantity": False,
            "spells": True, "spell_stats": False,
            "random_prices": True, "price_mode": "shuffle", "sell_prices": False,
            "random_durations": True, "duration_mode": "shuffle",
            "somber_infusable": False, "random_movesets": False, "random_default_ash": False,
            "random_stats": False, "random_enemy_drops": False, "random_loot_levels": False,
            "random_runes": False, "random_enemy_hp": False, "random_flask_locations": False,
            "random_armor": False, "random_armor_fresh": False, "random_talismans": False,
            "random_gem_skills": False, "random_gem_effects": False,
            "random_weapon_drops": False, "random_goods_drops": False, "random_armor_drops": False,
            "random_talisman_drops": False, "random_ashes_drops": False,
        },
    },
    {
        "key": "loot-and-stats",
        "label": "Loot and stats",
        "tip": "Weapons get new movesets, new skills and new stats on every affinity, and every weapon can "
               "drop anywhere. No consumable or price changes, so the RPG side stays readable.",
        "values": {
            "goods": False, "spells": False, "random_prices": False,
            "somber_infusable": True, "random_movesets": True, "moveset_mode": "affinity",
            "random_default_ash": True, "random_stats": True, "stat_groups": "", "stamina_rate": "0.8,1.2",
            "random_enemy_drops": True, "enemy_drop_rolls": 1, "enemy_drop_chance": 100,
            "enemy_drop_kinds": "weapons", "random_loot_levels": True, "loot_rarity": "common",
            "loot_boss_bonus": "better",
            "random_weapon_drops": True, "random_goods_drops": False, "random_armor_drops": False,
            "random_talisman_drops": False, "random_ashes_drops": False, "armour_drop_sets": False,
            "random_runes": False, "random_enemy_hp": False, "random_durations": False,
            "random_flask_locations": False, "random_armor": False, "random_armor_fresh": False,
            "random_talismans": False, "random_gem_skills": False, "random_gem_effects": False,
        },
    },
    {
        "key": "armor-and-talismans",
        "label": "Armor and talismans",
        "tip": "Armour numbers are shaken and rolled again, sets stay coherent, and armour and talismans can "
               "drop off any enemy. Weapons, goods and prices are untouched.",
        "values": {
            "goods": False, "spells": False, "random_prices": False,
            "somber_infusable": False, "random_movesets": False, "random_default_ash": False,
            "random_stats": False, "random_enemy_drops": False, "random_loot_levels": False,
            "random_runes": False, "random_enemy_hp": False, "random_durations": False,
            "random_flask_locations": False,
            "random_armor": True, "random_armor_fresh": True, "armour_keep_sets": True,
            "random_talismans": True,
            "random_armor_drops": True, "armour_drop_sets": True, "random_talisman_drops": True,
            "random_weapon_drops": False, "random_goods_drops": False, "random_ashes_drops": False,
            "random_gem_skills": False, "random_gem_effects": False,
        },
    },
    {
        "key": "ashes",
        "label": "Ashes of War",
        "tip": "Every Ash of War gets another ash's skill and on-hit effects, and ashes can drop off any "
               "enemy. Weapons keep their own movesets and stats.",
        "values": {
            "goods": False, "spells": False, "random_prices": False,
            "somber_infusable": True, "random_movesets": False, "random_default_ash": False,
            "random_stats": False, "random_enemy_drops": True, "enemy_drop_rolls": 1,
            "enemy_drop_chance": 100, "enemy_drop_kinds": "ashes", "random_loot_levels": False,
            "random_runes": False, "random_enemy_hp": False, "random_durations": False,
            "random_flask_locations": False, "random_armor": False, "random_armor_fresh": False,
            "random_talismans": False,
            "random_gem_skills": True, "random_gem_effects": True, "random_ashes_drops": True,
            "random_weapon_drops": False, "random_goods_drops": False, "random_armor_drops": False,
            "random_talisman_drops": False,
        },
    },
    {
        "key": "prices",
        "label": "Prices only",
        "tip": "What shops charge and what they pay. Nothing else changes, so it is the safest possible run.",
        "values": {
            "goods": False, "spells": False,
            "random_prices": True, "price_mode": "shuffle", "sell_prices": True,
            "sell_equipment": True,
            "somber_infusable": False, "random_movesets": False, "random_default_ash": False,
            "random_stats": False, "random_enemy_drops": False, "random_loot_levels": False,
            "random_runes": False, "random_enemy_hp": False, "random_durations": False,
            "random_flask_locations": False, "random_armor": False, "random_armor_fresh": False,
            "random_talismans": False, "random_gem_skills": False, "random_gem_effects": False,
            "random_weapon_drops": False, "random_goods_drops": False, "random_armor_drops": False,
            "random_talisman_drops": False, "random_ashes_drops": False,
        },
    },
    {
        "key": "boss-rush",
        "label": "Boss rush",
        "tip": "Enemies are worth more and hit back: rune drops and hit points are redrawn, bosses roll the "
               "best upgrade curve, and every enemy always drops one item.",
        "values": {
            "goods": False, "spells": False, "random_prices": False,
            "somber_infusable": False, "random_movesets": False, "random_default_ash": False,
            "random_stats": False,
            "random_enemy_drops": True, "enemy_drop_rolls": 1, "enemy_drop_chance": 100,
            "enemy_drop_kinds": "", "random_loot_levels": True, "loot_rarity": "common",
            "loot_boss_bonus": "best",
            "random_runes": True, "rune_mode": "range", "rune_min": "200", "rune_max": "150000",
            "random_enemy_hp": True, "hp_mode": "range", "hp_min": "150", "hp_max": "9000",
            "random_durations": False, "random_flask_locations": False,
            "random_armor": False, "random_armor_fresh": False, "random_talismans": False,
            "random_gem_skills": False, "random_gem_effects": False,
            "random_weapon_drops": False, "random_goods_drops": False, "random_armor_drops": False,
            "random_talisman_drops": False, "random_ashes_drops": False,
        },
    },
    {
        "key": "boss-hunt",
        "label": "Boss hunt",
        "tip": "Bosses stay the hard part: enemy HP is redrawn, but every boss is scaled back up (1.5-2x HP "
               "and runes) and bounty tracks HP, so a boss is always worth the fight and never a pushover. "
               "Ordinary enemies stay random.",
        "values": {
            "goods": False, "spells": False, "random_prices": False,
            "somber_infusable": False, "random_movesets": False, "random_default_ash": False,
            "random_stats": False,
            "random_enemy_hp": True, "hp_mode": "bands",
            "boss_hp_scale": "1.5,2.0", "boss_rune_scale": "1.5,2.0",
            "couple_runes_to_hp": True, "random_runes": False,
            "random_enemy_drops": False, "random_loot_levels": False, "loot_boss_bonus": "same",
            "random_durations": False, "random_flask_locations": False,
            "random_armor": False, "random_armor_fresh": False, "random_talismans": False,
            "random_gem_skills": False, "random_gem_effects": False,
            "random_weapon_drops": False, "random_goods_drops": False, "random_armor_drops": False,
            "random_talisman_drops": False, "random_ashes_drops": False,
        },
    },
    {
        "key": "level-1-run",
        "label": "Level 1 run",
        "tip": "A fresh start: every weapon, its moveset and where it drops are random, but nothing is "
               "cruel. No enemy becomes a bullet sponge, so a new character can play from the beginning.",
        "values": {
            "goods": False, "spells": False, "random_prices": False,
            "somber_infusable": True, "random_movesets": True, "moveset_mode": "affinity",
            "random_default_ash": True, "random_stats": True, "stat_groups": "", "stamina_rate": "0.8,1.2",
            "req_mode": "normal",
            "random_enemy_drops": True, "enemy_drop_rolls": 1, "enemy_drop_chance": 100,
            "enemy_drop_kinds": "", "random_loot_levels": True, "loot_rarity": "even",
            "loot_boss_bonus": "same", "unique_drops": False, "material_drops": False,
            "random_weapon_drops": True, "random_goods_drops": False, "random_armor_drops": False,
            "random_talisman_drops": False, "random_ashes_drops": False, "armour_drop_sets": False,
            "random_runes": True, "rune_mode": "shuffle",
            "random_enemy_hp": False, "random_durations": False, "random_flask_locations": False,
            "random_armor": False, "random_armor_fresh": False, "random_talismans": False,
            "random_gem_skills": False, "random_gem_effects": False,
            "random_shop_stock": False,
        },
    },
    {
        "key": "balanced",
        "label": "Balanced",
        "tip": "Chaos that stays fair: weapons get new movesets, stats and upgrade levels, enemies drop "
               "random gear, and both enemy HP and rune bounties are redrawn within a band - no bullet "
               "sponges and no rat worth a dragon. A safe default that still changes everything.",
        "values": {
            "goods": False, "spells": False, "random_prices": False,
            "somber_infusable": True, "random_movesets": True, "moveset_mode": "affinity",
            "random_default_ash": True, "random_stats": True, "stat_groups": "",
            "stamina_rate": "0.8,1.2", "req_mode": "normal",
            "random_enemy_drops": True, "enemy_drop_rolls": 1, "enemy_drop_chance": 100,
            "enemy_drop_kinds": "", "random_loot_levels": True, "loot_rarity": "common",
            "loot_boss_bonus": "better", "loot_max_level": 10,
            "unique_drops": True, "material_drops": True,
            "random_weapon_drops": True, "random_goods_drops": False, "random_armor_drops": False,
            "random_talisman_drops": False, "random_ashes_drops": False, "armour_drop_sets": False,
            "random_runes": True, "rune_mode": "bands",
            "random_enemy_hp": True, "hp_mode": "balanced", "boss_hp_scale": "1.0,1.3",
            "random_durations": False, "random_flask_locations": False,
            "random_armor": False, "random_armor_fresh": False, "random_talismans": False,
            "random_gem_skills": False, "random_gem_effects": False,
            "random_shop_stock": False,
        },
    },
    {
        "key": "glass-cannon",
        "label": "Glass cannon",
        "tip": "Weapons roll the biggest attack they can and enemies have little health: every fight is "
               "over in a hit or two, yours included. Expect wild weapons and fragile foes.",
        "values": {
            "goods": False, "spells": False, "random_prices": False,
            "somber_infusable": True, "random_movesets": True, "moveset_mode": "affinity",
            "random_default_ash": True, "random_stats": True, "stat_groups": "attack",
            "stamina_rate": "0,1.0", "req_mode": "wild",
            "random_enemy_drops": True, "enemy_drop_rolls": 1, "enemy_drop_chance": 100,
            "enemy_drop_kinds": "weapons", "random_loot_levels": True, "loot_rarity": "common",
            "loot_boss_bonus": "better", "unique_drops": False, "material_drops": False,
            "random_weapon_drops": True, "random_goods_drops": False, "random_armor_drops": False,
            "random_talisman_drops": False, "random_ashes_drops": False, "armour_drop_sets": False,
            "random_runes": False,
            "random_enemy_hp": True, "hp_mode": "range", "hp_min": "100", "hp_max": "1200",
            "random_durations": False, "random_flask_locations": False,
            "random_armor": False, "random_armor_fresh": False, "random_talismans": False,
            "random_gem_skills": False, "random_gem_effects": False,
            "random_shop_stock": False,
        },
    },
    {
        "key": "chaos",
        "label": "Full chaos",
        "tip": "Everything at once: every pass on, every drop random, every stat rolled. Expect a very "
               "different game, and give the compression its minutes.",
        "values": {
            "goods": True, "mode": "shuffle", "split_anim": "none", "include_flasks": False,
            "include_remembrances": False, "goods_quantity": True,
            "spells": True, "spell_stats": True,
            "random_prices": True, "price_mode": "shuffle", "sell_prices": True, "sell_equipment": True,
            "somber_infusable": True, "random_movesets": True, "moveset_mode": "affinity",
            "random_default_ash": True, "random_stats": True, "stat_groups": "", "stamina_rate": "0,2.0",
            "random_enemy_drops": True, "enemy_drop_rolls": 4, "enemy_drop_chance": 75,
            "enemy_drop_kinds": "", "random_loot_levels": True, "loot_rarity": "common",
            "loot_boss_bonus": "better", "unique_drops": True, "material_drops": True,
            "random_runes": True, "rune_mode": "shuffle", "random_enemy_hp": True,
            "hp_mode": "shuffle", "random_durations": True, "duration_mode": "shuffle",
            "random_flask_locations": True, "start_bell": True, "start_lantern": True,
            "random_armor": True, "random_armor_fresh": True, "armour_keep_sets": True,
            "random_talismans": True, "random_gem_skills": True, "random_gem_effects": True,
            "random_weapon_drops": True, "random_goods_drops": True, "random_armor_drops": True,
            "random_talisman_drops": True, "random_ashes_drops": True,
            "random_shop_stock": True, "shop_stock_kinds": "",
            "random_weapon_onhit_shuffle": True, "req_mode": "tight",
        },
    },
    {
        "key": "texture-vanilla-ish",
        "label": "Vanilla-ish loot texture",
        "tip": "Enemies keep a thin random texture: 3 rolls per enemy at 10%, so roughly one kill in three "
               "drops something, and a rare unique occasionally comes along with the ordinary loot. Safe and "
               "familiar.",
        "values": {
            "random_enemy_drops": True, "enemy_drop_rolls": 3, "enemy_drop_chance": 10,
            "enemy_drop_kinds": "", "unique_drops": True, "unique_rate": 1, "material_drops": False,
            "random_enemy_hp": False, "random_loot_levels": False, "random_runes": False,
            "random_shop_stock": False, "random_weapon_drops": False, "random_goods_drops": False,
            "random_armor_drops": False, "random_talisman_drops": False, "random_ashes_drops": False,
        },
    },
    {
        "key": "texture-event-loot",
        "label": "Event loot texture",
        "tip": "A bigger loot surface: every enemy gets 5 rolls at 25%, and uniques show up far more often "
               "than usual.",
        "values": {
            "random_enemy_drops": True, "enemy_drop_rolls": 5, "enemy_drop_chance": 25,
            "enemy_drop_kinds": "", "unique_drops": True, "unique_rate": 8, "material_drops": False,
            "random_enemy_hp": False, "random_loot_levels": False, "random_runes": False,
            "random_shop_stock": False, "random_weapon_drops": False, "random_goods_drops": False,
            "random_armor_drops": False, "random_talisman_drops": False, "random_ashes_drops": False,
        },
    },
    {
        "key": "texture-generous",
        "label": "Generous loot texture",
        "tip": "Very rich loot: every enemy gets 8 rolls at 30%, and uniques are common.",
        "values": {
            "random_enemy_drops": True, "enemy_drop_rolls": 8, "enemy_drop_chance": 30,
            "enemy_drop_kinds": "", "unique_drops": True, "unique_rate": 20, "material_drops": False,
            "random_enemy_hp": False, "random_loot_levels": False, "random_runes": False,
            "random_shop_stock": False, "random_weapon_drops": False, "random_goods_drops": False,
            "random_armor_drops": False, "random_talisman_drops": False, "random_ashes_drops": False,
        },
    },
)

BY_KEY = {p["key"]: p for p in PRESETS}


def labels() -> list[str]:
    return [p["label"] for p in PRESETS]


def find(label: str) -> dict | None:
    for p in PRESETS:
        if p["label"] == label:
            return p
    return None
