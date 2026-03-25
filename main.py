# ============================================================
#  Chorus v1.0  –  chorus.py  (tkinter GUI)
#  Dark-mode desktop dashboard.
#  Run: python chorus.py
# ============================================================

import threading
import queue
from datetime import datetime
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog
import os
import re

import config as cfg
from adb_controller import check_devices
from call_monitor import run_cycle
from report import init_csv, generate_summary_report
from device_picker import DevicePickerDialog

# ── theme ────────────────────────────────────────────────────
BG     = "#0f1117"
BG2    = "#2a2d3a"  # Lighter background for better contrast
BG3    = "#3a3e50"  # Even lighter for better contrast
FG     = "#ffffff"  # Bright white text
FG_DIM = "#b0b5c5"  # Lighter dimmed text
BLUE   = "#6daaff"  # Brighter blue
YELLOW = "#8a440b"  # Darker amber/brown color
GREEN  = "#5aff9d"  # Brighter green
RED    = "#ff8585"  # Brighter red
CYAN   = "#33e3ff"  # Brighter cyan
MONO   = "Consolas"
SANS   = "Segoe UI"

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
               "pass": 0, "fail": 0, "done": False, "last_result": "–", "enabled": False},
    "ref":    {"cycle": 0, "stage": "–", "detail": "",
               "pass": 0, "fail": 0, "done": False, "last_result": "–", "enabled": True},
}


def _status_cb(pair: str, cycle: int, stage: str, detail: str) -> None:
    _ui_queue.put(("status", pair, cycle, stage, detail))


def _sync_worker(pair: str, mo: str, mt: str, number: str, loops: int) -> None:
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
        run_cycle(pair=pair, dut_mo=mo, dut_mt=mt, phone_number=number,
                  cycle=cycle, status_callback=_status_cb, stop_event=_stop_event)
                  
        # Wait for all pairs to finish the cycle before starting the next one
        try:
            _sync_barrier.wait()
        except threading.BrokenBarrierError:
            break
            
    _ui_queue.put(("done", pair))


def _worker(pair: str, mo: str, mt: str, number: str, loops: int) -> None:
    """Worker function for normal (non-synchronized) testing mode."""
    for cycle in range(1, loops + 1):
        if _stop_event.is_set():
            break
        run_cycle(pair=pair, dut_mo=mo, dut_mt=mt, phone_number=number,
                  cycle=cycle, status_callback=_status_cb, stop_event=_stop_event)
    _ui_queue.put(("done", pair))


