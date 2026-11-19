"""Backup and restore the user's files before a "backup and replace" run.

The randomizer writes its result to an output folder (default ``randomized/`` inside the program
folder).  When the "Backup and replace files" option is on, the engine also copies the *input*
files the user pointed at - their ``regulation.bin`` and the ``msg/<lang>/item_dlc02.msgbnd.dcx``
archives - into a timestamped backup folder under ``<program>/backups/`` **before** overwriting
them with the freshly generated ones.  A revert puts every file back exactly where it came from.

A backup folder holds the copied files plus a ``manifest.json`` that records each file's original
absolute path, so a revert does not have to guess where anything belongs.  Backups are plain
folders: a user can browse, copy or delete them with Explorer.
"""
from __future__ import annotations

import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

BACKUP_DIR_NAME = "backups"
MANIFEST = "manifest.json"
ARCHIVE_NAME = "item_dlc02.msgbnd.dcx"
KEEP_BACKUPS = 20


def _archive_files(archives: list[Path]) -> list[Path]:
    """The msg archive files behind the --archives folders (or files): a msg/<lang> folder holds
    item_dlc02.msgbnd.dcx directly, the msg parent holds one per <lang> subfolder."""
    out: list[Path] = []
    for a in archives:
        p = Path(a)
        if p.is_dir():
            direct = p / ARCHIVE_NAME
            if direct.is_file():
                out.append(direct)
            else:
                out.extend(sorted(p.glob(f"*/{ARCHIVE_NAME}")))
        elif p.is_file():
            out.append(p)
    return out


def collect_files(input_file: Path, archives: list[Path]) -> list[Path]:
    """The files a backup would cover: the input regulation.bin plus every msg archive file."""
    return [Path(input_file)] + _archive_files(archives)


def program_dir() -> Path:
    """The folder the program runs from: next to the frozen exe, or the repo root from source."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def backup_root() -> Path:
    """Where every backup lives: ``<program>/backups/``."""
    return program_dir() / BACKUP_DIR_NAME


def make_backup(files: list[Path]) -> Path | None:
    """Copy ``files`` into a timestamped backup folder and write a manifest.

    Returns the backup folder, or ``None`` when none of the files existed (nothing to back up).
    Existing files keep their bytes and mtime (``copy2``); a second backup inside the same second
    gets a ``-2`` suffix rather than overwriting the first."""
    existing = [Path(f) for f in files if Path(f).is_file()]
    if not existing:
        return None
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    dest = backup_root() / stamp
    suffix = 1
    while dest.exists():
        suffix += 1
        dest = backup_root() / f"{stamp}-{suffix}"
    dest.mkdir(parents=True, exist_ok=True)
    manifest: list[dict[str, str]] = []
    for index, src in enumerate(existing):
        target = dest / f"{index:02d}_{src.name}"
        shutil.copy2(src, target)
        manifest.append({"name": target.name, "original": str(src.resolve())})
    (dest / MANIFEST).write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    prune_backups()
    return dest


def list_backups() -> list[Path]:
    """Every backup folder, newest first."""
    root = backup_root()
    if not root.is_dir():
        return []
    return sorted((p for p in root.iterdir() if p.is_dir() and (p / MANIFEST).is_file()), reverse=True)


def prune_backups(keep: int = KEEP_BACKUPS) -> int:
    """Delete all but the newest ``keep`` backup folders.  Returns how many were removed."""
    backups = list_backups()          # newest first
    removed = 0
    for old in backups[keep:]:
        shutil.rmtree(old, ignore_errors=True)
        removed += 1
    return removed


def restore(backup: Path) -> list[Path]:
    """Copy every file of ``backup`` back to where it came from.  Returns the restored paths."""
    manifest = json.loads((Path(backup) / MANIFEST).read_text(encoding="utf-8"))
    restored: list[Path] = []
    for entry in manifest:
        src = Path(backup) / entry["name"]
        if not src.is_file():
            continue
        dst = Path(entry["original"])
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        restored.append(dst)
    return restored


def backup_and_replace(input_file: Path, output_file: Path, archives: list[Path]) -> Path | None:
    """Back up the user's input files, then copy the generated output over them.

    ``input_file`` is their ``regulation.bin``; ``archives`` are the ``msg`` folders (or
    ``msg/<lang>`` folders) they passed - the weapon-name sources.  The generated ``regulation.bin``
    replaces the input, and each archive is replaced by the patched copy the engine wrote under
    ``<output folder>/msg/``.

    Returns the backup folder (so the caller can offer a revert), or ``None`` when nothing was backed
    up (the input did not exist)."""
    input_file = Path(input_file)
    output_file = Path(output_file)
    archive_files = _archive_files(archives)
    backup = make_backup([input_file] + archive_files)
    if backup is None:
        return None
    # replace the regulation.bin
    if output_file.is_file() and output_file.resolve() != input_file.resolve():
        shutil.copy2(output_file, input_file)
    # replace each msg archive with the patched copy the engine wrote next to the output
    msg_dir = output_file.resolve().parent / "msg"
    for archive in archive_files:
        patched = msg_dir / archive.parent.name / archive.name
        if patched.is_file() and patched.resolve() != archive.resolve():
            shutil.copy2(patched, archive)
    return backup