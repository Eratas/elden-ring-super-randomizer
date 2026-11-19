"""Colours, fonts and the handful of ttk styles the window uses.

No images, no gradients, no animation: a flat dark palette whose only accent marks what matters
(the run button, the section markers, the progress bar).  Every colour is a module constant so a
widget never hard-codes one.
"""
from __future__ import annotations

import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk

BG = "#0e0d0b"          # window and section background - a warm near-black, the ER menu's base
PANEL = "#191611"       # entry / combobox field, log - a lifted warm dark
BAR = "#080706"         # top and bottom bars - the deepest tone
FG = "#e9e0c9"          # parchment / bone text
MUTED = "#9b9079"       # aged gold-grey for secondary text
ACCENT = "#c6a24a"      # antique gold - the run button, section markers, the progress bar
ACCENT_DARK = "#5f4a17" # dark bronze - secondary buttons and scrollbar troughs
ACCENT_HOVER = "#e2c268"  # bright gold - hover / pressed
BORDER = "#3a3222"      # dark bronze border
OK = "#8fa06a"          # muted moss green
WARN = "#d8a542"        # amber gold
ERR = "#b9564c"         # muted blood red

FONT = "Segoe UI"
MONO = "Consolas"

_fonts: dict = {}


def font(small: bool = False) -> tkfont.Font:
    """The UI font (8 pt for secondary text, 9 pt otherwise)."""
    key = "small" if small else "plain"
    if key not in _fonts:
        _fonts[key] = tkfont.Font(family=FONT, size=8 if small else 9)
    return _fonts[key]


def init(root: tk.Tk) -> dict[str, tkfont.Font]:
    """Switch to a DPI-aware, dark, image-free theme and build the styles.  Returns the fonts."""
    try:                                   # on Windows, without this the window is bitmap-scaled by the OS
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass

    style = ttk.Style(root)
    if "clam" in style.theme_names():
        style.theme_use("clam")

    fonts = {
        "plain": font(),
        "small": font(small=True),
        "bold": tkfont.Font(family=FONT, size=9, weight="bold"),
        "title": tkfont.Font(family=FONT, size=12, weight="bold"),
        "mono": tkfont.Font(family=MONO, size=9),
    }
    root.option_add("*Font", fonts["plain"])

    style.configure(".", background=BG, foreground=FG, fieldbackground=PANEL, bordercolor=BORDER,
                    lightcolor=BORDER, darkcolor=BORDER, troughcolor=BAR, focuscolor=ACCENT)
    style.configure("TFrame", background=BG)
    style.configure("Bar.TFrame", background=BAR)
    style.configure("TLabel", background=BG, foreground=FG)
    style.configure("Muted.TLabel", background=BG, foreground=MUTED, font=fonts["small"])
    style.configure("Title.TLabel", background=BAR, foreground=FG, font=fonts["title"])
    style.configure("Warn.TLabel", background=BG, foreground=WARN, font=fonts["small"])
    style.configure("Error.TLabel", background=BG, foreground=ERR)
    style.configure("Mono.TLabel", background=BG, foreground=FG, font=fonts["mono"])

    style.configure("TButton", background=ACCENT_DARK, foreground="#f2ead6", borderwidth=0,
                    focusthickness=1, focuscolor=ACCENT, padding=(12, 5), font=fonts["plain"])
    style.map("TButton",
              background=[("disabled", "#1b1812"), ("pressed", ACCENT), ("active", ACCENT_HOVER)],
              foreground=[("disabled", MUTED)])
    style.configure("Small.TButton", padding=(6, 2), font=fonts["small"], focusthickness=1)
    style.configure("Section.TButton", background=BG, foreground=FG, borderwidth=0, padding=(2, 4),
                    font=fonts["bold"], anchor="w", focusthickness=1)
    style.map("Section.TButton", background=[("active", PANEL)])
    style.configure("Run.TButton", background=ACCENT, foreground="#0e0d0b", font=fonts["bold"],
                    padding=(16, 7), focusthickness=1)
    style.map("Run.TButton", background=[("disabled", "#1b1812"), ("active", ACCENT_HOVER)],
              foreground=[("disabled", MUTED)])

    style.configure("Check.TCheckbutton", background=BG, foreground=FG, padding=(2, 1),
                    focuscolor=BG, font=fonts["small"])
    style.map("Check.TCheckbutton", background=[("active", BG)],
              indicatorcolor=[("selected", ACCENT), ("!selected", PANEL)])

    style.configure("TEntry", fieldbackground=PANEL, foreground=FG, insertcolor=FG, bordercolor=BORDER,
                    padding=4)
    style.configure("TCombobox", fieldbackground=PANEL, background=PANEL, foreground=FG,
                    arrowcolor=MUTED, bordercolor=BORDER, padding=2)
    style.map("TCombobox", fieldbackground=[("readonly", PANEL), ("disabled", BAR)],
              foreground=[("disabled", MUTED)])
    style.configure("Vertical.TScrollbar", background=PANEL, troughcolor=BG, bordercolor=BG,
                    arrowcolor=MUTED, darkcolor=ACCENT_DARK, lightcolor=ACCENT_DARK, borderwidth=0,
                    relief="flat")
    style.configure("Horizontal.TScrollbar", background=PANEL, troughcolor=BG, bordercolor=BG,
                    arrowcolor=MUTED, darkcolor=ACCENT_DARK, lightcolor=ACCENT_DARK, borderwidth=0)
    style.configure("Hint.Horizontal.TProgressbar", background=ACCENT, troughcolor=PANEL,
                    bordercolor=PANEL, lightcolor=ACCENT, darkcolor=ACCENT, thickness=6)

    root.configure(background=BG)
    return fonts