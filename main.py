# ============================================================
#  Chorus v2.6  –  main.py (tkinter GUI)
#  Dark-mode desktop dashboard for automated voice-call testing.
#  Run: python main.py
# ============================================================

from __future__ import annotations

import sys
import os
import threading
import time
import queue
import re
import json
from datetime import datetime
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

import config as cfg
from core.adb_commands import check_devices, get_signal_info, launch_scrcpy, find_scrcpy
from core.call_monitor import run_cycle
from core.sync_coordinator import SyncCoordinator
from core.report import init_csv, generate_summary_report
from gui.device_picker import DevicePickerDialog
from gui.device_controls import DeviceControlsDialog
from gui.rat_dialog import RatSettingsDialog
from gui.config_tab import ConfigTab
from gui.pair_tab import PairTab
from gui.log_tab import LogTab
from gui.summary_dialog import SummaryDialog
from gui.chart_panel import ChartPanel
from utils.phone_history import add_to_history

# ── optional matplotlib (graceful degradation) ───────────────
_MATPLOTLIB_OK = False
try:
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    _MATPLOTLIB_OK = True
except ImportError:
    pass

# ── font detection (fallback for non-standard Windows installs) ──
def _detect_fonts():
    """Detect available fonts, return (mono_font, sans_font)."""
    try:
        families = tk.font.families()
    except Exception:
        families = set()

    mono_candidates = ["Consolas", "Courier New", "Lucia Console", "DejaVu Sans Mono"]
    mono = "Courier New"
    for f in mono_candidates:
        if f in families:
            mono = f
            break

    sans_candidates = ["Segoe UI", "Arial", "Helvetica", "Tahoma", "Trebuchet MS"]
    sans = "Arial"
    for f in sans_candidates:
        if f in sans_candidates:
            sans = f
            break

    return mono, sans


