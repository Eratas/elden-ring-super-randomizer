#!/usr/bin/env bash
# Pack the window into one executable with PyInstaller: dist/EldenRingSuperRandomizer (for the platform this runs on;
# PyInstaller cannot cross-compile, use build_exe.bat on Windows).  paramdef/, names/ and liblinoodle.so go
# inside the executable; the game's oo2core_6_win64.dll does not (keep it next to the executable).
# tools/msg/<language>/item_dlc02.msgbnd.dcx (the weapon names) is copied next to the executable as
# dist/msg/<language>/...: ship the executable together with the msg folder.  The DLL is never shipped (it is
# RAD Game Tools' and comes with the game); the user copies it from the game folder.
set -e
cd "$(dirname "$0")"
VENV="$HOME/.venvs/er_mod"
# Python 3.10 to 3.14, the range the dependencies ship wheels for (see randomize.sh)
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
[ -n "$PY" ] || { echo "No Python 3.10 to 3.14 found. Install Python 3.14 (Ubuntu: sudo apt install python3 python3-venv python3-tk)."; exit 1; }
[ -x "$VENV/bin/python" ] || "$PY" -m venv "$VENV"
"$VENV/bin/python" -c 'import zstandard, cryptography' 2>/dev/null \
  || "$VENV/bin/python" -m pip install --quiet -r tools/requirements.txt
# tkcheck.py fails loudly when Tk is unusable and prints NAME=value lines for PyInstaller's tkinter hook.
# Parsed with `while read` into exported variables: no temporary script file is written (build_exe.bat does the same).
tkenv="$("$VENV/bin/python" -I tools/tkcheck.py)" || { echo "tkinter unusable (Ubuntu / WSL: sudo apt install python3-tk)"; exit 1; }
while IFS='=' read -r _k _v; do export "$_k=$_v"; done <<EOF
$tkenv
EOF
"$VENV/bin/python" -c 'import PyInstaller' 2>/dev/null \
  || "$VENV/bin/python" -m pip install --quiet pyinstaller
"$VENV/bin/python" -m PyInstaller --noconfirm --clean --onefile --windowed --noupx --name EldenRingSuperRandomizer \
  --version-file "$PWD/tools/version_info.txt" \
  --hidden-import test_logic \
  --hidden-import lang_de --hidden-import lang_es --hidden-import lang_fi --hidden-import lang_fr \
  --hidden-import lang_it --hidden-import lang_ja --hidden-import lang_ko --hidden-import lang_nl \
  --hidden-import lang_pl --hidden-import lang_pt --hidden-import lang_ru --hidden-import lang_sv \
  --hidden-import lang_zh \
  --add-data "$PWD/tools/paramdef:paramdef" --add-data "$PWD/tools/names:names" \
  --add-data "$PWD/tools/linoodle/liblinoodle.so:linoodle" \
  --distpath dist --workpath build --specpath build tools/gui.py
[ -x dist/EldenRingSuperRandomizer ] || { echo "PyInstaller reported success but dist/EldenRingSuperRandomizer is missing"; exit 1; }
for f in tools/msg/*/item_dlc02.msgbnd.dcx; do
  [ -e "$f" ] || continue
  lang="$(basename "$(dirname "$f")")"
  mkdir -p "dist/msg/$lang"
  cp "$f" "dist/msg/$lang/"
done
echo
ls -l dist/EldenRingSuperRandomizer dist/msg/*/
echo "ship dist/EldenRingSuperRandomizer together with the dist/msg folder (the weapon names); the user adds the game's oo2core_6_win64.dll"