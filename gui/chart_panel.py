# ============================================================
#  Chorus v2.5  –  gui/chart_panel.py
#  Live Pass/Fail bar chart: DUT/REF pass and fail counts.
# ============================================================

from __future__ import annotations

import tkinter as tk

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
MONO, SANS = "Consolas", "Segoe UI"


class ChartPanel:
    """Live Pass/Fail bar chart for DUT and REF pairs."""

    def __init__(self, parent):
        self._canvas = None
        self.chart_data = {"dut": {"pass": 0, "fail": 0}, "ref": {"pass": 0, "fail": 0}}
        self._build(parent)

    def _build(self, parent):
        chart_frame = tk.LabelFrame(parent, text="  Live Pass/Fail Chart  ", bg=BG,
                                    fg=FG_DIM, font=(SANS, 9), bd=1, relief="groove")
        chart_frame.pack(fill="x", pady=(0, 6))

        self._canvas = tk.Canvas(chart_frame, bg=BG2, height=100, highlightthickness=0)
        self._canvas.pack(fill="both", expand=True, padx=4, pady=4)

        self.draw_chart()

    def draw_chart(self):
        """Redraw the Pass/Fail bar chart."""
        self._canvas.delete("all")

        width = self._canvas.winfo_width()
        height = self._canvas.winfo_height()

        if width <= 1:
            width = 400
        if height <= 1:
            height = 100

        bar_width = 40
        bar_spacing = 20
        chart_top_margin = 10
        chart_bottom_margin = 30

        chart_height = height - chart_top_margin - chart_bottom_margin

        total_bars = 4
        total_width = total_bars * bar_width + (total_bars - 1) * bar_spacing
        start_x = (width - total_width) // 2

        max_value = max(
            self.chart_data["dut"]["pass"],
            self.chart_data["dut"]["fail"],
            self.chart_data["ref"]["pass"],
            self.chart_data["ref"]["fail"]
        )
        if max_value == 0:
            max_value = 1

        bars = [
            ("DUT Pass", self.chart_data["dut"]["pass"], GREEN),
            ("DUT Fail", self.chart_data["dut"]["fail"], RED),
            ("REF Pass", self.chart_data["ref"]["pass"], GREEN),
            ("REF Fail", self.chart_data["ref"]["fail"], RED)
        ]

        for i, (label, value, color) in enumerate(bars):
            bar_height = int((value / max_value) * chart_height)

            x1 = start_x + i * (bar_width + bar_spacing)
            y1 = height - chart_bottom_margin - bar_height
            x2 = x1 + bar_width
            y2 = height - chart_bottom_margin

            self._canvas.create_rectangle(x1, y1, x2, y2, fill=color, outline=color)

            if bar_height > 0:
                self._canvas.create_text(
                    x1 + bar_width // 2,
                    y1 - 10,
                    text=str(value),
                    fill=FG,
                    font=(MONO, 8)
                )

            self._canvas.create_text(
                x1 + bar_width // 2,
                height - chart_bottom_margin + 15,
                text=label,
                fill=FG_DIM,
                font=(MONO, 8)
            )
