#!/usr/bin/env python3
"""Elden Ring regulation.bin randomizer: the window.

Every option, label and hover text comes from options.py, which also builds the command line
(randomize.py).  The window runs the command line engine in a worker thread and shows its output.

    python tools/gui.py            # or randomize_gui.bat on Windows

The window remembers its size, its open sections, the paths you used and every option value in
settings.json next to the program.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ui.app import main  # noqa: E402

if __name__ == "__main__":
    if "--self-test" in sys.argv[1:]:
        # Runs inside the frozen bundle: prove the modules and the shipped data (msg/, paramdef/,
        # names/) load and the core logic works, then exit.  Writes a result file next to the exe for
        # headless verification, and shows it in a message box (the exe is windowed, no console).
        import tkinter as tk
        from tkinter import messagebox

        import test_logic
        root = tk.Tk()
        root.withdraw()
        checks, fails = test_logic.run_self_test()
        msg = f"{'PASS' if fails == 0 else 'FAIL'}: {checks} checks, {fails} failed"
        for line in test_logic._FAILS[:20]:
            msg += "\n" + line
        try:
            Path(sys.executable).with_name("self_test_result.txt").write_text(msg + "\n", encoding="utf-8")
        except OSError:
            pass
        try:
            messagebox.showinfo("Elden Ring Super Randomizer self-test", msg)
        except tk.TclError:
            pass
        root.destroy()
        sys.exit(0 if fails == 0 else 1)
    sys.exit(main())