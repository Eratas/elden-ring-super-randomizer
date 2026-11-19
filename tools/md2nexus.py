#!/usr/bin/env python3
"""Render README.md as a Nexus Mods description (BBCode).

Why this exists: Nexus Mods' description editor takes **BBCode, not Markdown**.  There is no Markdown
support and none is planned (the site's own suggestion board has an open, unanswered request for it), so
a README.md cannot simply be pasted into a mod page.  The usual answer is a converter, and a
*generated* file rather than a second hand-written one: two documents describing the same tool drift the
first time either is edited.

    python tools/md2nexus.py            # rewrite NEXUS_DESCRIPTION.txt (and .strict.txt) from README.md
    python tools/md2nexus.py --check    # exit 1 if either checked-in file is stale (gate.py runs this)
    python tools/md2nexus.py --stdout   # print the normal render instead of writing
    python tools/md2nexus.py --stdout --strict-tags   # ... the wiki-tags-only render

Two artifacts are generated from the same README:

    NEXUS_DESCRIPTION.txt         the normal render; fenced blocks use [code]
    NEXUS_DESCRIPTION.strict.txt  fenced blocks use [quote] instead

[code] is what Nexus's own Markdown->BBCode converters emit, but it is *not* in the Nexus wiki's tag
list, so it could not be verified against the live site.  The strict render uses only tags the wiki
documents, at the cost of code blocks looking like quotes.  Both are generated and both are checked by
the gate, so neither can rot: use the strict one for a first upload if you want zero risk.

Mapping (only tags the Nexus wiki documents, plus [code]):

    # / ##            [heading]           ### and deeper  [b]
    **bold**          [b]                 *italic*        [i]
    `code`            plain text          (Nexus has no inline code tag)
    fenced block      [code]              ---             [line]
    - item            [list] [*]          1. item         [list=1] [*]
    [text](url)       [url=url]text[/url] (no quotes around the url - the wiki warns Nexus rejects them)
    | a | b |         [list] of "a | b" rows, the header row in [b] (Nexus has no table tag)

Nothing else is emitted: `--check` and the gate fail if the output ever contains a tag outside
ALLOWED_TAGS, so the document cannot silently start depending on markup the site may not render.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SOURCE = ROOT / "README.md"
TARGET = ROOT / "NEXUS_DESCRIPTION.txt"
STRICT_TARGET = ROOT / "NEXUS_DESCRIPTION.strict.txt"

# Every BBCode tag this renderer may emit.  All of them are in the Nexus wiki's tag list except [code]:
# that one is what Nexus's own Markdown->BBCode converters emit for fenced blocks.  The strict render
# swaps it for [quote], which is documented, so the strict artifact only ever uses wiki tags.
ALLOWED_TAGS = {"b", "i", "u", "s", "heading", "line", "list", "*", "url", "code", "quote",
                "color", "center", "right", "font", "img", "youtube", "spoiler"}
DOCUMENTED_TAGS = ALLOWED_TAGS - {"code"}     # what the strict render is allowed to use
CODE_OPEN, CODE_CLOSE = "[code]", "[/code]"
STRICT_CODE_OPEN, STRICT_CODE_CLOSE = "[quote]", "[/quote]"

BULLET = re.compile(r"^(\s*)([-*])\s+(.*)$")
NUMBERED = re.compile(r"^(\s*)(\d+)\.\s+(.*)$")
HEADING = re.compile(r"^(#{1,6})\s+(.*)$")
RULE = re.compile(r"^\s*(-{3,}|\*{3,}|_{3,})\s*$")
FENCE = re.compile(r"^\s*(```|~~~)")
LINK = re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)")
BOLD = re.compile(r"\*\*(.+?)\*\*")
ITALIC = re.compile(r"(?<![*\w])\*([^*\n]+)\*(?![*\w])")


def inline(text: str) -> str:
    """One line of Markdown text -> BBCode.

    Inline code is stashed behind a placeholder before anything else runs.  Splitting on the backticks
    instead would let a `**bold `code` bold**` pair leave its ** markers orphaned on either side of the
    stash, which is exactly what the first version of this file did.
    """
    codes: list[str] = []

    def stash(match: re.Match[str]) -> str:
        codes.append(match.group(1))
        return f"\x00{len(codes) - 1}\x00"

    masked = re.sub(r"`([^`\n]+)`", stash, text)
    masked = LINK.sub(r"[url=\2]\1[/url]", masked)
    masked = BOLD.sub(r"[b]\1[/b]", masked)
    masked = ITALIC.sub(r"[i]\1[/i]", masked)
    return re.sub(r"\x00(\d+)\x00", lambda m: codes[int(m.group(1))], masked)


def _cells(row: str) -> list[str]:
    """Split a Markdown table row on pipes that are not inside `code`."""
    row = row.strip()
    if row.startswith("|"):
        row = row[1:]
    if row.endswith("|") and not row.endswith("\\|"):
        row = row[:-1]
    cells, buf, in_code = [], [], False
    for ch in row:
        if ch == "`":
            in_code = not in_code
            buf.append(ch)
        elif ch == "|" and not in_code:
            cells.append("".join(buf).strip())
            buf = []
        else:
            buf.append(ch)
    cells.append("".join(buf).strip())
    return cells


def _is_separator(row: str) -> bool:
    return bool(re.match(r"^\s*\|?[\s:|-]+\|[\s:|-]*$", row)) and "-" in row


def table(rows: list[str]) -> list[str]:
    """A Markdown table -> a BBCode list of "a | b | c" rows, the header in bold.

    Nexus has no table tag.  A list keeps the data and reads fine; alignment is not preserved, which is
    the honest trade-off for markup the site actually supports.
    """
    grid = [_cells(r) for r in rows if not _is_separator(r)]
    if not grid:
        return []
    width = max(len(r) for r in grid)
    out = ["[list]"]
    for n, row in enumerate(grid):
        cells = row + [""] * (width - len(row))
        line = " | ".join(inline(c) for c in cells)
        out.append(f"[*] [b]{line}[/b]" if n == 0 else f"[*] {line}")
    out.append("[/list]")
    return out


def render(markdown: str, strict: bool = False) -> str:
    """The whole document.  Deterministic: the same README always yields the same BBCode.

    `strict` swaps the fenced-block wrapper from [code] to [quote], so the result only uses tags the
    Nexus wiki documents.
    """
    code_open, code_close = (STRICT_CODE_OPEN, STRICT_CODE_CLOSE) if strict else (CODE_OPEN, CODE_CLOSE)
    lines = markdown.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    out: list[str] = []
    i, n = 0, len(lines)

    def para(start: int) -> int:
        buf: list[str] = []
        while start < n:
            line = lines[start]
            if not line.strip():
                break
            if buf and (HEADING.match(line) or RULE.match(line) or FENCE.match(line)
                        or line.lstrip().startswith("|") or BULLET.match(line) or NUMBERED.match(line)):
                break
            buf.append(line.strip())
            start += 1
        if buf:
            out.append(inline(" ".join(buf)))
            out.append("")
        return start

    while i < n:
        line = lines[i]

        if FENCE.match(line):
            i += 1
            buf = []
            while i < n and not FENCE.match(lines[i]):
                buf.append(lines[i])
                i += 1
            i += 1                                 # the closing fence
            out.append(code_open)
            out.extend(buf)
            out.append(code_close)
            out.append("")
            continue

        if not line.strip():
            i += 1
            continue

        m = HEADING.match(line)
        if m:
            level, text = len(m.group(1)), m.group(2)
            body = inline(text)
            out.append(f"[heading]{body}[/heading]" if level <= 2 else f"[b]{body}[/b]")
            out.append("")
            i += 1
            continue

        if RULE.match(line):
            out.append("[line]")
            out.append("")
            i += 1
            continue

        if line.lstrip().startswith("|"):
            rows = []
            while i < n and lines[i].lstrip().startswith("|"):
                rows.append(lines[i])
                i += 1
            out.extend(table(rows))
            out.append("")
            continue

        m = BULLET.match(line) or NUMBERED.match(line)
        if m:
            ordered = NUMBERED.match(line) is not None
            items: list[str] = []
            while i < n:
                item = BULLET.match(lines[i]) or NUMBERED.match(lines[i])
                if item:
                    items.append(item.group(3))
                    i += 1
                    continue
                # a wrapped list item continues on an indented line until a blank or a new block
                if items and lines[i].startswith((" ", "\t")) and lines[i].strip() \
                        and not (HEADING.match(lines[i]) or FENCE.match(lines[i])
                                 or lines[i].lstrip().startswith("|")):
                    items[-1] = items[-1] + " " + lines[i].strip()
                    i += 1
                    continue
                break
            out.append("[list=1]" if ordered else "[list]")
            out.extend(f"[*] {inline(x)}" for x in items)
            out.append("[/list]")
            out.append("")
            continue

        i = para(i)

    text = "\n".join(out)
    text = re.sub(r"\n{3,}", "\n\n", text)          # collapse runs of blank lines
    return text.strip() + "\n"


def bracket_tokens(text: str, strict: bool = False) -> list[str]:
    """Lowercased names of every ``[tag]`` / ``[tag=x]`` token outside a fenced block.

    A fenced block is excluded because its content is literal by definition: the README's ASCII mock-up
    contains ``[Preview] [Repack only] [Randomize]`` and its TOML contains ``[extension.regulation]``,
    which are not markup.  In a strict render the wrapper is [quote], so that is what gets excluded.
    Everywhere else a bracket token is markup, and must be allowed - that is the whole check: it fails
    both if this renderer starts emitting a tag the site may not support, and if prose ever starts
    containing a literal ``[b]`` Nexus would silently turn into bold.
    """
    code_open, code_close = (STRICT_CODE_OPEN, STRICT_CODE_CLOSE) if strict else (CODE_OPEN, CODE_CLOSE)
    outside = re.sub(rf"{re.escape(code_open)}.*?{re.escape(code_close)}", "", text, flags=re.DOTALL)
    return [m.group(1).lower() for m in re.finditer(r"\[/?([a-zA-Z*]+)(?:=[^\]]*)?\]", outside)]


STRAY_MARKERS = (("**", "bold"), ("`", "backtick"), ("](", "link"), ("##", "heading"))


def problems(text: str, strict: bool = False) -> list[str]:
    """Everything wrong with a rendered document, as human-readable lines.

    Three invariants, all of which have broken at least once:

      * only allowed tags - the site may not render anything else (and a strict render only uses tags
        the Nexus wiki documents, so [code] must not appear in one);
      * no leftover Markdown outside a fenced block - an orphaned `**` is bold that never opened;
      * every BBCode tag balanced - an unclosed [list] swallows the rest of the page.
    """
    bad: list[str] = []
    allowed = DOCUMENTED_TAGS if strict else ALLOWED_TAGS
    unknown = sorted({t for t in bracket_tokens(text, strict=strict) if t not in allowed})
    if unknown:
        bad.append(f"tags outside the allowed set: {unknown} "
                   f"(a literal [b] in prose, or a new tag this renderer emits)")
    code_open, code_close = (STRICT_CODE_OPEN, STRICT_CODE_CLOSE) if strict else (CODE_OPEN, CODE_CLOSE)
    outside = re.sub(rf"{re.escape(code_open)}.*?{re.escape(code_close)}", "", text, flags=re.DOTALL)
    for marker, what in STRAY_MARKERS:
        if marker in outside:
            bad.append(f"stray Markdown {what} marker {marker!r} outside a fenced block")
    # a tag that wraps a fenced block is counted on the whole text: its spans are excluded from `outside`
    whole = {"code"} | ({"quote"} if strict else set())
    for name in sorted(allowed - {"line", "*"}):       # line and * are void tags
        scope = text if name in whole else outside
        opens = len(re.findall(rf"\[{re.escape(name)}(?:=[^\]]*)?\]", scope))
        closes = len(re.findall(rf"\[/{re.escape(name)}\]", scope))
        if opens != closes:
            bad.append(f"unbalanced [{name}]: {opens} opening, {closes} closing")
    return bad


def stray_source_tags(markdown: str) -> list[str]:
    """Literal ``[tag]`` tokens in the *Markdown* that Nexus would read as markup.

    A fenced block is exempt (its content is literal by definition) and so is a Markdown link
    ``[text](url)``.  Anything else that spells a known tag - a literal [b] in prose - would reach the
    page as a formatting toggle nobody wrote, so the source is checked rather than the output: the output
    cannot tell an intentional [b] from an accidental one.
    """
    outside = re.sub(r"^[`~]{3,}[^\n]*\n.*?^[`~]{3,}\s*$", "", markdown, flags=re.DOTALL | re.MULTILINE)
    outside = re.sub(r"\[[^\]]*\]\([^)]*\)", "", outside)
    return sorted({m.group(1).lower()
                   for m in re.finditer(r"\[/?([a-zA-Z*]+)(?:=[^\]]*)?\]", outside)
                   if m.group(1).lower() in ALLOWED_TAGS})


def main(argv: list[str]) -> int:
    check = "--check" in argv
    stdout = "--stdout" in argv
    strict = "--strict-tags" in argv
    if not SOURCE.is_file():
        print(f"md2nexus: {SOURCE} is missing", file=sys.stderr)
        return 2
    markdown = SOURCE.read_text(encoding="utf-8")

    stray = stray_source_tags(markdown)
    if stray:
        print(f"md2nexus: {SOURCE.name} contains literal {stray} outside a fenced block; Nexus would "
              f"read {stray[0]} as markup.  Escape it or move it into a fenced block.", file=sys.stderr)
        return 4

    if stdout:
        rendered = render(markdown, strict=strict)
        bad = problems(rendered, strict=strict)
        if bad:
            for line in bad:
                print(f"md2nexus: {line}", file=sys.stderr)
            return 3
        sys.stdout.write(rendered)
        return 0

    stale: list[str] = []
    for target, use_strict in ((TARGET, False), (STRICT_TARGET, True)):
        rendered = render(markdown, strict=use_strict)
        bad = problems(rendered, strict=use_strict)
        if bad:
            for line in bad:
                print(f"md2nexus: {target.name}: {line}", file=sys.stderr)
            return 3
        if check:
            if not target.is_file() or target.read_text(encoding="utf-8") != rendered:
                stale.append(target.name)
        else:
            target.write_text(rendered, encoding="utf-8")
            print(f"md2nexus: wrote {target.name} "
                  f"({len(rendered)} bytes, {len(rendered.splitlines())} lines)")

    if check:
        if stale:
            print(f"md2nexus: stale - run 'python tools/md2nexus.py': {', '.join(stale)}")
            return 1
        print("md2nexus: both Nexus descriptions are current")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))