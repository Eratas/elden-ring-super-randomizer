#!/usr/bin/env python3
"""Contract tests for the language packs (the data rails the gate leans on).

These assert the pack *contract*, not the prose:

  * every pack defines every option label and tip (no silent English fallback),          #19
  * every pack has the same key set, and the same `{placeholder}` names for each key,    #20
  * every tip is >= 2 non-empty, non-repeated paragraphs,                                 #21
  * every enum option's English tip names each of its choices,                           #18

check_packs.py enforces the same rules for the gate; this module is the unit-test entry point
(so a failing assertion names the exact broken key).  Run:  python tools/test_packs.py
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import check_packs  # noqa: E402
import options  # noqa: E402


def option_keys() -> set[str]:
    keys: set[str] = set()
    for o in options.OPTIONS:
        keys.add(f"opt:{o.key}:label")
        keys.add(f"opt:{o.key}:tip")
    return keys


def main() -> int:
    packs = check_packs.load_packs()
    if not packs:
        print("FAIL - no packs found")
        return 1
    problems: list[str] = []

    # #19: per-pack option coverage
    want = option_keys()
    for code, table in sorted(packs.items()):
        missing = sorted(want - set(table))
        if missing:
            problems.append(f"{code}: missing {len(missing)} option key(s): {missing[:4]}")

    # #20a: identical key sets (compare every pack against the first)
    first_code = next(iter(packs))
    first_keys = set(packs[first_code])
    for code, table in sorted(packs.items()):
        if set(table) != first_keys:
            problems.append(f"{code}: key set differs from {first_code}")

    # #20b: placeholder parity
    problems += check_packs.placeholder_parity_problems(packs)

    # #21: paragraph structure
    for code, table in sorted(packs.items()):
        for key, value in table.items():
            if key.endswith(":tip"):
                problems += [f"{code}: {p}" for p in check_packs.paragraph_problems(key, value)]

    # #18: English choices named
    problems += check_packs.choices_problems(packs)

    if problems:
        print(f"FAIL - {len(problems)} problem(s)")
        for problem in problems:
            print("  -", problem)
        return 1
    print(f"PASS - {len(packs)} packs, {len(want)} option keys each, "
          f"{len(first_keys)} total keys, placeholders and paragraphs consistent")
    return 0


if __name__ == "__main__":
    sys.exit(main())
