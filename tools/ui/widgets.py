"""Building blocks for the window: hover help, a scrollable page, collapsible sections, aligned rows
   that never clip their text, and the file pickers that remember what was typed before.

The rule behind the layout: **nothing is allowed to disappear**.  Every section is a grid, so its
labels share one column and its controls line up; labels wrap instead of being cut off, and controls
stretch instead of overlapping.
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from . import theme

PAD = 12                 # page padding, left and right
INDENT = 24              # options that depend on another one are shifted right by this much


class Tooltip:
    """Hover help: appears the moment the pointer arrives (no delay), stays as long as it is hovered,
       never takes focus, and never covers the widget it describes."""

    WRAP = 460

    def __init__(self, widget: tk.Misc, text: str, wrap: int | None = None) -> None:
        self.widget = widget
        self.text = (text or "").strip()
        self.wrap = wrap or self.WRAP
        self.tw: tk.Toplevel | None = None
        if not self.text:
            return
        widget.bind("<Enter>", self._show, add="+")
        widget.bind("<Leave>", self._hide, add="+")
        widget.bind("<ButtonPress>", self._hide, add="+")
        widget.bind("<Destroy>", self._hide, add="+")

    def _show(self, _event=None) -> None:
        if self.tw is not None or not self.text:
            return
        try:
            if not self.widget.winfo_ismapped():
                return
        except tk.TclError:
            return
        tw = tk.Toplevel(self.widget)
        tw.withdraw()
        tw.overrideredirect(True)
        try:
            tw.attributes("-topmost", True)
        except tk.TclError:
            pass
        tw.configure(background=theme.BORDER)
        tk.Label(tw, text=self.text, justify="left", anchor="nw", wraplength=self.wrap,
                 background=theme.PANEL, foreground=theme.FG, relief="flat", borderwidth=0,
                 padx=9, pady=6, font=theme.font()).pack(fill="both", expand=True)
        tw.update_idletasks()
        x = self.widget.winfo_rootx() + 18
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 6
        w, h = tw.winfo_width(), tw.winfo_height()
        sw, sh = tw.winfo_screenwidth(), tw.winfo_screenheight()
        if x + w > sw - 10:
            x = max(10, sw - w - 10)
        if y + h > sh - 10:                       # not enough room below: show it above
            y = max(10, self.widget.winfo_rooty() - h - 6)
        tw.geometry(f"+{x}+{y}")
        tw.deiconify()
        self.tw = tw

    def _hide(self, _event=None) -> None:
        if self.tw is not None:
            self.tw.destroy()
            self.tw = None


class ScrollFrame(ttk.Frame):
    """A vertical scrollbar next to a frame that can be taller than the window.  Add rows to
       `self.body`, not to this widget.  The wheel scrolls only while the pointer is over the page."""

    def __init__(self, master, **kw) -> None:
        super().__init__(master, **kw)
        self.canvas = tk.Canvas(self, highlightthickness=0, background=theme.BG, borderwidth=0)
        self.vsb = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.vsb.set)
        self.vsb.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        self.body = ttk.Frame(self.canvas, style="TFrame")
        self.body.columnconfigure(1, weight=1)
        self._win = self.canvas.create_window((0, 0), window=self.body, anchor="nw")
        self.body.bind("<Configure>", self._on_body)
        self.canvas.bind("<Configure>", self._on_canvas)
        self.canvas.bind("<Enter>", self._wheel_on, add="+")
        self.canvas.bind("<Leave>", self._wheel_off, add="+")

    def _on_body(self, _event=None) -> None:
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas(self, event) -> None:
        self.canvas.itemconfigure(self._win, width=event.width)

    def _wheel_on(self, _event=None) -> None:
        self.canvas.bind_all("<MouseWheel>", self._on_wheel, add="+")

    def _wheel_off(self, _event=None) -> None:
        self.canvas.unbind_all("<MouseWheel>")

    def _on_wheel(self, event) -> None:
        self.canvas.yview_scroll(-1 if event.delta > 0 else 1, "units")


class Section(ttk.Frame):
    """A collapsible group: a header button that toggles its body, plus one line of explanation.

    The body is a two-column grid (label | control, with a third column for Browse buttons) so every
    row in the section lines up.  Call `next_row()` for each option and grid into that row.
    """

    def __init__(self, master, title: str, open_: bool = True, tip: str = "", **kw) -> None:
        super().__init__(master, style="TFrame", **kw)
        self.title = title
        self.is_open = open_
        self._row = 0
        self.header = ttk.Button(self, style="Section.TButton", command=self.toggle)
        self.header.pack(fill="x", padx=(PAD - 6, 0), pady=(8, 0))
        self.body = ttk.Frame(self, style="TFrame")
        self.body.columnconfigure(1, weight=1)
        self.tip = tip
        Tooltip(self.header, tip, wrap=520)
        self._label()
        if open_:
            self._show_body()
        self.columnconfigure(0, weight=1)

    def _label(self) -> None:
        self.header.configure(text=(("\u25be  " if self.is_open else "\u25b8  ") + self.title))

    def _show_body(self) -> None:
        self.body.pack(fill="x", padx=(PAD, PAD), pady=(4, 8))

    def toggle(self) -> None:
        self.is_open = not self.is_open
        self._label()
        if self.is_open:
            self._show_body()
        else:
            self.body.pack_forget()

    def setOpen(self, open_: bool) -> None:
        if open_ != self.is_open:
            self.toggle()

    def next_row(self) -> int:
        row = self._row
        self._row += 1
        return row


class HelpCheck(tk.Checkbutton):
    """A check box whose label wraps instead of being cut off.

    ttk.Checkbutton cannot wrap, which is how long labels used to disappear on a narrow window.  This
    one is a plain tk.Checkbutton painted with the theme colours and re-wrapped whenever it is resized.
    """

    def __init__(self, master, text: str, var: tk.BooleanVar, tip: str = "", on_change=None,
                 small: bool = False):
        super().__init__(
            master, text=text, variable=var, anchor="w", justify="left",
            background=theme.BG, foreground=theme.MUTED if small else theme.FG,
            activebackground=theme.BG, activeforeground=theme.FG,
            selectcolor=theme.PANEL, disabledforeground=theme.MUTED,
            relief="flat", borderwidth=0, highlightthickness=0, padx=2, pady=1,
            font=theme.font(small=small), wraplength=560)
        self.configure(command=lambda: on_change and on_change())
        self.bind("<Configure>", self._wrap)
        Tooltip(self, tip)

    def _wrap(self, event) -> None:
        width = event.width - 28
        if width > 40:
            self.configure(wraplength=width)


# ------------------------------------------------------------------ rows
def label_at(body, row: int, text: str, tip: str, padx: int = 0, col: int = 0):
    lab = ttk.Label(body, text=text, style="TLabel", anchor="w")
    lab.grid(row=row, column=col, sticky="w", padx=(padx, 8), pady=3)
    Tooltip(lab, tip)
    return lab


def check_row(body, row: int, text: str, var: tk.BooleanVar, tip: str, on_change=None,
              span: int = 3, padx: int = 0) -> HelpCheck:
    cb = HelpCheck(body, text, var, tip, on_change)
    cb.grid(row=row, column=0, columnspan=span, sticky="ew", padx=(padx, 0), pady=2)
    return cb


def value_row(body, row: int, opt, var: tk.StringVar, on_change=None, padx: int = 0,
              kind: str = "combo", values=()):
    """`label | control` on one row; the control stretches and never clips its label."""
    label_at(body, row, opt.label, opt.tip, padx)
    if kind == "combo":
        w = ttk.Combobox(body, textvariable=var, values=list(values or ()), state="readonly")
    else:
        w = ttk.Entry(body, textvariable=var)
    w.grid(row=row, column=1, sticky="ew", padx=padx, pady=2)
    Tooltip(w, opt.tip)
    if on_change:
        var.trace_add("write", lambda *_: on_change())
    return w


def path_row(body, row: int, opt, var: tk.StringVar, recent, browse, on_change=None, padx: int = 0,
             extra=None, browse_text: str = "Browse"):
    """`label | path (with history) | Browse [extra]`; `extra` is an optional (text, command) button."""
    label_at(body, row, opt.label, opt.tip, padx)
    combo = ttk.Combobox(body, textvariable=var, values=list(recent or ()))
    combo.grid(row=row, column=1, sticky="ew", padx=padx, pady=2)
    button = ttk.Button(body, text=browse_text, style="Small.TButton", command=lambda: _browse(combo, var, browse))
    button.grid(row=row, column=2, sticky="e", padx=(6, 0), pady=2)
    widgets = [combo, button]
    if extra is not None:
        text, command = extra[0], extra[1]
        tip = extra[2] if len(extra) > 2 else "Search this machine and fill the field with the first hit."
        more = ttk.Button(body, text=text, style="Small.TButton", command=command)
        more.grid(row=row, column=3, sticky="e", padx=(4, 0), pady=2)
        Tooltip(more, tip)
        widgets.append(more)
    for w in widgets:
        Tooltip(w, opt.tip)
        if isinstance(w, ttk.Combobox):
            # a path is finished when the field loses focus: save it then, not on every keystroke
            w.bind("<FocusOut>", lambda _e: on_change and on_change(), add="+")
    if on_change:
        var.trace_add("write", lambda *_: on_change())
    return widgets


def _browse(combo, var: tk.StringVar, browse) -> None:
    path = browse(var.get().strip())
    if path:
        var.set(path)


def groups_row(body, row: int, opt, var: tk.StringVar, on_change=None, padx: int = 0):
    """`label | [attack] [guard] ...` — small boxes that together write one comma-separated value."""
    label_at(body, row, opt.label, opt.tip, padx)
    bar = ttk.Frame(body, style="TFrame")
    bar.grid(row=row, column=1, sticky="w", padx=padx, pady=2)
    boxes: dict[str, tk.BooleanVar] = {}
    for i, item in enumerate(opt.items):
        v = tk.BooleanVar(value=False)
        boxes[item] = v
        cb = ttk.Checkbutton(bar, text=item, variable=v, style="Check.TCheckbutton",
                             command=lambda: _commit_groups(boxes, var, on_change))
        cb.grid(row=0, column=i, padx=(0, 10))
        Tooltip(cb, f"Randomize the {item} numbers.")
    _read_groups(boxes, var)
    var.trace_add("write", lambda *_: _read_groups(boxes, var))
    return bar


def _read_groups(boxes: dict, var: tk.StringVar) -> None:
    picked = {g.strip() for g in str(var.get() or "").split(",") if g.strip()}
    for item, v in boxes.items():
        v.set(item in picked if picked else True)


def _commit_groups(boxes: dict, var: tk.StringVar, on_change) -> None:
    picked = [item for item, v in boxes.items() if v.get()]
    if len(picked) == len(boxes):
        picked = []                       # all on = the default, kept short in the command line
    var.set(",".join(picked))
    if on_change:
        on_change()
