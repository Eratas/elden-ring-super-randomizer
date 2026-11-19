"""The loot simulator dialog and the two sys.stdout stand-ins the worker threads use.

Split out of ui/app.py so the main window module stays focused on the window itself.  LootDialog talks
to the App only through the instance it is handed (`app.root`, `app.t`, `app.values()`, `app.running`,
`app.sim_busy`, ...), so this module does not import App and there is no import cycle.
"""
from __future__ import annotations

import queue
import sys
import threading
import tkinter as tk
import traceback
from pathlib import Path
from tkinter import messagebox, ttk
from typing import TYPE_CHECKING

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import options  # noqa: E402

from ui import theme  # noqa: E402
from ui.widgets import Tooltip  # noqa: E402

if TYPE_CHECKING:                       # type hint only: no runtime import, so no cycle with ui.app
    from ui.app import App


class QueueWriter:
    """sys.stdout stand-in for the worker thread: every line goes to the GUI queue, headers too."""

    def __init__(self, q: queue.Queue) -> None:
        self.q = q

    def write(self, text: str) -> int:
        for line in (text or "").splitlines():
            self.q.put(("out", (line, line.startswith("#"))))
        return len(text or "")

    def flush(self) -> None:
        pass

    def isatty(self) -> bool:
        return False

    def reconfigure(self, **_kw) -> None:
        pass


class Collector:
    """A sys.stdout stand-in that keeps everything printed instead of showing it.

    The loot simulator collects the whole run and inserts it into its panel in one go: streaming every
    line into a visible Text widget re-lays the window out per line, which turned a 5 second run into
    half a minute."""

    def __init__(self) -> None:
        self.lines: list[str] = []

    def write(self, text: str) -> int:
        self.lines.extend((text or "").splitlines())
        return len(text or "")

    def flush(self) -> None:
        pass

    def isatty(self) -> bool:
        return False

    def reconfigure(self, **_kw) -> None:
        pass