# ── cross-platform sound ──────────────────────────────────────
def _beep(kind="ok"):
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
            import subprocess
            subprocess.Popen(["paplay", "/usr/share/sounds/freedesktop/stereo/complete.oga"],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass

# ── theme ────────────────────────────────────────────────────
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
MONO, SANS = _detect_fonts()

STAGE_COLOR = {
    "PASS": GREEN, "FAIL": RED, "ACTIVE": CYAN,
    "COMPLETE": GREEN, "CALLING": YELLOW, "RINGING": YELLOW,
    "ANSWERING": YELLOW,
    "IDLE": FG_DIM, "CHECKING": FG, "HANGING UP": FG_DIM,
}

# ── shared state ─────────────────────────────────────────────
_ui_queue = queue.Queue()
_stop_event = threading.Event()
_pause_event = threading.Event()
_threads = []
_sync_coordinator = None

_state = {
    "dut": {"cycle": 0, "stage": "\u2013", "detail": "",
            "pass": 0, "fail": 0, "done": False, "last_result": "\u2013", "enabled": True},
    "ref":    {"cycle": 0, "stage": "\u2013", "detail": "",
            "pass": 0, "fail": 0, "done": False, "last_result": "\u2013", "enabled": True},
}

_logged_cycles = set()


def _status_cb(pair, cycle, stage, detail):
    _ui_queue.put(("status", pair, cycle, stage, detail))


def _sync_worker(pair, mo, mt, number, loops):
    """Worker function for synchronized testing mode."""
    global _sync_coordinator

    sync = _sync_coordinator

    for cycle in range(1, loops + 1):
        if _stop_event.is_set():
            break

        while _pause_event.is_set() and not _stop_event.is_set():
            time.sleep(0.5)

        cycle_result = run_cycle(pair=pair, dut_mo=mo, dut_mt=mt, phone_number=number,
                  cycle=cycle, status_callback=_status_cb, stop_event=_stop_event,
                  max_answer_retries=cfg.ANSWER_RETRIES, answer_retry_delay=cfg.ANSWER_RETRY_DELAY,
                  sync=sync)

        # ── Synchronize at END of each cycle ───────────────────
        if sync is not None:
            sync.wait_end(pair, cycle)

        if cycle_result.get("result") in ["PASS", "FAIL"]:
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
                mt_signal_info = get_signal_info(mt)
                app._cycle_signal_data[cycle][f"{pair}_mt"] = mt_signal_info

        if cycle_result.get("result") in ["PASS", "FAIL"]:
            app = tk._default_root
            if app and hasattr(app, '_cycle_signal_data'):
                if f"{pair}_mo" in app._cycle_signal_data.get(cycle, {}):
                    app._cycle_signal_data[cycle][f"{pair}_mo"]["call_type"] = cycle_result.get("call_type", "UNKNOWN")

        while _pause_event.is_set() and not _stop_event.is_set():
            time.sleep(0.5)

        if cycle_result.get("result") in ["PASS", "FAIL"]:
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
                mt_signal_info = get_signal_info(mt)
                app._cycle_signal_data[cycle][f"{pair}_mt"] = mt_signal_info
    _ui_queue.put(("done", pair))


def _worker(pair, mo, mt, number, loops, stop_event, status_callback):
    """Worker function for independent testing mode."""
    for cycle in range(1, loops + 1):
        if stop_event.is_set():
            break

        while _pause_event.is_set() and not stop_event.is_set():
            time.sleep(0.5)

        run_cycle(pair=pair, dut_mo=mo, dut_mt=mt, phone_number=number,
                  cycle=cycle, status_callback=status_callback, stop_event=stop_event,
                  max_answer_retries=cfg.ANSWER_RETRIES, answer_retry_delay=cfg.ANSWER_RETRY_DELAY)

        if cycle < loops and not stop_event.is_set():
            time.sleep(0.5)


# ═══════════════════════════════════════════════════════════
class ChorusApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Chorus v2.10")
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
        s.configure("Pause.TButton", background="#854d0e", foreground="#fef08a")
        s.map("Pause.TButton", background=[("active", "#a16207")])
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
        tk.Label(hdr, text="  \U0001f4e1  Chorus",
                 font=(SANS, 14, "bold"), bg=BG2, fg=FG).pack(side="left", padx=10, pady=8)
        tk.Label(hdr, text="v2.10", font=(MONO, 10), bg=BG2, fg=BLUE).pack(side="left")
        self._lbl_mode = tk.Label(hdr, text="", font=(MONO, 9, "bold"), bg=BG2)
        self._lbl_mode.pack(side="right", padx=16)

        body = tk.Frame(self, bg=BG)
        body.pack(fill="both", expand=True, padx=10, pady=6)

        # Left panel with scrollbar
        left_container = tk.Frame(body, bg=BG, width=350)
        left_container.pack(side="left", fill="y", padx=(0, 8))
        left_container.pack_propagate(False)

        left_canvas = tk.Canvas(left_container, bg=BG, highlightthickness=0)
        left_scrollbar = ttk.Scrollbar(left_container, orient="vertical", command=left_canvas.yview)
        self.left_scrollable_frame = tk.Frame(left_canvas, bg=BG)

        self.left_scrollable_frame.bind(
            "<Configure>",
            lambda e: left_canvas.configure(scrollregion=left_canvas.bbox("all"))
        )

        left_canvas.create_window((0, 0), window=self.left_scrollable_frame, anchor="nw")
        left_canvas.configure(yscrollcommand=left_scrollbar.set)

        left_canvas.pack(side="left", fill="both", expand=True)
        left_scrollbar.pack(side="right", fill="y")

        def _on_mousewheel(event):
            left_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        left_canvas.bind_all("<MouseWheel>", _on_mousewheel)
        self.left_scrollable_frame.bind("<MouseWheel>", _on_mousewheel)

        # Build config panel
        self.config_panel = ConfigTab(self.left_scrollable_frame, _ui_queue)

        # Build controls
        self._build_controls(self.left_scrollable_frame)

        # Right panel
        right = tk.Frame(body, bg=BG)
        right.pack(side="left", fill="both", expand=True)
        self.pair_tab = PairTab(right, self._on_scrcpy)
        self.chart_panel = ChartPanel(right)
        self.log_tab = LogTab(right)

    def _build_controls(self, parent):
        f = tk.Frame(parent, bg=BG)
        f.pack(fill="x", pady=4)

        self.btn_pick = ttk.Button(f, text="\U0001f50c  Pick Devices",
                                    style="Pick.TButton",
                                    command=self._do_pick_devices)
        self.btn_pick.pack(fill="x", pady=(0, 6))

        self.btn_check = ttk.Button(f, text="\U0001f50d  Check Devices",
                                     command=self._do_check)
        self.btn_check.pack(fill="x", pady=2)

        self.btn_rat = ttk.Button(f, text="\U0001f4f6  Ustaw RAT",
                                    style="Pick.TButton",
                                    command=self._do_set_rat)
        self.btn_rat.pack(fill="x", pady=2)

        # self.btn_sim = ttk.Button(f, text="\U0001f4f1  SIM Controls",
        #                             style="Pick.TButton",
        #                             command=self._do_sim_controls)
        # self.btn_sim.pack(fill="x", pady=2)

# self.btn_apk = ttk.Button(f, text="\U0001f4e6  Install APK",
        #                              style="Pick.TButton",
        #                              command=self._do_install_apk)
        # self.btn_apk.pack(fill="x", pady=2)

        self.btn_start = ttk.Button(f, text="\u25b6   Start Test",
                                     style="Start.TButton",
                                     command=self._do_start)
        self.btn_start.pack(fill="x", pady=2)

        self.btn_pause = ttk.Button(f, text="\u23f8  Pause/Resume",
                                    style="Pause.TButton",
                                    command=self._do_pause, state="disabled")
        self.btn_pause.pack(fill="x", pady=2)

        self.btn_stop = ttk.Button(f, text="\u23f9   Stop",
                                    style="Stop.TButton",
                                    command=self._do_stop, state="disabled")
        self.btn_stop.pack(fill="x", pady=2)

        ttk.Button(f, text="\U0001f5d1   Clear Log",
                    command=self._clear_log).pack(fill="x", pady=(8, 2))

    # ── callbacks ──────────────────────────────────────────────
    def _on_scrcpy(self, pair, role):
        """Handle scrcpy launch request from pair panel."""
        self._launch_scrcpy(pair, role)

    # ── device picker ────────────────────────────────────────
    def _do_pick_devices(self):
        enabled_pairs = []
        if self.config_panel.v_enable_dut.get():
            enabled_pairs.append("dut")
        if self.config_panel.v_enable_ref.get():
            enabled_pairs.append("ref")
        prefill = {
            "dut_MO": self.config_panel.v_emo.get(),
            "dut_MT": self.config_panel.v_emt.get(),
            "ref_MO": self.config_panel.v_rmo.get(),
            "ref_MT": self.config_panel.v_rmt.get(),
            "gps_source": self.config_panel.v_gps.get(),
        }
        dialog = DevicePickerDialog(self, prefill=prefill, enabled_pairs=enabled_pairs)
        self.wait_window(dialog)
        if dialog.result is None:
            return
        r = dialog.result
        self.config_panel.v_emo.set(r["dut_MO"])
        self.config_panel.v_emt.set(r["dut_MT"])
        self.config_panel.v_rmo.set(r["ref_MO"])
        self.config_panel.v_rmt.set(r["ref_MT"])
        if "gps_source" in r:
            self.config_panel.v_gps.set(r["gps_source"])
        self.log_tab.log_line("Device assignment from picker:", "info")
        self.log_tab.log_line(f"  dut_MO \u2192 {r['dut_MO']}", "dut")
        self.log_tab.log_line(f"  dut_MT \u2192 {r['dut_MT']}", "dut")
        self.log_tab.log_line(f"  ref_MO    \u2192 {r['ref_MO']}",    "ref")
        self.log_tab.log_line(f"  ref_MT    \u2192 {r['ref_MT']}",    "ref")
        self.config_panel.save_persistent_config()

    def _do_check(self):
        c = self.config_panel.read_config()
        if not c:
            return
        self.config_panel.apply_config(c)
        self.log_tab.log_line("Checking devices\u2026", "dim")
        serials = [c["dut_MO"], c["dut_MT"], c["ref_MO"], c["ref_MT"]]
        labels = {
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
                    self.log_tab.log_line(
                        f"\u2705  {labels.get(serial, serial)}  [{serial}]" if ok
                        else f"\u274c  {labels.get(serial, serial)}  [{serial}]",
                        "PASS" if ok else "FAIL")
                    if not ok:
                        all_ok = False
                self.log_tab.log_line(
                    "All devices reachable \u2714" if all_ok
                    else "One or more devices offline \u2013 check USB / adb devices",
                    "PASS" if all_ok else "FAIL")
            self.after(0, show)
        threading.Thread(target=task, daemon=True).start()

    def _do_set_rat(self):
        c = self.config_panel.read_config()
        if not c:
            return

        devices = {
            "dut_MO": c["dut_MO"],
            "dut_MT": c["dut_MT"],
            "ref_MO": c["ref_MO"],
            "ref_MT": c["ref_MT"]
        }

        dialog = RatSettingsDialog(self, devices)
        self.wait_window(dialog)

    def _do_sim_controls(self):
        dialog = DeviceControlsDialog(self)
        self.wait_window(dialog)

    def _do_install_apk(self):
        """Open file dialog to select APK, then install on all devices."""
        apk_path = filedialog.askopenfilename(
            parent=self,
            title="Select APK to Install",
            filetypes=[("Android APK", "*.apk"), ("All files", "*.*")],
        )
        if not apk_path:
            return

        if apk_path not in cfg.APK_PATHS:
            cfg.APK_PATHS.append(apk_path)

        self.log_tab.log_line(f"\U0001f4e6  APK selected: {apk_path}", "info")

        # Start installation in background thread
        threading.Thread(
            target=self._install_apk_on_all,
            args=(apk_path,),
            daemon=True,
        ).start()

    def _install_apk_on_all(self, apk_path: str):
        """Install APK on all 4 devices in parallel (dut_MO, dut_MT, ref_MO, ref_MT)."""
        from core.adb_controller import install_apk

        devices = [
            ("DUT MO", self.config_panel.v_emo.get()),
            ("DUT MT", self.config_panel.v_emt.get()),
            ("REF MO", self.config_panel.v_rmo.get()),
            ("REF MT", self.config_panel.v_rmt.get()),
        ]

        results = []
        for label, serial in devices:
            if not serial or serial in ("YOUR_SERIAL_HERE",):
                results.append((label, False, "No serial configured"))
                continue

            ok, msg = install_apk(serial, apk_path, replace=True)
            results.append((label, ok, msg))

        # Update UI on main thread
        def show_results():
            self.log_tab.log_line("\U0001f4e6  APK Installation Results:", "info")
            for label, ok, msg in results:
                icon = "\u2705" if ok else "\u274c"
                self.log_tab.log_line(
                    f"{icon}  {label:<10} [{serial}]  {msg}",
                    "PASS" if ok else "FAIL",
                )
            self.log_tab.log_line(
                f"\u2500  {sum(1 for _, ok, _ in results if ok)}/{len(results)} devices installed",
                "info",
            )

        self.after(0, show_results)

    # ── start / stop ──────────────────────────────────────────
    def _do_start(self):
        global _threads
        c = self.config_panel.read_config()
        if not c:
            return

        if not c["enable_dut"] and not c["enable_ref"]:
            messagebox.showwarning("No pairs enabled",
                "Enable at least one pair (DUT or REF) before starting.")
            return

        self.config_panel.apply_config(c)
        self._loops = c["loops"]
        _stop_event.clear()

        global _logged_cycles
        _logged_cycles.clear()

        if c["dut_num"]:
            add_to_history("dut", c["dut_num"])
        if c["ref_num"]:
            add_to_history("ref", c["ref_num"])

        test_folder_path = self.config_panel.create_test_folder(c["test_case"])
        timestamp_file_path = self.config_panel.create_timestamp_file(test_folder_path)
        device_info_path = self.config_panel.save_device_info(test_folder_path, c)

        test_csv_path = os.path.join(test_folder_path, "results.csv")
        cfg.CSV_OUTPUT_PATH = test_csv_path

        self.config_panel.save_persistent_config()

        for pair in ("dut", "ref"):
            _state[pair] = {"cycle": 0, "stage": "\u2013", "detail": "",
                            "pass": 0, "fail": 0, "done": False, "last_result": "\u2013"}
            enabled = c[f"enable_{pair}"]
            _state[pair]["enabled"] = enabled
            self.pair_tab.set_enabled(pair, enabled)

        init_csv()
        self.log_tab.log_line("\u2500" * 54, "dim")
        enabled_str = " + ".join(
            p.upper() for p in ("dut", "ref") if c[f"enable_{p}"])
        sync_str = " [SYNCHRONIZED]" if c["sync"] else ""
        self.log_tab.log_line(
            f"\u25b6  START  [LIVE]{sync_str}  pairs={enabled_str}  "
            f"loops={c['loops']}  idle={c['idle']}s  call={c['call']}s", "info")
        self.log_tab.log_line(f"\U0001f4c2 Test folder: {test_folder_path}", "info")
        self.log_tab.log_line("\u2500" * 54, "dim")

        _threads = []
        global _sync_coordinator
        _sync_coordinator = None

        if c["sync"]:
            _sync_coordinator = SyncCoordinator(
                enabled=True,
                timeout=cfg.SYNC_TIMEOUT
            )
            _sync_coordinator.reset()

        worker_func = _sync_worker if c["sync"] else _worker

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
                args=(pair, c[mo_key], c[mt_key], c[num_key], c["loops"]),
                daemon=True, name=pair,
            )
            _threads.append(t)
            t.start()

        self.btn_start.configure(state="disabled")
        self.btn_check.configure(state="disabled")
        self.btn_pick.configure(state="disabled")
        self.btn_stop.configure(state="normal")
        self.btn_pause.configure(state="normal")

    def _do_stop(self):
        _stop_event.set()
        self.log_tab.log_line("\u23f9  Stop requested \u2013 finishing current cycle\u2026", "FAIL")
        self.btn_stop.configure(state="disabled")
        self.btn_pause.configure(state="disabled")

    def _do_pause(self):
        if _pause_event.is_set():
            _pause_event.clear()
            self.log_tab.log_line("\u25b6  Resume requested \u2013 continuing test\u2026", "info")
            self.btn_pause.configure(text="\u23f8  Pause")
        else:
            _pause_event.set()
            self.log_tab.log_line("\u23f8  Pause requested \u2013 finishing current cycle\u2026", "FAIL")
            self.btn_pause.configure(text="\u25b6  Resume")

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

    # ── scrcpy launcher ──────────────────────────────────────
    def _launch_scrcpy(self, pair, role):
        """Launch scrcpy for MO or MT device of given pair."""
        var_map = {
            "dut_MO": self.config_panel.v_emo,
            "dut_MT": self.config_panel.v_emt,
            "ref_MO": self.config_panel.v_rmo,
            "ref_MT": self.config_panel.v_rmt,
        }
        key = f"{pair}_{role}"
        var = var_map.get(key)
        serial = var.get().strip() if var else ""

        if not serial or serial in ("YOUR_SERIAL_HERE", ""):
            messagebox.showwarning("scrcpy", f"No serial configured for {key}.")
            return

        exe = getattr(self, "_scrcpy_path", None) or find_scrcpy()
        if not exe:
            exe = filedialog.askopenfilename(
                parent=self,
                title="Locate scrcpy executable",
                filetypes=[("scrcpy", "scrcpy.exe"), ("All files", "*.*")],
            )
            if not exe:
                return
            self._scrcpy_path = exe

        title = f"Chorus \u2014 {pair.upper()} {role}  [{serial}]"
        ok = launch_scrcpy(serial, title=title, scrcpy_path=exe)
        if ok:
            self.log_tab.log_line(f"\U0001f4fa  scrcpy launched: {pair.upper()} {role} [{serial}]", "info")
        else:
            self.log_tab.log_line(f"\U0001f6a8  scrcpy FAILED: {pair.upper()} {role} [{serial}]", "error")
            messagebox.showerror("scrcpy failed",
                f"Could not launch scrcpy for {serial}.\n\n"
                "Make sure scrcpy is installed:\n"
                "  https://github.com/Genymobile/scrcpy")

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
                if hasattr(self, 'chart_panel'):
                    self.chart_panel.chart_data[pair]["pass"] += 1
                    self.chart_panel.draw_chart()
            elif stage == "FAIL":
                s["fail"] += 1
                s["last_result"] = f"FAIL  {detail}"
                if hasattr(self, 'chart_panel'):
                    self.chart_panel.chart_data[pair]["fail"] += 1
                    self.chart_panel.draw_chart()

            if not (detail.endswith("s") and detail[:-1].isdigit()):
                if stage in {"CALLING", "ACTIVE", "PASS", "FAIL",
                              "ANSWERING", "RINGING", "CHECKING", "HANGING UP",
                              "ANSWERED", "SIGNAL"}:
                    tag = stage if stage in ("PASS", "FAIL", "ACTIVE", "ANSWERED", "SIGNAL") else pair
                    self.log_tab.log_line(
                        f"{pair.upper():<7} Call_{cycle}  {stage:<12} {detail}", tag)

                    if stage in {"PASS", "FAIL"}:
                        if cycle not in _logged_cycles:
                            enabled_pairs = [p for p in ("dut", "ref") if _state[p].get("enabled", False)]
                            if all(_state[p]["cycle"] >= cycle for p in enabled_pairs):
                                test_folder_path = os.path.dirname(cfg.CSV_OUTPUT_PATH)
                                signal_data = getattr(self, '_cycle_signal_data', {}).get(cycle, None)
                                results = {
                                    p: (_state[p]["last_result"] if _state[p].get("enabled") else "\u2013")
                                    for p in ("dut", "ref")
                                }
                                self.config_panel.append_cycle_to_timestamp_file(
                                    test_folder_path, cycle, signal_data, results)
                                _logged_cycles.add(cycle)

            if hasattr(self, 'pair_tab'):
                self.pair_tab.update(pair, _state, self._loops)

        elif kind == "done":
            _, pair = msg
            _state[pair].update({"done": True, "stage": "COMPLETE", "detail": ""})
            self.log_tab.log_line(f"{pair.upper()} \u2014 all cycles complete \u2714", "PASS")
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
        self.btn_pause.configure(state="disabled")
        self.btn_pause.configure(text="\u23f8  Pause")

        _beep("ok")

        try:
            from core.report import generate_detailed_summary
            detailed_summary = generate_detailed_summary()

            SummaryDialog(self, detailed_summary)

            self.log_tab.log_line("\u2500" * 54, "dim")
            self.log_tab.log_line(f"\u2714  All cycles complete!  Results \u2192 {cfg.CSV_OUTPUT_PATH}", "PASS")
            self.log_tab.log_line(f"\U0001f4ca Detailed summary generated", "info")

            if cfg.GPS_ENABLED:
                try:
                    from utils.map_generator import generate_all
                    import os as _os
                    test_name = _os.path.basename(cfg.CSV_OUTPUT_PATH).replace(".csv", "")
                    html_path, png_path = generate_all(cfg.CSV_OUTPUT_PATH, cfg.LOG_OUTPUT_PATH, test_name)
                    maps_info = []
                    if html_path:
                        maps_info.append(f"HTML \u2192 {html_path}")
                    if png_path:
                        maps_info.append(f"PNG  \u2192 {png_path}")
                    if maps_info:
                        self.log_tab.log_line(f"\U0001f5fa  GPS maps saved:", "info")
                        for m in maps_info:
                            self.log_tab.log_line(f"     {m}", "info")
                except Exception as _e:
                    self.log_tab.log_line(f"\u26a0  GPS map generation failed: {str(_e)}", "WARN")

                try:
                    kml_path = os.path.join(os.path.dirname(str(cfg.CSV_OUTPUT_PATH)), "gps_map.kml")
                    if os.path.exists(kml_path):
                        self.log_tab.log_line(f"\U0001f4d1 KML map: {kml_path}", "PASS")
                    else:
                        self.log_tab.log_line(f"\u26a0 KML map not generated (GPS_ENABLED=False?)", "WARN")
                except Exception:
                    pass

            self.log_tab.log_line("\u2500" * 54, "dim")
        except Exception as e:
            self.log_tab.log_line("\u2500" * 54, "dim")
            self.log_tab.log_line(f"\u2714  All cycles complete!  Results \u2192 {cfg.CSV_OUTPUT_PATH}", "PASS")
            self.log_tab.log_line(f"\u26a0  Failed to generate detailed summary: {str(e)}", "FAIL")
            self.log_tab.log_line("\u2500" * 54, "dim")
            messagebox.showinfo("Done",
                f"All cycles complete!\n\n"
                f"Results saved to:\n{cfg.CSV_OUTPUT_PATH}\n\n"
                f"Note: Failed to generate detailed summary.\nError: {str(e)}")

    # ── helpers ──────────────────────────────────────────────
    def _clear_log(self):
        self.log_tab.clear()

    def _refresh_mode_label(self):
        self._lbl_mode.configure(
            text="\u25cf LIVE",
            fg=GREEN,
        )

    def _get_config_file_path(self):
        app_dir = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(app_dir, "chorus_config.json")

    def _load_persistent_config(self):
        config_file = self._get_config_file_path()
        if os.path.exists(config_file):
            try:
                with open(config_file, "r") as f:
                    config = json.load(f)

                if "devices" in config:
                    cfg.DEVICES["dut_MO"] = config["devices"].get("dut_MO", cfg.DEVICES["dut_MO"])
                    cfg.DEVICES["dut_MT"] = config["devices"].get("dut_MT", cfg.DEVICES["dut_MT"])
                    cfg.DEVICES["ref_MO"] = config["devices"].get("ref_MO", cfg.DEVICES["ref_MO"])
                    cfg.DEVICES["ref_MT"] = config["devices"].get("ref_MT", cfg.DEVICES["ref_MT"])

                if "phone_numbers" in config:
                    cfg.PHONE_NUMBERS["dut"] = config["phone_numbers"].get("dut", cfg.PHONE_NUMBERS["dut"])
                    cfg.PHONE_NUMBERS["ref"] = config["phone_numbers"].get("ref", cfg.PHONE_NUMBERS["ref"])

                if "gps_source" in config:
                    cfg.GPS_SOURCE = config["gps_source"]

                if "apk_paths" in config:
                    cfg.APK_PATHS = config["apk_paths"]

            except Exception as e:
                print(f"Error loading persistent config: {e}")

    def _save_persistent_config(self):
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
                },
                "gps_source": cfg.GPS_SOURCE,
                "apk_paths": cfg.APK_PATHS,
            }

            with open(config_file, "w") as f:
                json.dump(config, f, indent=2)
        except Exception as e:
            print(f"Error saving persistent config: {e}")

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
