"""The tool's version, in one place.

Shown in the window footer.  The update check is offline on purpose: nothing phones home.  A release
can ship a one-line `latest_version.txt` next to the program (or in tools/); when it is newer than
`__version__`, the window says so.  Bump `__version__` here and nowhere else.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

__version__ = "1.0.3"

HERE = Path(__file__).resolve().parent


def _base_dir() -> Path:
    """The folder the program runs from: next to the frozen exe, or tools/ from source."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return HERE


# path -> (mtime, value).  The window calls read_latest() on every hint refresh, so a missing or
# unchanged file must stay cheap: cache the parsed value and re-read only when the file's mtime moves
# (a release dropping a newer latest_version.txt).
_LATEST_CACHE: dict[str, tuple[float, str | None]] = {}


def read_latest() -> str | None:
    """The version in `latest_version.txt` (next to the exe, or in tools/), or None."""
    for base in (_base_dir(), HERE):
        path = base / "latest_version.txt"
        try:
            mtime = path.stat().st_mtime
        except OSError:
            continue
        key = str(path)
        cached = _LATEST_CACHE.get(key)
        if cached is not None and cached[0] == mtime:
            if cached[1] is not None:
                return cached[1]
            continue
        try:
            text = path.read_text(encoding="utf-8").strip()
        except OSError:
            text = ""
        value = text.splitlines()[0].strip() if text else None
        _LATEST_CACHE[key] = (mtime, value)
        if value is not None:
            return value
    return None


def version_tuple(text: str) -> tuple[int, ...]:
    """Parse the leading numeric part of a version ("v1.2.3-beta" -> (1, 2, 3))."""
    parts: list[int] = []
    for chunk in re.split(r"[.\-+]", text.strip().lstrip("vV")):
        if chunk.isdigit():
            parts.append(int(chunk))
        else:
            break
    return tuple(parts)


def is_newer(candidate: str, current: str) -> bool:
    """True when `candidate` is a strictly newer version than `current`."""
    a, b = version_tuple(candidate), version_tuple(current)
    length = max(len(a), len(b))
    a += (0,) * (length - len(a))
    b += (0,) * (length - len(b))
    return a > b