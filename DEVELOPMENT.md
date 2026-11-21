# Development

Running the randomizer from source, and the checks that keep it honest. For what the tool does and how to
use it, see [README.md](README.md).

## Requirements

* **Python 3.10–3.14** (developed on 3.14, which `.python-version` pins). Tk must be available (on
  Windows, tick *tcl/tk and IDLE* in the python.org installer; on Linux, `sudo apt install python3-tk`).
  **3.15 is not supported**: `zstandard` publishes no 3.15 wheel, so pip falls back to a source build
  (needs MSVC) and the install fails; `findpython.bat` and the launchers deliberately skip it.
* Two dependencies only: `zstandard` (zstd output) and `cryptography` (the file's AES-256-CBC
  encryption). `oo2core_6_win64.dll` is **not** a dependency: it is RAD Game Tools' and ships with the
  game; without it the tool writes zstd instead of kraken.

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
source.

## Run

```bat
python tools\gui.py                rem the window
python tools\randomize.py --help   rem the command line
randomize_gui.bat                  rem the window, using the venv above
```

## The gate

```bat
python tools\gate.py               rem byte-compile + packs + phases + contract + nexus + logic + synthetic + lint
```

`gate.py` runs, in order: byte-compile every `tools/*.py`, `check_packs.py --min-tip 120
--strict-structure` (the language packs), `test_phases.py` (the progress bar cannot drift from the
engine), `test_packs.py` (keys, placeholders, paragraphs, choices), `md2nexus.py --check` (the Nexus
description matches the README), `test_logic.py`, `test_passes_synthetic.py` (the weapons / gems /
gear / spells / goods / shops / enemy-drop passes on a built regulation), and `lint.py` (ruff's
pyflakes + syntax checks). Exit code 0 means all green.

Against a real `regulation.bin` (slow, needs the game's DLL for the kraken round-trip):

```bat
python tools\test_logic.py --fuzz "C:\Games\ELDEN RING\Game\regulation.bin"
```

## Linting

`tools/lint.py` runs ruff's real-bug checks (pyflakes `F` + syntax `E9`) over `tools/`. Ruff is a dev
tool, not a runtime dependency, so the lint step is *skipped* (not failed) when it is not installed:

```bat
pip install -r requirements-dev.txt    rem installs ruff (dev only; the tool itself needs requirements.txt)
python tools\lint.py             rem or directly: python -m ruff check tools\ --select F,E9
```

`gate.py` runs it as its last step, so a green gate also means no undefined names (an annotation that
references a module that was never imported), unused locals, or f-strings without a placeholder
slipped in.

## The Nexus description

Nexus Mods' description editor takes **BBCode, not Markdown** (there is no Markdown support and none is
planned), so the mod page cannot be a copy of README.md. It is generated instead:

```bat
python tools\md2nexus.py            rem rewrite NEXUS_DESCRIPTION.txt + NEXUS_DESCRIPTION.strict.txt
python tools\md2nexus.py --check    rem what the gate runs: fail if either file is stale
python tools\md2nexus.py --stdout   rem print the normal render
python tools\md2nexus.py --stdout --strict-tags   rem ... the wiki-tags-only render
```

Two artifacts, identical except for the fenced-block wrapper and the callout:

| File | Fenced blocks | Callout (`> …`) | Use it when |
|---|---|---|---|
| `NEXUS_DESCRIPTION.txt` | `[code]` | `[quote]` | normal case — it is what Nexus's own Markdown→BBCode converters emit |
| `NEXUS_DESCRIPTION.strict.txt` | `[quote]` | plain paragraph | you want zero risk on a first upload: `[code]` is the one emitted tag the Nexus wiki does not document |

The strict render leaves the callout unwrapped on purpose: `[quote]` is its fenced-block tag there, and
two indistinguishable `[quote]` blocks would make the raw file unreadable. The count is exact — the
strict file carries one `[quote]` per fenced block and no other.

