# ============================================================
#  Chorus v2.1  –  gui/device_controls.py
#  SIM stack control tiles — per-device DATA/CALL/SMS/IMS
# ============================================================

from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import subprocess
import threading
import time
from datetime import datetime


# ── theme ────────────────────────────────────────────────────
BG      = "#0f1117"
BG2     = "#2a2d3a"
BG3     = "#3a3e50"
FG      = "#ffffff"
FG_DIM  = "#b0b5c5"
BLUE    = "#6daaff"
GREEN   = "#5aff9d"
RED     = "#ff8585"
CYAN    = "#33e3ff"
YELLOW  = "#ffaa00"

# ── font detection ────────────────────────────────────────
def _detect_fonts():
    """Detect available fonts, return (mono_font, sans_font)."""
    try:
        families = tk.font.families()
    except Exception:
        families = set()
    mono = "Courier New"
    for f in ["Consolas", "Courier New", "Lucida Console", "DejaVu Sans Mono"]:
        if f in families:
            mono = f
            break
    sans = "Arial"
    for f in ["Segoe UI", "Arial", "Helvetica", "Tahoma", "Trebuchet MS"]:
        if f in families:
            sans = f
            break
    return mono, sans

MONO, SANS = _detect_fonts()


def scan_adb_devices() -> list[dict]:
    """Run `adb devices -l` and return a list of dicts with serial, status, model."""
    try:
        result = subprocess.run(
            ["adb", "devices", "-l"],
            capture_output=True, text=True, timeout=10
        )
        devices = []
        for line in result.stdout.splitlines()[1:]:
            parts = line.split()
            if len(parts) >= 2 and parts[1] == "device":
                serial = parts[0]
                model = "unknown"
                for p in parts:
                    if p.startswith("model:"):
                        model = p.split(":")[1]
                        break
                devices.append({"serial": serial, "status": "online", "model": model})
        return devices
    except Exception:
        return []


class ADBLogger:
    """ADB command logger that logs commands and responses."""

    def __init__(self, log_writer):
        self.log_writer = log_writer

    def log(self, message: str, level: str = "INFO"):
        """Log a message via the log_writer."""
        self.log_writer.log(message, level)

    def run(self, serial: str, *args, timeout: int = 5) -> tuple[int, str, str]:
        """Run ADB command and log it."""
        cmd = ["adb", "-s", serial, *args]
        cmd_str = " ".join(cmd)
        
        self.log_writer.log(f"> {cmd_str}", "INFO")
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
            output = result.stdout.strip() if result.stdout else "(empty)"
            error = result.stderr.strip() if result.stderr else ""
            
            if output and output != "(empty)":
                self.log_writer.log(f"< {output}", "OK")
            if error:
                self.log_writer.log(f"  ERR: {error}", "ERROR")
            
            return result.returncode, result.stdout.strip(), result.stderr.strip()
        except subprocess.TimeoutExpired:
            self.log_writer.log(f"< TIMEOUT", "ERROR")
            return -1, "", "timeout"
        except Exception as e:
            self.log_writer.log(f"< ERROR: {e}", "ERROR")
            return -1, "", str(e)


def _adb_log(serial: str, log_writer: ADBLogger, *args, timeout: int = 5) -> tuple[int, str, str]:
    """Run ADB command with logging."""
    return log_writer.run(serial, *args, timeout=timeout)


def _read_setting(serial: str, setting: str, adb_log: ADBLogger):
    """Read a global settings value with logging."""
    rc, output, _ = _adb_log(serial, adb_log, "shell", "settings", "get", "global", setting, timeout=5)
    if rc == 0 and output.strip().isdigit():
        val = int(output.strip())
        if val in (1, 2):
            return val
    return None


