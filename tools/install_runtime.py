#!/usr/bin/env python3
"""Install the optional loot-variants native mod into a Mod Engine 3 game folder.

--loot-variants writes loot_variants.txt; the DLL that acts on it is a separate, optional file.  This
module finds the DLL the build produced and copies it (plus a fresh ini, if there is none) into the
`dll\\offline` folder that Mod Engine auto-loads.  Nothing here ever touches regulation.bin or a save.

It is deliberately fail-soft and idempotent: a missing DLL, a missing target or an identical file is a
clear message, not a traceback, and an existing ini is never overwritten.  The copy is atomic, so a
cancelled or interrupted install cannot leave a half-written DLL in the game folder.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DLL_NAME = "loot_variants.dll"
INI_NAME = "loot_variants.ini"
DEFAULT_TARGET = Path(r"C:\Games\ERR\dll\offline")
SOURCE_HINT = "Run: pwsh -NoProfile -File mods\\loot-variants\\build.ps1 (then copy dist\\loot_variants.dll here)."


def program_dir() -> Path:
    """Next to the frozen exe, or the repo root when running from source (backup.py's convention)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return HERE.parent


def find_dll(source: str | Path | None = None) -> Path | None:
    """Where the built DLL can be: explicit path, env override, or one of the build outputs."""
    if source:
        p = Path(source).expanduser()
        return p if p.is_file() else None
    env = os.environ.get("LOOT_VARIANTS_DLL")
    if env and Path(env).is_file():
        return Path(env)
    root = program_dir()
    candidates = [
        root / "dist" / DLL_NAME,                          # the shipped location
        root / "mods" / "loot-variants" / "dist" / DLL_NAME,
        root / DLL_NAME,
        HERE / "dist" / DLL_NAME,
    ]
    return next((p for p in candidates if p.is_file()), None)


def find_target(dll_dir: str | Path | None = None) -> Path | None:
    """The Mod Engine `dll\\offline` folder: explicit, env, the known ERR layout, then a scan."""
    if dll_dir:
        return Path(dll_dir).expanduser()
    env = os.environ.get("LOOT_VARIANTS_DLL_DIR")
    if env:
        return Path(env)
    if DEFAULT_TARGET.is_dir():
        return DEFAULT_TARGET
    # C:\Games\ERR itself can be a mod root, as can any sibling folder under C:\Games.
    for parent in (DEFAULT_TARGET.parents[1], DEFAULT_TARGET.parents[2]):
        if not parent.is_dir():
            continue
        try:
            children = sorted(parent.iterdir())
        except OSError:
            continue
        for child in (parent, *children):
            target = child / "dll" / "offline"
            if target.is_dir() and (child / "mod" / "regulation.bin").is_file():
                return target
    return None


def _digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def _copy_atomic(src: Path, dst: Path) -> None:
    """Write to a sibling temp file then replace, so readers never see a partial DLL."""
    import tempfile

    fd, name = tempfile.mkstemp(prefix=dst.name + ".", suffix=".tmp", dir=dst.parent)
    tmp = Path(name)
    os.close(fd)
    try:
        shutil.copy2(src, tmp)
        os.replace(tmp, dst)
    finally:
        if tmp.exists():
            tmp.unlink()


def install(source: str | Path | None = None, dll_dir: str | Path | None = None) -> list[str]:
    """Copy the DLL and, if absent, the sample ini.  Returns human-readable lines; raises ValueError
    only for a missing source or target (the caller turns that into a user-facing error)."""
    dll = find_dll(source)
    if dll is None:
        raise ValueError(f"cannot find {DLL_NAME}. {SOURCE_HINT}")
    target = find_target(dll_dir)
    if target is None:
        raise ValueError("cannot find a Mod Engine dll\\offline folder; pass --dll-dir <mod>\\dll\\offline")
    if not target.is_dir():
        raise ValueError(f"install folder does not exist: {target}")

    lines = [f"# runtime mod: {dll}", f"# install folder: {target}"]
    dst = target / DLL_NAME
    if dst.is_file() and _digest(dst) == _digest(dll):
        lines.append(f"# {DLL_NAME} is already up to date (unchanged)")
    else:
        _copy_atomic(dll, dst)
        lines.append(f"# installed {dst}")

    candidates = [program_dir() / INI_NAME,                       # released zip: ini at dist root
                  target / ".." / INI_NAME,                       # source tree: beside dll/offline
                  program_dir() / "mods" / "loot-variants" / INI_NAME,
                  HERE / INI_NAME]
    ini_src = next((p for p in candidates if p.is_file()), None)
    ini_dst = target / INI_NAME
    if ini_src is not None and not ini_dst.exists():
        _copy_atomic(ini_src, ini_dst)
        lines.append(f"# installed a fresh {ini_dst} (your settings can be changed there)")
    elif ini_dst.exists():
        lines.append(f"# kept your existing {ini_dst}")
    lines.append("# the randomizer writes loot_variants.txt next to regulation.bin; copy both files together")
    return lines


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--source", help=f"path to {DLL_NAME} (default: search the build outputs)")
    ap.add_argument("--dll-dir", help="the Mod Engine dll\\offline folder (default: auto-detect)")
    ap.add_argument("--check", action="store_true", help="only report what would be installed")
    args = ap.parse_args(argv)
    try:
        if args.check:
            print(f"# DLL: {find_dll(args.source) or 'NOT FOUND'}")
            print(f"# target: {find_target(args.dll_dir) or 'NOT FOUND'}")
            return 0
        for line in install(args.source, args.dll_dir):
            print(line)
    except (ValueError, OSError) as e:
        print(f"# error: {e}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
