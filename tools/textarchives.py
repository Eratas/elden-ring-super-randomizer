"""The game's text archives: where they are, and which copy an option should patch.

Two kinds of text are patched by this tool and both live in msg/<language>/ archives:

  item_dlc02.msgbnd.dcx   WeaponName / WeaponCaption -- the names of the affinity rows that
                          --somber-infusable adds (tools/weapon_names.py)
  (menu_dlc02.msgbnd.dcx  TalkMsg -- dialogue subtitles; the joke shifu and the subtitle options
                          that used to live here were removed)

The shipped copies sit in tools/msg/<language>/ (next to the executable in the packaged program).
When the input is the output of another randomizer, its own archives must be patched instead, so
every option that writes text takes the folder(s) to use: a language folder (msg/<language>), a msg
folder or a mod folder that contains one.  A later folder wins for the same language, which is the
me3 / ModEngine 2 load order.
"""
from __future__ import annotations

import sys
from pathlib import Path

import erreg
from talkmsg import fmg_name, patch_fmgs, read_fmg  # noqa: F401  (re-exported for callers)

HERE = Path(__file__).resolve().parent


def _msg_dir() -> Path:
    """Where the shipped text archives live.  In a frozen exe PyInstaller extracts --add-data into
    sys._MEIPASS (the onefile temp dir, or the onedir _internal folder), so prefer that; a onefile
    build that copies msg next to the exe instead (build_exe.bat) falls back to the exe's folder; in
    dev it is tools/msg."""
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass and (Path(meipass) / "msg").is_dir():
            return Path(meipass) / "msg"
        return Path(sys.executable).resolve().parent / "msg"
    return HERE / "msg"


MSG_DIR = _msg_dir()
ITEM_ARCHIVE = "item_dlc02.msgbnd.dcx"
MENU_ARCHIVE = "menu_dlc02.msgbnd.dcx"


def shipped_languages(name: str = ITEM_ARCHIVE) -> list[str]:
    """Languages the program ships a text archive for (whatever is actually there)."""
    return sorted(p.parent.name for p in MSG_DIR.glob(f"*/{name}") if p.is_file())


def shipped_archives(name: str = ITEM_ARCHIVE) -> list[Path]:
    return [MSG_DIR / lang / name for lang in shipped_languages(name)]


def expand_archives(flag: str, given, name: str = ITEM_ARCHIVE,
                    langs: list[str] | None = None) -> list[str]:
    """The FOLDER arguments of an option as archive paths.

    A file is taken as it is; a folder stands for the archives called `name` inside it: a language
    folder (msg/<language>/, whatever the language) holding the archive itself, else a msg folder or
    a mod folder holding msg/ (then every language in `langs` that has the archive there).  One
    archive per language (named by its folder), a later argument replacing an earlier one, so mod
    folders can be listed in the me3 order: the last one wins, as in the game."""
    langs = langs or shipped_languages(name)
    found: dict[str, str] = {}
    for g in given or ():
        p = Path(g)
        if p.is_file():
            hits = [p]
        elif p.is_dir():
            if (p / name).is_file():
                hits = [p / name]
            else:
                base = p / "msg" if (p / "msg").is_dir() else p
                hits = [base / lang / name for lang in langs if (base / lang / name).is_file()]
                if not hits:
                    raise SystemExit(f"{flag}: no {name} in {p}: expected {p / name} or "
                                     f"{base / '<language>' / name} for {', '.join(langs)}")
        else:
            raise SystemExit(f"{flag}: {p} does not exist")
        for h in hits:
            found[h.parent.name.lower()] = str(h)
    return list(found.values())


def read_entries(path: Path) -> dict[int, str]:
    """Every entry of the first FMG in an archive ({id: text}); used by the reports and the tests."""
    raw = path.read_bytes()
    bnd = erreg.read_bnd4(erreg.read_dcx(raw).data if raw[:4] == b"DCX\0" else raw)
    for f in bnd.files:
        if fmg_name(f).lower().endswith(".fmg"):
            return read_fmg(bnd.datas[f.index])
    raise SystemExit(f"{path}: no FMG inside")
