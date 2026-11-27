#!/usr/bin/env python3
"""Check the native mod's AOB patterns against a game executable before a game update lands.

Run after updating Elden Ring:

    python tools/verify_aobs.py                       # default install path
    python tools/verify_aobs.py --exe <path>          # another install / Steam library

If a give-call pattern no longer matches, that call site is skipped; the DLL only logs `inert` when
*both* give patterns fail. The other three patterns only gate the optional auto-equip feature. This
script tells you *which* pattern broke so the source can be updated. The two give-call patterns must
resolve to the same target: that is the function the detour hooks at every call site.
"""
from __future__ import annotations

import argparse
import struct
from pathlib import Path

DEFAULT_EXE = Path(r"C:\Games\ELDEN RING\Game\eldenring.exe")

# name -> (pattern, call offset in the match, expected minimum hits)
PATTERNS = {
    "give/map": ("4C 8D 45 34 48 8D 55 90 49 8B CC E8 ?? ?? ?? ?? "
                 "48 8B 05 ?? ?? ?? ?? 48 85 C0 75 2E", 11, 1),
    "give/lua": ("44 8B 4C 24 34 4C 8D 45 74 48 8D 55 D0 49 8B CC E8 ?? ?? ?? ?? "
                 "83 7D 98 00 74 68", 16, 1),
    "get_inventory_id": ("48 8D 8F 58 01 00 00 E8 ?? ?? ?? ?? 8B D8 85 C0 78 6A", 7, 1),
    "equip_item": ("57 48 83 EC 20 48 8B F9 48 83 C1 10 E8 ?? ?? ?? ?? 8B 4F 08 "
                   "48 8D 57 10 E8 ?? ?? ?? ?? E8 ?? ?? ?? ?? 44 8B 47 58", 0, 1),
    "WorldChrMan singleton": ("48 8B ?? ???????? 48 85 ?? 75 2E 48 8D 0D ???????? "
                              "E8 ???????? 4C 8B C8 4C 8D 05 ???????? BA ?? ?? 00 00 "
                              "48 8D 0D ???????? E8 ????????", 0, 1),
}


def parse(pattern: str) -> tuple[bytes, bytes]:
    needle = bytearray()
    mask = bytearray()
    for token in pattern.split():
        if token and set(token) == {"?"}:          # ?? = one byte, ???????? = four bytes
            count = len(token) // 2
            needle.extend(b"\0" * count)
            mask.extend(b"\0" * count)
        else:
            needle.append(int(token, 16))
            mask.append(1)
    return bytes(needle), bytes(mask)


def scan(data: bytes, pattern: str, limit: int = 20) -> list[int]:
    needle, mask = parse(pattern)
    anchor = next(i for i, m in enumerate(mask) if m)
    first = needle[anchor:anchor + 1]
    hits: list[int] = []
    start = 0
    while len(hits) < limit:
        pos = data.find(first, start)
        if pos < 0:
            break
        begin = pos - anchor
        if begin < 0 or begin + len(needle) > len(data):
            start = pos + 1
            continue
        if all(m == 0 or data[begin + i] == b
                              for i, (m, b) in enumerate(zip(mask, needle))):
            hits.append(begin)
        start = pos + 1
    return hits


def call_target(data: bytes, match: int, offset: int) -> int | None:
    call = match + offset
    if call + 5 > len(data) or data[call] != 0xE8:
        return None
    return call + 5 + struct.unpack_from("<i", data, call + 1)[0]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--exe", default=str(DEFAULT_EXE), help="path to eldenring.exe")
    args = ap.parse_args(argv)
    path = Path(args.exe)
    if not path.is_file():
        print(f"# error: {path} does not exist")
        return 1
    data = path.read_bytes()
    print(f"# {path} ({len(data):,} bytes)")
    targets: dict[str, int] = {}
    failed = False
    for name, (pattern, call_offset, minimum) in PATTERNS.items():
        hits = scan(data, pattern)
        ok = len(hits) >= minimum
        failed |= not ok
        count = f"{len(hits)}+" if len(hits) >= 20 else str(len(hits))
        print(f"  {'OK  ' if ok else 'FAIL'} {name}: {count} hit(s) at "
              + ", ".join(hex(h) for h in hits[:5]))
        if name.startswith("give/") and hits:
            target = call_target(data, hits[0], call_offset)
            if target is None:
                failed = True
                print(f"       no E8 at the expected call offset in {name}")
            else:
                targets[name] = target
    if len(targets) == 2 and len(set(targets.values())) == 1:
        print(f"  OK   both give patterns target file offset {next(iter(targets.values())):#x}")
    elif len(targets) == 2:
        failed = True
        print(f"  FAIL give patterns disagree: {targets}")
    print("# all AOBs match; the DLL's offsets are still plausible" if not failed else
          "# some patterns changed - update mods/loot-variants/src/loot_variants.cpp before shipping")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
