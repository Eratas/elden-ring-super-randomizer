# Smoke-test plan — EldenRingSuperRandomizer.exe

Exe: `dist\EldenRingSuperRandomizer.exe`. **The exe is the window only** — PyInstaller builds it
`--windowed`, so it has no console and does not take the randomizer's flags (they are silently
ignored and the window opens). Run the command lines below from source with `randomize.bat` (the same
`tools/` engine the window runs); in the window, tick the same option and press **Preview**, then read
the same reports.

First line of defence: `--dry-run` — every pass runs and the reports print, but no file is written, so
your game's `regulation.bin` is untouched.

Inputs/outputs: point `--input` at your `regulation.bin` (the game's real table) — the window's
Files section can find it too. Reports land next to `--output`: `weapons.txt`, `mapping.txt`,
`drops.txt`, `hp.txt`, ... (`.txt` is ASCII; `loot.txt`/`loot-shuffle.txt` appear with loot options).

## 1. Feature 4 — true-random on-hit statuses

Command:
```
randomize.bat --random-weapon-status-roll --input <reg.bin> --output <out.bin> --dry-run
```
Checks in the `weapons.txt` report:
- Starts with `# weapon statuses on hit: every status slot rerolled with a true-random status id`,
  ends with `# N on-hit status slots rerolled` with N > 0 (the real table carries statuses on many
  weapons — the Longsword family has them by design).
- Same family, different id: a weapon whose on-hit status was blood-family still shows a
  blood-family status (ids 6400-6406 are the flat bloods, 105xxx are the growing blood series).
- Slots that held nothing stay empty: weapons with no on-hit status should not gain one.
- Holder effects untouched: rerun the same command without `--random-weapon-status-roll` — the
  holder-swap section of the report (from `--random-weapon-holder-shuffle`) should be identical; only the
  status draws differ.
- Determinism: run twice with the same `--seed` — both reports are byte-identical.

## 2. Feature 5 — numeric unique rate

Commands:
```
randomize.bat --random-enemy-drops --enemy-drop-rolls 3 --enemy-drop-chance 10 --unique-drops --unique-rate 20 --input <reg.bin> --output <out.bin> --dry-run
randomize.bat --random-enemy-drops --enemy-drop-rolls 3 --enemy-drop-chance 10 --unique-drops --unique-rate 2 --input <reg.bin> --output <out.bin> --dry-run
```
Checks:
- `--unique-rate 20` with 3 rolls x 10%: about one dropped item in five is a unique (the baseline at
  the default 3 is roughly 0.9 uniques per 100 kills, so you should see many more).
- `--unique-rate 2`: noticeably fewer uniques than the default 3.
- Boundaries rejected before anything runs: `--unique-rate 0` and `--unique-rate 21` print
  "Unique weapon rate must be between 1 and 20 (percent)" and write nothing.
- GUI: with "Rare unique weapons" on, the "Unique weapon rate" field is active; typing 21 shows the
  same error on Start; typing 1-20 runs.

## 3. Feature 6 — loot-texture presets

In the window, the Presets list gains three new bundles:
- "Vanilla-ish loot texture" — 3 rolls x 10%, unique rate 1 (rare uniques, the usual luck).
- "Event loot texture" — 5 rolls x 25%, unique rate 8 (common uniques).
- "Generous loot texture" — 8 rolls x 30%, unique rate 20 (uniques very common).

Check with the loot simulator:
```
randomize.bat --simulate 300 --random-enemy-drops --seed 1 --dry-run
```
or just run each preset once in dry-run and read the drops: Vanilla-ish gives a thin random layer on
top of normal luck (few drops, rare uniques), Event loot and Generous give many more drops with
uniques showing up far more often.

## 4. Feature 7 — random effects on loot weapons

The weapon-effect switches were renamed in the Weapons section (Shuffle on-hit effects, Shuffle
holder effects, Roll statuses on hit) and a fourth joined them:

```
randomize.bat --random-weapon-status-roll --random-loot-effects --input <reg.bin> --output <out.bin> --dry-run
```

Checks in `weapons.txt`:
- Starts with `# loot weapons: N bases appear in the drop lots, on-hit slots redrawn` with N > 0, and
  ends with `# 3N on-hit status slots redrawn on loot weapons`.
- Every on-hit slot of those weapons now holds a flat status id from the game's pools (6400-6406
  bleed, 106000 poison, 107000 rot, 105000 frost, 108000 sleep, 109000 madness); a slot that held
  nothing gains one — that is the difference from *Roll statuses on hit*, which leaves empty slots
  empty.
- Runs last in the weapons pass: with both it and *Shuffle on-hit effects* on, the loot weapons show
  the fresh draws, not the permutation.

## 5. Regression

- A plain run with none of the new options changes nothing visible you can compare — reports
  should look like they always did (same structure, same sections).
- The gate is green for the code; in-game, the exe opens a window, the reports print, no crash.

## Antivirus note

The exe is unsigned — SmartScreen/AV engines may flag it (README "Antivirus notes"). If the exe will
not start, open the Security app, restore the file, or check `build\pyinstaller.log` for the
PyInstaller output.

## Notes

- `dist\msg\engus\item_dlc02.msgbnd.dcx` sits next to the exe — the user adds
  `oo2core_6_win64.dll` from the game folder for real runs (the tool never ships it).
- Hover any field for its tooltip; the tooltips explain
  the random_stats/status-pass interplay.
