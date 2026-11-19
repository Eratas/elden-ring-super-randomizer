#!/usr/bin/env python3
"""Run ruff's real-bug checks over the tools, using the rules pinned in ruff.toml.

Ruff is a dev tool, not a runtime dependency, so this skips cleanly when it is not installed -
`pip install -r requirements-dev.txt` enables it.  It is a fast companion to the gate: `tools/gate.py`
byte-compiles every module (catching syntax errors) and runs the logic tests, while this catches the
things a byte-compile misses - an undefined name in an annotation, an unused local, an unsorted
import block, a pre-3.10 idiom - before they reach a code review.

    python tools/lint.py            # or, equivalently: python -m ruff check tools/

The rule set lives in ruff.toml so this and a bare `ruff check tools/` agree.  Exit code 0 when clean
or when ruff is unavailable (so the gate never fails just because a dev tool is missing), 1 when ruff
reports a problem.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main() -> int:
    try:
        probe = subprocess.run([sys.executable, "-m", "ruff", "--version"],
                               capture_output=True, text=True)
    except OSError:
        probe = None
    if probe is None or probe.returncode != 0:
        print("LINT SKIP - ruff is not installed (pip install -r requirements-dev.txt to enable)")
        return 0

    result = subprocess.run([sys.executable, "-m", "ruff", "check", str(HERE),
                             "--output-format", "concise"])
    if result.returncode == 0:
        print("LINT PASS - no ruff issues")
    else:
        print("LINT FAIL - see the ruff output above")
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
