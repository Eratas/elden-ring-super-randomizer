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
       `self.body`, not to this widget.  The wheel scrolls the page whenever the pointer is over it.

    The wheel is routed at the toplevel, not with `bind_all` on Enter: Tk fires Enter/Leave for the
    canvas when the pointer crosses into a child, so the old Enter/Leave pair unbound the handler as
    soon as the pointer reached a label.  A focused ttk.Combobox also has a class binding that changes
    its value on the wheel; replacing that binding for this window is what keeps a selected dropdown
    from stealing the scroll."""

    WHEEL_EVENTS = ("<MouseWheel>", "<Button-4>", "<Button-5>")

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
        top = self.winfo_toplevel()
        # a language switch rebuilds the page; drop the previous page's wheel bindings so they do not
        # pile up on the toplevel (a stale handler would be harmless, but it would keep the old page alive)
        for event, funcid in getattr(top, "_page_wheel_ids", ()):
            top.unbind(event, funcid)
        ids = []
        for event in self.WHEEL_EVENTS:
            ids.append((event, top.bind(event, self._on_wheel, add="+")))
            # comboboxes are the one widget class that eats the wheel by default: replace the class
            # binding so a dropdown scrolls the page instead of silently changing the chosen value
            top.bind_class("TCombobox", event, self._on_combo_wheel)
        top._page_wheel_ids = tuple(ids)

    def _on_body(self, _event=None) -> None:
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas(self, event) -> None:
        self.canvas.itemconfigure(self._win, width=event.width)

    @staticmethod
    def _steps(event) -> int:
        """Wheel delta in scroll units: up is negative, down positive, on X11 and Windows alike."""
        if getattr(event, "num", None) == 4:
            return -1
        if getattr(event, "num", None) == 5:
            return 1
        return -1 if event.delta > 0 else 1

    def _inside(self, widget) -> bool:
        """True when `widget` is this page or lives inside it."""
        try:
            while widget is not None:
                if widget is self or widget is self.canvas:
                    return True
                widget = widget.master
        except (AttributeError, tk.TclError):
            pass
        return False

    def _pointer_inside(self, event) -> bool:
        """True when the event landed on this page or a widget inside it.

        The event names the deepest widget it reached. `winfo_containing` is not used: it can
        return None for a mapped canvas-embedded child, which would make the wheel dead."""
        widget = getattr(event, "widget", None)
        return widget is not None and self._inside(widget)

    def _scroll(self, event) -> None:
        self.canvas.yview_scroll(self._steps(event), "units")

    def _on_wheel(self, event):
        if self._pointer_inside(event):
            self._scroll(event)
            return "break"
        return None

    def _on_combo_wheel(self, event):
        # the class binding runs wherever the combobox is, including the language box outside the page;
        # scroll only when the pointer is over this page, but always stop the value from changing
        if self._pointer_inside(event):
            self._scroll(event)
        return "break"


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
