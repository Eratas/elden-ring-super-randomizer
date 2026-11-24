"""Backup and restore the user's files before a "backup and replace" run.

The randomizer writes its result to an output folder (default ``randomized/`` inside the program
folder).  When the "Backup and replace files" option is on, the engine also copies the *input*
files the user pointed at - their ``regulation.bin`` and the ``msg/<lang>/item_dlc02.msgbnd.dcx``
archives - into a timestamped backup folder under ``<program>/backups/`` **before** overwriting
them with the freshly generated ones.  A revert puts every file back exactly where it came from.

Unlike the old version, a backup covers **every file in the msg language folders**, not just
``item_dlc02.msgbnd.dcx``: if a mod adds menu or caption archives, rollback still restores them.
A backup folder is built in a staging directory and renamed into place only once its manifest is
complete, so an interrupted run never leaves a half-created restore point.  The manifest records each
file's original absolute path, size and SHA-256, so a rollback can tell whether a backup is intact.
Backups are plain folders: a user can browse, copy or delete them with Explorer.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path

MANIFEST = "manifest.json"
BACKUP_DIR_NAME = "backups"


def _atomic_copy(src: Path, dst: Path) -> None:
    """Copy src onto dst atomically: write a sibling temp file, then os.replace() over dst, so a
    crash or full disk mid-copy can never leave a half-written file over the user's original."""
    tmp = dst.with_name(dst.name + ".tmp")
    try:
        shutil.copy2(src, tmp)
        os.replace(tmp, dst)
    except OSError:
        tmp.unlink(missing_ok=True)
        raise


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


def _digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def _msg_files(archives: list[Path]) -> list[Path]:
    """Every file under the given msg folders - not just item_dlc02.msgbnd.dcx.

    A mod can ship item, menu, caption and script archives.  Backing up only the one the name pass
    touches used to lose everything else in a rollback.  Explicit files are accepted unchanged.
    """
    out: list[Path] = []
    for a in archives:
        p = Path(a)
        if p.is_dir():
            out.extend(sorted(x for x in p.rglob("*") if x.is_file()))
        elif p.is_file():
            out.append(p)
    # deterministic, and stable even when the caller passes overlapping folders
    return list(dict.fromkeys(p.resolve() for p in out))


def collect_files(input_file: Path, archives: list[Path]) -> list[Path]:
    """The files a backup covers: the input regulation.bin plus every file in the msg folders."""
    return [Path(input_file)] + _msg_files(archives)


def detected_archives(input_file: Path, given=()) -> list[Path]:
    """The msg archives a backup should cover, from the option or from the input mod's own folder.

    The GUI passes the patched archives through --weapon-names, not through the hidden --archives
    option, so relying on --archives alone backed up no text at all.  When no archive is given, the
    input mod's ``msg/<language>/item_dlc02.msgbnd.dcx`` files are exactly the ones the game loads
    next to that regulation.bin, so they are the ones to copy before replacing them.
    """
    files = _msg_files([Path(a) for a in given])
    if files:
        return files
    msg = Path(input_file).resolve().parent / "msg"
    return _msg_files([msg]) if msg.is_dir() else []


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
    staging = backup_root() / f".staging-{dest.name}"
    if staging.exists():
        shutil.rmtree(staging, ignore_errors=True)
    staging.mkdir(parents=True, exist_ok=True)
    manifest: list[dict] = []
    try:
        for index, src in enumerate(existing):
            target = staging / f"{index:02d}_{src.name}"
            _atomic_copy(src, target)
            manifest.append({"name": target.name, "original": str(src.resolve()),
                             "size": src.stat().st_size, "sha256": _digest(src)})
        # The manifest is written last: until it exists, list_backups() ignores the staging folder.
        (staging / MANIFEST).write_text(json.dumps(manifest, indent=1), encoding="utf-8")
        os.replace(staging, dest)
    except OSError:
        shutil.rmtree(staging, ignore_errors=True)
        raise
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
        if not old.exists():
            removed += 1
    return removed


def restore(backup: Path) -> list[Path]:
    """Copy every file of ``backup`` back to where it came from.  Returns the restored paths."""
    manifest = json.loads((Path(backup) / MANIFEST).read_text(encoding="utf-8"))
    restored: list[Path] = []
    for entry in manifest:
        # the manifest's name is always a bare filename (make_backup writes target.name); force the
        # basename so a tampered manifest cannot read a file from outside the backup folder
        src = Path(backup) / Path(entry["name"]).name
        if not src.is_file():
            continue
        dst = Path(entry["original"])
        dst.parent.mkdir(parents=True, exist_ok=True)
        _atomic_copy(src, dst)
        restored.append(dst)
    return restored


def backup_info(backup: Path) -> dict:
    """A short summary a rollback picker can show: folder name, file count, total bytes."""
    manifest = json.loads((Path(backup) / MANIFEST).read_text(encoding="utf-8"))
    return {"name": Path(backup).name, "files": len(manifest),
            "bytes": sum(int(e.get("size", 0)) for e in manifest)}


def verify_backup(backup: Path) -> list[str]:
    """Problems that would make a rollback partial: missing or changed copied files."""
    problems: list[str] = []
    folder = Path(backup)
    try:
        manifest = json.loads((folder / MANIFEST).read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        return [f"cannot read {MANIFEST}: {e}"]
    if not isinstance(manifest, list):
        return [f"{MANIFEST} is not a list"]
    for entry in manifest:
        try:
            name = Path(entry["name"]).name
            original = Path(entry["original"])
            src = folder / name
        except (KeyError, TypeError):
            problems.append("a manifest entry is malformed")
            continue
        if not src.is_file():
            problems.append(f"{name}: missing from the backup")
            continue
        expected = entry.get("sha256")
        if expected and _digest(src) != expected:
            problems.append(f"{name}: checksum changed")
        if entry.get("size") is not None and src.stat().st_size != entry["size"]:
            problems.append(f"{name}: size changed")
        if not original.is_absolute():
            problems.append(f"{name}: original path is not absolute")
    return problems


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
    backup = make_backup(collect_files(input_file, archives))
    if backup is None:
        return None
    # replace the regulation.bin
    if output_file.is_file() and output_file.resolve() != input_file.resolve():
        _atomic_copy(output_file, input_file)
    # replace each msg archive with the patched copy the engine wrote next to the output
    msg_dir = output_file.resolve().parent / "msg"
    for archive in archive_files:
        patched = msg_dir / archive.parent.name / archive.name
        if patched.is_file() and patched.resolve() != archive.resolve():
            _atomic_copy(patched, archive)
    return backup
