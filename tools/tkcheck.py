#!/usr/bin/env python3
"""Check that Tk works with this Python and print the Tcl / Tk library paths for build_exe.bat / .sh.

stdout: one `NAME=value` assignment per line (no shell syntax) so the build script can apply them
without a temporary script file -- build_exe.bat parses them with `for /f`, build_exe.sh with
`while read`.  PyInstaller's tkinter hook needs a working `tkinter.Tcl()` and honours
TCL_LIBRARY / TK_LIBRARY.  Diagnostics go to stderr; exit status 1 when Tk is unusable.

Tcl/Tk 9 on Windows (python.org 3.14) keeps the Tk script library inside tk90.dll and reports it as
`//zipfs:/lib/tk/tk_library`; PyInstaller recognises that prefix and skips the collection, so such a
path must be passed on verbatim (Path() would turn its slashes into backslashes, which
PyInstaller then treats as a missing directory and aborts the build; seen 2026-10-18).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path


def _tcl_from_base() -> None:
    """Point TCL_LIBRARY / TK_LIBRARY at the base interpreter's Tcl/Tk.

    A venv made from a Python whose Tcl/Tk lives outside the venv (uv-managed Windows Python)
    cannot find init.tcl on its own; the base copy is where it actually is.
    """
    base = Path(sys.base_prefix)
    for var, sub in (("TCL_LIBRARY", "tcl"), ("TK_LIBRARY", "tk")):
        if os.environ.get(var):
            continue
        for d in sorted(base.glob(f"{sub}/{sub}*")):
            if d.is_dir():
                os.environ[var] = str(d)
                break


def _read_paths() -> tuple[str, str] | None:
    import tkinter as tk
    try:
        root = tk.Tk()
        root.withdraw()
        tcl_dir = root.tk.eval("info library")
        tk_dir = root.tk.eval("set tk_library")
        root.destroy()
        return tcl_dir, tk_dir
    except Exception:
        return None


def main() -> int:
    try:
        import tkinter as tk
    except Exception as error:  # ImportError and its friends
        print("tkinter cannot be imported:\n" + str(error), file=sys.stderr)
        return 1
    paths = _read_paths()
    if paths is None:
        # Retry once with the base interpreter's Tcl/Tk on the search path.
        _tcl_from_base()
        paths = _read_paths()
    if paths is None:
        print("Tk cannot be initialised with this Python.", file=sys.stderr)
        return 1
    tcl_dir, tk_dir = paths
    print(f"tkinter {tk.TkVersion} from {sys.base_prefix}: tcl={tcl_dir} tk={tk_dir}", file=sys.stderr)
    for var, value in (("TCL_LIBRARY", tcl_dir), ("TK_LIBRARY", tk_dir)):
        if not value.startswith("//zipfs:/"):
            value = str(Path(value))
        print(f"{var}={value}")
    return 0


if __name__ == "__main__":
    sys.exit(main())