def _read_ims(serial: str, adb_log: ADBLogger):
    """Read IMS enabled state from ril.ims.ltevoicesupport property.
    Returns: 'on' if both SIMs enabled, 'off' if both disabled, 'mixed' if different, None if unknown.
    """
    rc, output, _ = _adb_log(serial, adb_log, "shell", "getprop", "ril.ims.ltevoicesupport", timeout=5)
    if rc == 0 and output.strip():
        parts = output.strip().split(",")
        if len(parts) == 2:
            s1 = parts[0].strip()
            s2 = parts[1].strip()
            if s1 == "1" and s2 == "1":
                return "on"
            elif s1 == "0" and s2 == "0":
                return "off"
            else:
                return "mixed"
    return None


def _write_setting(serial: str, setting: str, value: str, adb_log: ADBLogger):
    """Write a global settings value with logging."""
    rc, _, _ = _adb_log(serial, adb_log, "shell", "settings", "put", "global", setting, value, timeout=5)
    return rc == 0


def _verify_ims(serial: str, adb_log: ADBLogger):
    """Verify actual IMS state on device with logging."""
    rc, output, _ = _adb_log(serial, adb_log, "shell", "settings", "get", "global", "ims_enabled", timeout=5)
    if rc == 0 and output.strip() in ("0", "1"):
        actual = output.strip() == "1"
        return actual, actual
    return None, None


class LogWriter:
    """Console log writer with timestamps and colors."""

    def __init__(self, text_widget):
        self.text = text_widget

    def log(self, message: str, level: str = "INFO"):
        """Add a log line with timestamp and color."""
        ts = datetime.now().strftime("%H:%M:%S")
        color_map = {
            "INFO": FG_DIM,
            "OK": GREEN,
            "WARN": YELLOW,
            "ERROR": RED,
            "TS": CYAN,
        }
        color = color_map.get(level, FG)

        self.text.configure(state="normal")
        self.text.insert("end", f"[{ts}]  ", "ts")
        self.text.insert("end", message + "\n", level.lower())
        self.text.see("end")
        self.text.configure(state="disabled")

    def clear(self):
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.configure(state="disabled")


