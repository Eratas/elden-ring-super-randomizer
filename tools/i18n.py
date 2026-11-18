"""GUI translations.

Only the window is translated.  The reports, the console output and the msg folder stay in English:
the game's text archives are patched in the language the user points at, and a report that changes
language under you is worse than one that does not.

Adding a language is one file: `tools/lang_<code>.py` with a dict `T` whose keys are

    opt:<option key>:label     the label of an option
    opt:<option key>:tip       its hover text
    ui:<name>                  a piece of the window chrome

Anything missing falls back to English, so a half‑finished pack still works.  The language itself is
never saved: the window always starts in English and the list is in the top right corner.
"""
from __future__ import annotations

import importlib

LANGUAGES: tuple[tuple[str, str], ...] = (
    ("en", "English"),
    ("fr", "Français"),
    ("es", "Español"),
    ("de", "Deutsch"),
    ("it", "Italiano"),
    ("pt", "Português (Brasil)"),
    ("ja", "日本語"),
    ("zh", "简体中文"),
    ("nl", "Nederlands"),
    ("sv", "Svenska"),
    ("fi", "Suomi"),
    ("pl", "Polski"),
    ("ru", "Русский"),
    ("ko", "한국어"),
)

_cache: dict[str, dict] = {}


def pack(code: str) -> dict:
    if code not in _cache:
        try:
            _cache[code] = importlib.import_module(f"lang_{code}").T
        except Exception:
            # Do not cache a failed import: a transient error (or a pack fixed on disk)
            # should recover on the next call instead of showing English for the whole session.
            return {}
    return _cache[code]


def get(code: str, key: str, fallback: str) -> str:
    """The translation for `key`, or the English text that was passed in."""
    if code and code != "en":
        table = pack(code)
        value = table.get(key)
        if value:
            return value
    return fallback


def name_of(code: str) -> str:
    for key, label in LANGUAGES:
        if key == code:
            return label
    return "English"