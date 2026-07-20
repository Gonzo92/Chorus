# ============================================================
#  Chorus v2.5  –  gui/pair_panel.py
#  Pair status panels: MO/MT serials, cycle counter, progress
#  bar, stage display, timer, pass/fail counters, scrcpy mirror.
# ============================================================

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

import config as cfg

# ── theme ──────────────────────────────────────────────────────
BG     = "#0f1117"
BG2    = "#2a2d3a"
BG3    = "#747579"
FG     = "#ffffff"
FG_DIM = "#B0B2B6"
BLUE   = "#6daaff"
YELLOW = "#8a440b"
GREEN  = "#5aff9d"
RED    = "#ff8585"
CYAN   = "#33e3ff"
MONO   = "Consolas"
SANS   = "Segoe UI"

STAGE_COLOR = {
    "PASS": GREEN, "FAIL": RED, "ACTIVE": CYAN,
    "COMPLETE": GREEN, "CALLING": YELLOW, "RINGING": YELLOW,
    "ANSWERING": YELLOW,
    "IDLE": FG_DIM, "CHECKING": FG, "HANGING UP": FG_DIM,
}


class PairPanels:
    """Builds and manages DUT + REF status panels."""

    def __init__(self, parent, on_scrcpy_callback):
        """
        Args:
            parent: parent frame to pack panels into
            on_scrcpy_callback: callable(pair, role) -> None
        """
        self._on_scrcpy = on_scrcpy_callback
        self._panels = {}
        self._build(parent)

    @property
    def panels(self):
        return self._panels

    # ── layout ─────────────────────────────────────────────────
    def _build(self, parent):
        row = tk.Frame(parent, bg=BG)
        row.pack(fill="x", pady=(0, 6))
        for pair, color, title in [
            ("dut", BLUE,   "DUT"),
            ("ref", YELLOW, "REF"),
        ]:
            self._panels[pair] = self._make_panel(row, pair, color, title)

    def _make_panel(self, parent, pair, color, title):
        border = tk.Frame(parent, bg=color, bd=2)
        border.pack(side="left", fill="both", expand=True,
                    padx=(0, 4) if pair == "dut" else (4, 0))
        inner = tk.Frame(border, bg=BG2, padx=10, pady=8)
        inner.pack(fill="both", expand=True, padx=2, pady=2)

        tk.Label(inner, text=title, font=(SANS, 11, "bold"),
                 bg=BG2, fg=color).pack(anchor="w")
        tk.Frame(inner, bg=color, height=1).pack(fill="x", pady=(2, 6))

        w = {}

        def kv(lbl, make_val):
            f = tk.Frame(inner, bg=BG2)
            f.pack(fill="x", pady=1)
            tk.Label(f, text=f"{lbl:<14}", font=(MONO, 9),
                     bg=BG2, fg=FG_DIM).pack(side="left")
            v = make_val(f)
            v.pack(side="left")
            return v

        w["mo"] = kv("MO serial", lambda p: tk.Label(
            p, text="–", font=(MONO, 9), bg=BG2, fg=FG, width=18, anchor="w"))
        w["mt"] = kv("MT serial", lambda p: tk.Label(
            p, text="–", font=(MONO, 9), bg=BG2, fg=FG, width=18, anchor="w"))
        kv("Direction", lambda p: tk.Label(
            p, text="MO → MT  (fixed)", font=(MONO, 9), bg=BG2, fg=FG_DIM))

        tk.Frame(inner, bg=BG3, height=1).pack(fill="x", pady=(6, 3))

        w["cycle_lbl"] = tk.Label(inner, text="Cycle  –/–  (–%)",
                                   font=(MONO, 10, "bold"), bg=BG2, fg=color)
        w["cycle_lbl"].pack(anchor="w")
        pb_style = ("blue" if pair == "dut" else "yellow") + ".Horizontal.TProgressbar"
        w["progress"] = ttk.Progressbar(inner, style=pb_style, maximum=100, value=0)
        w["progress"].pack(fill="x", pady=(2, 6))

        stage_frame = tk.Frame(inner, bg=BG2)
        stage_frame.pack(fill="x", pady=1)
        tk.Label(stage_frame, text=f"{'Stage':<14}", font=(MONO, 9),
                 bg=BG2, fg=FG_DIM).pack(side="left")
        w["stage"] = tk.Label(stage_frame, text="WAITING",
                               font=(MONO, 9, "bold"), bg=BG2, fg=FG_DIM, width=12, anchor="w")
        w["stage"].pack(side="left")
        w["timer"] = tk.Label(stage_frame, text="",
                               font=(MONO, 11, "bold"), bg=BG2, fg=CYAN, width=6, anchor="e")
        w["timer"].pack(side="left")

        w["last"] = kv("Last result", lambda p: tk.Label(
            p, text="–", font=(MONO, 9, "bold"), bg=BG2, fg=FG_DIM))

        tk.Frame(inner, bg=BG3, height=1).pack(fill="x", pady=4)
        stat = tk.Frame(inner, bg=BG2)
        stat.pack(fill="x")
        w["pass_lbl"] = tk.Label(stat, text="PASS: 0",
                                  font=(MONO, 10, "bold"), bg=BG2, fg=GREEN)
        w["pass_lbl"].pack(side="left", padx=(0, 12))
        w["fail_lbl"] = tk.Label(stat, text="FAIL: 0",
                                  font=(MONO, 10, "bold"), bg=BG2, fg=RED)
        w["fail_lbl"].pack(side="left")
        w["rate_lbl"] = tk.Label(stat, text="", font=(MONO, 9),
                                  bg=BG2, fg=FG_DIM)
        w["rate_lbl"].pack(side="right")

        # scrcpy buttons
        tk.Frame(inner, bg=BG3, height=1).pack(fill="x", pady=(6, 3))
        scr_frame = tk.Frame(inner, bg=BG2)
        scr_frame.pack(fill="x")
        tk.Label(scr_frame, text="📺  Mirror", font=(SANS, 8, "bold"),
                 bg=BG2, fg=FG_DIM).pack(side="left", padx=(0, 6))
        w["btn_scrcpy_mo"] = tk.Button(
            scr_frame, text="MO", font=(MONO, 8, "bold"),
            bg="#0e3a4a", fg=CYAN, relief="flat", bd=0,
            padx=8, pady=2,
            command=lambda p=pair: self._on_scrcpy(p, "MO"))
        w["btn_scrcpy_mo"].pack(side="left", padx=(0, 4))
        w["btn_scrcpy_mt"] = tk.Button(
            scr_frame, text="MT", font=(MONO, 8, "bold"),
            bg="#0e3a4a", fg=CYAN, relief="flat", bd=0,
            padx=8, pady=2,
            command=lambda p=pair: self._on_scrcpy(p, "MT"))
        w["btn_scrcpy_mt"].pack(side="left")

        w["disabled_lbl"] = tk.Label(inner, text="⏸  Not enabled",
                                      font=(SANS, 10), bg=BG2, fg=BG3)

        return w

    # ── public API ─────────────────────────────────────────────
    def set_enabled(self, pair, enabled):
        """Dim or restore a panel when pair is enabled/disabled."""
        w = self._panels[pair]
        color = BLUE if pair == "dut" else YELLOW
        dim = BG3
        for key in ("mo", "mt", "stage", "last", "pass_lbl",
                    "fail_lbl", "rate_lbl", "cycle_lbl", "timer"):
            w[key].configure(fg=(color if key == "cycle_lbl" else FG) if enabled else dim)
        if not enabled:
            w["stage"].configure(text="DISABLED", fg=dim)
            w["timer"].configure(text="")
            w["cycle_lbl"].configure(text="Cycle  –/–  (–%)", fg=dim)

    def update(self, pair, state, loops):
        """Update panel display with current state."""
        w = self._panels[pair]
        color = BLUE if pair == "dut" else YELLOW
        s = state[pair]

        w["mo"].configure(text=cfg.DEVICES[f"{pair}_MO"])
        w["mt"].configure(text=cfg.DEVICES[f"{pair}_MT"])

        cycle = s["cycle"]
        pct = int(cycle / loops * 100) if loops else 0
        w["cycle_lbl"].configure(text=f"Cycle  {cycle}/{loops}  ({pct}%)", fg=color)
        w["progress"]["value"] = pct

        stage = s["stage"]
        detail = s["detail"]

        sc = STAGE_COLOR.get(stage, FG)
        w["stage"].configure(text=stage, fg=sc)

        if detail.endswith("s") and detail[:-1].isdigit():
            w["timer"].configure(text=detail, fg=CYAN)
        else:
            w["timer"].configure(text="")

        last = s["last_result"]
        lc = GREEN if last == "PASS" else (RED if "FAIL" in last else FG_DIM)
        w["last"].configure(text=last, fg=lc)

        p, f = s["pass"], s["fail"]
        w["pass_lbl"].configure(text=f"PASS: {p}")
        w["fail_lbl"].configure(text=f"FAIL: {f}")
        total = p + f
        w["rate_lbl"].configure(
            text=f"success {int(p/total*100)}%" if total else "")
