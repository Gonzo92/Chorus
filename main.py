# ============================================================
#  Chorus v2.2  –  main.py (tkinter GUI)
#  Dark-mode desktop dashboard.
#  Run: python main.py
# ============================================================

from __future__ import annotations

import sys
import os

# ── ensure app directory is in sys.path (works from any CWD) ──
_APP_DIR = os.path.dirname(os.path.abspath(__file__))
if _APP_DIR not in sys.path:
    sys.path.insert(0, _APP_DIR)

import threading
import queue
from datetime import datetime
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog
import re
import json

import config as cfg
from core.adb_controller import check_devices, get_signal_info, launch_scrcpy, find_scrcpy

# ── optional matplotlib (graceful degradation) ───────────────
_MATPLOTLIB_OK = False
try:
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    _MATPLOTLIB_OK = True
except ImportError:
    pass

# ── font detection (fallback for non-standard Windows installs) ──
def _detect_fonts() -> tuple[str, str]:
    """Detect available fonts, return (mono_font, sans_font)."""
    try:
        families = tk.font.families()
    except Exception:
        families = set()

    # Mono font candidates (ordered by preference)
    mono_candidates = ["Consolas", "Courier New", "Lucida Console", "DejaVu Sans Mono"]
    mono = "Courier New"  # guaranteed fallback
    for f in mono_candidates:
        if f in families:
            mono = f
            break

    # Sans-serif font candidates
    sans_candidates = ["Segoe UI", "Arial", "Helvetica", "Tahoma", "Trebuchet MS"]
    sans = "Arial"  # guaranteed fallback
    for f in sans_candidates:
        if f in families:
            sans = f
            break

    return mono, sans


# ── imports ────────────────────────────────────────────────────
from core.call_monitor import run_cycle
from core.report import init_csv, generate_summary_report
from gui.device_picker import DevicePickerDialog
from utils.phone_history import load_history, add_to_history
from gui.rat_dialog import RatSettingsDialog
from gui.device_controls import DeviceControlsDialog

