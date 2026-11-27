"""Crash-safe replacement of one file, shared by every writer that touches user data.

Write a temp file in the *same* directory, flush it to disk, rename it over the target, then make
the rename durable where the OS allows it.  Without the fsync steps a power cut after the rename
could leave a zero-length regulation.bin (or backup) even though the atomic rename "succeeded".
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path


def _fsync_dir(folder: Path) -> None:
    """Make the directory entry durable on POSIX; Windows has no portable directory fsync."""
    if sys.platform == "win32":
        return
    fd = os.open(folder, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def atomic_replace(tmp: Path, target: Path) -> None:
    """Commit an already-written sibling temp file.  Caller cleans up `tmp` on failure."""
    # Windows refuses fsync on a read-only handle (EBADF); open for writing on every platform.
    fd = os.open(tmp, os.O_WRONLY | os.O_BINARY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
    os.replace(tmp, target)
    _fsync_dir(Path(target).parent)


def atomic_write(target: Path, data: bytes) -> None:
    """Write `data` to `target` atomically, with no half-written file visible to a reader."""
    target = Path(target)
    fd, name = tempfile.mkstemp(prefix=target.name + ".", suffix=".tmp", dir=target.parent)
    tmp = Path(name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
        atomic_replace(tmp, target)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise


def atomic_copy(src: Path, dst: Path) -> None:
    """Copy `src` over `dst` atomically, preserving the source's metadata."""
    dst = Path(dst)
    fd, name = tempfile.mkstemp(prefix=dst.name + ".", suffix=".tmp", dir=dst.parent)
    tmp = Path(name)
    os.close(fd)
    try:
        shutil.copy2(src, tmp)
        atomic_replace(tmp, dst)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
