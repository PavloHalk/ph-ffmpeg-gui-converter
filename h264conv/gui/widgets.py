"""Допоміжні віджети: підказки, прокручувана панель, розгортуваний розділ."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

HINT_COLOR = "#555555"


def hint(parent, text: str, wrap: int = 400) -> ttk.Label:
    """Сірий пояснювальний текст під полем."""
    return ttk.Label(parent, text=text, foreground=HINT_COLOR, wraplength=wrap, justify="left")


class ToolTip:
    """Класична жовта підказка при наведенні миші."""

    def __init__(self, widget, text: str, delay: int = 500, wraplength: int = 380):
        self.widget = widget
        self.text = text
        self.delay = delay
        self.wraplength = wraplength
        self._after = None
        self._tip = None
        widget.bind("<Enter>", self._schedule, add="+")
        widget.bind("<Leave>", self._hide, add="+")
        widget.bind("<ButtonPress>", self._hide, add="+")

    def _schedule(self, _event=None):
        self._cancel()
        self._after = self.widget.after(self.delay, self._show)

    def _cancel(self):
        if self._after:
            try:
                self.widget.after_cancel(self._after)
            except tk.TclError:
                pass
            self._after = None

    def _show(self):
        self._after = None
        if self._tip or not self.text:
            return
        try:
            x = self.widget.winfo_rootx() + 12
            y = self.widget.winfo_rooty() + self.widget.winfo_height() + 4
        except tk.TclError:
            return
        tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.attributes("-topmost", True)
        tk.Label(tw, text=self.text, justify="left", background="#ffffe1",
                 relief="solid", borderwidth=1, wraplength=self.wraplength,
                 padx=4, pady=2).pack()
        tw.geometry(f"+{x}+{y}")
        self._tip = tw

    def _hide(self, _event=None):
        self._cancel()
        if self._tip is not None:
            try:
                self._tip.destroy()
            except tk.TclError:
                pass
            self._tip = None


class ScrollableFrame(ttk.Frame):
    """Фрейм з вертикальною прокруткою; вміст кладіть у .inner."""

    _wheel_bound = False

    def __init__(self, master, **kw):
        super().__init__(master, **kw)
        self.canvas = tk.Canvas(self, highlightthickness=0, borderwidth=0, yscrollincrement=20)
        self.vsb = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.vsb.set)
        self.inner = ttk.Frame(self.canvas)
        self._win = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.vsb.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        self.inner.bind("<Configure>", self._on_inner_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        if not ScrollableFrame._wheel_bound:
            self.bind_all("<MouseWheel>", ScrollableFrame._on_wheel, add="+")
            ScrollableFrame._wheel_bound = True

    def _on_inner_configure(self, _event=None):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas_configure(self, event):
        self.canvas.itemconfigure(self._win, width=event.width)

    def scroll(self, delta: int) -> None:
        top, bottom = self.canvas.yview()
        if top <= 0 and bottom >= 1:
            return
        steps = int(-delta / 120) or (-1 if delta > 0 else 1)
        self.canvas.yview_scroll(steps * 2, "units")

    def scroll_to_bottom(self) -> None:
        self.canvas.update_idletasks()
        self.canvas.yview_moveto(1.0)

    @staticmethod
    def _on_wheel(event):
        w = event.widget
        if not isinstance(w, tk.Misc):
            return
        try:
            cls = w.winfo_class()
        except tk.TclError:
            return
        if cls in ("Treeview", "Text", "Listbox"):
            return  # у цих віджетів своя прокрутка
        while w is not None:
            if isinstance(w, ScrollableFrame):
                w.scroll(event.delta)
                return
            w = w.master


class Collapsible(ttk.Frame):
    """Розділ, що розгортається/згортається кнопкою-заголовком."""

    def __init__(self, master, title: str, expanded: bool = False):
        super().__init__(master)
        self.title = title
        self.expanded = expanded
        self.header = ttk.Button(self, command=self.toggle)
        self.header.pack(fill="x")
        self.body = ttk.Frame(self, padding=(8, 6, 4, 4))
        self._update()

    def toggle(self):
        self.expanded = not self.expanded
        self._update()

    def _update(self):
        if self.expanded:
            self.header.configure(text=f"▾  {self.title}")
            self.body.pack(fill="x")
        else:
            self.header.configure(text=f"▸  {self.title}  (натисніть, щоб розгорнути)")
            self.body.pack_forget()
