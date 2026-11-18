#!/usr/bin/env bash
# One-shot run: ./randomize.sh [options]   (the full list: tools/randomize.py --help)
set -e
cd "$(dirname "$0")"
VENV="$HOME/.venvs/er_mod"   # the project drive is exFAT and cannot hold a venv's symlinks, so the venv lives in $HOME
# Python 3.10 to 3.14: the dependencies ship no wheels for 3.15 yet.  An existing venv whose packages are
# missing is repaired in place; a venv built by a Python that is gone is simply replaced.
PY=""
for v in 3.14 3.13 3.12 3.11 3.10; do
  if command -v "python$v" >/dev/null 2>&1; then PY="python$v"; break; fi
done
if [ -z "$PY" ]; then
  for c in python3 python; do
    if command -v "$c" >/dev/null 2>&1 \
       && "$c" -c 'import sys; raise SystemExit(0 if (3,10) <= sys.version_info[:2] < (3,15) else 1)'; then
      PY="$c"; break
    fi
  done
fi
[ -n "$PY" ] || { echo "No Python 3.10 to 3.14 found. Install Python 3.14 (Ubuntu: sudo apt install python3 python3-venv)."; exit 1; }
[ -x "$VENV/bin/python" ] || "$PY" -m venv "$VENV"
"$VENV/bin/python" -c 'import zstandard, cryptography' 2>/dev/null \
  || "$VENV/bin/python" -m pip install --quiet -r tools/requirements.txt
PYTHONDONTWRITEBYTECODE=1 exec "$VENV/bin/python" -I tools/randomize.py "$@"