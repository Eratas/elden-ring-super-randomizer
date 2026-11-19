#!/usr/bin/env python3
"""Guard the progress bar against drift from the engine.

The bug this locks down: PHASES once held a phantom "weapon effects" and missed "loot shuffle",
so the window's `_phase()` caught the ValueError and silently reset the bar to 0.  There is now a
single source (phases.py); randomize.py names its passes with its constants and the window reads
PHASES from it.  This test proves the three stay in agreement:

  * phases.PHASES is a non-empty tuple of unique, non-empty strings that ends with "done";
  * the engine's say() order (resolved through phases.py) matches phases.PHASES;
  * the window reads phases.PHASES instead of carrying its own copy.

Run:  python tools/test_phases.py     (exit 0 = the bar cannot drift)
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import check_packs  # noqa: E402
import phases  # noqa: E402


def phases_shape_problems() -> list[str]:
    problems: list[str] = []
    if not isinstance(phases.PHASES, tuple) or not phases.PHASES:
        return ["phases.PHASES must be a non-empty tuple"]
    if any(not isinstance(p, str) or not p.strip() for p in phases.PHASES):
        problems.append("phases.PHASES has an empty or non-string entry")
    if len(phases.PHASES) != len(set(phases.PHASES)):
        problems.append("phases.PHASES has duplicate entries")
    if phases.PHASES[-1] != "done":
        problems.append("phases.PHASES must end with 'done'")
    return problems


def window_reads_phases_problems() -> list[str]:
    """The window must take PHASES from phases.py, not repeat the list by hand."""
    app = (HERE / "ui" / "app.py").read_text(encoding="utf-8")
    tree = ast.parse(app)
    imports_phases = any(
        isinstance(node, ast.Import) and any(a.name == "phases" for a in node.names)
        or isinstance(node, ast.ImportFrom) and node.module == "phases"
        for node in ast.walk(tree)
    )
    if not imports_phases:
        return ["ui/app.py does not import phases"]
    if "phases.PHASES" not in app:
        return ["ui/app.py does not read phases.PHASES (it still repeats the list by hand)"]
    return []


def main() -> int:
    problems: list[str] = []
    problems += phases_shape_problems()
    problems += window_reads_phases_problems()
    problems += check_packs.phase_order_problems()

    if problems:
        print("FAIL")
        for problem in problems:
            print("  -", problem)
        return 1
    print(f"PASS - {len(phases.PHASES)} phases in step: phases.py, randomize.py and the window")
    return 0


if __name__ == "__main__":
    sys.exit(main())
