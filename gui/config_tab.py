# ============================================================
#  Chorus v2.5  –  gui/config_tab.py
#  Configuration tab: device serials, phone numbers, timing,
#  test case name, log path, display options, and persistence.
# ============================================================

from __future__ import annotations

import os
import json
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

import config as cfg
from core.adb_commands import get_sim_phone_numbers
from utils.phone_history import get_history, add_to_history
from utils.theme import BG, BG2, BG3, FG, FG_DIM, BLUE, YELLOW, GREEN, RED, CYAN, MONO, SANS


class ConfigTab:
    """Configuration panel with device assignment, timing, and persistence."""

    def __init__(self, parent, ui_queue):
        self._ui_queue = ui_queue
        self._build(parent)

    # ── public StringVars (bound to GUI) ───────────────────────
    @property
    def v_emo(self): return self._v_emo
    @property
    def v_emt(self): return self._v_emt
    @property
    def v_enum(self): return self._v_enum
    @property
    def v_rmo(self): return self._v_rmo
    @property
    def v_rmt(self): return self._v_rmt
    @property
    def v_gps(self): return self._v_gps
    @property
    def v_loops(self): return self._v_loops
    @property
    def v_idle(self): return self._v_idle
    @property
    def v_call(self): return self._v_call
    @property
    def v_ring(self): return self._v_ring
    @property
    def v_test_case(self): return self._v_test_case
    @property
    def v_log_path(self): return self._v_log_path
    @property
    def v_enable_dut(self): return self._v_enable_dut
    @property
    def v_enable_ref(self): return self._v_enable_ref
    
    @property
    def v_sync(self): return self._v_sync
    @property
    def v_apk(self): return self._v_apk

    # ── layout ─────────────────────────────────────────────────
    def _build(self, parent):
        outer = tk.LabelFrame(parent, text="  Configuration  ", bg=BG,
                              fg=BLUE, font=(SANS, 10, "bold"),
                              bd=1, relief="groove", labelanchor="nw")
        outer.pack(fill="x", pady=(0, 8))

        # ── DUT ──────────────────────────────────
        dut_hdr = tk.Frame(outer, bg=BG)
        dut_hdr.pack(fill="x", padx=6, pady=(6, 0))
        self._v_enable_dut = tk.BooleanVar(value=True)
        self._dut_dot = tk.Label(dut_hdr, text="●", bg=BG, fg=GREEN,
                                  font=(SANS, 14, "bold"), padx=4, pady=2)
        self._dut_dot.pack(side="left")
        self._v_enable_dut.trace_add("write", lambda *args: self._update_dots())
        tk.Checkbutton(dut_hdr, text="  DUT  ",
                        variable=self._v_enable_dut,
                        command=self._toggle_pair_entries,
                        bg=BG, fg=BLUE, activebackground=BG, activeforeground=BLUE,
                        selectcolor=BG3, font=(SANS, 11, "bold"),
                        padx=8, pady=4).pack(side="left")

        self._s1 = tk.Frame(outer, bg=BG)
        self._s1.pack(fill="x", padx=6, pady=(0, 4))
        self._v_emo  = tk.StringVar(value=cfg.DEVICES["dut_MO"])
        self._v_emt  = tk.StringVar(value=cfg.DEVICES["dut_MT"])
        self._v_enum = tk.StringVar(value=cfg.PHONE_NUMBERS["dut"])
        self._dut_entries = [
            self._entry_row(self._s1, "MO serial", self._v_emo),
            self._entry_row(self._s1, "MT serial", self._v_emt),
            self._number_entry_row(self._s1, "MT number", self._v_enum, pair="dut"),
        ]

        tk.Frame(outer, bg=BG3, height=1).pack(fill="x", padx=6)

        # ── REF ─────────────────────────────────
        ref_hdr = tk.Frame(outer, bg=BG)
        ref_hdr.pack(fill="x", padx=6, pady=(6, 0))
        self._v_enable_ref = tk.BooleanVar(value=True)
        self._ref_dot = tk.Label(ref_hdr, text="●", bg=BG, fg=GREEN,
                                  font=(SANS, 14, "bold"), padx=4, pady=2)
        self._ref_dot.pack(side="left")
        self._v_enable_ref.trace_add("write", lambda *args: self._update_dots())
        tk.Checkbutton(ref_hdr, text="  REF  ",
                        variable=self._v_enable_ref,
                        command=self._toggle_pair_entries,
                        bg=BG, fg=YELLOW, activebackground=BG, activeforeground=YELLOW,
                        selectcolor=BG3, font=(SANS, 11, "bold"),
                        padx=8, pady=4).pack(side="left")

        self._s2 = tk.Frame(outer, bg=BG)
        self._s2.pack(fill="x", padx=6, pady=(0, 4))
        self._v_rmo  = tk.StringVar(value=cfg.DEVICES["ref_MO"])
        self._v_rmt  = tk.StringVar(value=cfg.DEVICES["ref_MT"])
        self._v_rnum = tk.StringVar(value=cfg.PHONE_NUMBERS["ref"])
        self._v_gps  = tk.StringVar(value=cfg.GPS_SOURCE)
        self._ref_entries = [
            self._entry_row(self._s2, "MO serial", self._v_rmo),
            self._entry_row(self._s2, "MT serial", self._v_rmt),
            self._number_entry_row(self._s2, "MT number", self._v_rnum, pair="ref"),
        ]

        tk.Frame(outer, bg=BG3, height=1).pack(fill="x", padx=6)

        # ── timing ─────────────────────────────────────────
        s3 = tk.LabelFrame(outer, text=" Timing & Loops ", bg=BG,
                           fg=FG_DIM, font=(SANS, 8), bd=1, relief="groove")
        s3.pack(fill="x", padx=6, pady=4)
        self._v_loops = tk.StringVar(value=str(cfg.LOOP_COUNT))
        self._v_idle  = tk.StringVar(value=str(cfg.IDLE_SECONDS))
        self._v_call  = tk.StringVar(value=str(cfg.CALL_SECONDS))
        self._v_ring = tk.StringVar(value=str(cfg.RINGING_TIMEOUT))
        self._entry_row(s3, "Loop count",   self._v_loops, width=6)
        self._entry_row(s3, "Idle (s)",     self._v_idle,  width=6)
        self._entry_row(s3, "Call (s)",     self._v_call,  width=6)
        self._entry_row(s3, "Setup Time (s)", self._v_ring, width=6)

        # ── Test Case Name ───────────────────────────────────
        # s6 = tk.LabelFrame(outer, text=" Test Case Name ", bg=BG,
        #                     fg=FG_DIM, font=(SANS, 8), bd=1, relief="groove")
        # s6.pack(fill="x", padx=6, pady=(0, 4))
        # self._v_test_case = tk.StringVar(value="TR-0000")
        # self._entry_row(s6, "Test case", self._v_test_case, width=16)

        # ── Log path ──────────────────────────────────────────
        s5 = tk.LabelFrame(outer, text=" Log Output Path ", bg=BG,
                            fg=FG_DIM, font=(SANS, 8), bd=1, relief="groove")
        s5.pack(fill="x", padx=6, pady=(0, 4))
        self._v_log_path = tk.StringVar(value="")

        log_path_frame = tk.Frame(s5, bg=BG)
        log_path_frame.pack(fill="x", padx=8, pady=2)

        tk.Label(log_path_frame, text="Timestamp path", font=(MONO, 8), bg=BG,
                 fg=FG_DIM, width=14, anchor="w").pack(side="left")

        self._log_path_entry = tk.Entry(log_path_frame, textvariable=self._v_log_path, font=(MONO, 9),
                         bg=BG3, fg=FG, insertbackground=FG,
                         relief="flat", bd=0, width=16,
                         highlightthickness=1,
                         highlightcolor=BLUE, highlightbackground=BG3)
        self._log_path_entry.pack(side="left", ipady=3)

        ttk.Button(log_path_frame, text="Browse...", command=self._browse_log_path).pack(side="left", padx=(4, 0))

        # ── display options ──────────────────────────────────────
        df = tk.Frame(outer, bg=BG)
        df.pack(fill="x", padx=8, pady=(2, 6))

        self._v_sync = tk.BooleanVar(value=True)
        tk.Checkbutton(df, text="SYNCHRONIZED TESTING",
                        variable=self._v_sync,
                        bg=BG, fg=FG, activebackground=BG,
                        activeforeground=FG, selectcolor=BG3,
                        font=(SANS, 9, "bold")).pack(side="left")

        self._v_apk = tk.StringVar(value=cfg.APK_PATHS[0] if cfg.APK_PATHS else "")

        # apply initial dim states
        parent.after(50, lambda: self._toggle_pair_entries())

    # ── internal helpers ───────────────────────────────────────
    def _entry_row(self, frame, label, var, width=16, pair=None):
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

        if label == "MT number" and pair:
            history_btn = tk.Button(f, text="🕒", font=(MONO, 8), bg=BG3, fg=FG,
                                   relief="flat", bd=0, width=2,
                                   command=lambda p=pair: self._show_history(p, var))
            history_btn.pack(side="left", padx=(2, 0))

        return e

    def _number_entry_row(self, frame, label, var, width=16, pair=None):
        f = tk.Frame(frame, bg=BG)
        f.pack(fill="x", padx=8, pady=2)
        tk.Label(f, text=label, font=(MONO, 8), bg=BG,
                 fg=FG_DIM, width=14, anchor="w").pack(side="left")

        cmb = ttk.Combobox(f, textvariable=var, font=(MONO, 9),
                          state="readonly", width=width)
        cmb.pack(side="left", ipady=2)

        refresh_btn = tk.Button(f, text="🔄", font=(MONO, 8), bg=BG3, fg=FG,
                               relief="flat", bd=0, width=2,
                               command=lambda p=pair: self._refresh_sim_numbers(p))
        refresh_btn.pack(side="left", padx=(2, 0))
        self._create_tooltip(refresh_btn, "Read SIM numbers from device")

        history_btn = tk.Button(f, text="🕒", font=(MONO, 8), bg=BG3, fg=FG,
                               relief="flat", bd=0, width=2,
                               command=lambda p=pair: self._show_history(p, var))
        history_btn.pack(side="left", padx=(2, 0))
        self._create_tooltip(history_btn, "Phone number history")

        return cmb

    def _toggle_pair_entries(self):
        """Dim entry widgets when pair is disabled."""
        pair = None
        if self._v_enable_dut is not None:
            pair = "dut" if not self._v_enable_dut.get() else None
        if self._v_enable_ref is not None:
            pair = "ref" if not self._v_enable_ref.get() else None

        # Toggle both if called without specific pair
        for p in ("dut", "ref"):
            enabled = self._v_enable_dut.get() if p == "dut" else self._v_enable_ref.get()
            entries = self._dut_entries if p == "dut" else self._ref_entries
            state = "normal" if enabled else "disabled"
            fg_color = FG if enabled else FG_DIM
            bg_color = BG3 if enabled else BG2
            for e in entries:
                if isinstance(e, ttk.Combobox):
                    e.configure(state=state)
                else:
                    e.configure(state=state, fg=fg_color, bg=bg_color,
                                highlightbackground=bg_color)

            # Update dot color
            dot = self._dut_dot if p == "dut" else self._ref_dot
            dot.configure(fg=GREEN if enabled else BG3)

    def _update_dots(self):
        """Update dot colors based on enable state."""
        dut_enabled = self._v_enable_dut.get()
        ref_enabled = self._v_enable_ref.get()
        self._dut_dot.configure(fg=GREEN if dut_enabled else BG3)
        self._ref_dot.configure(fg=GREEN if ref_enabled else BG3)

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

    # ── callbacks (called from main.py buttons) ────────────────
    def _show_history(self, pair, var):
        """Show a dropdown menu with phone number history."""
        history = get_history(pair)
        if not history:
            return

        menu = tk.Menu(self._get_toplevel(), tearoff=0)
        for number in history:
            menu.add_command(label=number, command=lambda n=number: var.set(n))

        try:
            widget = self._get_toplevel()
            if widget:
                menu.post(widget.winfo_rootx(), widget.winfo_rooty() + widget.winfo_height())
        except tk.TclError:
            menu.post(self._get_toplevel().winfo_pointerx(), self._get_toplevel().winfo_pointery())

    def _refresh_sim_numbers(self, pair):
        """Read SIM phone numbers from device and populate combobox."""
        if pair == "dut":
            serial = self._v_emt.get()
            var = self._v_enum
            cmb = self._dut_entries[2]
        else:
            serial = self._v_rmt.get()
            var = self._v_rnum
            cmb = self._ref_entries[2]

        if not serial or serial in ("YOUR_SERIAL_HERE", ""):
            messagebox.showwarning("No device",
                "Assign a device first (click 'Pick Devices').")
            return

        sim_data = get_sim_phone_numbers(serial)

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

        cmb["values"] = options
        if options:
            first = options[0]
            if ": " in first:
                var.set(first.split(": ")[1])

    def _browse_log_path(self):
        """Open a directory selection dialog for choosing the log output path."""
        initial_dir = self._v_log_path.get() or "."
        selected_path = filedialog.askdirectory(
            parent=self._get_toplevel(),
            title="Select Log Output Directory",
            initialdir=initial_dir
        )
        if selected_path:
            self._v_log_path.set(selected_path)

    def _get_toplevel(self):
        """Get the root window for dialog parent."""
        return tk._default_root or tk.Tk()

    # ── config read/write ──────────────────────────────────────
    def read_config(self):
        """Read configuration from GUI fields and validate."""
        try:
            c = {
                "dut_MO": self._v_emo.get().strip(),
                "dut_MT": self._v_emt.get().strip(),
                "ref_MO": self._v_rmo.get().strip(),
                "ref_MT": self._v_rmt.get().strip(),
                "dut_num": self._v_enum.get().strip(),
                "ref_num": self._v_rnum.get().strip(),
                "enable_dut": self._v_enable_dut.get(),
                "enable_ref": self._v_enable_ref.get(),
                "loops": int(self._v_loops.get()),
                "idle": int(self._v_idle.get()),
                "call": int(self._v_call.get()),
                "ring": int(self._v_ring.get()),
                "test_case": self._v_test_case.get().strip(),
                "log_path": self._v_log_path.get().strip() or ".",
                "sync": self._v_sync.get(),
                "uppercase": self._v_uppercase.get(),
            }

            if not c["enable_dut"] and not c["enable_ref"]:
                messagebox.showwarning("Configuration Error",
                    "Enable at least one pair (DUT or REF) before starting.")
                return None

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

            for key in ("loops", "idle", "call", "ring"):
                if c[key] <= 0:
                    messagebox.showwarning("Configuration Error",
                        f"{key.capitalize()} must be a positive integer.")
                    return None

            return c

        except ValueError:
            messagebox.showerror("Configuration Error",
                "Invalid configuration value. Please check that all numeric fields contain valid numbers.")
            return None
        except Exception as e:
            messagebox.showerror("Configuration Error",
                f"Error reading configuration: {str(e)}")
            return None

    def apply_config(self, c):
        """Apply configuration from dict to global config module."""
        cfg.DEVICES["dut_MO"]    = c["dut_MO"]
        cfg.DEVICES["dut_MT"]    = c["dut_MT"]
        cfg.DEVICES["ref_MO"]       = c["ref_MO"]
        cfg.DEVICES["ref_MT"]       = c["ref_MT"]
        cfg.PHONE_NUMBERS["dut"] = c["dut_num"]
        cfg.PHONE_NUMBERS["ref"]    = c["ref_num"]
        cfg.LOOP_COUNT              = c["loops"]
        cfg.IDLE_SECONDS            = c["idle"]
        cfg.CALL_SECONDS            = c["call"]
        cfg.RINGING_TIMEOUT         = c["ring"]
        cfg.LOG_OUTPUT_PATH         = c["log_path"]
        cfg.CSV_OUTPUT_PATH         = os.path.join(c["log_path"], "results.csv")
        cfg.UPPERCASE_TEXT          = c["uppercase"]

    # ── persistence ────────────────────────────────────────────
    def _get_config_file_path(self):
        app_dir = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(app_dir, "..", "chorus_config.json")

    def load_persistent_config(self):
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

            except Exception:
                pass

    def save_persistent_config(self):
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
            }

            with open(config_file, "w") as f:
                json.dump(config, f, indent=2)
        except Exception:
            pass

    # ── test folder helpers ────────────────────────────────────
    def create_test_folder(self, test_case_name):
        """Create a unique test folder for the current test run."""
        sanitized_name = __import__('re').sub(r'[<>:"/\\|?*]', '_', test_case_name)
        sanitized_name = sanitized_name.strip()
        if not sanitized_name:
            sanitized_name = "TR-0000"

        timestamp = __import__('datetime').datetime.now().strftime("%Y%m%d_%H%M%S")
        folder_name = f"{sanitized_name}_{timestamp}"
        test_folder_path = os.path.join(cfg.LOG_OUTPUT_PATH, folder_name)
        os.makedirs(test_folder_path, exist_ok=True)
        return test_folder_path

    def create_timestamp_file(self, test_folder_path):
        """Create a timestamp TXT file in the test folder."""
        timestamp_file_path = os.path.join(test_folder_path, "timestamps.txt")
        now = __import__('datetime').datetime.now()
        with open(timestamp_file_path, "w", encoding="utf-8") as f:
            f.write("Chorus - Test Timestamps\n")
            f.write("=" * 40 + "\n")
            f.write(f"Test started: {now.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f.write("Cycle timestamps:\n")
            f.write("-" * 20 + "\n\n")
            f.write(f"{'LP':<10} - {'TIME':<10} - {'DUT_MO':<8} - {'DUT_MT':<8} - {'REF_MO':<8} - {'REF_MT'} - {'RAT':<6} - {'RSRP':<6} - {'RSRQ':<6} - {'SINR':<6} - {'BAND'}\n")
        return timestamp_file_path

    def append_cycle_to_timestamp_file(self, test_folder_path, cycle, signal_data=None, results=None):
        """Append cycle info to timestamps.txt."""
        timestamp_file_path = os.path.join(test_folder_path, "timestamps.txt")
        current_time = __import__('datetime').datetime.now().strftime('%H:%M:%S')

        if results:
            dut_r = results.get("dut", "–")
            ref_r = results.get("ref", "–")
        else:
            from main import _state
            dut_r = _state["dut"]["last_result"] if _state["dut"]["cycle"] >= cycle else "–"
            ref_r = _state["ref"]["last_result"] if _state["ref"]["cycle"] >= cycle else "–"

        def _norm(r):
            return r if r in ("PASS", "FAIL") else "–"
        dut_r = _norm(dut_r)
        ref_r = _norm(ref_r)

        sig_dut_mo = (signal_data or {}).get("dut_mo", {})
        sig_dut_mt = (signal_data or {}).get("dut_mt", {})
        sig_ref_mo = (signal_data or {}).get("ref_mo", {})
        sig_ref_mt = (signal_data or {}).get("ref_mt", {})

        dut_mo_rat = str(sig_dut_mo.get("rat", "N/A"))
        dut_mt_rat = str(sig_dut_mt.get("rat", "N/A"))
        ref_mo_rat = str(sig_ref_mo.get("rat", "N/A"))
        ref_mt_rat = str(sig_ref_mt.get("rat", "N/A"))

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

    def save_device_info(self, test_folder_path, c):
        """Save device information and test configuration to a file."""
        device_info_path = os.path.join(test_folder_path, "device_info.txt")
        now = __import__('datetime').datetime.now()
        with open(device_info_path, "w", encoding="utf-8") as f:
            f.write("Chorus - Device Information\n")
            f.write("=" * 40 + "\n")
            f.write(f"Test started: {now.strftime('%Y-%m-%d %H:%M:%S')}\n\n")

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
            f.write(f"Synchronized testing: {c['sync']}\n")
            f.write(f"Uppercase text: {c['uppercase']}\n")

        return device_info_path