# ═══════════════════════════════════════════════════════════
class ChorusApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Chorus v1.0")
        self.configure(bg=BG)
        self.resizable(True, True)
        self.minsize(1060, 760)
        self._loops = cfg.LOOP_COUNT
        self._configure_styles()
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
        tk.Label(hdr, text="v1.0", font=(MONO, 10), bg=BG2, fg=BLUE).pack(side="left")
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
        self._build_log(right)

        self._refresh_mode_label()

    # ── config panel ─────────────────────────────────────────
    def _build_config(self, parent):
        outer = tk.LabelFrame(parent, text="  Configuration  ", bg=BG,
                               fg=BLUE, font=(SANS, 10, "bold"),
                               bd=1, relief="groove", labelanchor="nw")
        outer.pack(fill="x", pady=(0, 8))

        def entry_row(frame, label, var, width=16):
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
            return e

        # ── DUT ──────────────────────────────────
        dut_hdr = tk.Frame(outer, bg=BG)
        dut_hdr.pack(fill="x", padx=6, pady=(6, 0))
        self.v_enable_dut = tk.BooleanVar(value=False)
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
            entry_row(self._s1, "MT number", self.v_enum),
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
            entry_row(self._s2, "MT number", self.v_rnum),
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
        
        self.v_sync = tk.BooleanVar(value=False)
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
            e.configure(state=state, fg=fg_color, bg=bg_color,
                        highlightbackground=bg_color)

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

        # disabled overlay label
        w["disabled_lbl"] = tk.Label(inner, text="⏸  Not enabled",
                                      font=(SANS, 10), bg=BG2, fg=BG3)
        # shown/hidden by _set_panel_enabled

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
            f.write(f"{'LP':<10} - {'TIME':<10} - {'DUT_MO':<8} - {'DUT_MT':<8} - {'REF_MO':<8} - {'REF_MT'}\n")
        return timestamp_file_path

    def _append_cycle_to_timestamp_file(self, test_folder_path: str, cycle: int) -> None:
        """
        Append cycle information to the timestamp TXT file.
        """
        timestamp_file_path = os.path.join(test_folder_path, "timestamps.txt")
        
        # Get the current time
        current_time = datetime.now().strftime('%H:%M:%S')
        
        # Get the results for both DUT and REF
        dut_result = _state["dut"]["last_result"] if cycle <= _state["dut"]["cycle"] else "–"
        ref_result = _state["ref"]["last_result"] if cycle <= _state["ref"]["cycle"] else "–"
        
        # Format the results to match the requested format
        dut_mo_result = dut_result if dut_result in ["PASS", "FAIL"] else "–"
        dut_mt_result = dut_result if dut_result in ["PASS", "FAIL"] else "–"
        ref_mo_result = ref_result if ref_result in ["PASS", "FAIL"] else "–"
        ref_mt_result = ref_result if ref_result in ["PASS", "FAIL"] else "–"
        
        # Append the cycle data to the file
        with open(timestamp_file_path, "a", encoding="utf-8") as f:
            f.write(f"{'Call_' + str(cycle):<10}   {current_time:<10}   {dut_mo_result:<8}   {dut_mt_result:<8}   {ref_mo_result:<8}   {ref_mt_result}\n")

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

    def _read_config(self):
        try:
            return {
                "dut_MO":  self.v_emo.get().strip(),
                "dut_MT":  self.v_emt.get().strip(),
                "dut_num": self.v_enum.get().strip(),
                "ref_MO":     self.v_rmo.get().strip(),
                "ref_MT":     self.v_rmt.get().strip(),
                "ref_num":    self.v_rnum.get().strip(),
                "loops":      int(self.v_loops.get()),
                "idle":       int(self.v_idle.get()),
                "call":       int(self.v_call.get()),
                "wait":       int(self.v_wait.get()),
                "log_path":   self.v_log_path.get().strip(),
                "test_case":  self.v_test_case.get().strip(),
                "uppercase":  self.v_uppercase.get(),
                "sync":       self.v_sync.get(),
                "enable_dut": self.v_enable_dut.get(),
                "enable_ref":    self.v_enable_ref.get(),
            }
        except ValueError as e:
            messagebox.showerror("Config error", f"Invalid value:\n{e}")
            return None

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

        # Create a unique test folder for this test run
        test_folder_path = self._create_test_folder(c["test_case"])
        
        # Create timestamp file
        timestamp_file_path = self._create_timestamp_file(test_folder_path)
        
        # Save device information
        device_info_path = self._save_device_info(test_folder_path, c)
        
        # Update the CSV output path to use the test folder
        test_csv_path = os.path.join(test_folder_path, "results.csv")
        cfg.CSV_OUTPUT_PATH = test_csv_path
        

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
        
        for pair, mo_key, mt_key, num_key in [
            ("dut", "dut_MO", "dut_MT", "dut_num"),
            ("ref", "ref_MO", "ref_MT", "ref_num"),
        ]:
            if not c[f"enable_{pair}"]:
                _ui_queue.put(("skip", pair))
                continue
            t = threading.Thread(
                target=worker_func,
                args=(pair, c[mo_key], c[mt_key], c[num_key], c["loops"]),
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

            # log only non-tick events (avoid spamming with "14s", "13s"...)
            if not (detail.endswith("s") and detail[:-1].isdigit()):
                if stage in {"CALLING", "ACTIVE", "PASS", "FAIL",
                             "ANSWERING", "RINGING", "CHECKING", "HANGING UP"}:
                    tag = stage if stage in ("PASS", "FAIL", "ACTIVE") else pair
                    self._log_line(
                        f"{pair.upper():<7} Call_{cycle}  {stage:<12} {detail}", tag)
                    
                    # Append cycle data to timestamp file when cycle completes
                    if stage in {"PASS", "FAIL"}:
                        # Get the test folder path from the CSV output path
                        test_folder_path = os.path.dirname(cfg.CSV_OUTPUT_PATH)
                        self._append_cycle_to_timestamp_file(test_folder_path, cycle)

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
        
        # Generate summary report
        try:
            summary_path = generate_summary_report()
            self._log_line("─" * 54, "dim")
            self._log_line(f"✔  All cycles complete!  Results → {cfg.CSV_OUTPUT_PATH}", "PASS")
            self._log_line(f"📊 Summary report generated → {summary_path}", "info")
            self._log_line("─" * 54, "dim")
            messagebox.showinfo("Done",
                f"All cycles complete!\n\n"
                f"Results saved to:\n{cfg.CSV_OUTPUT_PATH}\n\n"
                f"Summary report saved to:\n{summary_path}")
        except Exception as e:
            self._log_line("─" * 54, "dim")
            self._log_line(f"✔  All cycles complete!  Results → {cfg.CSV_OUTPUT_PATH}", "PASS")
            self._log_line(f"⚠  Failed to generate summary report: {str(e)}", "FAIL")
            self._log_line("─" * 54, "dim")
            messagebox.showinfo("Done",
                f"All cycles complete!\n\n"
                f"Results saved to:\n{cfg.CSV_OUTPUT_PATH}\n\n"
                f"Note: Failed to generate summary report.\nError: {str(e)}")

    def _on_close(self):
        if any(t.is_alive() for t in _threads):
            if not messagebox.askyesno("Quit", "Test is still running. Stop and quit?"):
                return
            _stop_event.set()
        self.destroy()


if __name__ == "__main__":
    app = ChorusApp()
    app.mainloop()
