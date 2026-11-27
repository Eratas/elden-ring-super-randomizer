"""The handful of shape constants shared by every pass that reads item lots.

One definition each: a future game update that changes the lot width or the number of affinity rows
must only be applied here, not in four unrelated passes.
"""
from __future__ import annotations

import re

SLOTS = 8                                      # lotItemId01 .. lotItemId08
BRACKET = re.compile(r"^\[(.+?)\]")             # "[Merchant Kale] Torch" -> "Merchant Kale"
CURVE_ORDER = ("even", "common", "legendary")  # rarity -> upgrade curve
AFFINITY_IDS = range(1, 13)                     # Standard, Heavy .. Occult
AFFINITY_COUNT = 13                             # the same ids, as a count