class DeviceControlsDialog(tk.Toplevel):
    """Modal dialog with per-device control tiles for DATA/CALL/SMS/IMS."""

    def __init__(self, parent):
        super().__init__(parent)
        self.title("SIM Controls — Chorus")
        self.configure(bg=BG)
        self.resizable(False, False)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self._tiles = {}
        self._devices = []

        self._configure_styles()
        self._build_ui()
        self._scan_devices()

        self.transient(parent)
        self.geometry(f"+{parent.winfo_x()+100}+{parent.winfo_y()+100}")

    def _configure_styles(self):
        s = ttk.Style(self)
        s.theme_use("clam")
        for w in ("TFrame", "TLabelframe", "TLabelframe.Label",
                  "TLabel", "TButton", "TEntry"):
            s.configure(w, background=BG, foreground=FG,
                        fieldbackground=BG3, bordercolor=BG3,
                        font=(SANS, 10), relief="flat")
        s.configure("TButton", padding=(10, 6), font=(SANS, 10, "bold"))
        s.configure("SIM.TButton", padding=(6, 3), font=(MONO, 9, "bold"))

    def _build_ui(self):
        # Header
        hdr = tk.Frame(self, bg=BG2, height=44)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        tk.Label(hdr, text="  SIM Stack Controls",
                 font=(SANS, 12, "bold"), bg=BG2, fg=BLUE).pack(side="left", padx=12, pady=10)
        tk.Label(hdr, text="— per-function SIM selection",
                 font=(SANS, 9), bg=BG2, fg=FG_DIM).pack(side="left", padx=4)

        # Refresh button
        self._btn_refresh = ttk.Button(hdr, text="🔄 Refresh",
                                       command=self._scan_devices)
        self._btn_refresh.pack(side="right", padx=12, pady=6)

        # ── Global IMS Toggle ────────────────────────────────
        ims_frame = tk.LabelFrame(self, text="  Global IMS / VoLTE Toggle  ", bg=BG,
                                  fg=BLUE, font=(SANS, 9, "bold"), bd=1, relief="groove")
        ims_frame.pack(fill="x", padx=10, pady=(10, 4))

        self._ims_toggle_var = tk.BooleanVar(value=False)
        self._ims_toggle_btn = tk.Button(ims_frame, text="IMS OFF", font=(MONO, 9, "bold"),
                                         bg=BG3, fg=FG, relief="flat", bd=0,
                                         padx=10, pady=4, width=10,
                                         command=self._toggle_global_ims)
        self._ims_toggle_btn.pack(side="left", padx=(10, 6), pady=6)

        self._ims_status = tk.Label(ims_frame, text="Checking...", font=(MONO, 8),
                                     bg=BG, fg=FG_DIM)
        self._ims_status.pack(side="left", padx=(0, 4), pady=6)

        self._ims_check_btn = tk.Button(ims_frame, text="🔍 Check IMS", font=(MONO, 8, "bold"),
                                         bg=BG3, fg=CYAN, relief="flat", bd=0,
                                         padx=6, pady=4,
                                         command=self._check_ims_all_devices)
        self._ims_check_btn.pack(side="left", padx=(0, 10), pady=6)

        # Tile container
        self._tile_frame = tk.Frame(self, bg=BG)
        self._tile_frame.pack(fill="both", expand=True, padx=10, pady=4)

        # Status label
        self._lbl_status = tk.Label(self, text="Scanning devices...",
                                     font=(SANS, 9), bg=BG, fg=FG_DIM)
        self._lbl_status.pack(pady=(4, 8))

        # ── Log Console ──────────────────────────────────────
        log_frame = tk.LabelFrame(self, text="  ADB Log Console  ", bg=BG,
                                  fg=FG_DIM, font=(SANS, 9), bd=1, relief="groove")
        log_frame.pack(fill="x", padx=10, pady=(0, 10))

        # Scrollable log text
        self._log_text = scrolledtext.ScrolledText(
            log_frame,
            bg=BG, fg=FG, font=(MONO, 8),
            relief="flat", bd=0, state="disabled", wrap="word",
            height=6, maxundo=1
        )
        self._log_text.pack(fill="x", padx=4, pady=4)

        # Tag configuration for colors
        self._log_text.tag_configure("info", foreground=FG_DIM)
        self._log_text.tag_configure("ok", foreground=GREEN)
        self._log_text.tag_configure("warn", foreground=YELLOW)
        self._log_text.tag_configure("error", foreground=RED)
        self._log_text.tag_configure("ts", foreground=CYAN)

        self._log_writer = LogWriter(self._log_text)
        self._adb_loggers = {}  # serial -> ADBLogger

        # Copy button
        self._btn_copy = tk.Button(log_frame, text="📋 Copy Log",
                                    font=(MONO, 8, "bold"), bg=BG3, fg=FG,
                                    relief="flat", bd=0, padx=8, pady=2,
                                    command=self._copy_log)
        self._btn_copy.pack(side="right", padx=4, pady=(0, 4))

    def _copy_log(self):
        """Copy log content to clipboard."""
        content = self._log_text.get("1.0", "end-1c")
        self.clipboard_clear()
        self.clipboard_append(content)
        self._btn_copy.configure(text="✓ Copied!", bg=GREEN, fg="#000000")
        self.after(1500, lambda: self._btn_copy.configure(text="📋 Copy Log", bg=BG3, fg=FG))

    def _create_tile(self, parent, device_info):
        """Create a single control tile for a device."""
        serial = device_info["serial"]
        model = device_info["model"]

        # Create ADB logger for this device
        self._adb_loggers[serial] = ADBLogger(self._log_writer)

        tile = tk.LabelFrame(parent, text=f"  {serial}  ",
                             bg=BG, fg=BLUE, font=(SANS, 9, "bold"),
                             bd=1, relief="groove", labelanchor="n")
        tile.pack(fill="x", pady=4)

        # Model label
        tk.Label(tile, text=f"  {model}", font=(SANS, 9),
                 bg=BG, fg=FG_DIM).pack(anchor="w", padx=8, pady=(4, 8))

        # Feature rows: DATA, CALL, SMS (IMS is now global)
        features = [
            ("DATA", "preferred_data_sim", True),
            ("CALL", "preferred_voice_sim", True),
            ("SMS", "preferred_sms_sim", True),
        ]

        tile_data = {}

        for name, setting, has_sim in features:
            row = tk.Frame(tile, bg=BG)
            row.pack(fill="x", padx=8, pady=2)

            # Feature label
            tk.Label(row, text=f"{name}:", font=(MONO, 9, "bold"),
                     bg=BG, fg=FG, width=8, anchor="w").pack(side="left")

            # Toggle ON/OFF
            toggle_var = tk.BooleanVar(value=False)
            toggle_btn = tk.Button(row, text="OFF", font=(MONO, 8, "bold"),
                                   bg=BG3, fg=FG, relief="flat", bd=0,
                                   padx=6, pady=2, width=5,
                                   command=lambda v=toggle_var, n=name: self._toggle_feature(v, n, tile_data.get(n, {})))
            toggle_btn.pack(side="left", padx=(0, 4))
            toggle_var.set(False)  # default OFF

            # IMS status label (only for IMS)
            ims_status = None
            if not has_sim:
                ims_status = tk.Label(row, text="", font=(MONO, 8),
                                      bg=BG, fg=FG_DIM, width=14, anchor="w")
                ims_status.pack(side="left", padx=(4, 0))

            # SIM1 / SIM2 buttons (only for DATA, CALL, SMS)
            sim1_btn = None
            sim2_btn = None
            if has_sim:
                sim1_btn = tk.Button(row, text="SIM1", font=(MONO, 8, "bold"),
                                     bg=BG3, fg=FG, relief="flat", bd=0,
                                     padx=6, pady=2, width=5,
                                     state="disabled",
                                     command=lambda s=serial, sl=1, st=setting: self._set_sim(s, sl, st, toggle_var, sim1_btn, sim2_btn))
                sim1_btn.pack(side="left", padx=(0, 2))

                sim2_btn = tk.Button(row, text="SIM2", font=(MONO, 8, "bold"),
                                     bg=BG3, fg=FG, relief="flat", bd=0,
                                     padx=6, pady=2, width=5,
                                     state="disabled",
                                     command=lambda s=serial, sl=2, st=setting: self._set_sim(s, sl, st, toggle_var, sim1_btn, sim2_btn))
                sim2_btn.pack(side="left", padx=(2, 0))

            tile_data[name] = {
                "toggle_var": toggle_var,
                "toggle_btn": toggle_btn,
                "ims_status": ims_status,
                "sim1_btn": sim1_btn,
                "sim2_btn": sim2_btn,
                "setting": setting,
                "has_sim": has_sim,
            }

        self._tiles[serial] = tile_data

        # Load current state in background
        self.after(10, lambda s=serial, t=tile_data: self._load_state(s, t))

        return tile_data

    def _load_state(self, serial, tile_data):
        """Load current device state and update UI."""
        adb_log = self._adb_loggers.get(serial)
        if not adb_log:
            return

        state = self._read_all_state(serial, adb_log)

        def show():
            for name, info in tile_data.items():
                sim_val = state.get(name.lower() + "_sim")
                if sim_val is not None:
                    info["toggle_var"].set(True)
                    self._update_toggle_button(info["toggle_btn"], True)
                    self._update_sim_buttons(info["sim1_btn"], info["sim2_btn"], sim_val)
                else:
                    info["toggle_var"].set(False)

        self.after(0, show)

    def _read_all_state(self, serial, adb_log):
        """Read all device settings."""
        state = {}
        state["data_sim"] = _read_setting(serial, "preferred_data_sim", adb_log)
        state["call_sim"] = _read_setting(serial, "preferred_voice_sim", adb_log)
        state["sms_sim"] = _read_setting(serial, "preferred_sms_sim", adb_log)
        state["ims_enabled"] = _read_ims(serial, adb_log)
        return state

    def _get_ims_ril_state(self, serial, adb_log):
        """Quick read of ril.ims.ltevoicesupport for status display."""
        rc, output, _ = _adb_log(serial, adb_log, "shell", "getprop", "ril.ims.ltevoicesupport", timeout=5)
        if rc == 0 and output.strip():
            parts = output.strip().split(",")
            if len(parts) == 2:
                s1, s2 = parts[0].strip(), parts[1].strip()
                if s1 == "1" and s2 == "1":
                    return "on"
                elif s1 == "0" and s2 == "0":
                    return "off"
                else:
                    return "mixed"
        return None

    def _toggle_feature(self, toggle_var, name, info):
        """Toggle ON/OFF for a feature (DATA, CALL, SMS only)."""
        current = toggle_var.get()
        new_val = not current
        toggle_var.set(new_val)
        self._update_toggle_button(info["toggle_btn"], new_val)

        # Enable/disable SIM buttons
        if info.get("has_sim"):
            state = "normal" if new_val else "disabled"
            info["sim1_btn"].configure(state=state)
            info["sim2_btn"].configure(state=state)

    def _update_ims_status(self, serial, info, ims_val):
        """Update IMS status label with current state (on/off/mixed)."""
        if info.get("ims_status"):
            if ims_val == "on":
                info["ims_status"].configure(text="ON ✓", fg=GREEN)
            elif ims_val == "off":
                info["ims_status"].configure(text="OFF ✓", fg=GREEN)
            elif ims_val == "mixed":
                info["ims_status"].configure(text="MIXED ⚠", fg=YELLOW)
            else:
                info["ims_status"].configure(text="unknown", fg=FG_DIM)

    def _update_toggle_button(self, btn, is_on):
        """Update toggle button appearance."""
        if is_on:
            btn.configure(text="ON", bg=GREEN, fg="#000000")
        else:
            btn.configure(text="OFF", bg=BG3, fg=FG)

    def _update_sim_buttons(self, sim1_btn, sim2_btn, active_sim):
        """Update SIM button appearance based on active slot."""
        if sim1_btn is None or sim2_btn is None:
            return  # IMS feature has no SIM buttons
        if active_sim == 1:
            sim1_btn.configure(bg=BLUE, fg="white")
            sim2_btn.configure(bg=BG3, fg=FG)
        else:
            sim2_btn.configure(bg=BLUE, fg="white")
            sim1_btn.configure(bg=BG3, fg=FG)

    def _set_sim(self, serial, slot, setting, toggle_var, sim1_btn, sim2_btn):
        """Set SIM slot for a feature."""
        feature_name = setting.replace("preferred_", "").replace("_sim", "").upper()
        adb_log = self._adb_loggers.get(serial)

        def task():
            if not adb_log:
                return

            success = _write_setting(serial, setting, str(slot), adb_log)

            def show():
                if success:
                    self._update_sim_buttons(sim1_btn, sim2_btn, slot)
                else:
                    pass
            self.after(0, show)

        threading.Thread(target=task, daemon=True).start()

    def _scan_devices(self):
        """Scan for ADB devices and update tiles."""
        self._btn_refresh.configure(state="disabled")
        self._log_writer.log("Scanning ADB devices...", "INFO")

        def task():
            devices = scan_adb_devices()
            self._devices = devices

            def show():
                # Clear existing tiles
                for widget in self._tile_frame.winfo_children():
                    widget.destroy()
                self._tiles.clear()
                self._adb_loggers.clear()

                if not devices:
                    self._lbl_status.configure(text="No ADB devices connected", fg=RED)
                    self._log_writer.log("No ADB devices found", "WARN")
                    return

                self._lbl_status.configure(text=f"{len(devices)} device(s) found", fg=GREEN)
                self._log_writer.log(f"Found {len(devices)} device(s): {', '.join(d['serial'] for d in devices)}", "OK")

                for dev in devices:
                    self._create_tile(self._tile_frame, dev)

            self.after(0, show)
            self.after(0, lambda: self._btn_refresh.configure(state="normal"))

        threading.Thread(target=task, daemon=True).start()

    # ── Global IMS Toggle ──────────────────────────────────

    def _toggle_global_ims(self):
        """Toggle IMS ON/OFF for all connected devices."""
        current = self._ims_toggle_var.get()
        new_val = not current
        self._ims_toggle_var.set(new_val)
        self._ims_toggle_btn.configure(text=f"IMS {'ON' if new_val else 'OFF'}",
                                        bg=GREEN if new_val else BG3,
                                        fg="#000000" if new_val else FG)
        self._ims_status.configure(text="applying...", fg=YELLOW)

        # Toggle on all devices in background
        threading.Thread(target=self._apply_ims_all, args=(new_val,), daemon=True).start()

    def _apply_ims_all(self, enable):
        """Apply IMS toggle to all connected devices."""
        from core.adb_controller import toggle_volte_adaptive

        success_count = 0
        total = len(self._devices)

        for dev in self._devices:
            serial = dev["serial"]
            adb_log = self._adb_loggers.get(serial)
            if not adb_log:
                continue

            try:
                result = toggle_volte_adaptive(serial, enable, adb_log)
                if result["success"]:
                    success_count += 1
            except Exception:
                pass

        def show():
            if success_count == total:
                self._ims_status.configure(text=f"ON ✓ ({total}/{total})", fg=GREEN)
            elif success_count > 0:
                self._ims_status.configure(text=f"Partial ({success_count}/{total})", fg=YELLOW)
            else:
                self._ims_status.configure(text="Failed", fg=RED)
                # Revert toggle
                self._ims_toggle_var.set(not enable)
                self._ims_toggle_btn.configure(text=f"IMS {'ON' if enable else 'OFF'}",
                                                bg=BG3, fg=FG)

        self.after(0, show)

    def _check_ims_all_devices(self):
        """Check IMS state on all devices and display status."""
        self._ims_status.configure(text="Checking...", fg=CYAN)

        def task():
            from core.adb_controller import verify_ims_state

            results = []
            for dev in self._devices:
                serial = dev["serial"]
                adb_log = self._adb_loggers.get(serial)
                if not adb_log:
                    results.append((serial, "no logger"))
                    continue

                try:
                    state = verify_ims_state(serial)
                    setting = state.get("setting")
                    registered = state.get("registered")

                    if setting is True and registered is True:
                        results.append((serial, "ON ✓"))
                    elif setting is False and registered is False:
                        results.append((serial, "OFF ✓"))
                    else:
                        results.append((serial, "unknown"))
                except Exception:
                    results.append((serial, "error"))

            def show():
                on_count = sum(1 for _, s in results if "ON" in s)
                off_count = sum(1 for _, s in results if "OFF" in s)
                total = len(results)

                if on_count == total:
                    self._ims_status.configure(text=f"ALL ON ✓ ({total})", fg=GREEN)
                    self._ims_toggle_var.set(True)
                    self._ims_toggle_btn.configure(text="IMS ON", bg=GREEN, fg="#000000")
                elif off_count == total:
                    self._ims_status.configure(text=f"ALL OFF ✓ ({total})", fg=GREEN)
                    self._ims_toggle_var.set(False)
                    self._ims_toggle_btn.configure(text="IMS OFF", bg=BG3, fg=FG)
                else:
                    self._ims_status.configure(text=f"Mixed ({on_count} ON, {off_count} OFF)", fg=YELLOW)

                for serial, status in results:
                    self._log_writer.log(f"  {serial}: {status}", "OK" if "✓" in status else "WARN")

            self.after(0, show)

        threading.Thread(target=task, daemon=True).start()

    def _on_close(self):
        self.destroy()