class LootDialog:
    """The loot simulator: run the current settings in memory and show what N random kills dropped.

    It runs the same passes as a real run (same seed, same tables) but with `--simulate N` instead of a
    save, so nothing is written and nothing is compressed.  Output goes to its own queue, so it never
    mixes with the main window's log."""

    def __init__(self, app: App) -> None:
        self.app = app
        self.q: queue.Queue = queue.Queue()
        self.busy = False
        self.top = tk.Toplevel(app.root)
        self.top.withdraw()                          # built off-screen: no white flash before the theme applies
        self.top.configure(bg=theme.BG)
        self.top.title(app.t("dlg:title_loot", "Loot simulator"))
        self.top.transient(app.root)
        self.top.minsize(560, 380)
        sw, sh = self.top.winfo_screenwidth(), self.top.winfo_screenheight()
        self.top.geometry(f"820x600+{max(0, (sw - 820) // 2)}+{max(0, (sh - 600) // 2)}")
        self._build()
        self.top.protocol("WM_DELETE_WINDOW", self._close)
        self.top.after(100, self._poll)

    def _build(self) -> None:
        bar = ttk.Frame(self.top)
        bar.pack(fill="x", padx=10, pady=8)
        ttk.Label(bar, text=self.app.t("dlg:kills", "Kills to simulate")).pack(side="left")
        self.count = tk.StringVar(value="20")
        ttk.Spinbox(bar, from_=1, to=200, width=5, textvariable=self.count).pack(side="left", padx=(6, 12))
        ttk.Label(bar, text=self.app.t("dlg:seed", "Seed")).pack(side="left")
        seed = self.app.vars.get("seed")
        self.seed = tk.StringVar(value=str(seed.get()) if seed is not None else "")
        ttk.Entry(bar, textvariable=self.seed, width=12).pack(side="left", padx=(6, 12))
        ttk.Label(bar, text=self.app.t("dlg:seed_hint", "(empty = a fresh seed)"),
                  style="Muted.TLabel").pack(side="left")

        box = ttk.Frame(self.top, style="Bar.TFrame")
        box.pack(fill="both", expand=True, padx=10)
        self.text = tk.Text(box, wrap="word", background=theme.PANEL, foreground=theme.FG,
                            relief="flat", borderwidth=0, font=self.app.fonts["mono"], height=18)
        sb = ttk.Scrollbar(box, orient="vertical", command=self.text.yview)
        self.text.configure(yscrollcommand=sb.set)
        self.text.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        self.note = ttk.Label(self.top, text=self.app.t("dlg:tip_note", "Tick the passes you want to judge "
                                                              "in the main window first."),
                              style="Warn.TLabel")
        self.note.pack(fill="x", padx=10, pady=4)
        self.run = ttk.Button(self.top, text=self.app.t("dlg:simulate", "Simulate"), style="Run.TButton",
                              command=self._run)
        self.run.pack(pady=(0, 10))
        Tooltip(self.run, self.app.t("dlg:tip_sim", "Build the tables and show what N random kills drop. "
                                              "Writes no file."))
        self.top.bind("<Escape>", lambda _event: self._close())
        self.top.deiconify()
        self.top.focus_set()

    def _run(self) -> None:
        if self.busy or self.app.running:
            return
        try:
            n = int(self.count.get().strip())
        except ValueError:
            messagebox.showerror(self.app.t("dlg:title_cannot", "Cannot simulate"),
                                 self.app.t("dlg:kills_number", "Kills must be a whole number."),
                                 parent=self.top)
            return
        values = self.app.values()
        values["simulate"] = max(1, min(200, n))
        values["dry_run"] = False
        values["repack"] = False
        raw = self.seed.get().strip()
        values["seed"] = int(raw) if raw else None
        try:
            values = options.validate(values)
        except ValueError as e:
            messagebox.showerror(self.app.t("dlg:title_cannot", "Cannot simulate"), str(e), parent=self.top)
            return
        problem = self.app._dll_error(values)
        if problem:
            messagebox.showerror(self.app.t("dlg:title_oodle", "Oodle DLL missing"), problem, parent=self.top)
            return
        argv = options.argv_from_values(values)
        self.text.delete("1.0", "end")
        self.run.configure(state="disabled", text=self.app.t("dlg:running", "Running ..."))
        self.busy = True
        self.app.sim_busy = True
        threading.Thread(target=self._worker, args=(argv,), daemon=True).start()
        self.top.after(100, self._poll)

    def _worker(self, argv: list[str]) -> None:
        import randomize
        out = Collector()
        old = sys.stdout
        sys.stdout = out
        code = 0
        try:
            code = randomize.main(argv, quiet=True)   # only the loot sample reaches the text area
        except SystemExit as e:
            code = e.code if isinstance(e.code, int) else 1
            out.lines.append(f"# stopped: exit {code}")
        except BaseException:
            out.lines.append(traceback.format_exc())
        finally:
            # restore the real stdout only if it is still ours (see App._worker): a run that started
            # while this dialog was closing must not have its stdout clobbered by this thread
            if sys.stdout is out:
                sys.stdout = old
        self.q.put(("result", out.lines))

    def _poll(self) -> None:
        try:
            kind, payload = self.q.get_nowait()
        except queue.Empty:
            kind = None
        if kind == "result":
            self.text.delete("1.0", "end")
            self.text.insert("end", "\n".join(payload) + ("\n" if payload else ""))
            self.text.see("end")
            self.busy = False
            self.app.sim_busy = False
            self.run.configure(state="normal", text=self.app.t("dlg:simulate", "Simulate"))
            return
        if self.busy and self.top.winfo_exists():
            try:
                self.top.after(200, self._poll)
            except tk.TclError:
                pass

    def _close(self) -> None:
        self.app.sim_busy = False
        self.top.destroy()