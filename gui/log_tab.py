# ============================================================
#  Chorus v2.5  –  gui/log_tab.py
#  Live log panel: timestamped message display.
# ============================================================

from __future__ import annotations

from datetime import datetime
import tkinter as tk
from tkinter import scrolledtext

import config as cfg
from utils.theme import BG, FG, FG_DIM, YELLOW, GREEN, RED, CYAN, MONO, SANS, LOG_TAGS


class LogTab:
    """Live log panel with timestamped messages."""

    def __init__(self, parent):
        self._text = None
        self._build(parent)

    def _build(self, parent):
        lf = tk.LabelFrame(parent, text="  Live Log  ", bg=BG,
                           fg=FG_DIM, font=(SANS, 9), bd=1, relief="groove")
        lf.pack(fill="both", expand=True)
        self._text = scrolledtext.ScrolledText(
            lf, bg=BG, fg=FG, font=(MONO, 9),
            relief="flat", bd=0, state="disabled", wrap="word", height=11)
        self._text.pack(fill="both", expand=True, padx=4, pady=4)
        for tag, fg in LOG_TAGS.items():
            self._text.tag_configure(tag, foreground=fg)

    def log_line(self, msg, tag="info"):
        """Append a timestamped line to the log."""
        ts = datetime.now().strftime("%H:%M:%S")
        self._text.configure(state="normal")
        self._text.insert("end", f"[{ts}]  ", "ts")
        self._text.insert("end", msg + "\n", tag)
        self._text.see("end")
        self._text.configure(state="disabled")

    def clear(self):
        """Clear the log panel."""
        self._text.configure(state="normal")
        self._text.delete("1.0", "end")
        self._text.configure(state="disabled")
