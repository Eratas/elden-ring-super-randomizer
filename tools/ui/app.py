"""The randomizer window.

Everything the window shows comes from options.OPTIONS: the label, the hover text, the default and
which options depend on which.  A tooltip therefore cannot disagree with the flag it describes, and a
new option appears in the command line and in the window by being added once.

Layout rules (these are what the old window got wrong):

  * the options live in a scrollable page; the progress bar, the command line, the log and the action
    bar are packed at the bottom and never scroll, so no button can end up behind the taskbar;
  * labels wrap instead of being cut off, controls stretch instead of overlapping;
  * every option is indented under the switch it depends on, so the hierarchy is visible;
  * every control explains itself on hover, immediately and for as long as the pointer stays;
  * the window remembers its size, open sections, last paths and every option value.
"""
from __future__ import annotations

import json
import os
import queue
import subprocess
import sys
import threading
import time
import tkinter as tk
import traceback
from dataclasses import replace
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import backup  # noqa: E402
import i18n  # noqa: E402
import oodle  # noqa: E402
import options  # noqa: E402
import phases  # noqa: E402
import presets  # noqa: E402
import version  # noqa: E402

from ui import theme  # noqa: E402
from ui.lootdialog import LootDialog, QueueWriter  # noqa: E402
from ui.widgets import (  # noqa: E402
    INDENT,
    PAD,
    ScrollFrame,
    Section,
    Tooltip,
    check_row,
    groups_row,
    label_at,
    path_row,
    value_row,
)

HERE = Path(__file__).resolve().parent.parent
CONFIG = ((Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else HERE) / "settings.json")
RECENT_MAX = 8
MIN_SIZE = (860, 540)
DEFAULT_OPEN = {"files": True, "goods": True, "spells": False, "prices": False, "weapons": False,
                "gems": False, "gear": False, "drops": False, "world": False, "advanced": False}
PATH_KEYS = ("input", "output", "oodle_dll", "archives")

# The passes in the order randomize.py runs them.  phases.py is the single source both the engine and
# this window read, so the bar cannot drift from the run (check_packs.py enforces it too).
PHASES = list(phases.PHASES)
SECTION_TIPS = {
    "files": "Where the input is, where the output goes, and how the file is compressed.",
    "goods": "What a consumable does, and how long a buff lasts. The oldest part of the tool.",
    "spells": "What a sorcery or incantation does, and what it costs.",
    "prices": "What shops charge and what they pay you.",
    "weapons": "Affinities, movesets, default skills and stat rolls, for every weapon row.",
    "gems": "What an Ash of War does when it is mounted: its skill and its on-hit effects.",
    "gear": "Armour pieces and talismans. Whole columns / rows are shuffled, never invented.",
    "drops": "What enemies drop, what they are worth, and how much health they have.",
    "world": "Where the two flasks are, and what you start with.",
    "advanced": "Settings that only matter for unusual setups.",
}


def load_config() -> dict:
    try:
        got = json.loads(Path(CONFIG).read_text(encoding="utf-8"))
        return got if isinstance(got, dict) else {}
    except (OSError, ValueError):
        return {}


