#!/usr/bin/env python3
"""Check the GUI language packs in one command.

    python tools/check_packs.py              # report
    python tools/check_packs.py --min-tip 120 --strict-structure   # the gate
    python tools/check_packs.py --quiet      # only the verdict
    python tools/check_packs.py --fix        # apply the safe mechanical fixes (writes a .bak)

For every `lang_<code>.py` next to this file the check verifies that

  * it imports and exposes a dict `T`,
  * `T` has exactly the key set the other packs use, so nothing falls back by accident,
  * no two options share the same label, which is what a half-translated pack looks like,
  * no value is empty,
  * every `{placeholder}` matches the names the GUI passes to `.format()` - both against the
    known dialog keys and across every pack (a translator who renames `{name}` breaks the run),
  * every option label and tip the table defines exists in every pack (coverage),
  * every enum option's English tip names each of its choices, so a tip can never invent a value
    that `validate()` would reject,
  * tips are at least two non-empty, non-repeated paragraphs and reach the depth threshold,
  * quotes are balanced (guillemets, straight and curly double quotes),
  * the Russian pack uses an em-dash for asides, an en-dash for numeric ranges and a dot for
    decimals (its typography convention),
  * the engine's run order (randomize.py's `say()` calls) matches phases.PHASES, so the progress
    bar cannot silently rewind.

Japanese and Chinese are exempt from the script check, because their characters are the point.

Exit code 0 when every check passes, 1 otherwise.  English is the fallback and has no pack.
"""
from __future__ import annotations

import argparse
import ast
import importlib
import json
import re
import string
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import i18n  # noqa: E402
import phases  # noqa: E402

DENSE_SCRIPTS = {"ja", "zh"}
# A Chinese or Japanese tip carries roughly this much more per character than a Latin one,
# so a character threshold calibrated on English would call a complete CJK tip "thin".
CJK_DIVISOR = 2.5
# A tip is a short summary, a blank line, then the body (what it does / example / risk).  English
# itself uses two paragraphs; a translation that collapses to one has lost the summary/body split.
MIN_PARAGRAPHS = 2
SCRIPT_RE = re.compile(r"[\u3040-\u30ff\u4e00-\u9fff]")
# digit-hyphen-digit: a numeric range written with a hyphen instead of an en-dash.
RANGE_HYPHEN_RE = re.compile(r"(?<=\d)-(?=\d)")
# An ISO date (2024-01-15, a patch date) is a date, not a numeric range.  It is masked before the
# range scan so a legitimate date written in a tip is not mistaken for a hyphen-written range.
ISO_DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")
# A decimal-comma range: both endpoints use a comma and are joined by a dash (0,5–1,5).  Prose like
# German "1,5-Fache" (a comma value followed by a word) does not match, so it is left alone.
DECIMAL_RANGE_RE = re.compile(r"\d+,\d+\s*[\u2013-]\s*\d+,\d+")

# Dialog keys whose `{placeholder}` names are fixed by the `.format()` call in ui/app.py.
PLACEHOLDERS: dict[str, set[str]] = {
    "dlg:find_none": {"what"},
    "dlg:find_many": {"n", "first", "others"},
    "dlg:save_exists": {"name"},
    "dlg:delete_body": {"name"},
    "dlg:import_bad": {"path", "error"},
    "dlg:import_skipped": {"good"},
}

# Quotes that must balance when a pack uses them.
GUILLEMET_OPEN, GUILLEMET_CLOSE = "\u00ab", "\u00bb"          # « »
CURLY_OPEN, CURLY_CLOSE = "\u201c", "\u201d"                  # “ ”

# Keys a pack may define to localize a GUI choice token (ui:tok:<value>).  They are optional: a pack
# that leaves them out falls back to the raw English token, so they are excluded from key-set parity.
OPTIONAL_PREFIXES = ("ui:tok:",)


def _structural_keys(keys) -> set[str]:
    return {k for k in keys if not k.startswith(OPTIONAL_PREFIXES)}


def placeholders(text: str) -> set[str]:
    return {field for _, field, _, _ in string.Formatter().parse(text) if field}


def has_positional(text: str) -> bool:
    """True when a value uses `{}` / `{0}`: every .format() call here passes keyword arguments."""
    return any(field == "" for _, field, _, _ in string.Formatter().parse(text))


