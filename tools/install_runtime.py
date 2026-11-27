#!/usr/bin/env python3
"""Install an optional native mod (loot-variants or shops-periodic) into a Mod Engine 3 folder.

--loot-variants writes loot_variants.txt and --random-shop-stock writes shops_periodic.txt; the DLLs
that act on them are separate, optional files.  This
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
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DLL_NAME = "loot_variants.dll"
INI_NAME = "loot_variants.ini"
DEFAULT_TARGET = Path(r"C:\Games\ERR\dll\offline")

# One entry per optional native mod: the shipped names, the env overrides and the source-tree hints.
_KINDS: dict[str, dict[str, str]] = {
    "loot_variants": {"dll": "loot_variants.dll", "ini": "loot_variants.ini",
                      "mod_dir": "loot-variants", "env_dll": "LOOT_VARIANTS_DLL",
                      "env_dir": "LOOT_VARIANTS_DLL_DIR",
                      "hint": "Run: pwsh -NoProfile -File mods\\loot-variants\\build.ps1"},
    "shops_periodic": {"dll": "shops_periodic.dll", "ini": "shops_periodic.ini",
                       "mod_dir": "shops-periodic", "env_dll": "SHOPS_PERIODIC_DLL",
                       "env_dir": "SHOPS_PERIODIC_DLL_DIR",
                       "hint": "Run: pwsh -NoProfile -File mods\\shops-periodic\\build.ps1"},
}


def program_dir() -> Path:
    """Next to the frozen exe, or the repo root when running from source (backup.py's convention)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return HERE.parent


def find_dll(source: str | Path | None = None, kind: str = "loot_variants") -> Path | None:
    """Where the built DLL can be: explicit path, env override, or one of the build outputs."""
    names = _KINDS[kind]
    if source:
        p = Path(source).expanduser()
        return p if p.is_file() else None
    env = os.environ.get(names["env_dll"])
    if env and Path(env).is_file():
        return Path(env)
    root = program_dir()
    candidates = [
        root / "dist" / names["dll"],                       # the shipped location
        root / "mods" / names["mod_dir"] / "dist" / names["dll"],
        root / names["dll"],
        HERE / "dist" / names["dll"],
    ]
    return next((p for p in candidates if p.is_file()), None)


def _discovered_targets() -> list[Path]:
    """Mod roots found from the game's own location: Steam libraries, registry and usual folders."""
    try:
        import discover
    except (OSError, ImportError):
        return []
    roots: list[Path] = []
    for finder in (discover.err_folders, discover.game_dirs):
        try:
            roots.extend(finder())
        except OSError:
            continue
    out: list[Path] = []
    for root in roots:
        # A real Mod Engine root has mod/regulation.bin; keep the old guard so a folder that merely
        # happens to contain dll/offline cannot collect the native mod.
        if not (root / "mod" / "regulation.bin").is_file():
            continue
        for candidate in (root / "dll" / "offline", root.parent / "dll" / "offline"):
            if candidate.is_dir() and candidate not in out:
                out.append(candidate)
    return out


def find_target(dll_dir: str | Path | None = None, kind: str = "loot_variants") -> Path | None:
    """The Mod Engine `dll\\offline` folder: explicit, env, then discovered from the game path."""
    if dll_dir:
        return Path(dll_dir).expanduser()
    env = os.environ.get(_KINDS[kind]["env_dir"])
    if env:
        return Path(env)
    candidates = [DEFAULT_TARGET, *_discovered_targets()]
    return next((p for p in candidates if p.is_dir()), None)


def _digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def _copy_atomic(src: Path, dst: Path) -> None:
    """Write to a sibling temp file then replace, so readers never see a partial DLL."""
    import atomicio  # local: keeps this module importable on its own

    atomicio.atomic_copy(src, dst)


def install(source: str | Path | None = None, dll_dir: str | Path | None = None,
            kind: str = "loot_variants") -> list[str]:
    """Copy the DLL and, if absent, the sample ini.  Returns human-readable lines; raises ValueError
    only for a missing source or target (the caller turns that into a user-facing error)."""
    names = _KINDS[kind]
    dll = find_dll(source, kind)
    if dll is None:
        raise ValueError(f"cannot find {names['dll']}. {names['hint']}")
    target = find_target(dll_dir, kind)
    if target is None:
        raise ValueError("cannot find a Mod Engine dll\\offline folder; pass --dll-dir <mod>\\dll\\offline")
    if not target.is_dir():
        raise ValueError(f"install folder does not exist: {target}")

    lines = [f"# runtime mod: {dll}", f"# install folder: {target}"]
    dst = target / names["dll"]
    if dst.is_file() and _digest(dst) == _digest(dll):
        lines.append(f"# {names['dll']} is already up to date (unchanged)")
    else:
        _copy_atomic(dll, dst)
        lines.append(f"# installed {dst}")

    names = _KINDS[kind]
    ini_name = names["ini"]
    candidates = [program_dir() / ini_name,                       # released zip: ini at dist root
                  target / ".." / ini_name,                       # source tree: beside dll/offline
                  program_dir() / "mods" / names["mod_dir"] / ini_name,
                  HERE / ini_name]
    ini_src = next((p for p in candidates if p.is_file()), None)
    ini_dst = target / ini_name
    if ini_src is not None and not ini_dst.exists():
        _copy_atomic(ini_src, ini_dst)
        lines.append(f"# installed a fresh {ini_dst} (your settings can be changed there)")
    elif ini_dst.exists():
        lines.append(f"# kept your existing {ini_dst}")
    manifest = "loot_variants.txt" if kind == "loot_variants" else "shops_periodic.txt"
    lines.append(f"# the randomizer writes {manifest} into its output folder and, with Backup and "
                 "replace, copies it beside regulation.bin automatically; otherwise copy it there yourself")
    return lines


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--kind", choices=sorted(_KINDS), default="loot_variants",
                    help="which optional native mod to install (default: loot_variants)")
    ap.add_argument("--source", help="path to the DLL (default: search the build outputs)")
    ap.add_argument("--dll-dir", help="the Mod Engine dll\\offline folder (default: auto-detect)")
    ap.add_argument("--check", action="store_true", help="only report what would be installed")
    args = ap.parse_args(argv)
    try:
        if args.check:
            print(f"# DLL: {find_dll(args.source, args.kind) or 'NOT FOUND'}")
            print(f"# target: {find_target(args.dll_dir, args.kind) or 'NOT FOUND'}")
            return 0
        for line in install(args.source, args.dll_dir, args.kind):
            print(line)
    except (ValueError, OSError) as e:
        print(f"# error: {e}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
