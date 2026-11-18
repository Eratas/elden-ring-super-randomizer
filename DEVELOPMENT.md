# Development

Running the randomizer from source, and the checks that keep it honest.

## Requirements

* **Python 3.10–3.14** (developed on 3.14). Tk must be available (on Windows, tick *tcl/tk and IDLE*
  in the python.org installer; on Linux, `sudo apt install python3-tk`).
* Two dependencies only: `zstandard` (zstd output) and `cryptography` (the game's Blowfish `regulation.bin`).
  `oo2core_6_win64.dll` is **not** a dependency: it is RAD Game Tools' and ships with the game; without it
  the tool writes zstd instead of kraken.

## Set up a virtual environment

```bat
rem Windows (cmd)
python -m venv "%USERPROFILE%\.venvs\er_mod"
"%USERPROFILE%\.venvs\er_mod\Scripts\python.exe" -m pip install -r tools\requirements.txt
```

```bash
# Linux / macOS
python3 -m venv ~/.venvs/er_mod
~/.venvs/er_mod/bin/python -m pip install -r tools/requirements.txt
```

`build_exe.bat` creates this same venv if it is missing, so the commands above are only needed to run from
source. `.python-version` pins the version the project is developed against.

## Run

```bat
python tools\ui\app.py            rem the window
python tools\randomize.py --help  rem the command line
randomize_gui.bat                 rem the window, using the venv above
```

## The gate

```bat
python tools\gate.py              rem compile + packs + phases + contract
```

`gate.py` runs, in order: byte-compile every `tools/*.py`, `check_packs.py --min-tip 120
--strict-structure` (the language packs), `test_phases.py` (the progress bar cannot drift from the
engine), and `test_packs.py` (keys, placeholders, paragraphs, choices). Exit code 0 means all green.

## Layout

* `tools/options.py` — the option table (flags, labels, hints, defaults, dependencies). The window and the
  command line are both generated from it, so they cannot disagree.
* `tools/phases.py` — the run's passes in order; `randomize.py` and the window both read it.
* `tools/tips.py` — the English hover text of every option.
* `tools/lang_<code>.py` — the translated window text; `tools/check_packs.py` gates them.
* `tools/version.py` — the version shown in the window footer; bump it here.