def save_config(cfg: dict) -> None:
    try:
        Path(CONFIG).write_text(json.dumps(cfg, indent=1, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass


class App:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.cfg = load_config()
        self.fonts = theme.init(root)
        self.queue: queue.Queue = queue.Queue()
        self.running = False
        self.syncing = False
        self._choice_guard = False
        self.ready = False
        self.vars: dict[str, tk.Variable] = {}
        self.widgets: dict[str, list] = {}
        self.kinds: dict[str, list[str]] = {}
        self.sections: dict[str, Section] = {}
        self._row_widgets: dict[str, list] = {}     # every widget in an option's row, for the Find filter
        self.recent: dict[str, list[str]] = {k: list(self.cfg.get("recent", {}).get(k, [])) for k in PATH_KEYS}
        self.saved: dict = self.cfg.get("values", {})
        self.my_presets: dict[str, dict] = dict(self.cfg.get("my_presets") or {})
        saved_lang = self.cfg.get("lang")
        # the window opens in the language you last chose (English on a fresh install); --lang overrides it
        self.lang = saved_lang if saved_lang in {code for code, _ in i18n.LANGUAGES} else "en"
        self.sim_busy = False
        self.outputs: dict[str, str] = dict(self.cfg.get("outputs") or {})
        self._last_input = ""
        self._t0 = 0.0
        self._save_job = None
        self._failed = False

        root.title("Elden Ring Super Randomizer")
        root.minsize(*MIN_SIZE)
        self._geometry()
        self._make_vars()
        self._build()
        self._restore_sections()
        root.protocol("WM_DELETE_WINDOW", self._close)
        self.root.after(100, self._poll)
        self.ready = True
        self._refresh(save=False)

    # ------------------------------------------------------------------ state
    def _geometry(self) -> None:
        geo = self.cfg.get("geometry")
        if isinstance(geo, str) and geo.strip():
            try:
                self.root.geometry(geo)
                return
            except tk.TclError:
                pass
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        w, h = min(1180, int(sw * 0.8)), min(860, int(sh * 0.84))
        self.root.geometry(f"{w}x{h}+{max(0, (sw - w) // 2)}+{max(0, (sh - h) // 2 - 24)}")

    def _make_vars(self) -> None:
        for o in options.OPTIONS:
            if o.key in ("weapon_names", "no_weapon_names"):
                continue
            if o.kind == "bool":
                self.vars[o.key] = tk.BooleanVar(value=bool(self._saved(o.key, o.default)))
            else:
                self.vars[o.key] = tk.StringVar(value=str(self._saved(o.key, o.default) or ""))
        on = self.saved.get("weapon_names_on")
        self.vars["weapon_names_on"] = tk.BooleanVar(value=True if on is None else bool(on))

    def _saved(self, key: str, default) -> object:
        got = self.saved.get(key)
        if got is None:
            return default
        if got == "" and default not in (None, ""):
            return default
        return got

    def values(self) -> dict:
        """What the window currently says, in the shape options.validate() takes."""
        out: dict = {}
        for o in options.OPTIONS:
            if o.key == "no_weapon_names":
                out[o.key] = not bool(self.vars["weapon_names_on"].get())
            elif o.key == "weapon_names":
                out[o.key] = ()
            elif o.key in self.vars:
                out[o.key] = self.vars[o.key].get()
            else:
                out[o.key] = o.default
        # a relative output lands in the program folder, so the randomized/ folder is always
        # next to the program - clear and easy to find
        out_path = (out.get("output") or "").strip()
        if out_path and not Path(out_path).is_absolute():
            out["output"] = str(backup.program_dir() / out_path)
        return out

    # ------------------------------------------------------------------ language
    def t(self, key: str, fallback: str) -> str:
        """The window's text for `key` in the selected language, or the English fallback."""
        return i18n.get(self.lang, key, fallback)

    def _tr_opt(self, o: options.Opt) -> options.Opt:
        """A copy of the option with its label and tooltip in the selected language."""
        label = self.t(f"opt:{o.key}:label", o.label)
        tip = self.t(f"opt:{o.key}:tip", o.tip)
        if label == o.label and tip == o.tip:
            return o
        return replace(o, label=label, tip=tip)

    def _change_language(self, _event=None) -> None:
        if self.running:
            self.lang_var.set(i18n.name_of(self.lang))
            return
        code = "en"
        for key, label in i18n.LANGUAGES:
            if label == self.lang_var.get():
                code = key
                break
        self.set_language(code)

    def set_language(self, code: str) -> None:
        """Rebuild the window in another language.  The options keep their values."""
        if code == self.lang:
            return
        values = self.values()
        for child in self.root.winfo_children():
            child.destroy()
        self.vars, self.widgets, self.kinds, self.sections = {}, {}, {}, {}
        self._row_widgets = {}
        self._choice_guard = False
        self.lang = code
        self._make_vars()
        for key, raw_value in values.items():
            var = self.vars.get(key)
            value = raw_value
            if var is None and key == "no_weapon_names":
                # values() emits the inverse flag name (no_weapon_names); the rebuilt window tracks it
                # as weapon_names_on, so map it back or the toggle silently resets on a language change
                var = self.vars.get("weapon_names_on")
                value = not bool(raw_value)
            if var is None:
                continue
            if isinstance(var, tk.BooleanVar):
                var.set(bool(value))
            else:
                var.set("" if value is None else str(value))
        self._build()
        self._restore_sections()
        self.ready = True
        self._refresh(save=False)
        self.cfg["lang"] = code
        self._save(now=True)              # remember the choice for next time

    # ------------------------------------------------------------------ layout
    def _build(self) -> None:
        top = ttk.Frame(self.root, style="Bar.TFrame")
        top.pack(fill="x", side="top")
        ttk.Label(top, text=self.t("ui:title", "Elden Ring Super Randomizer"), style="Title.TLabel").pack(
            side="left", padx=(PAD, 8), pady=6)
        ttk.Label(top, text=f"v{version.__version__}", style="Muted.TLabel").pack(side="left", padx=(0, 8))
        self.preset_var = tk.StringVar(value=self.cfg.get("preset") or self.t("ui:presets", "Presets"))
        self.preset_box = ttk.Combobox(top, textvariable=self.preset_var, values=self._preset_labels(),
                                       state="readonly", width=17)
        self.preset_box.pack(side="left", padx=(0, 4))
        self.preset_box.bind("<<ComboboxSelected>>", self._apply_preset)
        Tooltip(self.preset_box, self.t("ui:tip_presets",
                                        "Pick one to load a whole set of options, then change anything you like. "
                                        "The window shows what was switched on."))
        self.save_preset_btn = ttk.Button(top, text=self.t("ui:save_preset", "Save preset"), style="Small.TButton",
                                          command=self._save_preset)
        self.save_preset_btn.pack(side="left", padx=4)
        Tooltip(self.save_preset_btn, self.t("ui:tip_save_preset",
                                             "Save the current options as a named bundle. It appears in the "
                                             "dropdown next to the built-in presets."))
        self.delete_preset_btn = ttk.Button(top, text=self.t("ui:delete", "Delete"), style="Small.TButton",
                                            command=self._delete_preset, state="disabled")
        self.delete_preset_btn.pack(side="left", padx=4)
        Tooltip(self.delete_preset_btn, self.t("ui:tip_delete",
                                               "Remove the selected bundle of yours. Built-in presets cannot be "
                                               "deleted."))
        self.lang_var = tk.StringVar(value=i18n.name_of(self.lang))
        # "Aa" is the one language mark that renders in every font: the globe emoji is not in Segoe UI and
        # shows up as an empty box on this system (checked: same width as a missing glyph).
        ttk.Label(top, text="Aa", style="Muted.TLabel").pack(side="right", padx=(0, 3))
        self.lang_box = ttk.Combobox(top, textvariable=self.lang_var, state="readonly", width=13,
                                     values=[label for _code, label in i18n.LANGUAGES])
        self.lang_box.pack(side="right", padx=(0, PAD))
        self.lang_box.bind("<<ComboboxSelected>>", self._change_language)
        Tooltip(self.lang_box, self.t("ui:tip_lang", "Language of the window only. The reports and the game "
                                                       "text stay in English. The choice is remembered for "
                                                       "next time."))
        self.log_btn = ttk.Button(top, text=self.t("ui:log", "Log"), style="Small.TButton",
                                  command=self._toggle_log)
        self.log_btn.pack(side="right", padx=4)
        Tooltip(self.log_btn, self.t("ui:tip_log", "Show or hide the log of the last run. The status line "
                                                        "and the progress bar work with or without it."))
        copy_log_btn = ttk.Button(top, text=self.t("ui:copy_log", "Copy log"), style="Small.TButton",
                                  command=self._copy_log)
        copy_log_btn.pack(side="right", padx=4)
        Tooltip(copy_log_btn, self.t("ui:tip_copy_log", "Copy everything the run printed, for a bug report."))
        reset_btn = ttk.Button(top, text=self.t("ui:reset", "Reset all"), style="Small.TButton",
                               command=self._reset)
        reset_btn.pack(side="right", padx=(4, PAD))
        Tooltip(reset_btn, self.t("ui:tip_reset", "Put every option back to its default. The lists of paths "
                                                       "you used are kept."))
        about_btn = ttk.Button(top, text=self.t("ui:about", "About"), style="Small.TButton",
                               command=self._show_about)
        about_btn.pack(side="right", padx=4)
        Tooltip(about_btn, self.t("ui:tip_about", "Version, credits, and the GitHub links."))

        # Find bar: a thin row under the top bar.  Typing hides every option whose name or text does not
        # match; clearing it shows everything again.  It never scrolls away because it is packed at the top.
        fbar = ttk.Frame(self.root, style="Bar.TFrame")
        fbar.pack(fill="x", side="top")
        ttk.Label(fbar, text=self.t("ui:find", "Find"), style="Muted.TLabel").pack(
            side="left", padx=(PAD, 4), pady=2)
        self.filter_var = tk.StringVar(value="")
        find_entry = ttk.Entry(fbar, textvariable=self.filter_var)
        find_entry.pack(side="left", fill="x", expand=True, padx=(0, 6), pady=2)
        find_entry.bind("<KeyRelease>", self._on_filter)
        Tooltip(find_entry, self.t("ui:tip_find_box", "Hide options whose name or text does not match. "
                                                       "Clear the box to show everything again."))
        self.root.bind("<Control-f>", lambda _event: find_entry.focus_set())
        self.filter_count = ttk.Label(fbar, text="", style="Muted.TLabel")
        self.filter_count.pack(side="left", padx=(0, PAD), pady=2)

        # bottom block: a thin progress line, the command, then status + buttons.  Nothing here scrolls,
        # so no button can end up behind the taskbar; the log is a toggle so it costs no height by default.
        foot = ttk.Frame(self.root, style="Bar.TFrame")
        foot.pack(fill="x", side="bottom")
        self.foot = foot
        self.progress = ttk.Progressbar(foot, style="Hint.Horizontal.TProgressbar", maximum=100)
        self.progress.pack(fill="x", side="top")

        cmd_bar = ttk.Frame(foot, style="Bar.TFrame")
        cmd_bar.pack(fill="x", side="top")
        cmd_bar.columnconfigure(0, weight=1)
        self.cmd_var = tk.StringVar(value="")
        self.cmd = ttk.Label(cmd_bar, textvariable=self.cmd_var, style="Mono.TLabel", anchor="w")
        self.cmd.grid(row=0, column=0, sticky="ew", padx=(PAD, 6), pady=(3, 0))
        self.cmd.bind("<Button-1>", self._copy_command)
        Tooltip(self.cmd, self.t("ui:tip_command", "The command line this window will run. Click to copy it."))

        actions = ttk.Frame(foot, style="Bar.TFrame")
        actions.pack(fill="x", side="top")
        self.status = tk.StringVar(value=self.t("ui:ready", "ready"))
        self.status_label = ttk.Label(actions, textvariable=self.status, style="Muted.TLabel")
        self.status_label.pack(side="left", padx=(PAD, 8), pady=5)
        self.clock = tk.StringVar(value="")
        ttk.Label(actions, textvariable=self.clock, style="Muted.TLabel").pack(side="left", padx=(0, 8))
        self.open_btn = ttk.Button(actions, text=self.t("ui:open_output", "Open output folder"),
                                   style="TButton", command=self._open_output)
        self.open_btn.pack(side="left", padx=(0, 8), pady=5)
        Tooltip(self.open_btn, self.t("ui:tip_open_output", "Open the folder the output regulation.bin is written to."))
        self.backup_btn = ttk.Button(actions, text=self.t("ui:backup", "Backup"), style="TButton",
                                     command=self._backup_now)
        self.backup_btn.pack(side="left", padx=(0, 8), pady=5)
        Tooltip(self.backup_btn, self.t("ui:tip_backup", "Copy your input regulation.bin and msg archives into a "
                                                         "timestamped backup folder (backups/ next to the program). "
                                                         "Does not run anything."))
        self.revert_btn = ttk.Button(actions, text=self.t("ui:revert", "Revert"), style="TButton",
                                     command=self._revert)
        self.revert_btn.pack(side="left", padx=(0, 8), pady=5)
        Tooltip(self.revert_btn, self.t("ui:tip_revert", "Restore the most recent backup: put your original "
                                                         "regulation.bin and msg archives back where they were."))

        self.run_btn = ttk.Button(actions, text=self.t("ui:randomize", "Randomize"), style="Run.TButton",
                                  command=lambda: self._run("run"))
        self.run_btn.pack(side="right", padx=(6, PAD), pady=5)
        self.repack_btn = ttk.Button(actions, text=self.t("ui:repack", "Repack only"), style="TButton",
                                     command=lambda: self._run("repack"))
        self.repack_btn.pack(side="right", padx=6, pady=5)
        self.sim_btn = ttk.Button(actions, text=self.t("ui:sim", "Loot simulator"), style="TButton",
                                  command=self._loot_dialog)
        self.sim_btn.pack(side="right", padx=6, pady=5)
        self.preview_btn = ttk.Button(actions, text=self.t("ui:preview", "Preview"), style="TButton",
                                      command=lambda: self._run("preview"))
        self.preview_btn.pack(side="right", padx=(6, 0), pady=5)
        Tooltip(self.preview_btn, self.t("ui:tip_preview", "Run every pass and show the reports, but write "
                                                       "no file."))
        Tooltip(self.sim_btn, self.t("ui:tip_sim", "Show what N random kills would drop with the current "
                                                   "settings. Writes nothing."))
        Tooltip(self.repack_btn, self.t("ui:tip_repack", "Rewrite the input unchanged. Repairs a "
                                                        "regulation.bin another tool wrote in a form the "
                                                        "game rejects."))
        Tooltip(self.run_btn, self.t("ui:tip_run", "Rewrite regulation.bin with every option that is "
                                                  "switched on."))

        self.log = tk.Text(self.root, height=12, wrap="none", background=theme.PANEL, foreground=theme.FG,
                           insertbackground=theme.FG, relief="flat", borderwidth=0,
                           font=self.fonts["mono"], state="disabled")
        self.log.tag_configure("head", foreground=theme.ACCENT)
        self.log.tag_configure("error", foreground=theme.ERR)
        if self.cfg.get("log_open"):
            self.log.pack(fill="x", side="bottom", before=foot)
            self.log_btn.configure(text=self.t("ui:hide_log", "Hide log"))

        page = ScrollFrame(self.root)
        page.pack(fill="both", expand=True, side="top")
        self.page = page
        for key, title in options.GROUPS:
            opts = [o for o in options.OPTIONS if o.group == key and o.gui]
            if not opts:
                continue
            sec = Section(page.body, title, open_=DEFAULT_OPEN.get(key, False),
                          tip=self.t(f"ui:sec:{key}", SECTION_TIPS.get(key, "")))
            sec.header.configure(text=(("\u25be  " if sec.is_open else "\u25b8  ") + self.t(f"ui:sec:{key}", title)))
            sec.title = self.t(f"ui:sec:{key}", title)
            sec._label()
            sec.pack(fill="x")
            self.sections[key] = sec
            for o in opts:
                before = sec._row
                self._add_option(sec, o)
                if sec._row > before:                       # an option that was actually placed
                    self._row_widgets[o.key] = sec.body.grid_slaves(row=before)

        self.hint = ttk.Label(page.body, style="Warn.TLabel", text="", wraplength=780, justify="left")
        self.hint.pack(fill="x", padx=(PAD, PAD), pady=(2, 8))
        self._update_hints()
        self._add_preset_tools()

    def _add_preset_tools(self) -> None:
        """Export / import your own bundles as a JSON file, in the Advanced section."""
        sec = self.sections.get("advanced")
        if sec is None:
            return
        row = sec.next_row()
        label_at(sec.body, row, self.t("ui:your_presets", "Your presets"),
                 self.t("ui:tip_your_presets", "Save your own bundles to a file and load them back."), padx=PAD)
        bar = ttk.Frame(sec.body, style="TFrame")
        bar.grid(row=row, column=1, sticky="w", padx=PAD, pady=2)
        export = ttk.Button(bar, text=self.t("ui:export", "Export"), style="Small.TButton",
                            command=self._export_presets)
        export.pack(side="left")
        Tooltip(export, self.t("ui:tip_export", "Write your own presets to a JSON file you can keep or "
                                              "share."))
        imp = ttk.Button(bar, text=self.t("ui:import", "Import"), style="Small.TButton",
                         command=self._import_presets)
        imp.pack(side="left", padx=(6, 0))
        Tooltip(imp, self.t("ui:tip_import", "Load presets from a JSON file. Presets with the same name "
                                           "are replaced."))

    def _indent(self, o: options.Opt) -> int:
        return INDENT if o.needs else 0

    def _add_option(self, sec: Section, o: options.Opt) -> None:
        if o.key == "weapon_names":
            return                                   # the path itself is the archives field under Files
        o = self._tr_opt(o)
        row = sec.next_row()
        pad = self._indent(o)

        if o.kind == "bool":
            key = "weapon_names_on" if o.key == "no_weapon_names" else o.key
            label = (self.t("opt:no_weapon_names:label", "Name the new affinity rows")
                     if o.key == "no_weapon_names" else o.label)
            tip = o.tip
            if o.key == "no_weapon_names":
                tip = self.t(
                    "opt:no_weapon_names:tip",
                    "Write a name and a description for every affinity row the somber patch adds, into the "
                    "item text archive (item_dlc02.msgbnd.dcx) of the languages given under Files. Leave "
                    "this off and those rows show a placeholder name in game.")
            cb = check_row(sec.body, row, label, self.vars[key], tip,
                           on_change=(lambda: self._macro(o)) if o.expands else self._changed,
                           padx=pad)
            self.widgets[o.key] = [cb]
            self.kinds[o.key] = ["bool"]
            return

        if o.key == "stamina_rate":                     # two numbers, one row
            label_at(sec.body, row, o.label, o.tip, pad)
            lo, hi = self._pair()
            self.vars[o.key + "_lo"], self.vars[o.key + "_hi"] = lo, hi
            e1 = ttk.Entry(sec.body, textvariable=lo, width=7)
            e2 = ttk.Entry(sec.body, textvariable=hi, width=7)
            e1.grid(row=row, column=1, sticky="w", padx=pad)
            ttk.Label(sec.body, text=self.t("ui:to", "to"), style="Muted.TLabel").grid(row=row, column=1, sticky="w",
                                                                      padx=(pad + 64, 0))
            e2.grid(row=row, column=1, sticky="w", padx=(pad + 90, 0))
            for w in (e1, e2):
                Tooltip(w, o.tip)
            lo.trace_add("write", lambda *_: self._sync_pair(o.key))
            hi.trace_add("write", lambda *_: self._sync_pair(o.key))
            self.widgets[o.key] = [e1, e2]
            self.kinds[o.key] = ["entry", "entry"]
            return

        if o.key in ("input", "output", "oodle_dll", "archives"):
            self.vars[o.key] = tk.StringVar(value=self._path_value(o.key, o.default))
            find = self.t("dlg:title_find", "Find")
            extra = {
                "input": (find, self._find_input,
                          self.t("ui:tip_find_input", "Search this machine for regulation.bin (Steam "
                                                        "library, the usual Games folders, mod folders) and "
                                                        "fill the field with the first hit.")),
                "oodle_dll": (find, self._find_dll,
                              self.t("ui:tip_find_dll", "Search the game and mod folders for "
                                                         "oo2core_6_win64.dll and fill the field with "
                                                         "the first hit.")),
                "archives": (find, self._find_archives,
                             self.t("ui:tip_find_archives", "Search for a msg folder that holds "
                                                            "item_dlc02.msgbnd.dcx and fill the field "
                                                            "with the first hit.")),
            }.get(o.key)
            widgets = path_row(sec.body, row, o, self.vars[o.key], self.recent.get(o.key, []),
                               self._browser(o.key), on_change=self._changed, padx=pad, extra=extra,
                               browse_text=self.t("ui:browse", "Browse"))
            self.widgets[o.key] = widgets
            self.kinds[o.key] = ["path", "button"] + (["button"] if extra else [])
            return

        if o.kind == "groups":
            w = groups_row(sec.body, row, o, self.vars[o.key], on_change=self._changed, padx=pad)
            self.widgets[o.key] = [w]
            self.kinds[o.key] = ["groups"]
            return

        if o.key == "seed":
            # one text field plus two small buttons: a fresh random seed, and copy (the field or the
            # last seed a run printed).
            label_at(sec.body, row, o.label, o.tip, pad)
            entry = ttk.Entry(sec.body, textvariable=self.vars[o.key])
            entry.grid(row=row, column=1, sticky="ew", padx=pad, pady=2)
            Tooltip(entry, o.tip)
            roll = ttk.Button(sec.body, text=self.t("ui:reroll", "Random"), style="Small.TButton",
                              command=self._reroll_seed)
            roll.grid(row=row, column=2, sticky="e", padx=(6, 0), pady=2)
            Tooltip(roll, self.t("ui:tip_reroll", "Fill the seed with a fresh random number you can reuse."))
            copy = ttk.Button(sec.body, text=self.t("ui:copy_seed", "Copy"), style="Small.TButton",
                              command=self._copy_seed)
            copy.grid(row=row, column=3, sticky="e", padx=(4, 0), pady=2)
            Tooltip(copy, self.t("ui:tip_copy_seed", "Copy the seed to the clipboard."))
            self.vars[o.key].trace_add("write", lambda *_: self._changed())
            self.widgets[o.key] = [entry, roll, copy]
            self.kinds[o.key] = ["entry", "button", "button"]
            return

        values = list(o.choices)
        if values:
            self._add_choice_row(sec, row, o, values, pad)
            return
        w = value_row(sec.body, row, o, self.vars[o.key], on_change=self._changed, padx=pad, kind="entry")
        self.widgets[o.key] = [w]
        self.kinds[o.key] = ["entry"]

    def _add_choice_row(self, sec, row, o, values, pad) -> None:
        """A dropdown that shows each choice in the window's language but keeps the value key.

        The label is `ui:tok:<value>` (a pack may translate it; otherwise the raw token shows).  The
        combobox uses a display var; selecting a label maps back to the value key, so validate()/argv and
        the saved config keep using the English token.
        """
        labels = [self.t(f"ui:tok:{v}", str(v)) for v in values]
        label_to_value = {self.t(f"ui:tok:{v}", str(v)): v for v in values}
        value_to_label = {str(v): self.t(f"ui:tok:{v}", str(v)) for v in values}
        current = str(self.vars[o.key].get())
        disp = tk.StringVar(value=value_to_label.get(current, current))
        label_at(sec.body, row, o.label, o.tip, pad)
        combo = ttk.Combobox(sec.body, textvariable=disp, values=labels, state="readonly")
        combo.grid(row=row, column=1, sticky="ew", padx=pad, pady=2)
        Tooltip(combo, o.tip)

        def _on_display(*_) -> None:
            if self._choice_guard:
                return
            self._choice_guard = True
            try:
                value = label_to_value.get(disp.get(), disp.get())
                if str(self.vars[o.key].get()) != str(value):
                    self.vars[o.key].set(value)
            finally:
                self._choice_guard = False

        def _on_value(*_) -> None:
            if self._choice_guard:
                return
            self._choice_guard = True
            try:
                label = value_to_label.get(str(self.vars[o.key].get()), str(self.vars[o.key].get()))
                if disp.get() != label:
                    disp.set(label)
            finally:
                self._choice_guard = False

        disp.trace_add("write", lambda *_: _on_display())
        self.vars[o.key].trace_add("write", lambda *_: _on_value())
        self.vars[o.key].trace_add("write", lambda *_: self._changed())
        self.widgets[o.key] = [combo]
        self.kinds[o.key] = ["combo"]

    def _pair(self) -> tuple:
        raw = str(self.vars.get("stamina_rate").get() if "stamina_rate" in self.vars else "0.8,1.2")
        parts = [p.strip() for p in raw.split(",") if p.strip()]
        lo = parts[0] if parts else "0"
        hi = parts[1] if len(parts) > 1 else lo
        return tk.StringVar(value=lo), tk.StringVar(value=hi)

    def _sync_pair(self, key: str) -> None:
        lo, hi = self.vars.get(key + "_lo"), self.vars.get(key + "_hi")
        if lo is not None and hi is not None:
            self.vars[key].set(f"{lo.get().strip()},{hi.get().strip()}")

    def _pick_found(self, field: str, what: str, found) -> None:
        """Put the first hit in a path field and list the others in a small window."""
        if not found:
            messagebox.showinfo(
                self.t("dlg:title_find", "Find"),
                self.t("dlg:find_none", "No {what} was found. Looked in the Steam library, the usual "
                                        "Games folders and the mod folders. Use Browse to pick it by "
                                        "hand.").format(what=what), parent=self.root)
            return
        self.vars[field].set(str(found[0]))
        # every hit goes into the history, not only the one that landed in the field
        lst = self.recent.setdefault(field, [])
        for path in found:
            if str(path) in lst:
                lst.remove(str(path))
            lst.insert(0, str(path))
        del lst[RECENT_MAX:]
        self._refresh_combos(field)
        self._remember_paths()
        self._changed()
        self.status.set(self.t("ui:found", "found") + f" {len(found)} {what} " + self.t("ui:files", "file(s)"))
        if len(found) > 1:
            others = "\n".join(f"  {p}" for p in found[1:6])
            messagebox.showinfo(
                self.t("dlg:title_find", "Find"),
                self.t("dlg:find_many", "Found {n}. The first is in the field:\n\n  {first}\n\n"
                                        "The others are in the dropdown next to it:\n{others}"
                                        ).format(n=len(found), first=found[0], others=others),
                parent=self.root)

    def _find_input(self) -> None:
        import discover
        self._pick_found("input", "regulation.bin", discover.candidates())

    def _find_dll(self) -> None:
        import discover
        self._pick_found("oodle_dll", "Oodle DLL", discover.find_dll())

    def _find_archives(self) -> None:
        import discover
        self._pick_found("archives", "text archive folder", discover.find_archives())

    def _path_value(self, key: str, default) -> str:
        got = self.saved.get(key)
        if isinstance(got, (list, tuple)):
            got = ";".join(str(x) for x in got)
        return str(got or default or "")

    def _browser(self, key: str):
        def pick(start: str) -> str:
            start_dir = start.strip().split(";")[0].strip('"')
            start_dir = start_dir if start_dir and Path(start_dir).is_dir() else os.getcwd()
            if key in ("input", "output"):
                return filedialog.askopenfilename(title="regulation.bin", initialdir=start_dir,
                                                  filetypes=[("regulation.bin", "*.bin"), ("All files", "*.*")])
            if key == "oodle_dll":
                return filedialog.askopenfilename(title="oo2core_6_win64.dll", initialdir=start_dir,
                                                  filetypes=[("DLL", "*.dll"), ("All files", "*.*")])
            return filedialog.askdirectory(title="msg folder", initialdir=start_dir)
        return pick

    # ------------------------------------------------------------------ events
    # ------------------------------------------------------------------ presets
    def _export_presets(self) -> None:
        from tkinter import filedialog
        path = filedialog.asksaveasfilename(
            title=self.t("dlg:title_export", "Export presets"), defaultextension=".json",
            initialfile="my-presets.json", filetypes=[("JSON", "*.json")], parent=self.root)
        if not path:
            return
        data = {"format": 1, "presets": self.my_presets}
        try:
            Path(path).write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")
        except OSError as e:
            messagebox.showerror(self.t("dlg:title_export_failed", "Export failed"), str(e), parent=self.root)
            return
        self.status.set(self.t("ui:exported", "exported") + f" {len(self.my_presets)} preset(s) to {path}")

    def _import_presets(self) -> None:
        from tkinter import filedialog
        path = filedialog.askopenfilename(title=self.t("dlg:title_import", "Import presets"),
                                          filetypes=[("JSON", "*.json")], parent=self.root)
        if not path:
            return
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            messagebox.showerror(self.t("dlg:title_import_failed", "Import failed"),
                                 self.t("dlg:import_bad", "{path} is not a readable JSON file: {error}")
                                 .format(path=path, error=e), parent=self.root)
            return
        bundles = data.get("presets") if isinstance(data, dict) else None
        if not isinstance(bundles, dict) or not bundles:
            messagebox.showerror(self.t("dlg:title_import_failed", "Import failed"),
                                 self.t("dlg:import_empty", "That file has no presets in it."),
                                 parent=self.root)
            return
        base = {o.key: o.default for o in options.OPTIONS}
        good, skipped = 0, []
        for name, values in bundles.items():
            if not isinstance(values, dict):
                skipped.append(str(name))
                continue
            unknown = [k for k in values if k not in options.BY_KEY]
            if unknown:
                skipped.append(f"{name} (unknown options: {', '.join(unknown[:3])})")
                continue
            merged = dict(base)
            merged.update(values)
            try:
                checked = options.validate(merged)
            except ValueError as e:
                skipped.append(f"{name} ({e})")
                continue
            self.my_presets[str(name)] = {k: v for k, v in checked.items() if k in options.BY_KEY}
            good += 1
        self.cfg["my_presets"] = self.my_presets
        self.preset_box.configure(values=self._preset_labels())
        self._save(now=True)
        self.status.set(self.t("ui:imported", "imported") + f" {good} preset(s)"
                        + (self.t("ui:skipped", ", skipped") + f" {len(skipped)}" if skipped else ""))
        if skipped:
            messagebox.showwarning(self.t("dlg:title_import", "Import presets"),
                                   self.t("dlg:import_skipped", "Imported {good} preset(s).\n\nSkipped:\n  ")
                                   .format(good=good)
                                   + "\n  ".join(skipped[:8]), parent=self.root)

    def _preset_labels(self) -> list[str]:
        return presets.labels() + list(self.my_presets)

    def _is_my_preset(self, label: str) -> bool:
        return label in self.my_presets

    def _apply_preset(self, _event=None) -> None:
        """Load a plug-and-play bundle: start from every switch off, then apply its values."""
        label = self.preset_var.get()
        bundle = self.my_presets.get(label) or (presets.find(label) or {}).get("values")
        if not bundle:
            return
        self.syncing = True
        try:
            for o in options.OPTIONS:
                var = self.vars.get(o.key)
                if o.kind == "bool" and var is not None and o.key != "weapon_names_on":
                    var.set(False)
            for key, value in bundle.items():
                var = self.vars.get(key)
                if var is None:
                    continue
                if isinstance(var, tk.BooleanVar):
                    var.set(bool(value))
                else:
                    var.set("" if value is None else str(value))
        finally:
            self.syncing = False
        self._remember_paths()
        self._refresh(save=False)
        self._save(now=True)
        self.status.set(self.t("ui:preset_label", "preset") + f": {label}")
        self._sync_preset_buttons()

    def _sync_preset_buttons(self) -> None:
        try:
            self.delete_preset_btn.configure(state="normal" if self._is_my_preset(self.preset_var.get()) else "disabled")
        except tk.TclError:
            pass

    def _save_preset(self) -> None:
        from tkinter import simpledialog
        name = simpledialog.askstring(self.t("dlg:title_save", "Save preset"),
                                      self.t("dlg:save_name", "Name for this set of options:"),
                                      initialvalue="My preset", parent=self.root)
        if not name:
            return
        name = name.strip()
        if not name:
            return
        try:
            values = options.validate(self.values())
        except ValueError as e:
            messagebox.showerror(self.t("dlg:title_cannot_save", "Cannot save"), str(e), parent=self.root)
            return
        if name in self.my_presets and not messagebox.askyesno(
                self.t("dlg:title_save", "Save preset"),
                self.t("dlg:save_exists", "\"{name}\" already exists. Replace it?").format(name=name),
                parent=self.root):
            return
        self.my_presets[name] = {k: v for k, v in values.items() if k in options.BY_KEY}
        self.cfg["my_presets"] = self.my_presets
        self.preset_box.configure(values=self._preset_labels())
        self.preset_var.set(name)
        self._save(now=True)
        self._sync_preset_buttons()
        self.status.set(self.t("ui:preset_saved", "preset saved") + f": {name}")
    def _delete_preset(self) -> None:
        name = self.preset_var.get()
        if name not in self.my_presets:
            return
        if not messagebox.askyesno(self.t("dlg:title_delete", "Delete preset"),
                                   self.t("dlg:delete_body", "Delete \"{name}\"?").format(name=name),
                                   parent=self.root):
            return
        self.my_presets.pop(name, None)
        self.cfg["my_presets"] = self.my_presets
        self.preset_box.configure(values=self._preset_labels())
        self.preset_var.set(self.t("ui:presets", "Presets"))
        self._save(now=True)
        self._sync_preset_buttons()

    def _changed(self, *_args) -> None:
        if self.syncing or not self.ready:
            return
        if self.preset_var.get() != "Custom":
            self.preset_var.set(self.t("ui:custom", "Custom"))   # a manual change means the bundle no longer applies
            self.cfg["preset"] = None
        self._follow_input()
        self._remember_paths()
        self._refresh()

    def _follow_input(self) -> None:
        """When the input changes, offer the output folder that was last used for that exact file."""
        inp = (self.vars["input"].get() or "").strip()
        if not inp or inp == self._last_input:
            return
        self._last_input = inp
        out = self.outputs.get(inp)
        if out and out != (self.vars["output"].get() or ""):
            self.syncing = True
            try:
                self.vars["output"].set(out)
            finally:
                self.syncing = False

    def _macro(self, o: options.Opt) -> None:
        on = bool(self.vars[o.key].get())
        self.syncing = True
        try:
            for key in o.expands:
                self.vars[key].set(on)
        finally:
            self.syncing = False
        self._changed()

    def _remember_paths(self, force: bool = False) -> None:
        """Push the path fields to the front of their recent lists.  While typing, only paths that exist
           are remembered; a run remembers what it used, including an output that does not exist yet."""
        for key in PATH_KEYS:
            var = self.vars.get(key)
            if var is None:
                continue
            for raw_part in str(var.get()).split(";"):
                part = raw_part.strip()
                if not part or (not force and not Path(part).exists()):
                    continue
                lst = self.recent.setdefault(key, [])
                if part in lst:
                    lst.remove(part)
                lst.insert(0, part)
                del lst[RECENT_MAX:]
        for key in PATH_KEYS:
            self._refresh_combos(key)

    def _refresh_combos(self, key: str) -> None:
        for w in self.widgets.get(key, []):
            if isinstance(w, ttk.Combobox):
                w.configure(values=self.recent.get(key, []))

    def _refresh(self, save: bool = True) -> None:
        v = self.values()
        for o in options.OPTIONS:
            if o.key not in self.widgets:
                continue
            active = options.is_active(o, v) and not self.running
            for w, kind in zip(self.widgets[o.key], self.kinds[o.key]):
                if kind == "path":
                    w.configure(state="normal" if active else "disabled")
                elif kind == "combo":
                    w.configure(state="readonly" if active else "disabled")
                elif kind == "groups":
                    self._enable_group(w, active)
                elif kind == "bool":
                    w.configure(state="normal" if active else "disabled")
                else:
                    w.state(["!disabled"] if active else ["disabled"])
        self._update_preview()
        self._update_hints()
        if save:
            self._save()

    @staticmethod
    def _enable_group(bar, active: bool) -> None:
        """The stat-group row is a frame of small check boxes; they share the option's state."""
        for w in bar.winfo_children():
            try:
                w.state(["!disabled"] if active else ["disabled"])
            except tk.TclError:
                pass

    def _update_preview(self) -> None:
        try:
            argv = options.argv_from_values(options.validate(self.values()))
        except ValueError:
            self.cmd_var.set("")
            return
        text = " ".join(self._quote(a) for a in argv)
        self.cmd_var.set(text if len(text) <= 170 else text[:167] + "...")

    @staticmethod
    def _quote(a: str) -> str:
        return f'"{a}"' if " " in a else a

    def _copy_command(self, _event=None) -> None:
        try:
            text = " ".join(self._quote(a) for a in options.argv_from_values(options.validate(self.values())))
        except ValueError:
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.status.set(self.t("ui:command_copied", "command copied"))

    def _reroll_seed(self) -> None:
        """Fill the seed field with a fresh random number the player can reuse or share."""
        import random
        self.syncing = True
        try:
            self.vars["seed"].set(str(random.randrange(1, 2 ** 31)))
        finally:
            self.syncing = False
        self._changed()

    def _copy_seed(self) -> None:
        """Copy the seed field, or the last seed a run printed when the field is empty."""
        raw = str(self.vars["seed"].get()).strip() if "seed" in self.vars else ""
        if not raw:
            raw = self._last_seed_in_log()
        if not raw:
            self.status.set(self.t("ui:seed_none", "no seed yet"))
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(raw)
        self.status.set(self.t("ui:seed_copied", "seed copied") + f": {raw}")

    def _last_seed_in_log(self) -> str:
        """The last `seed=` value in the log, so Copy works after a random (empty-field) run."""
        try:
            text = self.log.get("1.0", "end")
        except tk.TclError:
            return ""
        found = ""
        for line in text.splitlines():
            at = line.find("seed=")
            if at == -1:
                continue
            tail = line[at + 5:].split()
            if tail and tail[0].strip(",").isdigit():
                found = tail[0].strip(",")
        return found

    def _on_filter(self, *_args) -> None:
        self._apply_filter(self.filter_var.get())

    def _apply_filter(self, query: str) -> None:
        """Hide every option whose (translated) label and tip do not contain the query.

        A section left with no matching option is hidden too, so a search does not leave a column of
        empty headers.  Clearing the box shows every section again, in their original order (sections
        are re-packed in GROUPS order before the hint so the order stays stable).
        """
        q = (query or "").strip().lower()
        shown = total = 0
        visible: dict[str, int] = {}
        for o in options.OPTIONS:
            widgets = self._row_widgets.get(o.key)
            if not widgets:
                continue
            total += 1
            if q:
                label = self.t(f"opt:{o.key}:label", o.label).lower()
                tip = self.t(f"opt:{o.key}:tip", o.tip or "").lower()
                match = q in label or q in tip
            else:
                match = True
            for widget in widgets:
                if match:
                    widget.grid()
                else:
                    widget.grid_remove()
            if match:
                shown += 1
                visible[o.group] = visible.get(o.group, 0) + 1
        anchor = getattr(self, "hint", None)
        for key, sec in self.sections.items():
            if (not q) or visible.get(key, 0) > 0:
                if anchor is not None:
                    sec.pack(fill="x", before=anchor)
                else:
                    sec.pack(fill="x")
            else:
                sec.pack_forget()
        self.filter_count.configure(text=(f"{shown}/{total}" if q else ""))

    def _copy_log(self) -> None:
        text = self.log.get("1.0", "end")
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.status.set(self.t("ui:log_copied", "log copied"))

    def _update_hints(self) -> None:
        """One line under the options: what will slow the run down, and what is missing."""
        parts: list[str] = []
        path = ""
        if "oodle_dll" in self.vars:
            path = str(self.vars["oodle_dll"].get() or "").strip()
        if path:
            oodle.use_dll(path)
        why = oodle.available()
        if why and "not found" in why:
            parts.append("oo2core_6_win64.dll not found: the output would be zstd, which is larger and may "
                         "not fit. Point the Oodle DLL field at the DLL in the game's Game folder.")
        elif why:
            parts.append(why)
        if self.values().get("compression_level") == "max":
            parts.append("Maximum effort is on: a full run takes about 1 to 4 minutes. The window stays "
                         "responsive and shows which pass it is in.")
        latest = version.read_latest()
        if latest and version.is_newer(latest, version.__version__):
            parts.append(f"update available: v{latest} (you have v{version.__version__})")
        self.hint.configure(text="  ".join(parts))

    # ------------------------------------------------------------------ persistence
    def _save(self, now: bool = False) -> None:
        if not now and self.ready:
            if self._save_job:
                self.root.after_cancel(self._save_job)
            self._save_job = self.root.after(400, lambda: self._save(now=True))
            return
        self.cfg["geometry"] = self.root.geometry()
        self.cfg["values"] = {k: (bool(v.get()) if isinstance(v, tk.BooleanVar) else v.get())
                              for k, v in self.vars.items()
                              if k in options.BY_KEY or k == "weapon_names_on"}
        self.cfg["recent"] = dict(self.recent)
        self.cfg["sections"] = {k: s.is_open for k, s in self.sections.items()}
        preset = self.preset_var.get()
        self.cfg["preset"] = preset if preset in presets.labels() else None
        inp = (self.vars["input"].get() or "").strip()
        out = (self.vars["output"].get() or "").strip()
        if inp and out:
            self.outputs[inp] = out
            if len(self.outputs) > 24:                  # keep the file small, drop the oldest
                for key in list(self.outputs)[:-24]:
                    self.outputs.pop(key, None)
            self.cfg["outputs"] = self.outputs
        save_config(self.cfg)

    def _restore_sections(self) -> None:
        want = self.cfg.get("sections")
        if isinstance(want, dict):
            for k, sec in self.sections.items():
                if isinstance(want.get(k), bool):
                    sec.setOpen(want[k])

    def _reset(self) -> None:
        if not messagebox.askyesno(self.t("dlg:title_reset", "Reset"),
                                   self.t("dlg:reset_body", "Put every option back to its default? The "
                                                              "lists of paths you used are kept.")):
            return
        self.syncing = True
        try:
            for o in options.OPTIONS:
                if o.key not in self.vars:
                    continue
                var = self.vars[o.key]
                if isinstance(var, tk.BooleanVar):
                    var.set(bool(o.default))
                else:
                    var.set("" if o.default is None else str(o.default))
            self.vars["weapon_names_on"].set(True)
            if "stamina_rate_lo" in self.vars:
                self.vars["stamina_rate_lo"].set("0")
                self.vars["stamina_rate_hi"].set("2.0")
        finally:
            self.syncing = False
        self._changed()

    def _clear_log(self) -> None:
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.configure(state="disabled")

    def _toggle_log(self) -> None:
        """Show or hide the log.  It is packed above the bottom block, so the buttons stay reachable."""
        if self.log.winfo_ismapped():
            self.log.pack_forget()
            self.cfg["log_open"] = False
        else:
            self.log.pack(fill="x", side="bottom", before=self.foot)
            self.cfg["log_open"] = True
        self.log_btn.configure(text=self.t("ui:hide_log", "Hide log") if self.cfg["log_open"]
                               else self.t("ui:log", "Log"))

    # ------------------------------------------------------------------ running
    def _dll_error(self, v: dict) -> str | None:
        """Why the run cannot write kraken, or None.  Without this the engine would ask for the DLL on
           the console the window was started from, which nobody is looking at.

        A preview writes nothing and the engine forces zstd for it (randomize.main: `codec = ZSTD if
        dry_run or simulate`), so blocking a preview on a DLL it never uses was a false alarm - it
        stopped the one mode that works without the DLL from running.
        """
        if (v["repack"] or v.get("simulate") or v.get("dry_run")
                or v["compression"] not in ("kraken", "leviathan", "auto")):
            return None
        if oodle.missing_dll():
            return (f"{oodle.DLL_NAME} was not found, so the game's own kraken format cannot be written.\n\n"
                    "Copy it from the game's Game folder next to this program, point the \"Oodle DLL\" field at "
                    "it, or choose zstd under Compression (larger output).")
        return None

    def _loot_dialog(self) -> None:
        LootDialog(self)

    def _run(self, mode: str) -> None:
        if self.running or getattr(self, "sim_busy", False):
            return
        v = self.values()
        if mode == "preview":
            v["dry_run"], v["repack"] = True, False
        elif mode == "repack":
            v["dry_run"], v["repack"] = False, True
        else:
            v["dry_run"], v["repack"] = False, False
            # nothing ticked: confirm before writing what would be a recompressed copy of the input
            if (not any(v.get(k) for k in self._masters())
                    and not messagebox.askyesno(
                        self.t("dlg:title_nothing", "Nothing is switched on"),
                        self.t("dlg:nothing_body", "No randomization option is ticked, so the output would "
                                                   "be the input, recompressed.\n\n"
                                                   "Tick what you want to change, or choose Preview to "
                                                   "try it anyway."))):
                return
        try:
            v = options.validate(v)
        except ValueError as e:
            messagebox.showerror(self.t("dlg:title_cannot", "Cannot start"), str(e), parent=self.root)
            return
        argv = options.argv_from_values(v)
        if not v["repack"]:
            problem = self._dll_error(v)
            if problem:
                messagebox.showerror(self.t("dlg:title_oodle", "Oodle DLL missing"), problem, parent=self.root)
                return
        if v["compression_level"] == "max" and not v["repack"] and not v["dry_run"]:
            self._log("# maximum effort: about 1 to 4 minutes. The window stays responsive and the bar shows "
                     "which pass the run is in.", True)
        self._remember_paths(force=True)
        self._save(now=True)
        self.running = True
        self._failed = False
        self._t0 = time.monotonic()
        self.status.set(self.t("ui:working", "working ..."))
        self.progress.configure(mode="determinate")
        self.progress["value"] = 0
        self.clock.set("00:00")
        self._refresh(save=False)
        self._tick()
        threading.Thread(target=self._worker, args=(argv,), daemon=True).start()

    @staticmethod
    def _masters() -> tuple[str, ...]:
        return tuple(o.key for o in options.master_switches())

    def _worker(self, argv: list[str]) -> None:
        import randomize
        writer = QueueWriter(self.queue)
        old = sys.stdout
        sys.stdout = writer
        try:
            code = randomize.main(argv, progress=lambda phase: self.queue.put(("phase", phase)))
            self.queue.put(("exit", code))
        except SystemExit as e:
            self.queue.put(("exit", e.code if isinstance(e.code, int) else 1))
        except BaseException:
            self.queue.put(("error", traceback.format_exc()))
        finally:
            # restore the real stdout only if it is still ours: a LootDialog worker (or a second run)
            # that finished first must not leave sys.stdout pointing at a dead Collector / QueueWriter
            if sys.stdout is writer:
                sys.stdout = old
            self.queue.put(("finished", None))

    def _tick(self) -> None:
        if not self.running:
            return
        elapsed = int(time.monotonic() - self._t0)
        self.clock.set(f"{elapsed // 60:02d}:{elapsed % 60:02d}")
        self.root.after(500, self._tick)

    def _poll(self) -> None:
        try:
            while True:
                kind, payload = self.queue.get_nowait()
                if kind == "out":
                    self._log(payload[0], payload[1])
                elif kind == "phase":
                    self._phase(payload)
                elif kind == "error":
                    for line in (payload or "").splitlines():
                        self._log(line, line.startswith("Traceback") or line.startswith("  File"))
                    self._failed = True
                    self.status.set(self.t("ui:failed", "failed"))
                    self.status_label.configure(style="Error.TLabel")
                elif kind == "exit":
                    if payload not in (0, None):
                        self._failed = True
                        self.status.set(self.t("ui:failed_exit", "failed") + f" (exit {payload})")
                        self.status_label.configure(style="Error.TLabel")
                elif kind == "finished":
                    self._finish()
        except queue.Empty:
            pass
        self.root.after(120, self._poll)

    def _phase(self, phase: str) -> None:
        if phase == phases.COMPRESSING:
            # compression is one long blocking C call with no progress; show an indeterminate bar and a
            # time hint so it does not look frozen (the slow part is ~1-3 min at max effort)
            self.progress.configure(mode="indeterminate")
            self.progress.start(15)
            self.status.set(self.t("ui:compressing", "compressing... (1-3 min)"))
            self.status_label.configure(style="Muted.TLabel")
            return
        self.progress.stop()
        self.progress.configure(mode="determinate")
        try:
            index = PHASES.index(phase)
        except ValueError:
            # An unknown phase is a bug: the engine and phases.py must agree, and check_packs.py enforces
            # that.  Surface it instead of silently rewinding the bar to 0, which is what hid the original
            # "weapon effects / loot shuffle" drift for so long.
            self._log(f"# progress: unknown phase {phase!r} (not in phases.py)", True)
            self.status.set(phase)
            self.status_label.configure(style="Muted.TLabel")
            return
        self.progress["value"] = round(100 * index / max(1, len(PHASES) - 1))
        self.status.set(f"{index + 1}/{len(PHASES)}  " + self.t(f"phase:{phase}", phase))
        self.status_label.configure(style="Muted.TLabel")

    def _log(self, line: str, head: bool) -> None:
        self.log.configure(state="normal")
        self.log.insert("end", line + "\n", "head" if head else "")
        self.log.see("end")
        self.log.configure(state="disabled")
        if head and not self.running:
            self.status.set(line.lstrip("#").strip()[:110])

    def _open_output(self) -> None:
        out = (self.vars["output"].get() or "").strip()
        folder = os.path.dirname(out) if out else ""
        if not folder or not os.path.isdir(folder):
            folder = os.getcwd()
        try:
            if sys.platform == "win32":
                os.startfile(folder)               # noqa: S606 - opening a local folder in Explorer
            elif sys.platform == "darwin":
                subprocess.Popen(["open", folder])
            else:
                subprocess.Popen(["xdg-open", folder])
        except Exception:
            pass

    def _backup_now(self) -> None:
        """Copy the input files into a timestamped backup, without running anything."""
        import backup
        v = self.values()
        files = backup.collect_files(Path(v["input"]), list(v["archives"] or ()))
        bdir = backup.make_backup(files)
        if bdir is None:
            messagebox.showwarning(self.t("ui:backup_none", "Nothing to back up"),
                                   self.t("ui:backup_none_body", "The input file was not found, so there is "
                                                                  "nothing to back up."),
                                   parent=self.root)
            return
        self._log(f"# backup: {len(files)} file(s) copied to {bdir}", True)
        messagebox.showinfo(self.t("ui:backup_done", "Backup complete"),
                            self.t("ui:backup_done_body", "Original files copied to:\n{0}").format(bdir),
                            parent=self.root)

    def _revert(self) -> None:
        """Restore the most recent backup, after a confirmation."""
        import backup
        backups = backup.list_backups()
        if not backups:
            messagebox.showinfo(self.t("ui:revert_none", "No backup yet"),
                                self.t("ui:revert_none_body", "There is no backup to restore. Use Backup first, "
                                                               "or run with Backup and replace files on."),
                                parent=self.root)
            return
        latest = backups[0]
        if not messagebox.askyesno(
                self.t("ui:revert_title", "Revert to the last backup?"),
                self.t("ui:revert_body", "This puts the files from\n{0}\nback where they were, overwriting "
                                         "whatever is there now.").format(latest),
                parent=self.root):
            return
        try:
            restored = backup.restore(latest) if (latest / backup.MANIFEST).is_file() else []
        except (OSError, ValueError):
            restored = []
        if not restored:
            messagebox.showerror(self.t("ui:revert_failed", "Revert failed"),
                                 self.t("ui:revert_failed_body", "Could not read the backup manifest in:\n{0}")
                                 .format(latest), parent=self.root)
            return
        self._log(f"# revert: {len(restored)} file(s) restored from {latest}", True)
        messagebox.showinfo(self.t("ui:revert_done", "Reverted"),
                            self.t("ui:revert_done_body", "{0} file(s) restored from:\n{1}").format(
                                len(restored), latest),
                            parent=self.root)

    def _finish(self) -> None:
        self.running = False
        self.clock.set("")
        self.progress.stop()
        self.progress.configure(mode="determinate")
        if not self._failed:
            self.status.set(self.t("ui:done", "done"))
            # only a completed run may fill the bar: a run that died in the weapons pass used to end at
            # 100 % with a full bar and the word "failed" next to it, which reads as "finished"
            self.progress["value"] = 100
        self._refresh()

    def _show_about(self) -> None:
        """The About window: version, credits, and the two GitHub links."""
        win = tk.Toplevel(self.root)
        win.title(self.t("ui:about_title", "About"))
        win.resizable(False, False)
        win.transient(self.root)
        frame = ttk.Frame(win, padding=16)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text=self.t("ui:title", "Elden Ring Super Randomizer"),
                  style="Title.TLabel").pack(anchor="w")
        ttk.Label(frame, text=f"v{version.__version__}", style="Muted.TLabel").pack(anchor="w")
        ttk.Separator(frame).pack(fill="x", pady=8)
        body = (
            f"{self.t('ui:about_original', 'Original creator')}: WenchengDShao\n"
            "  https://github.com/WenchengDShao/elden_ring_further_random\n"
            "\n"
            f"{self.t('ui:about_fork', 'Fork')}: Eratas\n"
            "  https://github.com/Eratas/elden-ring-super-randomizer\n"
            "\n"
            f"{self.t('ui:about_credits', 'Credits')}:\n"
            "  WenchengDShao \u2014 the original elden_ring_further_random\n"
            "  Eratas \u2014 the Super Randomizer fork (this build)\n"
            "  The tools/ modules and the 13 language translations\n"
        )
        txt = tk.Text(frame, width=72, height=13, wrap="word", relief="flat",
                      background=theme.PANEL, foreground=theme.FG, highlightthickness=0)
        txt.insert("1.0", body)
        txt.configure(state="disabled")
        txt.pack(fill="both", expand=True)
        btns = ttk.Frame(frame)
        btns.pack(fill="x", pady=(8, 0))

        def _copy() -> None:
            self.root.clipboard_clear()
            self.root.clipboard_append(body)

        ttk.Button(btns, text=self.t("ui:about_copy", "Copy"),
                   command=_copy).pack(side="left")
        ttk.Button(btns, text=self.t("ui:close", "Close"),
                   command=win.destroy).pack(side="right")
        win.grab_set()
        win.focus_set()

    def _close(self) -> None:
        self._save(now=True)
        self.root.destroy()


def main(argv: list[str] | None = None) -> int:
    """Open the window.  `--lang <code>` starts in that language; the choice is then saved for next time."""
    args = list(sys.argv[1:] if argv is None else argv)
    code = "en"
    if "--lang" in args:
        index = args.index("--lang")
        if index + 1 >= len(args):
            print("--lang needs a code, e.g. --lang pt", file=sys.stderr)
            return 2
        code = args[index + 1]
        if code not in {item[0] for item in i18n.LANGUAGES}:
            print(f"unknown language {code!r}; known codes: "
                  + ", ".join(item[0] for item in i18n.LANGUAGES), file=sys.stderr)
            return 2
    root = tk.Tk()
    app = App(root)
    if code != "en":
        app.set_language(code)
    root.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