# ── cross-platform sound ──────────────────────────────────────
def _beep(kind: str = "ok") -> None:
    """Play a system beep. Silently ignored if unavailable."""
    try:
        if sys.platform == "win32":
            import winsound
            sounds = {"ok": winsound.MB_OK,
                      "error": winsound.MB_ICONHAND,
                      "warn": winsound.MB_ICONEXCLAMATION}
            winsound.MessageBeep(sounds.get(kind, winsound.MB_OK))
        elif sys.platform == "darwin":
            import subprocess
            subprocess.Popen(["afplay", "/System/Library/Sounds/Glass.aiff"],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            # Linux — try paplay or bell
            import subprocess
            subprocess.Popen(["paplay", "/usr/share/sounds/freedesktop/stereo/complete.oga"],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass

# ── theme ────────────────────────────────────────────────────
BG     = "#0f1117"
BG2    = "#2a2d3a"  # Lighter background for better contrast
BG3    = "#747579"  # Even lighter for better contrast
FG     = "#ffffff"  # Bright white text
FG_DIM = "#B0B2B6"  # Lighter dimmed text
BLUE   = "#6daaff"  # Brighter blue
YELLOW = "#8a440b"  # Darker amber/brown color
GREEN  = "#5aff9d"  # Brighter green
RED    = "#ff8585"  # Brighter red
CYAN   = "#33e3ff"  # Brighter cyan
MONO, SANS = _detect_fonts()

STAGE_COLOR = {
    "PASS": GREEN, "FAIL": RED, "ACTIVE": CYAN,
    "COMPLETE": GREEN, "CALLING": YELLOW, "RINGING": YELLOW,
    "ANSWERING": YELLOW,
    "IDLE": FG_DIM, "CHECKING": FG, "HANGING UP": FG_DIM,
}

# ── shared state ─────────────────────────────────────────────
_ui_queue: queue.Queue = queue.Queue()
_stop_event = threading.Event()
_threads: list = []
_sync_barrier = None  # For synchronized testing
_sync_lock = threading.Lock()

_state = {
    "dut": {"cycle": 0, "stage": "–", "detail": "",
               "pass": 0, "fail": 0, "done": False, "last_result": "–", "enabled": True},
    "ref":    {"cycle": 0, "stage": "–", "detail": "",
               "pass": 0, "fail": 0, "done": False, "last_result": "–", "enabled": True},
}

# Set to keep track of which cycles have been logged to timestamps file
_logged_cycles = set()


def _status_cb(pair: str, cycle: int, stage: str, detail: str) -> None:
    _ui_queue.put(("status", pair, cycle, stage, detail))


def _sync_worker(pair: str, mo: str, mt: str, number: str, loops: int, max_retries: int = 3, retry_delay: int = 1) -> None:
    """Worker function for synchronized testing mode."""
    global _sync_barrier
    
    # Create a barrier for synchronization if not already created
    with _sync_lock:
        if _sync_barrier is None:
            # Count enabled pairs
            enabled_pairs = 0
            if _state["dut"].get("enabled", False):
                enabled_pairs += 1
            if _state["ref"].get("enabled", False):
                enabled_pairs += 1
            _sync_barrier = threading.Barrier(enabled_pairs)
    
    for cycle in range(1, loops + 1):
        if _stop_event.is_set():
            break
            
        # Wait for all pairs to reach this point before starting the cycle
        try:
            _sync_barrier.wait()
        except threading.BrokenBarrierError:
            break
            
        # Run the cycle
        cycle_result = run_cycle(pair=pair, dut_mo=mo, dut_mt=mt, phone_number=number,
                  cycle=cycle, status_callback=_status_cb, stop_event=_stop_event,
                  max_answer_retries=max_retries, answer_retry_delay=retry_delay)
                  
        # Store signal data for this cycle
        if cycle_result.get("result") in ["PASS", "FAIL"]:
            # Store signal data in the global app instance
            app = tk._default_root
            if app and hasattr(app, '_cycle_signal_data'):
                app._cycle_signal_data[cycle] = app._cycle_signal_data.get(cycle, {})
                app._cycle_signal_data[cycle][f"{pair}_mo"] = {
                    "rat": cycle_result.get("rat", "N/A"),
                    "rsrp": cycle_result.get("rsrp", "N/A"),
                    "rsrq": cycle_result.get("rsrq", "N/A"),
                    "sinr": cycle_result.get("sinr", "N/A"),
                    "band": cycle_result.get("band", "N/A")
                }
                # Get signal info for MT device
                mt_signal_info = get_signal_info(mt)
                app._cycle_signal_data[cycle][f"{pair}_mt"] = mt_signal_info
                  
        # Store call type information
        if cycle_result.get("result") in ["PASS", "FAIL"]:
            # Store call type in the global app instance
            app = tk._default_root
            if app and hasattr(app, '_cycle_signal_data'):
                if f"{pair}_mo" in app._cycle_signal_data.get(cycle, {}):
                    app._cycle_signal_data[cycle][f"{pair}_mo"]["call_type"] = cycle_result.get("call_type", "UNKNOWN")
                  
        # Wait for all pairs to finish the cycle before starting the next one
        try:
            _sync_barrier.wait()
        except threading.BrokenBarrierError:
            break
            
    _ui_queue.put(("done", pair))


def _worker(pair: str, mo: str, mt: str, number: str, loops: int, max_retries: int = 3, retry_delay: int = 1) -> None:
    """Worker function for normal (non-synchronized) testing mode."""
    for cycle in range(1, loops + 1):
        if _stop_event.is_set():
            break
        cycle_result = run_cycle(pair=pair, dut_mo=mo, dut_mt=mt, phone_number=number,
                  cycle=cycle, status_callback=_status_cb, stop_event=_stop_event,
                  max_answer_retries=max_retries, answer_retry_delay=retry_delay)
        
        # Store signal data for this cycle
        if cycle_result.get("result") in ["PASS", "FAIL"]:
            # Store signal data in the global app instance
            app = tk._default_root
            if app and hasattr(app, '_cycle_signal_data'):
                app._cycle_signal_data[cycle] = app._cycle_signal_data.get(cycle, {})
                app._cycle_signal_data[cycle][f"{pair}_mo"] = {
                    "rat": cycle_result.get("rat", "N/A"),
                    "rsrp": cycle_result.get("rsrp", "N/A"),
                    "rsrq": cycle_result.get("rsrq", "N/A"),
                    "sinr": cycle_result.get("sinr", "N/A"),
                    "band": cycle_result.get("band", "N/A")
                }
                # Get signal info for MT device
                mt_signal_info = get_signal_info(mt)
                app._cycle_signal_data[cycle][f"{pair}_mt"] = mt_signal_info
    _ui_queue.put(("done", pair))


# ═══════════════════════════════════════════════════════════
class ChorusApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Chorus v2.2")
        self.configure(bg=BG)
        self.resizable(True, True)
        self.minsize(1060, 760)
        self._loops = cfg.LOOP_COUNT
        self._configure_styles()
        self._load_persistent_config()
        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(80, self._poll_queue)

    # ── ttk styles ───────────────────────────────────────────
    def _configure_styles(self):
        s = ttk.Style(self)
        s.theme_use("clam")
        for w in ("TFrame", "TLabelframe", "TLabelframe.Label",
                  "TLabel", "TButton", "TEntry", "TCheckbutton"):
            s.configure(w, background=BG, foreground=FG,
                        fieldbackground=BG3, bordercolor=BG3,
                        font=(SANS, 10), relief="flat")
        s.configure("TButton", padding=(10, 6), font=(SANS, 10, "bold"))
        s.map("TButton",
              background=[("active", BG3), ("!active", BG2)],
              foreground=[("active", FG)])
        s.configure("Start.TButton", background=BLUE, foreground="white")
        s.map("Start.TButton",
              background=[("active", "#2563eb"), ("disabled", BG3)],
              foreground=[("disabled", FG_DIM)])
        s.configure("Stop.TButton", background="#7f1d1d", foreground="#fca5a5")
        s.map("Stop.TButton", background=[("active", RED)])
        s.configure("Pick.TButton", background="#0e3a4a", foreground=CYAN,
                    font=(SANS, 10, "bold"))
        s.map("Pick.TButton", background=[("active", "#0a2a38")])
        s.configure("blue.Horizontal.TProgressbar",
                    troughcolor=BG3, background=BLUE, thickness=8)
        s.configure("yellow.Horizontal.TProgressbar",
                    troughcolor=BG3, background=YELLOW, thickness=8)
        s.configure("dim.Horizontal.TProgressbar",
                    troughcolor=BG3, background=BG3, thickness=8)

    # ── layout ───────────────────────────────────────────────
    def _build_ui(self):
        hdr = tk.Frame(self, bg=BG2, height=48)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        tk.Label(hdr, text="  📡  Chorus",
                 font=(SANS, 14, "bold"), bg=BG2, fg=FG).pack(side="left", padx=10, pady=8)
        tk.Label(hdr, text="v2.2", font=(MONO, 10), bg=BG2, fg=BLUE).pack(side="left")
        self._lbl_mode = tk.Label(hdr, text="", font=(MONO, 9, "bold"), bg=BG2)
        self._lbl_mode.pack(side="right", padx=16)

        body = tk.Frame(self, bg=BG)
        body.pack(fill="both", expand=True, padx=10, pady=6)

        # Create a frame for the left panel with scrollbar
        left_container = tk.Frame(body, bg=BG, width=350)
        left_container.pack(side="left", fill="y", padx=(0, 8))
        left_container.pack_propagate(False)
        
        # Create a canvas and scrollbar for the left panel
        left_canvas = tk.Canvas(left_container, bg=BG, highlightthickness=0)
        left_scrollbar = ttk.Scrollbar(left_container, orient="vertical", command=left_canvas.yview)
        self.left_scrollable_frame = tk.Frame(left_canvas, bg=BG)
        
        # Configure scrolling
        self.left_scrollable_frame.bind(
            "<Configure>",
            lambda e: left_canvas.configure(
                scrollregion=left_canvas.bbox("all")
            )
        )
        
        left_canvas.create_window((0, 0), window=self.left_scrollable_frame, anchor="nw")
        left_canvas.configure(yscrollcommand=left_scrollbar.set)
        
        # Pack canvas and scrollbar
        left_canvas.pack(side="left", fill="both", expand=True)
        left_scrollbar.pack(side="right", fill="y")
        
        # Bind mousewheel to canvas for scrolling
        def _on_mousewheel(event):
            left_canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        
        left_canvas.bind_all("<MouseWheel>", _on_mousewheel)
        self.left_scrollable_frame.bind("<MouseWheel>", _on_mousewheel)
        
        # Build UI elements inside the scrollable frame
        self._build_config(self.left_scrollable_frame)
        self._build_controls(self.left_scrollable_frame)

        right = tk.Frame(body, bg=BG)
        right.pack(side="left", fill="both", expand=True)
        self._build_pair_panels(right)
        self._build_live_chart(right)
        self._build_log(right)

    def _build_live_chart(self, parent):
        # Create a frame for the live chart
        chart_frame = tk.LabelFrame(parent, text="  Live Pass/Fail Chart  ", bg=BG,
                                    fg=FG_DIM, font=(SANS, 9), bd=1, relief="groove")
        chart_frame.pack(fill="x", pady=(0, 6))

        # Create a canvas for the chart
        self.chart_canvas = tk.Canvas(chart_frame, bg=BG2, height=100, highlightthickness=0)
        self.chart_canvas.pack(fill="both", expand=True, padx=4, pady=4)

        # Initialize chart data
        self.chart_data = {"dut": {"pass": 0, "fail": 0}, "ref": {"pass": 0, "fail": 0}}
        
        # Draw initial chart
        self._draw_chart()

    def _draw_chart(self):
        # Clear the canvas
        self.chart_canvas.delete("all")
        
        # Get the canvas dimensions
        width = self.chart_canvas.winfo_width()
        height = self.chart_canvas.winfo_height()
        
        # If width or height is 1, it means the canvas is not yet properly initialized
        if width <= 1:
            width = 400  # Default width
        if height <= 1:
            height = 100  # Default height
            
        # Define chart parameters
        bar_width = 40
        bar_spacing = 20
        chart_top_margin = 10
        chart_bottom_margin = 30
        
        # Calculate available height for bars
        chart_height = height - chart_top_margin - chart_bottom_margin
        
        # Calculate total number of bars
        total_bars = 4  # DUT Pass, DUT Fail, REF Pass, REF Fail
        total_width = total_bars * bar_width + (total_bars - 1) * bar_spacing
        
        # Calculate starting x position to center the chart
        start_x = (width - total_width) // 2
        
        # Find the maximum value to scale the bars
        max_value = max(
            self.chart_data["dut"]["pass"],
            self.chart_data["dut"]["fail"],
            self.chart_data["ref"]["pass"],
            self.chart_data["ref"]["fail"]
        )
        
        # If all values are 0, set max_value to 1 to avoid division by zero
        if max_value == 0:
            max_value = 1
            
        # Draw bars
        bars = [
            ("DUT Pass", self.chart_data["dut"]["pass"], GREEN),
            ("DUT Fail", self.chart_data["dut"]["fail"], RED),
            ("REF Pass", self.chart_data["ref"]["pass"], GREEN),
            ("REF Fail", self.chart_data["ref"]["fail"], RED)
        ]
        
        for i, (label, value, color) in enumerate(bars):
            # Calculate bar height
            bar_height = int((value / max_value) * chart_height)
            
            # Calculate bar position
            x1 = start_x + i * (bar_width + bar_spacing)
            y1 = height - chart_bottom_margin - bar_height
            x2 = x1 + bar_width
            y2 = height - chart_bottom_margin
            
            # Draw bar
            self.chart_canvas.create_rectangle(x1, y1, x2, y2, fill=color, outline=color)
            
            # Draw value above bar
            if bar_height > 0:
                self.chart_canvas.create_text(
                    x1 + bar_width // 2, 
                    y1 - 10, 
                    text=str(value), 
                    fill=FG, 
                    font=(MONO, 8)
                )
            
            # Draw label below bar
            self.chart_canvas.create_text(
                x1 + bar_width // 2, 
                height - chart_bottom_margin + 15, 
                text=label, 
                fill=FG_DIM, 
                font=(MONO, 8)
            )

        self._refresh_mode_label()

    # ── config panel ─────────────────────────────────────────
    def _build_config(self, parent):
        outer = tk.LabelFrame(parent, text="  Configuration  ", bg=BG,
                               fg=BLUE, font=(SANS, 10, "bold"),
                               bd=1, relief="groove", labelanchor="nw")
        outer.pack(fill="x", pady=(0, 8))

        def entry_row(frame, label, var, width=16, pair=None):
            f = tk.Frame(frame, bg=BG)
            f.pack(fill="x", padx=8, pady=2)
            tk.Label(f, text=label, font=(MONO, 8), bg=BG,
                     fg=FG_DIM, width=14, anchor="w").pack(side="left")
            e = tk.Entry(f, textvariable=var, font=(MONO, 9),
                         bg=BG3, fg=FG, insertbackground=FG,
                         relief="flat", bd=0, width=width,
                         highlightthickness=1,
                         highlightcolor=BLUE, highlightbackground=BG3)
            e.pack(side="left", ipady=3)
            
            # Add history button for MT number entries
            if label == "MT number" and pair:
                history_btn = tk.Button(f, text="🕒", font=(MONO, 8), bg=BG3, fg=FG,
                                       relief="flat", bd=0, width=2,
                                       command=lambda p=pair: self._show_history(p, var))
                history_btn.pack(side="left", padx=(2, 0))
            
            return e

        def number_entry_row(frame, label, var, width=16, pair=None):
            f = tk.Frame(frame, bg=BG)
            f.pack(fill="x", padx=8, pady=2)
            tk.Label(f, text=label, font=(MONO, 8), bg=BG,
                     fg=FG_DIM, width=14, anchor="w").pack(side="left")
            
            # Combobox for SIM numbers
            cmb = ttk.Combobox(f, textvariable=var, font=(MONO, 9),
                              state="readonly", width=width)
            cmb.pack(side="left", ipady=2)
            
            # Refresh button (read SIM numbers)
            refresh_btn = tk.Button(f, text="🔄", font=(MONO, 8), bg=BG3, fg=FG,
                                   relief="flat", bd=0, width=2,
                                   command=lambda p=pair: self._refresh_sim_numbers(p))
            refresh_btn.pack(side="left", padx=(2, 0))
            self._create_tooltip(refresh_btn, "Read SIM numbers from device")
            
            # History button
            history_btn = tk.Button(f, text="🕒", font=(MONO, 8), bg=BG3, fg=FG,
                                   relief="flat", bd=0, width=2,
                                   command=lambda p=pair: self._show_history(p, var))
            history_btn.pack(side="left", padx=(2, 0))
            self._create_tooltip(history_btn, "Phone number history")
            
            return cmb

        # ── DUT ──────────────────────────────────
        dut_hdr = tk.Frame(outer, bg=BG)
        dut_hdr.pack(fill="x", padx=6, pady=(6, 0))
        self.v_enable_dut = tk.BooleanVar(value=True)
        tk.Checkbutton(dut_hdr, text=" DUT",
                       variable=self.v_enable_dut,
                       command=lambda: self._toggle_pair_entries("dut"),
                       bg=BG, fg=BLUE, activebackground=BG, activeforeground=BLUE,
                       selectcolor=BG3, font=(SANS, 9, "bold")).pack(side="left")

        self._s1 = tk.Frame(outer, bg=BG)
        self._s1.pack(fill="x", padx=6, pady=(0, 4))
        self.v_emo  = tk.StringVar(value=cfg.DEVICES["dut_MO"])
        self.v_emt  = tk.StringVar(value=cfg.DEVICES["dut_MT"])
        self.v_enum = tk.StringVar(value=cfg.PHONE_NUMBERS["dut"])
        self._dut_entries = [
            entry_row(self._s1, "MO serial", self.v_emo),
            entry_row(self._s1, "MT serial", self.v_emt),
            number_entry_row(self._s1, "MT number", self.v_enum, pair="dut"),
        ]

        tk.Frame(outer, bg=BG3, height=1).pack(fill="x", padx=6)

        # ── REF ─────────────────────────────────
        ref_hdr = tk.Frame(outer, bg=BG)
        ref_hdr.pack(fill="x", padx=6, pady=(6, 0))
        self.v_enable_ref = tk.BooleanVar(value=True)
        tk.Checkbutton(ref_hdr, text=" REF",
                       variable=self.v_enable_ref,
                       command=lambda: self._toggle_pair_entries("ref"),
                       bg=BG, fg=YELLOW, activebackground=BG, activeforeground=YELLOW,
                       selectcolor=BG3, font=(SANS, 9, "bold")).pack(side="left")

        self._s2 = tk.Frame(outer, bg=BG)
        self._s2.pack(fill="x", padx=6, pady=(0, 4))
        self.v_rmo  = tk.StringVar(value=cfg.DEVICES["ref_MO"])
        self.v_rmt  = tk.StringVar(value=cfg.DEVICES["ref_MT"])
        self.v_rnum = tk.StringVar(value=cfg.PHONE_NUMBERS["ref"])
        self._ref_entries = [
            entry_row(self._s2, "MO serial", self.v_rmo),
            entry_row(self._s2, "MT serial", self.v_rmt),
            number_entry_row(self._s2, "MT number", self.v_rnum, pair="ref"),
        ]

        tk.Frame(outer, bg=BG3, height=1).pack(fill="x", padx=6)

        # ── timing ─────────────────────────────────────────
        s3 = tk.LabelFrame(outer, text=" Timing & Loops ", bg=BG,
                            fg=FG_DIM, font=(SANS, 8), bd=1, relief="groove")
        s3.pack(fill="x", padx=6, pady=4)
        self.v_loops = tk.StringVar(value=str(cfg.LOOP_COUNT))
        self.v_idle  = tk.StringVar(value=str(cfg.IDLE_SECONDS))
        self.v_call  = tk.StringVar(value=str(cfg.CALL_SECONDS))
        self.v_wait  = tk.StringVar(value=str(cfg.CALL_END_WAIT))
        entry_row(s3, "Loop count",   self.v_loops, width=6)
        entry_row(s3, "Idle (s)",     self.v_idle,  width=6)
        entry_row(s3, "Call (s)",     self.v_call,  width=6)
        entry_row(s3, "End wait (s)", self.v_wait,  width=6)

        # ── Test Case Name ───────────────────────────────────
        s6 = tk.LabelFrame(outer, text=" Test Case Name ", bg=BG,
                            fg=FG_DIM, font=(SANS, 8), bd=1, relief="groove")
        s6.pack(fill="x", padx=6, pady=(0, 4))
        self.v_test_case = tk.StringVar(value="TR-0000")
        entry_row(s6, "Test case", self.v_test_case, width=16)

        # ── Log path ──────────────────────────────────────────
        s5 = tk.LabelFrame(outer, text=" Log Output Path ", bg=BG,
                            fg=FG_DIM, font=(SANS, 8), bd=1, relief="groove")
        s5.pack(fill="x", padx=6, pady=(0, 4))
        self.v_log_path = tk.StringVar(value="")
        
        # Create a frame for the log path entry and browse button
        log_path_frame = tk.Frame(s5, bg=BG)
        log_path_frame.pack(fill="x", padx=8, pady=2)
        
        tk.Label(log_path_frame, text="Timestamp path", font=(MONO, 8), bg=BG,
                 fg=FG_DIM, width=14, anchor="w").pack(side="left")
        
        # Entry field for log path
        self.log_path_entry = tk.Entry(log_path_frame, textvariable=self.v_log_path, font=(MONO, 9),
                         bg=BG3, fg=FG, insertbackground=FG,
                         relief="flat", bd=0, width=16,
                         highlightthickness=1,
                         highlightcolor=BLUE, highlightbackground=BG3)
        self.log_path_entry.pack(side="left", ipady=3)
        
        # Browse button
        ttk.Button(log_path_frame, text="Browse...", command=self._browse_log_path).pack(side="left", padx=(4, 0))

        # ── display options ──────────────────────────────────────
        df = tk.Frame(outer, bg=BG)
        df.pack(fill="x", padx=8, pady=(2, 6))
        
        self.v_uppercase = tk.BooleanVar(value=cfg.UPPERCASE_TEXT)
        tk.Checkbutton(df, text="UPPERCASE TEXT",
                       variable=self.v_uppercase,
                       bg=BG, fg=FG, activebackground=BG,
                       activeforeground=FG, selectcolor=BG3,
                       font=(SANS, 9, "bold")).pack(side="left")
        
        self.v_sync = tk.BooleanVar(value=True)
        tk.Checkbutton(df, text="SYNCHRONIZED TESTING",
                       variable=self.v_sync,
                       bg=BG, fg=FG, activebackground=BG,
                       activeforeground=FG, selectcolor=BG3,
                       font=(SANS, 9, "bold")).pack(side="left", padx=(10, 0))

        # apply initial dim states
        self.after(50, lambda: [
            self._toggle_pair_entries("dut"),
            self._toggle_pair_entries("ref"),
        ])

    def _toggle_pair_entries(self, pair: str):
        """Dim entry widgets when pair is disabled."""
        enabled = (self.v_enable_dut if pair == "dut" else self.v_enable_ref).get()
        entries = self._dut_entries if pair == "dut" else self._ref_entries
        state = "normal" if enabled else "disabled"
        fg_color = FG if enabled else FG_DIM
        bg_color = BG3 if enabled else BG2
        for e in entries:
            if isinstance(e, ttk.Combobox):
                e.configure(state=state)
            else:
                e.configure(state=state, fg=fg_color, bg=bg_color,
                            highlightbackground=bg_color)

    def _create_tooltip(self, widget, text):
        """Create a tooltip for a widget."""
        def enter(event):
            tooltip = tk.Toplevel(widget)
            tooltip.overrideredirect(True)
            tooltip.configure(bg="#ffffe0")
            
            label = tk.Label(tooltip, text=text, font=(SANS, 9),
                            bg="#ffffe0", fg="black", padx=5, pady=3)
            label.pack()
            
            x = widget.winfo_rootx() + widget.winfo_width() + 5
            y = widget.winfo_rooty() - 25
            tooltip.geometry(f"+{x}+{y}")
            
            widget._tooltip = tooltip
        
        def leave(event):
            if hasattr(widget, '_tooltip'):
                widget._tooltip.destroy()
                del widget._tooltip
        
        widget.bind('<Enter>', enter)
        widget.bind('<Leave>', leave)

    # ── controls ──────────────────────────────────────────────
    def _build_controls(self, parent):
        f = tk.Frame(parent, bg=BG)
        f.pack(fill="x", pady=4)

        self.btn_pick = ttk.Button(f, text="🔌  Pick Devices",
                                   style="Pick.TButton",
                                   command=self._do_pick_devices)
        self.btn_pick.pack(fill="x", pady=(0, 6))

        self.btn_check = ttk.Button(f, text="🔍  Check Devices",
                                    command=self._do_check)
        self.btn_check.pack(fill="x", pady=2)

        self.btn_rat = ttk.Button(f, text="📶  Ustaw RAT",
                                   style="Pick.TButton",
                                   command=self._do_set_rat)
        self.btn_rat.pack(fill="x", pady=2)

        self.btn_sim = ttk.Button(f, text="📱  SIM Controls",
                                   style="Pick.TButton",
                                   command=self._do_sim_controls)
        self.btn_sim.pack(fill="x", pady=2)

        self.btn_start = ttk.Button(f, text="▶   Start Test",
                                    style="Start.TButton",
                                    command=self._do_start)
        self.btn_start.pack(fill="x", pady=2)

        self.btn_stop = ttk.Button(f, text="⏹   Stop",
                                   style="Stop.TButton",
                                   command=self._do_stop, state="disabled")
        self.btn_stop.pack(fill="x", pady=2)

        ttk.Button(f, text="🗑   Clear Log",
                   command=self._clear_log).pack(fill="x", pady=(8, 2))

    # ── pair status panels ────────────────────────────────────
    def _build_pair_panels(self, parent):
        row = tk.Frame(parent, bg=BG)
        row.pack(fill="x", pady=(0, 6))
        self._panels = {}
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

        # stage + live timer on one line
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

        # ── scrcpy buttons ────────────────────────────────────
        tk.Frame(inner, bg=BG3, height=1).pack(fill="x", pady=(6, 3))
        scr_frame = tk.Frame(inner, bg=BG2)
        scr_frame.pack(fill="x")
        tk.Label(scr_frame, text="📺  Mirror", font=(SANS, 8, "bold"),
                 bg=BG2, fg=FG_DIM).pack(side="left", padx=(0, 6))
        w["btn_scrcpy_mo"] = tk.Button(
            scr_frame, text="MO", font=(MONO, 8, "bold"),
            bg="#0e3a4a", fg=CYAN, relief="flat", bd=0,
            padx=8, pady=2,
            command=lambda p=pair: self._launch_scrcpy(p, "MO"))
        w["btn_scrcpy_mo"].pack(side="left", padx=(0, 4))
        w["btn_scrcpy_mt"] = tk.Button(
            scr_frame, text="MT", font=(MONO, 8, "bold"),
            bg="#0e3a4a", fg=CYAN, relief="flat", bd=0,
            padx=8, pady=2,
            command=lambda p=pair: self._launch_scrcpy(p, "MT"))
        w["btn_scrcpy_mt"].pack(side="left")

        # disabled overlay label
        w["disabled_lbl"] = tk.Label(inner, text="⏸  Not enabled",
                                      font=(SANS, 10), bg=BG2, fg=BG3)

        return w

    # ── log ──────────────────────────────────────────────────
    def _build_log(self, parent):
        lf = tk.LabelFrame(parent, text="  Live Log  ", bg=BG,
                           fg=FG_DIM, font=(SANS, 9), bd=1, relief="groove")
        lf.pack(fill="both", expand=True)
        self._log = scrolledtext.ScrolledText(
            lf, bg=BG, fg=FG, font=(MONO, 9),
            relief="flat", bd=0, state="disabled", wrap="word", height=11)
        self._log.pack(fill="both", expand=True, padx=4, pady=4)
        for tag, fg in [("ts", FG_DIM), ("ref", YELLOW),
                        ("PASS", GREEN), ("FAIL", RED), ("ACTIVE", CYAN),
                        ("dim", FG_DIM), ("info", FG)]:
            self._log.tag_configure(tag, foreground=fg)

    def _log_line(self, msg: str, tag: str = "info"):
        ts = datetime.now().strftime("%H:%M:%S")
        self._log.configure(state="normal")
        self._log.insert("end", f"[{ts}]  ", "ts")
        self._log.insert("end", msg + "\n", tag)
        self._log.see("end")
        self._log.configure(state="disabled")

    def _clear_log(self):
        self._log.configure(state="normal")
        self._log.delete("1.0", "end")
        self._log.configure(state="disabled")

    # ── helpers ──────────────────────────────────────────────
    def _refresh_mode_label(self):
        self._lbl_mode.configure(
            text="● LIVE",
            fg=GREEN,
        )

    def _get_config_file_path(self):
        """Get the path to the configuration file."""
        # Use the same directory as the application
        app_dir = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(app_dir, "chorus_config.json")

    def _load_persistent_config(self):
        """Load persistent configuration from file."""
        config_file = self._get_config_file_path()
        if os.path.exists(config_file):
            try:
                with open(config_file, "r") as f:
                    config = json.load(f)
                
                # Load device serials and phone numbers
                if "devices" in config:
                    cfg.DEVICES["dut_MO"] = config["devices"].get("dut_MO", cfg.DEVICES["dut_MO"])
                    cfg.DEVICES["dut_MT"] = config["devices"].get("dut_MT", cfg.DEVICES["dut_MT"])
                    cfg.DEVICES["ref_MO"] = config["devices"].get("ref_MO", cfg.DEVICES["ref_MO"])
                    cfg.DEVICES["ref_MT"] = config["devices"].get("ref_MT", cfg.DEVICES["ref_MT"])
                
                if "phone_numbers" in config:
                    cfg.PHONE_NUMBERS["dut"] = config["phone_numbers"].get("dut", cfg.PHONE_NUMBERS["dut"])
                    cfg.PHONE_NUMBERS["ref"] = config["phone_numbers"].get("ref", cfg.PHONE_NUMBERS["ref"])
                    
            except Exception as e:
                print(f"Error loading persistent config: {e}")
                pass  # Ignore errors and use defaults

    def _save_persistent_config(self):
        """Save current configuration to persistent file."""
        try:
            config_file = self._get_config_file_path()
            config = {
                "devices": {
                    "dut_MO": cfg.DEVICES["dut_MO"],
                    "dut_MT": cfg.DEVICES["dut_MT"],
                    "ref_MO": cfg.DEVICES["ref_MO"],
                    "ref_MT": cfg.DEVICES["ref_MT"]
                },
                "phone_numbers": {
                    "dut": cfg.PHONE_NUMBERS["dut"],
                    "ref": cfg.PHONE_NUMBERS["ref"]
                }
            }
            
            with open(config_file, "w") as f:
                json.dump(config, f, indent=2)
        except Exception as e:
            print(f"Error saving persistent config: {e}")
            pass  # Ignore errors

    def _on_close(self):
        """Handle application closing."""
        # Save current configuration before closing
        self._save_persistent_config()
        self.destroy()

    def _create_test_folder(self, test_case_name: str) -> str:
        """
        Create a unique test folder for the current test run.
        Returns the path to the created folder.
        """
        # Sanitize the test case name to make it filesystem-safe
        sanitized_name = re.sub(r'[<>:"/\\|?*]', '_', test_case_name)
        sanitized_name = sanitized_name.strip()
        
        # If the sanitized name is empty, use a default name
        if not sanitized_name:
            sanitized_name = "TR-0000"
        
        # Create a timestamp for uniqueness
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Create the folder name
        folder_name = f"{sanitized_name}_{timestamp}"
        
        # Create the full path
        test_folder_path = os.path.join(cfg.LOG_OUTPUT_PATH, folder_name)
        
        # Create the directory
        os.makedirs(test_folder_path, exist_ok=True)
        
        return test_folder_path

    def _create_timestamp_file(self, test_folder_path: str) -> str:
        """
        Create a timestamp TXT file in the test folder with the proper header format.
        Returns the path to the created file.
        """
        timestamp_file_path = os.path.join(test_folder_path, "timestamps.txt")
        with open(timestamp_file_path, "w", encoding="utf-8") as f:
            f.write("Chorus - Test Timestamps\n")
            f.write("=" * 40 + "\n")
            f.write(f"Test started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f.write("Cycle timestamps:\n")
            f.write("-" * 20 + "\n\n")
            # Write the header row with the requested format
            f.write(f"{'LP':<10} - {'TIME':<10} - {'DUT_MO':<8} - {'DUT_MT':<8} - {'REF_MO':<8} - {'REF_MT'} - {'RAT':<6} - {'RSRP':<6} - {'RSRQ':<6} - {'SINR':<6} - {'BAND'}\n")
        return timestamp_file_path

    def _append_cycle_to_timestamp_file(self, test_folder_path: str, cycle: int,
                                          signal_data: dict = None,
                                          results: dict = None) -> None:
        """
        Append cycle info to timestamps.txt.
        *results* should be {"dut": "PASS"/"FAIL"/"-", "ref": "PASS"/"FAIL"/"-"}
        passed in by the caller who already has both pair results — avoids race condition.
        """
        timestamp_file_path = os.path.join(test_folder_path, "timestamps.txt")
        current_time = datetime.now().strftime('%H:%M:%S')

        # Use passed results if available, fall back to _state (best-effort)
        if results:
            dut_r = results.get("dut", "–")
            ref_r = results.get("ref", "–")
        else:
            dut_r = _state["dut"]["last_result"] if _state["dut"]["cycle"] >= cycle else "–"
            ref_r = _state["ref"]["last_result"] if _state["ref"]["cycle"] >= cycle else "–"

        # Normalise: keep only PASS/FAIL, anything else → –
        def _norm(r):
            return r if r in ("PASS", "FAIL") else "–"
        dut_r = _norm(dut_r)
        ref_r = _norm(ref_r)

        # Get signal data for all devices
        sig_dut_mo = (signal_data or {}).get("dut_mo", {})
        sig_dut_mt = (signal_data or {}).get("dut_mt", {})
        sig_ref_mo = (signal_data or {}).get("ref_mo", {})
        sig_ref_mt = (signal_data or {}).get("ref_mt", {})
        
        # Get RAT for each device
        dut_mo_rat = str(sig_dut_mo.get("rat", "N/A"))
        dut_mt_rat = str(sig_dut_mt.get("rat", "N/A"))
        ref_mo_rat = str(sig_ref_mo.get("rat", "N/A"))
        ref_mt_rat = str(sig_ref_mt.get("rat", "N/A"))

        # Use DUT MO signal data as primary for overall signal info, but fallback to others if needed
        sig = sig_dut_mo
        if sig.get("rat") == "N/A":
            sig = sig_dut_mt if sig_dut_mt.get("rat") != "N/A" else sig_ref_mo
        if sig.get("rat") == "N/A":
            sig = sig_ref_mt
            
        rat  = str(sig.get("rat",  "N/A"))
        rsrp = str(sig.get("rsrp", "N/A"))
        rsrq = str(sig.get("rsrq", "N/A"))
        sinr = str(sig.get("sinr", "N/A"))
        band = str(sig.get("band", "N/A"))

        with open(timestamp_file_path, "a", encoding="utf-8") as f:
            f.write(
                f"{'Call_' + str(cycle):<10}   {current_time:<10}   "
                f"{dut_r:<8}   {sig_dut_mo.get('call_type', 'N/A') if sig_dut_mo else 'N/A':<8}   {ref_r:<8}   {sig_ref_mo.get('call_type', 'N/A') if sig_ref_mo else 'N/A':<8}   "
                f"{rat:<6}   {rsrp:<6}   {rsrq:<6}   {sinr:<6}   {band}\n"
            )

    def _save_device_info(self, test_folder_path: str, c: dict) -> str:
        """
        Save device information and test configuration to a file in the test folder.
        Returns the path to the created file.
        """
        device_info_path = os.path.join(test_folder_path, "device_info.txt")
        with open(device_info_path, "w", encoding="utf-8") as f:
            f.write("Chorus - Device Information\n")
            f.write("=" * 40 + "\n")
            f.write(f"Test started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            f.write("Device Configuration:\n")
            f.write("-" * 20 + "\n")
            if c["enable_dut"]:
                f.write(f"DUT MO: {c['dut_MO']}\n")
                f.write(f"DUT MT: {c['dut_MT']}\n")
                f.write(f"DUT MT Number: {c['dut_num']}\n\n")
            if c["enable_ref"]:
                f.write(f"REF MO: {c['ref_MO']}\n")
                f.write(f"REF MT: {c['ref_MT']}\n")
                f.write(f"REF MT Number: {c['ref_num']}\n\n")
            
            f.write("Test Parameters:\n")
            f.write("-" * 20 + "\n")
            f.write(f"Loop count: {c['loops']}\n")
            f.write(f"Idle time: {c['idle']}s\n")
            f.write(f"Call duration: {c['call']}s\n")
            f.write(f"End wait time: {c['wait']}s\n")
            f.write(f"Synchronized testing: {c['sync']}\n")
            f.write(f"Uppercase text: {c['uppercase']}\n")
            
        return device_info_path

    def _browse_log_path(self):
        """Open a directory selection dialog for choosing the log output path."""
        initial_dir = self.v_log_path.get() or "."
        selected_path = filedialog.askdirectory(
            parent=self,
            title="Select Log Output Directory",
            initialdir=initial_dir
        )
        if selected_path:
            self.v_log_path.set(selected_path)

    def _show_history(self, pair: str, var: tk.StringVar):
        """Show a dropdown menu with phone number history for the specified pair."""
        history = get_history(pair)
        if not history:
            return
            
        # Create a popup menu
        menu = tk.Menu(self, tearoff=0)
        for number in history:
            menu.add_command(label=number, command=lambda n=number: var.set(n))
            
        # Show the menu below the history button
        try:
            # Get the widget that called this function (the history button)
            widget = self.focus_get()
            if widget:
                # Show menu below the widget
                menu.post(widget.winfo_rootx(), widget.winfo_rooty() + widget.winfo_height())
        except tk.TclError:
            # Fallback if we can't get the widget
            menu.post(self.winfo_pointerx(), self.winfo_pointery())

    def _refresh_sim_numbers(self, pair: str):
        """Read SIM phone numbers from device and populate combobox."""
        from core.adb_controller import get_sim_phone_numbers
        
        # Get MT serial for this pair
        if pair == "dut":
            serial = self.v_emt.get()
            var = self.v_enum
            cmb = self._dut_entries[2]
        else:
            serial = self.v_rmt.get()
            var = self.v_rnum
            cmb = self._ref_entries[2]
        
        if not serial or serial in ("YOUR_SERIAL_HERE", ""):
            messagebox.showwarning("No device",
                "Assign a device first (click 'Pick Devices').")
            return
        
        # Read SIM numbers
        sim_data = get_sim_phone_numbers(serial)
        
        # Build options
        options = []
        if sim_data["sim1"]:
            sim1 = sim_data["sim1"]
            opt = f"{sim_data['model']} SIM1: {sim1['number']}"
            if sim1.get("operator"):
                opt += f" ({sim1['operator']})"
            options.append(opt)
        
        if sim_data["sim2"]:
            sim2 = sim_data["sim2"]
            opt = f"{sim_data['model']} SIM2: {sim2['number']}"
            if sim2.get("operator"):
                opt += f" ({sim2['operator']})"
            options.append(opt)
        
        if not options:
            messagebox.showinfo("No numbers",
                f"Could not read SIM numbers from {serial}.\n"
                f"Try: *#0## for Samsung diagnostic menu")
            return
        
        # Update combobox
        cmb["values"] = options
        if options:
            # Auto-select first number
            first = options[0]
            if ": " in first:
                var.set(first.split(": ")[1])

    def _read_config(self):
        """Read configuration from GUI fields and validate."""
        try:
            c = {
                # Device serials
                "dut_MO": self.v_emo.get().strip(),
                "dut_MT": self.v_emt.get().strip(),
                "ref_MO": self.v_rmo.get().strip(),
                "ref_MT": self.v_rmt.get().strip(),
                
                # Phone numbers
                "dut_num": self.v_enum.get().strip(),
                "ref_num": self.v_rnum.get().strip(),
                
                # Enable flags
                "enable_dut": self.v_enable_dut.get(),
                "enable_ref": self.v_enable_ref.get(),
                
                # Timing parameters (with type conversion)
                "loops": int(self.v_loops.get()),
                "idle": int(self.v_idle.get()),
                "call": int(self.v_call.get()),
                "wait": int(self.v_wait.get()),
                
                # Test case name
                "test_case": self.v_test_case.get().strip(),
                
                # Log path
                "log_path": self.v_log_path.get().strip() or ".",
                
                # Display options
                "sync": self.v_sync.get(),
                "uppercase": self.v_uppercase.get(),
            }
            
            # Validation: at least one pair must be enabled
            if not c["enable_dut"] and not c["enable_ref"]:
                messagebox.showwarning("Configuration Error",
                    "Enable at least one pair (DUT or REF) before starting.")
                return None
                
            # Validation: enabled pairs must have serials
            if c["enable_dut"]:
                if not c["dut_MO"] or not c["dut_MT"]:
                    messagebox.showwarning("Configuration Error",
                        "DUT pair requires both MO and MT serial numbers.")
                    return None
                    
            if c["enable_ref"]:
                if not c["ref_MO"] or not c["ref_MT"]:
                    messagebox.showwarning("Configuration Error",
                        "REF pair requires both MO and MT serial numbers.")
                    return None
            
            # Validation: positive integers for timing
            for key in ("loops", "idle", "call", "wait"):
                if c[key] <= 0:
                    messagebox.showwarning("Configuration Error",
                        f"{key.capitalize()} must be a positive integer.")
                    return None
                    
            return c
            
        except ValueError as e:
            messagebox.showerror("Configuration Error",
                "Invalid configuration value. Please check that all numeric fields contain valid numbers.")
            return None
        except Exception as e:
            messagebox.showerror("Configuration Error",
                f"Error reading configuration: {str(e)}")
            return None

    # ── scrcpy launcher ──────────────────────────────────────
    def _launch_scrcpy(self, pair: str, role: str) -> None:
        """Launch scrcpy for MO or MT device of given pair."""
        # Read serial directly from GUI fields — not from cfg.DEVICES
        # which may still hold placeholder values
        var_map = {
            "dut_MO": self.v_emo,
            "dut_MT": self.v_emt,
            "ref_MO": self.v_rmo,
            "ref_MT": self.v_rmt,
        }
        key = f"{pair}_{role}"
        var = var_map.get(key)
        serial = var.get().strip() if var else ""

        if not serial or serial in ("YOUR_SERIAL_HERE", ""):
            messagebox.showwarning("scrcpy", f"No serial configured for {key}.")
            return

        exe = getattr(self, "_scrcpy_path", None) or find_scrcpy()
        if not exe:
            from tkinter import filedialog
            exe = filedialog.askopenfilename(
                parent=self,
                title="Locate scrcpy executable",
                filetypes=[("scrcpy", "scrcpy.exe"), ("All files", "*.*")],
            )
            if not exe:
                return
            self._scrcpy_path = exe

        title = f"Chorus — {pair.upper()} {role}  [{serial}]"
        from core.adb_controller import launch_scrcpy as _launch
        ok = _launch(serial, title=title, scrcpy_path=exe)
        if ok:
            self._log_line(f"📺  scrcpy launched: {pair.upper()} {role} [{serial}]", "info")
        else:
            messagebox.showerror("scrcpy failed",
                f"Could not launch scrcpy for {serial}.\n\n"
                "Make sure scrcpy is installed:\n"
                "  https://github.com/Genymobile/scrcpy")

    def _apply_config(self, c: dict):
        cfg.DEVICES["dut_MO"]    = c["dut_MO"]
        cfg.DEVICES["dut_MT"]    = c["dut_MT"]
        cfg.DEVICES["ref_MO"]       = c["ref_MO"]
        cfg.DEVICES["ref_MT"]       = c["ref_MT"]
        cfg.PHONE_NUMBERS["dut"] = c["dut_num"]
        cfg.PHONE_NUMBERS["ref"]    = c["ref_num"]
        cfg.LOOP_COUNT              = c["loops"]
        cfg.IDLE_SECONDS            = c["idle"]
        cfg.CALL_SECONDS            = c["call"]
        cfg.CALL_END_WAIT           = c["wait"]
        cfg.LOG_OUTPUT_PATH         = c["log_path"]
        cfg.CSV_OUTPUT_PATH         = os.path.join(c["log_path"], "results.csv")
        cfg.UPPERCASE_TEXT          = c["uppercase"]

    def _set_panel_enabled(self, pair: str, enabled: bool):
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

    def _update_panel(self, pair: str):
        s = _state[pair]
        w = self._panels[pair]
        color = BLUE if pair == "dut" else YELLOW
        loops = self._loops

        w["mo"].configure(text=cfg.DEVICES[f"{pair}_MO"])
        w["mt"].configure(text=cfg.DEVICES[f"{pair}_MT"])

        cycle = s["cycle"]
        pct = int(cycle / loops * 100) if loops else 0
        w["cycle_lbl"].configure(text=f"Cycle  {cycle}/{loops}  ({pct}%)", fg=color)
        w["progress"]["value"] = pct

        stage = s["stage"]
        detail = s["detail"]   # contains "Xs" countdown

        sc = STAGE_COLOR.get(stage, FG)
        w["stage"].configure(text=stage, fg=sc)

        # show countdown in big timer label if detail is "Xs"
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

    # ── device picker ────────────────────────────────────────
    def _do_pick_devices(self):
        prefill = {
            "dut_MO": self.v_emo.get(),
            "dut_MT": self.v_emt.get(),
            "ref_MO":    self.v_rmo.get(),
            "ref_MT":    self.v_rmt.get(),
        }
        dialog = DevicePickerDialog(self, prefill=prefill)
        self.wait_window(dialog)
        if dialog.result is None:
            return
        r = dialog.result
        self.v_emo.set(r["dut_MO"])
        self.v_emt.set(r["dut_MT"])
        self.v_rmo.set(r["ref_MO"])
        self.v_rmt.set(r["ref_MT"])
        self._log_line("Device assignment from picker:", "info")
        self._log_line(f"  dut_MO → {r['dut_MO']}", "dut")
        self._log_line(f"  dut_MT → {r['dut_MT']}", "dut")
        self._log_line(f"  ref_MO    → {r['ref_MO']}",    "ref")
        self._log_line(f"  ref_MT    → {r['ref_MT']}",    "ref")
        
        # Save configuration after device selection
        self._save_persistent_config()

    # ── device check ─────────────────────────────────────────
    def _do_check(self):
        c = self._read_config()
        if not c:
            return
        self._apply_config(c)
        self._log_line("Checking devices…", "dim")
        serials = [c["dut_MO"], c["dut_MT"], c["ref_MO"], c["ref_MT"]]
        labels  = {
            c["dut_MO"]: "dut_MO  (DUT)",
            c["dut_MT"]: "dut_MT  (DUT)",
            c["ref_MO"]:    "ref_MO     (REF)",
            c["ref_MT"]:    "ref_MT     (REF)",
        }
        def task():
            results = check_devices(serials)
            def show():
                all_ok = True
                for serial, ok in results.items():
                    self._log_line(
                        f"{'✅' if ok else '❌'}  {labels.get(serial, serial)}  [{serial}]",
                        "PASS" if ok else "FAIL")
                    if not ok:
                        all_ok = False
                self._log_line(
                    "All devices reachable ✔" if all_ok
                    else "One or more devices offline – check USB / adb devices",
                    "PASS" if all_ok else "FAIL")
            self.after(0, show)
        threading.Thread(target=task, daemon=True).start()

    # ── RAT settings ─────────────────────────────────────────
    def _do_set_rat(self):
        # Pobierz aktualne konfiguracje urządzeń
        c = self._read_config()
        if not c:
            return
            
        # Przygotuj słownik urządzeń
        devices = {
            "dut_MO": c["dut_MO"],
            "dut_MT": c["dut_MT"],
            "ref_MO": c["ref_MO"],
            "ref_MT": c["ref_MT"]
        }
        
        # Otwórz dialog ustawień RAT
        dialog = RatSettingsDialog(self, devices)
        self.wait_window(dialog)

    # ── SIM controls ─────────────────────────────────────────
    def _do_sim_controls(self):
        dialog = DeviceControlsDialog(self)
        self.wait_window(dialog)

    # ── start / stop ──────────────────────────────────────────
    def _do_start(self):
        global _threads
        c = self._read_config()
        if not c:
            return

        if not c["enable_dut"] and not c["enable_ref"]:
            messagebox.showwarning("No pairs enabled",
                "Enable at least one pair (DUT or REF) before starting.")
            return

        self._apply_config(c)
        self._loops = c["loops"]
        _stop_event.clear()

        # Reset the logged cycles set for the new test run
        global _logged_cycles
        _logged_cycles.clear()

        # Reset chart data for the new test run
        self.chart_data = {"dut": {"pass": 0, "fail": 0}, "ref": {"pass": 0, "fail": 0}}
        self._draw_chart()

        # Save phone numbers to history
        if c["dut_num"]:
            add_to_history("dut", c["dut_num"])
        if c["ref_num"]:
            add_to_history("ref", c["ref_num"])

        # Create a unique test folder for this test run
        test_folder_path = self._create_test_folder(c["test_case"])
        
        # Create timestamp file
        timestamp_file_path = self._create_timestamp_file(test_folder_path)
        
        # Save device information
        device_info_path = self._save_device_info(test_folder_path, c)
        
        # Update the CSV output path to use the test folder
        test_csv_path = os.path.join(test_folder_path, "results.csv")
        cfg.CSV_OUTPUT_PATH = test_csv_path
        
        # Save configuration when starting test
        self._save_persistent_config()

        for pair in ("dut", "ref"):
            _state[pair] = {"cycle": 0, "stage": "–", "detail": "",
                            "pass": 0, "fail": 0, "done": False, "last_result": "–"}
            enabled = c[f"enable_{pair}"]
            _state[pair]["enabled"] = enabled
            self._set_panel_enabled(pair, enabled)
            if enabled:
                self._update_panel(pair)

        init_csv()
        self._log_line("─" * 54, "dim")
        enabled_str = " + ".join(
            p.upper() for p in ("dut", "ref") if c[f"enable_{p}"])
        sync_str = " [SYNCHRONIZED]" if c["sync"] else ""
        self._log_line(
            f"▶  START  [LIVE]{sync_str}  pairs={enabled_str}  "
            f"loops={c['loops']}  idle={c['idle']}s  call={c['call']}s", "info")
        self._log_line(f"📂 Test folder: {test_folder_path}", "info")
        self._log_line("─" * 54, "dim")

        _threads = []
        # Reset synchronization barrier for each new test run
        global _sync_barrier
        _sync_barrier = None
        
        # Select worker function based on sync mode
        worker_func = _sync_worker if c["sync"] else _worker
        
        # Get retry configuration from UI (with defaults)
        max_retries = 3
        retry_delay = 1
        
        # Store signal data for each cycle
        self._cycle_signal_data = {}
        
        for pair, mo_key, mt_key, num_key in [
            ("dut", "dut_MO", "dut_MT", "dut_num"),
            ("ref", "ref_MO", "ref_MT", "ref_num"),
        ]:
            if not c[f"enable_{pair}"]:
                _ui_queue.put(("skip", pair))
                continue
            t = threading.Thread(
                target=worker_func,
                args=(pair, c[mo_key], c[mt_key], c[num_key], c["loops"], max_retries, retry_delay),
                daemon=True, name=pair,
            )
            _threads.append(t)
            t.start()

        self.btn_start.configure(state="disabled")
        self.btn_check.configure(state="disabled")
        self.btn_pick.configure(state="disabled")
        self.btn_stop.configure(state="normal")

    def _do_stop(self):
        _stop_event.set()
        self._log_line("⏹  Stop requested – finishing current cycle…", "FAIL")
        self.btn_stop.configure(state="disabled")

    def _check_notifications(self, pair, stage):
        """Play system beep on PASS/FAIL and warn on high fail rate."""
        if stage == "PASS":
            _beep("ok")
        elif stage == "FAIL":
            _beep("error")
        s = _state[pair]
        total = s["pass"] + s["fail"]
        if total > 0 and s["fail"] / total > 0.5:
            _beep("warn")

    # ── event loop ────────────────────────────────────────────
    def _poll_queue(self):
        try:
            while True:
                msg = _ui_queue.get_nowait()
                self._handle_msg(msg)
        except queue.Empty:
            pass
        self.after(80, self._poll_queue)

    def _handle_msg(self, msg):
        kind = msg[0]
        if kind == "status":
            _, pair, cycle, stage, detail = msg
            s = _state[pair]
            s["cycle"] = cycle
            s["stage"] = stage
            s["detail"] = detail
            if stage == "PASS":
                s["pass"] += 1
                s["last_result"] = "PASS"
            elif stage == "FAIL":
                s["fail"] += 1
                s["last_result"] = f"FAIL  {detail}"
            self._update_panel(pair)

            # Update chart data and redraw chart
            if stage == "PASS":
                self.chart_data[pair]["pass"] += 1
                self._draw_chart()
            elif stage == "FAIL":
                self.chart_data[pair]["fail"] += 1
                self._draw_chart()

            # Check for notifications
            self._check_notifications(pair, stage)

            # log only non-tick events (avoid spamming with "14s", "13s"...)
            if not (detail.endswith("s") and detail[:-1].isdigit()):
                if stage in {"CALLING", "ACTIVE", "PASS", "FAIL",
                             "ANSWERING", "RINGING", "CHECKING", "HANGING UP"}:
                    tag = stage if stage in ("PASS", "FAIL", "ACTIVE") else pair
                    self._log_line(
                        f"{pair.upper():<7} Call_{cycle}  {stage:<12} {detail}", tag)
                    
                    # Append cycle data to timestamp file when cycle completes
                    if stage in {"PASS", "FAIL"}:
                        if cycle not in _logged_cycles:
                            enabled_pairs = [p for p in ("dut", "ref") if _state[p].get("enabled", False)]
                            if all(_state[p]["cycle"] >= cycle for p in enabled_pairs):
                                test_folder_path = os.path.dirname(cfg.CSV_OUTPUT_PATH)
                                signal_data = getattr(self, '_cycle_signal_data', {}).get(cycle, None)
                                # Build results dict from current _state — both pairs done at this point
                                results = {
                                    p: (_state[p]["last_result"] if _state[p].get("enabled") else "–")
                                    for p in ("dut", "ref")
                                }
                                self._append_cycle_to_timestamp_file(
                                    test_folder_path, cycle, signal_data, results)
                                _logged_cycles.add(cycle)

        elif kind == "done":
            _, pair = msg
            _state[pair].update({"done": True, "stage": "COMPLETE", "detail": ""})
            self._update_panel(pair)
            self._log_line(f"{pair.upper()} — all cycles complete ✔", "PASS")
            self._check_all_done()

        elif kind == "skip":
            _, pair = msg
            _state[pair]["done"] = True
            self._check_all_done()

    def _check_all_done(self):
        enabled = [p for p in ("dut", "ref") if _state[p].get("enabled", False)]
        if not enabled:
            return
        if all(_state[p]["done"] for p in enabled):
            self._on_all_done()

    def _on_all_done(self):
        self.btn_start.configure(state="normal")
        self.btn_check.configure(state="normal")
        self.btn_pick.configure(state="normal")
        self.btn_stop.configure(state="disabled")
        
        # Play completion sound
        _beep("ok")
        
        # Generate detailed summary
        try:
            from core.report import generate_detailed_summary
            detailed_summary = generate_detailed_summary()
            
            # Show summary dialog
            SummaryDialog(self, detailed_summary)
            
            self._log_line("─" * 54, "dim")
            self._log_line(f"✔  All cycles complete!  Results → {cfg.CSV_OUTPUT_PATH}", "PASS")
            self._log_line(f"📊 Detailed summary generated", "info")
            
            # GPS map notification
            if cfg.GPS_ENABLED:
                try:
                    from utils.map_generator import generate_all
                    import os as _os
                    test_name = _os.path.basename(cfg.CSV_OUTPUT_PATH).replace(".csv", "")
                    html_path, png_path = generate_all(cfg.CSV_OUTPUT_PATH, cfg.LOG_OUTPUT_PATH, test_name)
                    maps_info = []
                    if html_path:
                        maps_info.append(f"HTML → {html_path}")
                    if png_path:
                        maps_info.append(f"PNG  → {png_path}")
                    if maps_info:
                        self._log_line(f"🗺  GPS maps saved:", "info")
                        for m in maps_info:
                            self._log_line(f"     {m}", "info")
                except Exception as _e:
                    self._log_line(f"⚠  GPS map generation failed: {str(_e)}", "WARN")
            
            self._log_line("─" * 54, "dim")
        except Exception as e:
            self._log_line("─" * 54, "dim")
            self._log_line(f"✔  All cycles complete!  Results → {cfg.CSV_OUTPUT_PATH}", "PASS")
            self._log_line(f"⚠  Failed to generate detailed summary: {str(e)}", "FAIL")
            self._log_line("─" * 54, "dim")
            messagebox.showinfo("Done",
                f"All cycles complete!\n\n"
                f"Results saved to:\n{cfg.CSV_OUTPUT_PATH}\n\n"
                f"Note: Failed to generate detailed summary.\nError: {str(e)}")


class SummaryDialog(tk.Toplevel):
    def __init__(self, parent, summary_data):
        super().__init__(parent)
        self.title("Test Summary")
        self.configure(bg=BG)
        self.geometry("800x600")
        self.resizable(True, True)
        self.minsize(600, 400)
        
        # Store summary data
        self.summary_data = summary_data
        
        # Create UI
        self._build_ui()
        
        # Center the dialog
        self.transient(parent)
        self.grab_set()
        
    def _build_ui(self):
        # Header
        header = tk.Frame(self, bg=BG2, height=40)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="Test Summary", font=(SANS, 12, "bold"), bg=BG2, fg=FG).pack(pady=10)
        
        # Main content area with notebook for tabs
        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Overview tab
        self._build_overview_tab(notebook)
        
        # Statistics by pair tab
        self._build_pair_stats_tab(notebook)
        
        # Error distribution tab
        self._build_error_tab(notebook)
        
        # Signal data tab
        self._build_signal_tab(notebook)
        
        # Timeline tab
        self._build_timeline_tab(notebook)
        
        # Close button
        close_btn = ttk.Button(self, text="Close", command=self.destroy)
        close_btn.pack(pady=10)
        
    def _build_overview_tab(self, notebook):
        frame = tk.Frame(notebook, bg=BG)
        notebook.add(frame, text="Overview")
        
        # Overall statistics
        stats_frame = tk.LabelFrame(frame, text="Overall Statistics", bg=BG, fg=FG_DIM, font=(SANS, 10, "bold"))
        stats_frame.pack(fill="x", padx=10, pady=10)
        
        overall = self.summary_data["overall_stats"]
        
        # Grid for statistics
        stats_grid = tk.Frame(stats_frame, bg=BG)
        stats_grid.pack(fill="x", padx=10, pady=10)
        
        # Define statistics to display
        stats = [
            ("Total Cycles", overall["total_cycles"]),
            ("Passed Cycles", overall["passed_cycles"]),
            ("Failed Cycles", overall["failed_cycles"]),
            ("Success Rate", f"{overall['success_rate']:.2f}%"),
            ("Test Duration", self.summary_data["test_duration"]),
            ("First Timestamp", self.summary_data["first_timestamp"] or "N/A"),
            ("Last Timestamp", self.summary_data["last_timestamp"] or "N/A")
        ]
        
        # Create grid of statistics
        for i, (label, value) in enumerate(stats):
            row = i // 2
            col = (i % 2) * 2
            
            tk.Label(stats_grid, text=label, font=(MONO, 9), bg=BG, fg=FG_DIM, anchor="w", width=20).grid(row=row, column=col, sticky="w", padx=5, pady=2)
            tk.Label(stats_grid, text=str(value), font=(MONO, 9, "bold"), bg=BG, fg=FG, anchor="w", width=20).grid(row=row, column=col+1, sticky="w", padx=5, pady=2)
        
        # File paths
        files_frame = tk.LabelFrame(frame, text="Files", bg=BG, fg=FG_DIM, font=(SANS, 10, "bold"))
        files_frame.pack(fill="x", padx=10, pady=10)
        
        tk.Label(files_frame, text="Detailed CSV:", font=(MONO, 9), bg=BG, fg=FG_DIM, anchor="w").pack(fill="x", padx=10, pady=2)
        tk.Label(files_frame, text=self.summary_data["csv_path"], font=(MONO, 9), bg=BG, fg=BLUE, anchor="w").pack(fill="x", padx=10, pady=2)
        
        tk.Label(files_frame, text="Summary CSV:", font=(MONO, 9), bg=BG, fg=FG_DIM, anchor="w").pack(fill="x", padx=10, pady=2)
        tk.Label(files_frame, text=self.summary_data["summary_csv_path"], font=(MONO, 9), bg=BG, fg=BLUE, anchor="w").pack(fill="x", padx=10, pady=2)
        
    def _build_pair_stats_tab(self, notebook):
        frame = tk.Frame(notebook, bg=BG)
        notebook.add(frame, text="Statistics by Pair")
        
        # Create a canvas and scrollbar for the frame
        canvas = tk.Canvas(frame, bg=BG)
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg=BG)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(
                scrollregion=canvas.bbox("all")
            )
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Add statistics for each pair
        for pair, stats in self.summary_data["stats_by_pair"].items():
            pair_frame = tk.LabelFrame(scrollable_frame, text=f"{pair.upper()} Statistics", bg=BG, fg=FG_DIM, font=(SANS, 10, "bold"))
            pair_frame.pack(fill="x", padx=10, pady=10)
            
            # Grid for statistics
            stats_grid = tk.Frame(pair_frame, bg=BG)
            stats_grid.pack(fill="x", padx=10, pady=10)
            
            # Define statistics to display
            pair_stats = [
                ("Total Cycles", stats["total"]),
                ("Passed Cycles", stats["passed"]),
                ("Failed Cycles", stats["failed"]),
                ("Success Rate", f"{stats['success_rate']:.2f}%"),
                ("Average Duration (ms)", f"{stats['average_duration']:.2f}")
            ]
            
            # Create grid of statistics
            for i, (label, value) in enumerate(pair_stats):
                row = i // 2
                col = (i % 2) * 2
                
                tk.Label(stats_grid, text=label, font=(MONO, 9), bg=BG, fg=FG_DIM, anchor="w", width=20).grid(row=row, column=col, sticky="w", padx=5, pady=2)
                tk.Label(stats_grid, text=str(value), font=(MONO, 9, "bold"), bg=BG, fg=FG, anchor="w", width=20).grid(row=row, column=col+1, sticky="w", padx=5, pady=2)
                
        # Pack canvas and scrollbar
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
    def _build_error_tab(self, notebook):
        frame = tk.Frame(notebook, bg=BG)
        notebook.add(frame, text="Error Distribution")
        
        # Create a canvas and scrollbar for the frame
        canvas = tk.Canvas(frame, bg=BG)
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg=BG)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(
                scrollregion=canvas.bbox("all")
            )
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Add error distribution for each pair
        for pair, stats in self.summary_data["stats_by_pair"].items():
            if stats["errors"]:
                error_frame = tk.LabelFrame(scrollable_frame, text=f"{pair.upper()} Error Distribution", bg=BG, fg=FG_DIM, font=(SANS, 10, "bold"))
                error_frame.pack(fill="x", padx=10, pady=10)
                
                # Grid for errors
                error_grid = tk.Frame(error_frame, bg=BG)
                error_grid.pack(fill="x", padx=10, pady=10)
                
                # Create grid of errors
                for i, (error_type, count) in enumerate(stats["error_distribution"].items()):
                    row = i
                    tk.Label(error_grid, text=error_type, font=(MONO, 9), bg=BG, fg=FG_DIM, anchor="w", width=20).grid(row=row, column=0, sticky="w", padx=5, pady=2)
                    tk.Label(error_grid, text=str(count), font=(MONO, 9, "bold"), bg=BG, fg=FG, anchor="w", width=20).grid(row=row, column=1, sticky="w", padx=5, pady=2)
            else:
                # No errors for this pair
                no_error_frame = tk.Frame(scrollable_frame, bg=BG)
                no_error_frame.pack(fill="x", padx=10, pady=10)
                tk.Label(no_error_frame, text=f"{pair.upper()}: No errors", font=(MONO, 9), bg=BG, fg=GREEN, anchor="w").pack(fill="x", padx=10, pady=2)
                
        # Pack canvas and scrollbar
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
    def _build_signal_tab(self, notebook):
        frame = tk.Frame(notebook, bg=BG)
        notebook.add(frame, text="Signal Data")
        
        # Create a canvas and scrollbar for the frame
        canvas = tk.Canvas(frame, bg=BG)
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg=BG)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(
                scrollregion=canvas.bbox("all")
            )
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Add signal data for each pair
        for pair, stats in self.summary_data["stats_by_pair"].items():
            if "signal_data" in stats:
                signal_frame = tk.LabelFrame(scrollable_frame, text=f"{pair.upper()} Signal Data", bg=BG, fg=FG_DIM, font=(SANS, 10, "bold"))
                signal_frame.pack(fill="x", padx=10, pady=10)
                
                signal_data = stats["signal_data"]
                
                # Grid for signal statistics
                signal_grid = tk.Frame(signal_frame, bg=BG)
                signal_grid.pack(fill="x", padx=10, pady=10)
                
                # Define signal statistics to display
                signal_stats = []
                
                # Add average values if available
                if "avg_rsrp" in signal_data:
                    signal_stats.append(("Average RSRP", f"{signal_data['avg_rsrp']:.2f} dBm"))
                if "avg_rsrq" in signal_data:
                    signal_stats.append(("Average RSRQ", f"{signal_data['avg_rsrq']:.2f} dB"))
                if "avg_sinr" in signal_data:
                    signal_stats.append(("Average SINR", f"{signal_data['avg_sinr']:.2f} dB"))
                
                # Add RAT distribution
                if signal_data["rat_distribution"]:
                    signal_stats.append(("RAT Distribution", ""))
                    for rat, count in signal_data["rat_distribution"].items():
                        signal_stats.append((f"  {rat}", str(count)))
                
                # Add Band distribution
                if signal_data["band_distribution"]:
                    signal_stats.append(("Band Distribution", ""))
                    for band, count in signal_data["band_distribution"].items():
                        signal_stats.append((f"  Band {band}", str(count)))
                
                # Create grid of signal statistics
                for i, (label, value) in enumerate(signal_stats):
                    row = i
                    tk.Label(signal_grid, text=label, font=(MONO, 9), bg=BG, fg=FG_DIM, anchor="w", width=20).grid(row=row, column=0, sticky="w", padx=5, pady=2)
                    tk.Label(signal_grid, text=value, font=(MONO, 9, "bold"), bg=BG, fg=FG, anchor="w", width=20).grid(row=row, column=1, sticky="w", padx=5, pady=2)
            else:
                # No signal data for this pair
                no_signal_frame = tk.Frame(scrollable_frame, bg=BG)
                no_signal_frame.pack(fill="x", padx=10, pady=10)
                tk.Label(no_signal_frame, text=f"{pair.upper()}: No signal data", font=(MONO, 9), bg=BG, fg=FG_DIM, anchor="w").pack(fill="x", padx=10, pady=2)
                
        # Pack canvas and scrollbar
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

    def _build_timeline_tab(self, notebook):
        frame = tk.Frame(notebook, bg=BG)
        notebook.add(frame, text="Timeline")
        
        if not _MATPLOTLIB_OK:
            tk.Label(frame, text="matplotlib not installed — timeline unavailable.\nInstall with: pip install matplotlib",
                     font=(MONO, 9), bg=BG, fg=RED, wraplength=500).pack(expand=True)
            return
        
        try:
            # Create matplotlib figure for timeline
            fig, ax = plt.subplots(figsize=(8, 4), facecolor=BG2)
            fig.patch.set_facecolor(BG2)
            ax.set_facecolor(BG2)
            
            # Plot success rate by cycle
            cycles = [item["cycle"] for item in self.summary_data["call_success_rate_by_cycle"]]
            success_rates = [item["success_rate"] for item in self.summary_data["call_success_rate_by_cycle"]]
            
            ax.plot(cycles, success_rates, marker='o', linestyle='-', color=BLUE, markersize=4)
            ax.set_xlabel("Cycle", color=FG)
            ax.set_ylabel("Success Rate (%)", color=FG)
            ax.set_title("Success Rate by Cycle", color=FG)
            ax.grid(True, color=BG3)
            
            # Set tick colors
            ax.tick_params(colors=FG)
            for spine in ax.spines.values():
                spine.set_color(BG3)
            
            # Embed the plot in the tkinter window
            canvas = FigureCanvasTkAgg(fig, frame)
            canvas.draw()
            canvas.get_tk_widget().pack(fill="both", expand=True, padx=10, pady=10)
            
            # Add a note about the plot
            tk.Label(frame, text="Success rate per cycle over time", font=(MONO, 9), bg=BG, fg=FG_DIM).pack(pady=5)
        except Exception:
            tk.Label(frame, text="Failed to render timeline chart.",
                     font=(MONO, 9), bg=BG, fg=RED).pack(expand=True)

    def _on_close(self):
        if any(t.is_alive() for t in _threads):
            if not messagebox.askyesno("Quit", "Test is still running. Stop and quit?"):
                return
            _stop_event.set()
        self._save_persistent_config()
        self.destroy()


if __name__ == "__main__":
    app = ChorusApp()
    app.mainloop()
