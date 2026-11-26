#!/usr/bin/env python3
"""Zip a release from the *contents* of dist/, with an additive whitelist.

dist/ is also the program's live workspace: settings.json, randomized/, backups/ and test results
live there.  Copying the folder wholesale would ship the developer's input paths and saves.  This
module picks only what a player needs: the exe, the shipped msg archives, the optional loot-variants
DLL and sample ini.  The docs (README and the two generated Nexus descriptions) are read straight
from the repo root, so dist/ never keeps a stale copy.  The DLL is built by
mods/loot-variants/build.ps1 and placed in dist/ by that script; if it is missing the zip is still
made, but the tool says so loudly.
"""
from __future__ import annotations

import argparse
import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
EXE = "EldenRingSuperRandomizer.exe"
DLL = "loot_variants.dll"                       # required warning; the other native is optional too
DLLS = ("loot_variants.dll", "shops_periodic.dll")
INIS = ("loot_variants.ini", "shops_periodic.ini")
DOCS = ("README.md", "NEXUS_DESCRIPTION.txt", "NEXUS_DESCRIPTION.strict.txt")


def collect_release_files(dist: Path) -> list[Path]:
    """Paths relative to dist/, sorted; only files that actually exist."""
    dist = Path(dist)
    out: list[Path] = []
    for name in (EXE, *DLLS, *INIS):
        if (dist / name).is_file():
            out.append(Path(name))
    msg = dist / "msg"
    if msg.is_dir():
        out.extend(p.relative_to(dist) for p in sorted(msg.rglob("*")) if p.is_file())
    return sorted(set(out))


def doc_sources() -> list[Path]:
    """The docs ship straight from the repo root, never staged into the live dist/ workspace."""
    return [ROOT / name for name in DOCS if (ROOT / name).is_file()]


def make_release(dist: Path, target: Path) -> tuple[int, int]:
    """Write the zip; returns (bytes written, file count)."""
    files = collect_release_files(dist)
    docs = doc_sources()
    target.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for rel in files:
            zf.write(Path(dist) / rel, rel.as_posix())
        for source in docs:
            zf.write(source, source.name)
    return target.stat().st_size, len(files) + len(docs)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dist", default=str(ROOT / "dist"), help="the PyInstaller output folder")
    ap.add_argument("--out", help="zip path (default: <repo>/<name>-<version>.zip)")
    ap.add_argument("--check", action="store_true", help="only list what would be shipped")
    args = ap.parse_args(argv)
    sys.path.insert(0, str(HERE))
    import version

    dist = Path(args.dist)
    files = collect_release_files(dist)
    docs = doc_sources()
    if args.check:
        for rel in sorted([*files, *(Path(d.name) for d in docs)]):
            print(rel.as_posix())
        return 0
    if not any(p.name == EXE for p in files):
        print(f"# error: {dist / EXE} is missing - run build_exe.bat first", file=sys.stderr)
        return 1
    if not any(p.name == DLL for p in files):
        print(f"# warning: {dist / DLL} is missing - run mods/loot-variants/build.ps1 "
              "to ship the optional runtime mod", file=sys.stderr)
    target = Path(args.out) if args.out else ROOT / f"{dist.name}-{version.__version__}.zip"
    size, count = make_release(dist, target)
    print(f"# release: {target} ({size:,} bytes, {count} files)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
