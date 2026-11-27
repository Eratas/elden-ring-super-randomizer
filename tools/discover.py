"""Find the regulation.bin files on this machine.

The window's **Find** button uses this: it looks where the game and the usual mod loaders put the file,
so nobody has to click through My Computer again.

Search order:
  1. the Steam library (from the registry, plus every library in libraryfolders.vdf),
  2. the folders other tools use: <game>\\Game\\regulation.bin, <mod>\\mod\\regulation.bin,
  3. a shallow walk of the usual roots (C:\\Games, D:\\Games, E:\\Games, C:\\Games\\ERR).

Every hit is verified to exist and to be at least 1 MB, which filters out the tiny files some tools
leave behind.
"""
from __future__ import annotations

from pathlib import Path

MIN_SIZE = 1_000_000
GAME_FILES = ("ELDEN RING/Game/regulation.bin", "Game/regulation.bin")
MOD_FILES = ("mod/regulation.bin", "regulation.bin")
ROOTS = ("C:\\Games", "D:\\Games", "E:\\Games", "C:\\Games\\ERR")


def _ok(path: Path) -> bool:
    try:
        return path.is_file() and path.stat().st_size >= MIN_SIZE
    except OSError:
        return False


def steam_libraries() -> list[Path]:
    """Every Steam library folder, from the registry and from libraryfolders.vdf."""
    libs: list[Path] = []
    try:
        import winreg
        for hive, key in ((winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam"),
                          (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam")):
            try:
                root = winreg.QueryValueEx(winreg.OpenKey(hive, key), "SteamPath")[0]
            except OSError:
                continue
            steam = Path(root)
            libs.append(steam)
            vdf = steam / "steamapps" / "libraryfolders.vdf"
            if vdf.is_file():
                for line in vdf.read_text(encoding="utf-8", errors="replace").splitlines():
                    if '"path"' not in line:
                        continue
                    value = line.split('"path"', 1)[1].strip().strip('"').replace("\\\\", "\\")
                    if value:
                        libs.append(Path(value))
    except Exception:
        pass
    return libs


def candidates() -> list[Path]:
    """Every plausible regulation.bin that exists, best first (Steam, then ERR-style mods, then a walk)."""
    found: list[Path] = []

    def add(path: Path) -> None:
        if path not in found and _ok(path):
            found.append(path)

    libs = steam_libraries()               # read the registry + libraryfolders.vdf once, not twice
    for lib in libs:
        for rel in GAME_FILES:
            add(lib / "steamapps" / "common" / rel)
    for lib in libs:
        for rel in MOD_FILES:
            add(lib / rel)
    for root in ROOTS:
        base = Path(root)
        if not base.is_dir():
            continue
        for child in sorted(base.iterdir()):
            if not child.is_dir():
                continue
            for rel in GAME_FILES + MOD_FILES:
                add(child / rel)
            mods = child / "mods"
            if mods.is_dir():
                for sub in sorted(mods.iterdir()):
                    if sub.is_dir():
                        add(sub / "regulation.bin")
    return found


def err_folders() -> list[Path]:
    """Folders that look like a Mod Engine 2 mod: they contain mod/regulation.bin."""
    out = []
    for path in candidates():
        if path.parent.name.lower() == "mod":
            out.append(path.parent.parent)
    return out


def game_dirs() -> list[Path]:
    """Folders that can hold the game's own files: Steam library game folders plus the usual roots."""
    dirs: list[Path] = []

    def add(path: Path) -> None:
        try:
            if path.is_dir() and path not in dirs:
                dirs.append(path)
        except OSError:
            pass

    for lib in steam_libraries():
        add(lib / "steamapps" / "common" / "ELDEN RING")
        add(lib / "steamapps" / "common" / "ELDEN RING" / "Game")
    for root in ROOTS:
        base = Path(root)
        if not base.is_dir():
            continue
        for child in sorted(base.iterdir()):
            if not child.is_dir():
                continue
            add(child)
            add(child / "Game")
            add(child / "mod")
    return dirs


def find_dll() -> list[Path]:
    """Every oo2core_*.dll next to a game or mod folder (the game ships oo2core_6_win64.dll)."""
    out: list[Path] = []
    for folder in game_dirs():
        for dll in sorted(folder.glob("oo2core_*.dll")):
            if dll.is_file() and dll not in out:
                out.append(dll)
    return out


def find_archives() -> list[Path]:
    """Every msg folder that holds an item_dlc02 archive, the shipped one first."""
    out: list[Path] = []
    shipped = Path(__file__).resolve().parent / "msg"
    if (shipped / "engus" / "item_dlc02.msgbnd.dcx").is_file():
        out.append(shipped)
    for folder in game_dirs():
        msg = folder / "msg"
        if msg.is_dir() and (msg / "engus" / "item_dlc02.msgbnd.dcx").is_file() and msg not in out:
            out.append(msg)
    return out