def load_packs() -> dict[str, dict[str, str]]:
    packs: dict[str, dict[str, str]] = {}
    for path in sorted(HERE.glob("lang_*.py")):
        code = path.stem[5:]
        sys.modules.pop(f"lang_{code}", None)
        try:
            module = importlib.import_module(f"lang_{code}")
        except Exception as error:
            print(f"{code}: IMPORT FAILED - {type(error).__name__}: {error}")
            continue
        table = getattr(module, "T", None)
        if not isinstance(table, dict):
            print(f"{code}: no dict T in {path.name}")
            continue
        packs[code] = table
    importlib.invalidate_caches()
    return packs


def paragraph_problems(key: str, value: str) -> list[str]:
    """A tip must be >= MIN_PARAGRAPHS non-empty, non-repeated paragraphs."""
    parts = value.split("\n\n")
    if len(parts) < MIN_PARAGRAPHS:
        return [f"{key}: {len(parts)} paragraph(s), expected at least {MIN_PARAGRAPHS}"]
    if any(not p.strip() for p in parts):
        return [f"{key}: an empty paragraph"]
    stripped = [p.strip() for p in parts]
    if len(stripped) != len(set(stripped)):
        return [f"{key}: a paragraph is repeated"]
    return []


def quote_problems(code: str, table: dict[str, str]) -> list[str]:
    joined = "".join(table.values())
    problems: list[str] = []
    open_g, close_g = joined.count(GUILLEMET_OPEN), joined.count(GUILLEMET_CLOSE)
    if (open_g or close_g) and open_g != close_g:
        problems.append(f"unbalanced guillemets: {open_g} open vs {close_g} close")
    german_open = joined.count("\u201e")                         # „ opens a German quote
    if german_open:
        # German pairs „ with “ (U+201C): the “ is the closing mark here, not an English opener.
        if german_open != joined.count(CURLY_OPEN):
            problems.append(f"unbalanced German quotes: {german_open} \u201e vs "
                            f"{joined.count(CURLY_OPEN)} \u201c")
    else:
        open_c, close_c = joined.count(CURLY_OPEN), joined.count(CURLY_CLOSE)
        if (open_c or close_c) and open_c != close_c:
            problems.append(f"unbalanced curly double quotes: {open_c} open vs {close_c} close")
    straight = joined.count('"')
    if straight % 2:
        problems.append(f"odd number of straight double quotes: {straight}")
    return problems


def dash_problems(code: str, table: dict[str, str]) -> list[str]:
    """Numeric ranges must use an en-dash, not a hyphen, in every pack.

    The Russian pack also uses an em-dash for asides (no spaced hyphen); Latin packs keep " - " for
    asides on purpose.  Decimal commas in prose (1,59 MB, 1,5-Fache) are correct in several languages
    and are left alone (the one decimal value the player types is checked by input_decimal_problems).
    """
    tips = [v for k, v in table.items() if k.endswith(":tip")]
    joined = ISO_DATE_RE.sub(" ", "".join(tips))     # dates (2024-01-15) are not numeric ranges
    problems: list[str] = []
    ranges = RANGE_HYPHEN_RE.findall(joined)
    if ranges:
        problems.append(f"{len(ranges)} numeric range(s) use a hyphen; use an en-dash \u2013")
    if code == "ru":
        spaced = joined.count(" - ")
        if spaced:
            problems.append(f"{spaced} spaced hyphen(s) ' - ' used as a dash; use an em-dash \u2014")
    return problems


def input_decimal_problems(packs: dict[str, dict[str, str]]) -> list[str]:
    """The stamina_rate example is the only decimal the player types; float() needs a dot.

    Prose elsewhere may use the language's decimal comma (1,59 MB, 1,5-Fache), but a range written with
    comma endpoints (0,5–1,5) next to a numeric field is wrong: a player who copies it gets a validation
    error.  Only that range shape is flagged, so worded examples ("van half tot anderhalf") pass.
    """
    problems: list[str] = []
    for code, table in packs.items():
        tip = table.get("opt:stamina_rate:tip", "")
        if DECIMAL_RANGE_RE.search(tip):
            problems.append(f"{code}: opt:stamina_rate:tip shows a decimal-comma range; the field needs "
                            f"a dot (0.5 to 1.5)")
    return problems


