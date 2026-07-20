# ============================================================
#  Chorus v2.5  –  gui/log_viewer.py
#  Log viewer widget: text display with scrollbar and search.
# ============================================================

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from utils.theme import BG, BG2, FG, FG_DIM, MONO


class LogViewer:
    """Scrollable log viewer with search functionality."""

    def __init__(self, parent):
        self._build(parent)

    def _build(self, parent):
        frame = tk.Frame(parent, bg=BG2)
        frame.pack(fill="both", expand=True)

        self._text = tk.Text(frame, bg=BG, fg=FG, font=(MONO, 9),
                            relief="flat", bd=0, state="disabled",
                            wrap="word", yscrollcommand=self._scrollbar.set)
        self._text.pack(fill="both", expand=True, padx=4, pady=4)

        self._scrollbar = ttk.Scrollbar(frame, orient="vertical", command=self._text.yview)
        self._scrollbar.pack(side="right", fill="y")

    def append(self, text, tag=None):
        """Append text to the log viewer."""
        self._text.configure(state="normal")
        if tag:
            self._text.insert("end", text, tag)
        else:
            self._text.insert("end", text)
        self._text.see("end")
        self._text.configure(state="disabled")

    def clear(self):
        """Clear the log viewer."""
        self._text.configure(state="normal")
        self._text.delete("1.0", "end")
        self._text.configure(state="disabled")

    def get_content(self):
        """Get all content from the log viewer."""
        self._text.configure(state="normal")
        content = self._text.get("1.0", "end-1c")
        self._text.configure(state="disabled")
        return content
