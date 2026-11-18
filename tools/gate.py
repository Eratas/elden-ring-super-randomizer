#!/usr/bin/env python3
"""One command to gate the tools: compile everything, then run every check.

    python tools/gate.py

Runs, in order, and stops at the first failure:

  1. byte-compile every tools/*.py (a syntax error anywhere is a hard stop),
  2. check_packs.py --min-tip 120 --strict-structure   (the language-pack gate),
  3. test_phases.py                                    (the progress bar cannot drift),
  4. test_packs.py                                     (the pack contract: keys, placeholders, tips),
  5. test_logic.py                                     (pure helpers + binary round-trips: no game file needed).

Exit code 0 when all pass, 1 otherwise.  This is the local gate; CI runs the same steps.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
MIN_TIP = "120"


def run(label: str, argv: list[str]) -> bool:
    print(f"\n=== {label} ===", flush=True)
    result = subprocess.run(argv, cwd=str(HERE.parent))
    return result.returncode == 0


def main() -> int:
    py = sys.executable

    sources = sorted(str(p) for p in HERE.glob("*.py"))
    sources += sorted(str(p) for p in (HERE / "ui").glob("*.py"))
    if not run("byte-compile", [py, "-m", "py_compile", *sources]):
        print("\nGATE FAIL - a file does not compile")
        return 1

    steps = [
        ("pack gate", [py, str(HERE / "check_packs.py"), "--min-tip", MIN_TIP, "--strict-structure"]),
        ("phase order", [py, str(HERE / "test_phases.py")]),
        ("pack contract", [py, str(HERE / "test_packs.py")]),
        ("logic tests", [py, str(HERE / "test_logic.py")]),
    ]
    for label, argv in steps:
        if not run(label, argv):
            print(f"\nGATE FAIL - {label}")
            return 1

    print("\nGATE PASS - all checks green")
    return 0


if __name__ == "__main__":
    sys.exit(main())