def check_pack(code: str, table: dict[str, str], reference: set[str], min_tip: int,
               min_tip_cjk: int | None = None) -> tuple[list[str], list[str]]:
    problems: list[str] = []
    warnings: list[str] = []
    # `ui:tok:*` keys are optional (a pack may localize choice tokens or fall back to English), so they
    # are excluded from key-set parity.
    keys = _structural_keys(table)
    ref = _structural_keys(reference)

    missing = sorted(ref - keys)
    extra = sorted(keys - ref)
    if missing:
        problems.append(f"missing {len(missing)} key(s): {', '.join(missing[:4])}")
    if extra:
        problems.append(f"unknown {len(extra)} key(s): {', '.join(extra[:4])}")

    labels: dict[str, str] = {}
    for key, value in table.items():
        if not key.endswith(":label"):
            continue
        if value in labels:
            problems.append(f"duplicate label: {key} and {labels[value]} both say {value!r}")
        else:
            labels[value] = key

    empty = sorted(k for k, v in table.items() if not v.strip())
    if empty:
        problems.append(f"empty value(s): {', '.join(empty[:4])}")

    for key, expected in PLACEHOLDERS.items():
        if key in table and placeholders(table[key]) != expected:
            problems.append(f"{key}: placeholders {sorted(placeholders(table[key]))} != {sorted(expected)}")

    for key, value in table.items():
        if has_positional(value):
            problems.append(f"{key}: positional placeholder '{{}}' (the GUI passes keyword arguments)")

    if code not in DENSE_SCRIPTS:
        scripted = sorted(k for k, v in table.items() if SCRIPT_RE.search(v))
        if scripted:
            problems.append(f"unexpected CJK in {len(scripted)} value(s): {', '.join(scripted[:3])}")

    tips = [len(v) for k, v in table.items() if k.endswith(":tip")]
    threshold = min_tip
    if min_tip and code in DENSE_SCRIPTS:
        threshold = min_tip_cjk if min_tip_cjk is not None else round(min_tip / CJK_DIVISOR)
    if threshold and tips and min(tips) < threshold:
        thin = sorted((len(v), k) for k, v in table.items()
                      if k.endswith(":tip") and len(v) < threshold)[:3]
        detail = ", ".join(f"{k}={n}" for n, k in thin)
        problems.append(f"tips thinner than {threshold}: {detail}")

    for key, value in table.items():
        if key.endswith(":tip"):
            problems.extend(paragraph_problems(key, value))

    problems.extend(quote_problems(code, table))
    problems.extend(dash_problems(code, table))
    return problems, warnings


def placeholder_parity_problems(packs: dict[str, dict[str, str]]) -> list[str]:
    """Every pack must use the same `{placeholder}` names for a key as the others.

    The GUI calls `.format(...)` with fixed keyword arguments, so a translator who renames or drops a
    placeholder either loses the value silently or raises a KeyError at run time.  Comparing the packs
    catches both without needing to know the English text.
    """
    codes = list(packs)
    if len(codes) < 2:
        return []
    common = set(packs[codes[0]])
    for code in codes[1:]:
        common &= set(packs[code])
    problems: list[str] = []
    for key in sorted(common):
        per_pack = {code: frozenset(placeholders(packs[code][key])) for code in codes}
        distinct = set(per_pack.values())
        if len(distinct) > 1:
            # report the minority against the most common form
            counts: dict[frozenset, int] = {}
            for form in per_pack.values():
                counts[form] = counts.get(form, 0) + 1
            canonical = max(counts, key=lambda f: counts[f])
            odd = [c for c in codes if per_pack[c] != canonical]
            problems.append(f"{key}: placeholder set differs in {', '.join(odd)} "
                            f"(expected {sorted(canonical)}, found {sorted(per_pack[odd[0]])})")
    return problems


def choices_problems(packs: dict[str, dict[str, str]]) -> list[str]:
    """The English tip of every enum option must name each of its choices.

    This is the guard against a tip inventing a value `validate()` would reject (the old
    "fast / balanced / slow" when the choices were fast / max).  Pack tips are not checked: nl, sv,
    fi and pl translate the choice words, so requiring the English tokens would fail on purpose.
    """
    try:
        import options
    except Exception as error:  # options sits next to us; a failure here is a real problem
        return [f"could not import options to cross-check: {error}"]
    problems: list[str] = []
    for o in options.OPTIONS:
        if o.kind != "enum" or not o.choices:
            continue
        tip = o.tip or ""
        absent = [choice for choice in o.choices if choice not in tip]
        if absent:
            problems.append(f"tip for {o.key} does not name choice(s): {absent}")
    return problems


def check_coverage(reference: set[str]) -> list[str]:
    """Cross-check the union of packs against what the engine and the option table ask for.

    The per-pack check only sees keys that some pack defines, so a key *no* pack defines is invisible
    to it.  This closes that gap against the option table and phases.PHASES, so a silently-English
    label fails instead of shrugging.
    """
    problems: list[str] = []
    try:
        import options
    except Exception as error:
        return [f"could not import options to cross-check: {error}"]
    for o in options.OPTIONS:
        for suffix in ("label", "tip"):
            key = f"opt:{o.key}:{suffix}"
            if key not in reference:
                problems.append(f"no pack defines {key}")
    for phase in phases.PHASES:
        if f"phase:{phase}" not in reference:
            problems.append(f"no pack defines phase:{phase}")
    return problems