Never hand-edit either file; edit `README.md` and re-run the generator. The renderer only
emits tags from the Nexus wiki's list (plus `[code]`), refuses any other tag, refuses leftover Markdown
outside a fenced block, and refuses unbalanced BBCode — `test_logic.test_nexus_doc` checks the mapping,
those invariants, the strict variant, and the staleness of both checked-in files. A fuzz test
(`test_md2nexus_fuzz`) generates random Markdown and asserts the render always satisfies the invariants.

## What the tests pin

`test_logic.py` covers the behaviour that would otherwise fail *silently* in the field:

* `dropshuffle.set_plan` — armour sets stay coherent (the test calls the production function; a
  hand-written copy of the branch once diverged from it on 200 of 200 seeds while both "passed");
* `dropshuffle` protection — `shuffle()` leaves a one-time flagged drop and a row holding a key item
  untouched, and the items it does move stay conserved (a permutation);
* loot upgrade caps and rarity tiers — `--loot-max-level` with `--zone-loot-levels` never collapses a
  zone's cap to 0 (which would roll the full ceiling), and the half-open tiers cover every upgrade
  level with none double-counted;
* `erreg` round-trips — DCX (zstd + deflate), AES-256-CBC encrypt/decrypt, and a BND4 rebuilt
  byte-for-byte from the shipped `msg` archive;
* `erreg` robustness — truncated or corrupt input fails as a clean `ValueError`, never a raw
  `struct.error` / `IndexError`, and never the `read_bnd4` name-scan hang;
* **the options round trip** — `dict -> argv -> dict` for every option, and again over 600 random
  *combinations* of options (`test_argv_fuzz`). The window builds the command line with
  `options.argv_from_values()` and runs it verbatim, so an option that function forgets to emit looks
  ticked in the window and does nothing in the engine. `--goods`, `--spells`, `--loot-rarity` and
  `--no-backup-replace` all shipped that way once;
* empty pools — `new_prices`, the price passes and `talkmsg.read_fmg` must report "nothing to do", not
  crash on a regulation.bin that does not fill them;
* `version.py` vs `version_info.txt` — the window footer and the exe's PE resource must not drift.

`test_passes_synthetic.py` builds a small regulation in memory (real paramdefs, a few weapon types,
40 distinct Ashes of War, armour and talisman rows, a handful of sorceries, enemy lots and a boss) and
drives every randomizer pass over it: `--somber-infusable`, the three `--random-movesets` modes,
`--random-default-ash`, the weapon-effect switches (`--random-weapon-onhit-shuffle`,
`--random-weapon-holder-shuffle`, `--random-weapon-status-roll`, `--random-loot-effects`),
`--random-stats`, the gem / armour / talisman / spell / goods / shop passes, an FMG write/read round
trip, the enemy-drop and HP passes, a same-seed determinism check, and the degenerate cases (too few
Ashes, a single moveset, a regulation with no timed buffs) failing soft.

## Layout

* `tools/options.py` — the option table (flags, labels, hints, defaults, dependencies) **and** the
  argv builder. The window and the command line are both generated from it, so they cannot disagree.
* `tools/phases.py` — the run's passes in order; `randomize.py`, the window and the README table all read
  from it.
* `tools/tips.py` — the English hover text of every option.
* `tools/lang_<code>.py` — the translated window text; `tools/check_packs.py` gates them.
* `tools/version.py` — the version shown in the window footer; bump it here **and** the version tuple in
  `tools/version_info.txt` (a test fails if they drift).
* `tools/randomize.py` — the engine: parse, run the passes, write the output and the reports.
* `tools/backup.py` — backup-and-replace, revert and backup pruning.
* `tools/test_logic.py` — the logic tests above; also used by `gui.py --self-test` inside the frozen exe.
* `tools/test_passes_synthetic.py` — the randomizer passes (weapons, gems, gear, spells, goods, shops,
  enemy-drops) on a built regulation; part of the gate (`tools/gate.py`).