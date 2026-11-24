#!/usr/bin/env python3
"""Elden Ring regulation.bin randomizer: the window.

Every option, label and hover text comes from options.py, which also builds the command line
(randomize.py).  The window runs the command line engine in a worker thread and shows its output.

    python tools/gui.py            # or randomize_gui.bat on Windows
    python tools/gui.py --self-test-headless   # run the checks, write the result file, exit

The window remembers its size, its open sections, the paths you used and every option value in
settings.json next to the program.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ui.app import main  # noqa: E402

if __name__ == "__main__":
    args = sys.argv[1:]
    if "--self-test" in args or "--self-test-headless" in args:
        # Runs inside the frozen bundle: prove the modules and the shipped data (msg/, paramdef/,
        # names/) load and the core logic works, then exit.  Writes a result file next to the program
        # for headless verification.  The frozen exe is windowed, so it also shows a message box;
        # --self-test-headless skips that for CI and scripted runs.
        headless = "--self-test-headless" in args
        import test_logic
        checks, fails = test_logic.run_self_test()
        msg = f"{'PASS' if fails == 0 else 'FAIL'}: {checks} checks, {fails} failed"
        for line in test_logic._FAILS[:20]:
            msg += "\n" + line
        program = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) \
            else Path(__file__).resolve().parent.parent
        try:
            (program / "self_test_result.txt").write_text(msg + "\n", encoding="utf-8")
        except OSError:
            pass
        if not headless:
            import tkinter as tk
            from tkinter import messagebox
            root = tk.Tk()
            root.withdraw()
            try:
                messagebox.showinfo("Elden Ring Super Randomizer self-test", msg)
            except tk.TclError:
                pass
            root.destroy()
        sys.exit(0 if fails == 0 else 1)
    sys.exit(main())