def _engine_phase_order() -> list[str]:
    """The order of the engine's say() calls, source order, resolved through phases.py."""
    rnd = HERE / "randomize.py"
    tree = ast.parse(rnd.read_text(encoding="utf-8"))
    calls: list[tuple[int, int, str]] = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id == "say" and node.args):
            continue
        arg = node.args[0]
        if isinstance(arg, ast.Attribute) and isinstance(arg.value, ast.Name) and arg.value.id == "phases":
            value = getattr(phases, arg.attr, f"?{arg.attr}")
        elif isinstance(arg, ast.Constant) and isinstance(arg.value, str):
            value = arg.value
        else:
            continue
        calls.append((node.lineno, node.col_offset, value))
    calls.sort()
    order: list[str] = []
    for _, _, value in calls:
        if value not in order:
            order.append(value)
    return order


def phase_order_problems() -> list[str]:
    """Guard the progress bar: the engine's say() order must match phases.PHASES.

    This is the regression test for the bug where PHASES held a phantom "weapon effects" and missed
    "loot shuffle": _phase() caught the ValueError and silently reset the bar to 0.  The dry-run branch
    emits "done" before "compressing", so "done" is compared as the mandatory last entry rather than by
    first occurrence.
    """
    try:
        seen = _engine_phase_order()
    except (OSError, SyntaxError) as error:
        return [f"could not read the engine's phases: {error}"]
    declared = list(phases.PHASES)
    problems: list[str] = []
    missing = [p for p in declared if p not in seen]
    extra = [p for p in seen if p not in declared]
    if missing:
        problems.append(f"phase(s) in phases.py the engine never emits: {missing}")
    if extra:
        problems.append(f"engine emits phase(s) not in phases.py: {extra}")
    if len(declared) != len(set(declared)):
        problems.append("phases.py has duplicate entries")
    if declared and declared[-1] != "done":
        problems.append("phases.py must end with 'done'")
    if [p for p in declared if p != "done"] != [p for p in seen if p != "done"]:
        problems.append("the engine's say() order differs from phases.py")
    return problems


def _dict_value_nodes(text: str) -> dict[str, ast.expr]:
    """Map each key of the module's `T` dict to its value node, for surgical source edits."""
    tree = ast.parse(text)
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            targets = node.targets
        elif isinstance(node, ast.AnnAssign):
            targets = [node.target]
        else:
            continue
        if not isinstance(node.value, ast.Dict):
            continue
        if not any(getattr(t, "id", None) == "T" for t in targets):
            continue
        out: dict[str, ast.expr] = {}
        for key_node, value_node in zip(node.value.keys, node.value.values):
            if isinstance(key_node, ast.Constant) and isinstance(key_node.value, str):
                out[key_node.value] = value_node
        return out
    return {}


def fix_packs(packs: dict[str, dict[str, str]], only: set[str] | None = None) -> list[tuple[str, int]]:
    """Apply the safe mechanical fix to TIP VALUES only: a numeric range written with a hyphen -> en-dash.

    The edit is value-scoped through the AST, so a header comment or a date can never be touched (an
    earlier text-wide pass could have).  Only the unambiguous digit-hyphen-digit case is changed; quote
    balance is reported, not auto-fixed, because which quote opens and which closes needs a human.  A
    `.bak` is written next to every file that changes.
    """
    changed: list[tuple[str, int]] = []
    for code in sorted(packs):
        if only and code not in only:
            continue
        path = HERE / f"lang_{code}.py"
        try:
            raw = path.read_bytes()
        except OSError as error:
            print(f"{code}: cannot read {path.name}: {error}")
            continue
        crlf = b"\r\n" in raw
        text = raw.decode("utf-8").replace("\r\n", "\n")
        edits: list[tuple[str, str]] = []
        count = 0
        for key, node in _dict_value_nodes(text).items():
            if not key.endswith(":tip"):
                continue
            value = ast.literal_eval(node)
            new_value = RANGE_HYPHEN_RE.sub("\u2013", value)
            if new_value == value:
                continue
            seg = ast.get_source_segment(text, node)
            if not seg or text.count(seg) != 1:
                print(f"{code}: cannot safely edit {key}; skipped")
                continue
            edits.append((seg, json.dumps(new_value, ensure_ascii=False)))
            count += len(RANGE_HYPHEN_RE.findall(value))
        if not edits:
            continue
        new_text = text
        for seg, new_src in edits:
            new_text = new_text.replace(seg, new_src, 1)
        out = new_text.replace("\n", "\r\n") if crlf else new_text
        path.with_suffix(".py.bak").write_bytes(raw)
        path.write_bytes(out.encode("utf-8"))
        changed.append((code, count))
        print(f"{code}: fixed {count} range hyphen(s) -> en-dash (backup: {path.with_suffix('.py.bak').name})")
    if not changed:
        print("nothing to fix")
    return changed


