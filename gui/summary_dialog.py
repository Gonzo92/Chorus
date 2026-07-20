# ============================================================
#  Chorus v2.5  –  gui/summary_dialog.py
#  Test summary dialog: overview, pair stats, errors, signal
#  data, and timeline charts.
# ============================================================

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from utils.theme import BG, BG2, BG3, FG, FG_DIM, BLUE, GREEN, RED, MONO, SANS

# ── optional matplotlib ───────────────────────────────────────
_MATPLOTLIB_OK = False
try:
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    _MATPLOTLIB_OK = True
except ImportError:
    pass


class SummaryDialog(tk.Toplevel):
    """Test summary dialog with multiple tabs."""

    def __init__(self, parent, summary_data):
        super().__init__(parent)
        self.title("Test Summary")
        self.configure(bg=BG)
        self.geometry("800x600")
        self.resizable(True, True)
        self.minsize(600, 400)

        self.summary_data = summary_data

        self._build_ui()

        self.transient(parent)
        self.grab_set()

    def _build_ui(self):
        header = tk.Frame(self, bg=BG2, height=40)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="Test Summary", font=(SANS, 12, "bold"),
                 bg=BG2, fg=FG).pack(pady=10)

        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=10, pady=10)

        self._build_overview_tab(notebook)
        self._build_pair_stats_tab(notebook)
        self._build_error_tab(notebook)
        self._build_signal_tab(notebook)
        self._build_timeline_tab(notebook)

        close_btn = ttk.Button(self, text="Close", command=self.destroy)
        close_btn.pack(pady=10)

    def _build_overview_tab(self, notebook):
        frame = tk.Frame(notebook, bg=BG)
        notebook.add(frame, text="Overview")

        stats_frame = tk.LabelFrame(frame, text="Overall Statistics", bg=BG,
                                    fg=FG_DIM, font=(SANS, 10, "bold"))
        stats_frame.pack(fill="x", padx=10, pady=10)

        overall = self.summary_data["overall_stats"]

        stats_grid = tk.Frame(stats_frame, bg=BG)
        stats_grid.pack(fill="x", padx=10, pady=10)

        stats = [
            ("Total Cycles", overall["total_cycles"]),
            ("Passed Cycles", overall["passed_cycles"]),
            ("Failed Cycles", overall["failed_cycles"]),
            ("Success Rate", f"{overall['success_rate']:.2f}%"),
            ("Test Duration", self.summary_data["test_duration"]),
            ("First Timestamp", self.summary_data["first_timestamp"] or "N/A"),
            ("Last Timestamp", self.summary_data["last_timestamp"] or "N/A")
        ]

        for i, (label, value) in enumerate(stats):
            row = i // 2
            col = (i % 2) * 2

            tk.Label(stats_grid, text=label, font=(MONO, 9), bg=BG, fg=FG_DIM,
                     anchor="w", width=20).grid(row=row, column=col, sticky="w", padx=5, pady=2)
            tk.Label(stats_grid, text=str(value), font=(MONO, 9, "bold"), bg=BG, fg=FG,
                     anchor="w", width=20).grid(row=row, column=col + 1, sticky="w", padx=5, pady=2)

        files_frame = tk.LabelFrame(frame, text="Files", bg=BG, fg=FG_DIM,
                                    font=(SANS, 10, "bold"))
        files_frame.pack(fill="x", padx=10, pady=10)

        tk.Label(files_frame, text="Detailed CSV:", font=(MONO, 9), bg=BG, fg=FG_DIM,
                 anchor="w").pack(fill="x", padx=10, pady=2)
        tk.Label(files_frame, text=self.summary_data["csv_path"], font=(MONO, 9), bg=BG,
                 fg=BLUE, anchor="w").pack(fill="x", padx=10, pady=2)

        tk.Label(files_frame, text="Summary CSV:", font=(MONO, 9), bg=BG, fg=FG_DIM,
                 anchor="w").pack(fill="x", padx=10, pady=2)
        tk.Label(files_frame, text=self.summary_data["summary_csv_path"], font=(MONO, 9), bg=BG,
                 fg=BLUE, anchor="w").pack(fill="x", padx=10, pady=2)

    def _build_pair_stats_tab(self, notebook):
        frame = tk.Frame(notebook, bg=BG)
        notebook.add(frame, text="Statistics by Pair")

        canvas = tk.Canvas(frame, bg=BG)
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg=BG)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        for pair, stats in self.summary_data["stats_by_pair"].items():
            pair_frame = tk.LabelFrame(scrollable_frame, text=f"{pair.upper()} Statistics",
                                      bg=BG, fg=FG_DIM, font=(SANS, 10, "bold"))
            pair_frame.pack(fill="x", padx=10, pady=10)

            stats_grid = tk.Frame(pair_frame, bg=BG)
            stats_grid.pack(fill="x", padx=10, pady=10)

            pair_stats = [
                ("Total Cycles", stats["total"]),
                ("Passed Cycles", stats["passed"]),
                ("Failed Cycles", stats["failed"]),
                ("Success Rate", f"{stats['success_rate']:.2f}%"),
                ("Average Duration (ms)", f"{stats['average_duration']:.2f}")
            ]

            for i, (label, value) in enumerate(pair_stats):
                row = i // 2
                col = (i % 2) * 2

                tk.Label(stats_grid, text=label, font=(MONO, 9), bg=BG, fg=FG_DIM,
                         anchor="w", width=20).grid(row=row, column=col, sticky="w", padx=5, pady=2)
                tk.Label(stats_grid, text=str(value), font=(MONO, 9, "bold"), bg=BG, fg=FG,
                         anchor="w", width=20).grid(row=row, column=col + 1, sticky="w", padx=5, pady=2)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

    def _build_error_tab(self, notebook):
        frame = tk.Frame(notebook, bg=BG)
        notebook.add(frame, text="Error Distribution")

        canvas = tk.Canvas(frame, bg=BG)
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg=BG)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        for pair, stats in self.summary_data["stats_by_pair"].items():
            if stats["errors"]:
                error_frame = tk.LabelFrame(scrollable_frame,
                                            text=f"{pair.upper()} Error Distribution",
                                            bg=BG, fg=FG_DIM, font=(SANS, 10, "bold"))
                error_frame.pack(fill="x", padx=10, pady=10)

                error_grid = tk.Frame(error_frame, bg=BG)
                error_grid.pack(fill="x", padx=10, pady=10)

                for i, (error_type, count) in enumerate(stats["error_distribution"].items()):
                    tk.Label(error_grid, text=error_type, font=(MONO, 9), bg=BG, fg=FG_DIM,
                             anchor="w", width=20).grid(row=i, column=0, sticky="w", padx=5, pady=2)
                    tk.Label(error_grid, text=str(count), font=(MONO, 9, "bold"), bg=BG, fg=FG,
                             anchor="w", width=20).grid(row=i, column=1, sticky="w", padx=5, pady=2)
            else:
                no_error_frame = tk.Frame(scrollable_frame, bg=BG)
                no_error_frame.pack(fill="x", padx=10, pady=10)
                tk.Label(no_error_frame, text=f"{pair.upper()}: No errors", font=(MONO, 9),
                         bg=BG, fg=GREEN, anchor="w").pack(fill="x", padx=10, pady=2)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

    def _build_signal_tab(self, notebook):
        frame = tk.Frame(notebook, bg=BG)
        notebook.add(frame, text="Signal Data")

        canvas = tk.Canvas(frame, bg=BG)
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg=BG)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        for pair, stats in self.summary_data["stats_by_pair"].items():
            if "signal_data" in stats:
                signal_frame = tk.LabelFrame(scrollable_frame,
                                             text=f"{pair.upper()} Signal Data",
                                             bg=BG, fg=FG_DIM, font=(SANS, 10, "bold"))
                signal_frame.pack(fill="x", padx=10, pady=10)

                signal_data = stats["signal_data"]

                signal_grid = tk.Frame(signal_frame, bg=BG)
                signal_grid.pack(fill="x", padx=10, pady=10)

                signal_stats = []

                if "avg_rsrp" in signal_data:
                    signal_stats.append(("Average RSRP", f"{signal_data['avg_rsrp']:.2f} dBm"))
                if "avg_rsrq" in signal_data:
                    signal_stats.append(("Average RSRQ", f"{signal_data['avg_rsrq']:.2f} dB"))
                if "avg_sinr" in signal_data:
                    signal_stats.append(("Average SINR", f"{signal_data['avg_sinr']:.2f} dB"))

                if signal_data["rat_distribution"]:
                    signal_stats.append(("RAT Distribution", ""))
                    for rat, count in signal_data["rat_distribution"].items():
                        signal_stats.append((f"  {rat}", str(count)))

                if signal_data["band_distribution"]:
                    signal_stats.append(("Band Distribution", ""))
                    for band, count in signal_data["band_distribution"].items():
                        signal_stats.append((f"  Band {band}", str(count)))

                for i, (label, value) in enumerate(signal_stats):
                    tk.Label(signal_grid, text=label, font=(MONO, 9), bg=BG, fg=FG_DIM,
                             anchor="w", width=20).grid(row=i, column=0, sticky="w", padx=5, pady=2)
                    tk.Label(signal_grid, text=value, font=(MONO, 9, "bold"), bg=BG, fg=FG,
                             anchor="w", width=20).grid(row=i, column=1, sticky="w", padx=5, pady=2)
            else:
                no_signal_frame = tk.Frame(scrollable_frame, bg=BG)
                no_signal_frame.pack(fill="x", padx=10, pady=10)
                tk.Label(no_signal_frame, text=f"{pair.upper()}: No signal data", font=(MONO, 9),
                         bg=BG, fg=FG_DIM, anchor="w").pack(fill="x", padx=10, pady=2)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

    def _build_timeline_tab(self, notebook):
        frame = tk.Frame(notebook, bg=BG)
        notebook.add(frame, text="Timeline")

        if not _MATPLOTLIB_OK:
            tk.Label(frame, text="matplotlib not installed — timeline unavailable.\n"
                                 "Install with: pip install matplotlib",
                     font=(MONO, 9), bg=BG, fg=RED, wraplength=500).pack(expand=True)
            return

        try:
            fig, ax = plt.subplots(figsize=(8, 4), facecolor=BG2)
            fig.patch.set_facecolor(BG2)
            ax.set_facecolor(BG2)

            cycles = [item["cycle"] for item in self.summary_data["call_success_rate_by_cycle"]]
            success_rates = [item["success_rate"] for item in self.summary_data["call_success_rate_by_cycle"]]

            ax.plot(cycles, success_rates, marker='o', linestyle='-', color=BLUE, markersize=4)
            ax.set_xlabel("Cycle", color=FG)
            ax.set_ylabel("Success Rate (%)", color=FG)
            ax.set_title("Success Rate by Cycle", color=FG)
            ax.grid(True, color=BG3)

            ax.tick_params(colors=FG)
            for spine in ax.spines.values():
                spine.set_color(BG3)

            canvas = FigureCanvasTkAgg(fig, frame)
            canvas.draw()
            canvas.get_tk_widget().pack(fill="both", expand=True, padx=10, pady=10)

            tk.Label(frame, text="Success rate per cycle over time", font=(MONO, 9),
                     bg=BG, fg=FG_DIM).pack(pady=5)
        except Exception:
            tk.Label(frame, text="Failed to render timeline chart.",
                     font=(MONO, 9), bg=BG, fg=RED).pack(expand=True)