def report(packs: dict[str, dict[str, str]], min_tip: int, quiet: bool = False,
           min_tip_cjk: int | None = None, strict_structure: bool = False) -> int:
    if not packs:
        print("no lang_<code>.py files found")
        return 1

    listed = {code for code, _ in i18n.LANGUAGES if code != "en"}
    problems_total: list[str] = []

    unlisted = sorted(set(packs) - listed)
    if unlisted:
        problems_total.append(f"pack(s) not in i18n.LANGUAGES: {', '.join(unlisted)}")

    reference = set()
    for table in packs.values():
        reference |= set(table)

    print(f"{'pack':<6}{'keys':>6}{'avg':>6}{'min':>6}  result" if not quiet else "")
    for code, table in sorted(packs.items()):
        problems, warnings = check_pack(code, table, reference, min_tip, min_tip_cjk)
        if strict_structure:
            problems = problems + warnings
        tips = [len(v) for k, v in table.items() if k.endswith(":tip")]
        avg = round(sum(tips) / len(tips)) if tips else 0
        low = min(tips) if tips else 0
        verdict = "OK" if not problems else "FAIL"
        if not quiet:
            print(f"{code:<6}{len(table):>6}{avg:>6}{low:>6}  {verdict}")
        for warning in warnings:
            if not strict_structure:
                print(f"        ! {code}: {warning}")
        for problem in problems:
            print(f"        - {code}: {problem}")
        problems_total.extend(f"{code}: {p}" for p in problems)

    for problem in check_coverage(reference):
        print(f"        - {problem}")
        problems_total.append(problem)

    for problem in choices_problems(packs):
        print(f"        - {problem}")
        problems_total.append(problem)

    for problem in placeholder_parity_problems(packs):
        print(f"        - {problem}")
        problems_total.append(problem)

    for problem in input_decimal_problems(packs):
        print(f"        - {problem}")
        problems_total.append(problem)

    for problem in phase_order_problems():
        print(f"        - {problem}")
        problems_total.append(problem)

    missing_packs = sorted(listed - set(packs))
    if missing_packs:
        problems_total.append(f"listed but no pack: {', '.join(missing_packs)}")

    print()
    if problems_total:
        print(f"FAIL - {len(problems_total)} problem(s)")
        return 1
    scope = f"{len(packs)} packs, {len(reference)} keys"
    if min_tip == 0:
        print(f"PASS - {scope}, depth reported only")
    elif min_tip_cjk is not None:
        print(f"PASS - {scope}, tips >= {min_tip} (ja/zh >= {min_tip_cjk})")
    else:
        print(f"PASS - {scope}, tips >= {min_tip} (ja/zh >= {round(min_tip / CJK_DIVISOR)})")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check the GUI language packs.")
    parser.add_argument("--min-tip", type=int, default=0, metavar="N",
                        help="fail when a tip is shorter than N characters (default 0: report only)")
    parser.add_argument("--min-tip-cjk", type=int, default=None, metavar="N",
                        help=f"threshold for ja/zh, which fit more per character "
                             f"(default: --min-tip / {CJK_DIVISOR})")
    parser.add_argument("--strict-structure", action="store_true",
                        help="treat single-block tips as failures instead of warnings")
    parser.add_argument("--quiet", action="store_true", help="print only the verdict and any problems")
    parser.add_argument("--fix", action="store_true",
                        help="apply the safe mechanical fixes (range hyphen -> en-dash), writing a .bak")
    parser.add_argument("--lang", action="append", default=None, metavar="CODE",
                        help="with --fix, only fix these language codes (repeatable)")
    args = parser.parse_args(argv)
    packs = load_packs()
    if args.fix:
        fix_packs(packs, set(args.lang) if args.lang else None)
        packs = load_packs()          # reload so the report reflects the fix
    return report(packs, args.min_tip, args.quiet, args.min_tip_cjk, args.strict_structure)


if __name__ == "__main__":
    sys.exit(main())