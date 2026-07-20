# ============================================================
#  Chorus v2.6  –  gui/device_picker.py
#  Scans connected ADB devices and lets the user assign each
#  to one of the four roles: dut_MO, dut_MT, ref_MO, ref_MT
# ============================================================

from __future__ import annotations

import os
import re
import subprocess
import threading
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

# ── theme (mirrors main.py) ───────────────────────────────
BG      = "#0f1117"
BG2     = "#2a2d3a"  # Lighter background for better contrast
BG3     = "#3a3e50"  # Even lighter for better contrast
FG      = "#ffffff"  # Bright white text
FG_DIM  = "#b0b5c5"  # Lighter dimmed text
BLUE    = "#6daaff"  # Brighter blue
YELLOW  = "#8a440b"  # Darker amber/brown color
GREEN   = "#5aff9d"  # Brighter green
RED     = "#ff8585"  # Brighter red
CYAN    = "#33e3ff"  # Brighter cyan
PURPLE  = "#d094ff"  # Brighter purple

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

ROLES = ["dut_MO", "dut_MT", "ref_MO", "ref_MT"]
ROLE_COLORS = {
    "dut_MO": BLUE,
    "dut_MT": BLUE,
    "ref_MO":    YELLOW,
    "ref_MT":    YELLOW,
}
ROLE_LABELS = {
    "dut_MO": "DUT  MO  (caller)",
    "dut_MT": "DUT  MT  (answerer)",
    "ref_MO":    "REF  MO  (caller)",
    "ref_MT":    "REF  MT  (answerer)",
}

# ── ADB scanning ─────────────────────────────────────────

def scan_adb_devices() -> list[dict]:
    """
    Run `adb devices -l` and return a list of dicts:
      { serial, status, model, transport }
    """
    try:
        result = subprocess.run(
            ["adb", "devices", "-l"],
            capture_output=True, text=True, timeout=10,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return []

    devices = []
    for line in result.stdout.splitlines()[1:]:
        line = line.strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        serial = parts[0]
        status = parts[1]           # "device" | "unauthorized" | "offline"
        info = " ".join(parts[2:])  # "model:SM_G991B transport_id:1" etc.

        model = "unknown"
        for token in parts[2:]:
            if token.startswith("model:"):
                model = token.split(":", 1)[1].replace("_", " ")
                break

        devices.append({
            "serial":    serial,
            "status":    status,
            "model":     model,
            "info":      info,
        })
    return devices


# ═══════════════════════════════════════════════════════════
#  DIALOG
# ═══════════════════════════════════════════════════════════
class DevicePickerDialog(tk.Toplevel):
    """
    Modal dialog.  On confirm, self.result is a dict:
      { "dut_MO": serial, "dut_MT": serial,
        "ref_MO":    serial, "ref_MT":    serial }
    or None if the user cancelled.
    """

    def __init__(self, parent, prefill: dict | None = None, enabled_pairs: list[str] | None = None):
        super().__init__(parent)
        self.title("Device Picker — Call Automator")
        self.configure(bg=BG)
        self.resizable(False, False)
        self.grab_set()          # modal
        self.result = None
        self._devices: list[dict] = []
        self._prefill = prefill or {}
        self._apk_paths: list[str] = []  # list of selected APK file paths
        self._enabled_pairs = set(enabled_pairs) if enabled_pairs else {"dut", "ref"}

        self._configure_styles()
        self._build_ui()

        self.transient(parent)
        self.geometry(f"+{parent.winfo_x()+60}+{parent.winfo_y()+60}")
        self.after(100, self._do_scan)   # auto-scan on open

    # ── styles ───────────────────────────────────────────────
    def _configure_styles(self):
        s = ttk.Style(self)
        for w in ("TFrame", "TLabel", "TButton", "TCombobox",
                  "TLabelframe", "TLabelframe.Label"):
            s.configure(w, background=BG, foreground=FG,
                        fieldbackground=BG2, font=(SANS, 10), relief="flat")
        s.configure("TButton", padding=(8, 5))
        s.map("TButton",
              background=[("active", BG3), ("!active", BG2)],
              foreground=[("active", FG)])
        s.configure("Scan.TButton", background=BG3, foreground=CYAN)
        s.map("Scan.TButton", background=[("active", "#0e3a4a")])
        s.configure("Confirm.TButton", background=BLUE, foreground="white")
        s.map("Confirm.TButton", background=[("active", "#2563eb"),
                                               ("disabled", BG3)],
              foreground=[("disabled", FG_DIM)])
        # Dark mode for combobox dropdown popup on Windows
        s.configure("ComboboxListbox",
                    background=BG2,
                    foreground=FG,
                    selectbackground=BLUE,
                    selectforeground="white")

    # ── UI ───────────────────────────────────────────────────
    def _build_ui(self):
        # ── header ───────────────────────────────────────────
        hdr = tk.Frame(self, bg=BG2, height=44)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        tk.Label(hdr, text="  ADB Device Picker",
                 font=(SANS, 12, "bold"), bg=BG2, fg=FG).pack(side="left", padx=10, pady=8)
        self._lbl_count = tk.Label(hdr, text="", font=(MONO, 9),
                                   bg=BG2, fg=FG_DIM)
        self._lbl_count.pack(side="right", padx=12)

        body = tk.Frame(self, bg=BG)
        body.pack(fill="both", padx=12, pady=8)

        # ── device list ──────────────────────────────────────
        list_frame = tk.LabelFrame(body, text="  Connected devices  ",
                                   bg=BG, fg=CYAN, font=(SANS, 9),
                                   bd=1, relief="groove")
        list_frame.pack(fill="x", pady=(0, 10))

        cols = ("serial", "model", "status")
        self._tree = ttk.Treeview(list_frame, columns=cols,
                                   show="headings", height=5,
                                   selectmode="browse")
        self._tree.heading("serial", text="Serial")
        self._tree.heading("model",  text="Model")
        self._tree.heading("status", text="Status")
        self._tree.column("serial", width=160, anchor="w")
        self._tree.column("model",  width=200, anchor="w")
        self._tree.column("status", width=100, anchor="center")

        # treeview colours
        style = ttk.Style(self)
        style.configure("Treeview", background=BG2, foreground=FG,
                         fieldbackground=BG2, rowheight=24,
                         font=(MONO, 10))
        style.configure("Treeview.Heading", background=BG3,
                         foreground=FG, font=(SANS, 10, "bold"))
        style.map("Treeview", background=[("selected", BLUE_SEL := "#2a4a7f")],
                   foreground=[("selected", "white")])

        self._tree.pack(fill="x", padx=4, pady=(4, 2))

        self._tree.tag_configure("online", foreground=GREEN, font=(MONO, 10, "bold"))
        self._tree.tag_configure("offline", foreground=RED, font=(MONO, 10, "bold"))
        self._tree.tag_configure("unauth", foreground=YELLOW, font=(MONO, 10, "bold"))

        scan_row = tk.Frame(list_frame, bg=BG)
        scan_row.pack(fill="x", padx=4, pady=(0, 4))
        self._btn_scan = ttk.Button(scan_row, text="Refresh",
                                     style="Scan.TButton",
                                     command=self._do_scan)
        self._btn_scan.pack(side="left")
        self._lbl_scan_status = tk.Label(scan_row, text="Scanning...",
                                          font=(MONO, 9), bg=BG, fg=FG_DIM)
        self._lbl_scan_status.pack(side="left", padx=8)

        # ── role assignment ──────────────────────────────────
        role_frame = tk.LabelFrame(body, text="  Assign roles  ",
                                    bg=BG, fg=BLUE, font=(SANS, 9),
                                    bd=1, relief="groove")
        role_frame.pack(fill="x", pady=(0, 10))

        self._role_vars: dict[str, tk.StringVar] = {}
        self._role_combos: dict[str, ttk.Combobox] = {}

        # DUT section
        tk.Frame(role_frame, bg=BG3, height=1).pack(fill="x", padx=6, pady=(6, 0))
        tk.Label(role_frame, text="  DUT pair",
                 font=(SANS, 9, "bold"), bg=BG, fg=BLUE).pack(anchor="w", padx=8, pady=(4, 0))

        for role in ("dut_MO", "dut_MT"):
            self._add_role_row(role_frame, role)

        tk.Frame(role_frame, bg=BG3, height=1).pack(fill="x", padx=6, pady=(6, 0))
        tk.Label(role_frame, text="  REF pair",
                 font=(SANS, 9, "bold"), bg=BG, fg=YELLOW).pack(anchor="w", padx=8, pady=(4, 0))

        for role in ("ref_MO", "ref_MT"):
            self._add_role_row(role_frame, role)

        # ── GPS source selector ──────────────────────────────
        gps_frame = tk.LabelFrame(body, text="  GPS source  ",
                                   bg=BG, fg=GREEN, font=(SANS, 9),
                                   bd=1, relief="groove")
        gps_frame.pack(fill="x", pady=(0, 10))

        self._gps_var = tk.StringVar(value=self._prefill.get("gps_source", "not set"))
        self._gps_combo = ttk.Combobox(gps_frame, textvariable=self._gps_var,
                                        font=(MONO, 9), state="readonly", width=40)
        self._gps_combo.pack(fill="x", padx=8, pady=(6, 8))

        # ── APK installer tile ───────────────────────────────
        apk_frame = tk.LabelFrame(body, text="  APK Installer  ",
                                   bg=BG, fg=GREEN, font=(SANS, 9),
                                   bd=1, relief="groove")
        apk_frame.pack(fill="x", pady=(0, 10))

        # APK list (scrollable)
        list_frame = tk.Frame(apk_frame, bg=BG)
        list_frame.pack(fill="both", expand=True, padx=6, pady=(6, 2))

        self._apk_listbox = tk.Listbox(list_frame, bg=BG2, fg=FG,
                                        font=(MONO, 9), height=4,
                                        selectbackground=BLUE,
                                        selectforeground="white",
                                        activestyle="none",
                                        highlightthickness=0,
                                        relief="flat",
                                        bd=1)
        self._apk_listbox.pack(side="left", fill="both", expand=True, padx=(0, 0))

        apk_scroll = ttk.Scrollbar(list_frame, orient="vertical",
                                    command=self._apk_listbox.yview)
        apk_scroll.pack(side="right", fill="y")
        self._apk_listbox.configure(yscrollcommand=apk_scroll.set)
        self._apk_listbox.bind('<<ListboxSelect>>', lambda e: self._on_apk_select())

        # Action buttons
        apk_btn_row = tk.Frame(apk_frame, bg=BG)
        apk_btn_row.pack(fill="x", padx=6, pady=(0, 6))

        tk.Button(apk_btn_row, text="  Add APK", font=(MONO, 8), bg=BG2,
                   fg=CYAN, relief="flat",
                   command=self._add_apk_file).pack(side="left")

        tk.Button(apk_btn_row, text="  Remove", font=(MONO, 8), bg=BG2,
                   fg=FG_DIM, relief="flat",
                   command=self._remove_apk).pack(side="left", padx=(4, 0))

        self._btn_install = tk.Button(apk_btn_row, text="  Install", font=(MONO, 8, "bold"), bg=BG3,
                  fg=GREEN, relief="flat", bd=1,
                  command=self._install_selected_apk)
        self._btn_install.pack(side="left", padx=(4, 0))
        self._btn_install.configure(state="disabled")

        # Drag-and-drop zone
        self._apk_drop_zone = tk.Frame(apk_frame, bg=BG3, height=28)
        self._apk_drop_zone.pack(fill="x", padx=6, pady=(0, 4))
        self._apk_drop_zone.pack_propagate(False)
        tk.Label(self._apk_drop_zone,
                 text="  Drag & drop APK file here",
                 font=(MONO, 8), bg=BG3, fg=FG_DIM).pack()
        self._apk_drop_zone.bind("<Enter>",
                                  lambda e: self._apk_drop_zone.configure(bg=BG2))
        self._apk_drop_zone.bind("<Leave>",
                                  lambda e: self._apk_drop_zone.configure(bg=BG3))
        # ── drag & drop for APK files ──────────────────────────────
        try:
            self._apk_drop_zone.drop_target_register(tk.DND_FILES)
            self._apk_drop_zone.dnd_bind("Drop", self._on_drop_apk)
        except AttributeError:
            pass  # DnD not available on this platform

        tk.Frame(role_frame, bg=BG, height=4).pack()

        # ── direction reminder ───────────────────────────────
        hint = tk.Frame(body, bg=BG3, padx=10, pady=6)
        hint.pack(fill="x", pady=(0, 8))
        tk.Label(hint,
                 text="MO (caller) -> MT (answerer).  Direction is fixed in both pairs.",
                 font=(SANS, 9), bg=BG3, fg=FG_DIM).pack(anchor="w")

        # ── buttons ──────────────────────────────────────────
        btn_row = tk.Frame(body, bg=BG)
        btn_row.pack(fill="x")
        ttk.Button(btn_row, text="Cancel",
                   command=self.destroy).pack(side="right", padx=(4, 0))
        self._btn_confirm = ttk.Button(btn_row, text="Confirm & Apply",
                                        style="Confirm.TButton",
                                        command=self._do_confirm)
        self._btn_confirm.pack(side="right")

    def _add_role_row(self, parent, role: str):
        color = ROLE_COLORS[role]
        f = tk.Frame(parent, bg=BG)
        f.pack(fill="x", padx=8, pady=3)

        tk.Label(f, text="o", font=(MONO, 9), bg=BG, fg=color).pack(side="left")
        tk.Label(f, text=f"  {ROLE_LABELS[role]:<34}",
                 font=(MONO, 9), bg=BG, fg=FG).pack(side="left")

        var = tk.StringVar(value=self._prefill.get(role, "not assigned"))
        self._role_vars[role] = var

        combo = ttk.Combobox(f, textvariable=var, font=(MONO, 9),
                              state="readonly", width=26)
        combo.pack(side="left", padx=(6, 0))
        self._role_combos[role] = combo

    # ── scan ─────────────────────────────────────────────────
    def _do_scan(self):
        self._lbl_scan_status.configure(text="Scanning...", fg=FG_DIM)
        self._btn_scan.configure(state="disabled")

        def task():
            devices = scan_adb_devices()
            self.after(0, lambda: self._populate(devices))

        threading.Thread(target=task, daemon=True).start()

    def _populate(self, devices: list[dict]):
        self._devices = devices

        # clear tree
        for item in self._tree.get_children():
            self._tree.delete(item)

        # fill tree
        online_serials = []
        for d in devices:
            tag = {"device": "online", "unauthorized": "unauth"}.get(d["status"], "offline")
            status_icon = {"device": "online",
                           "unauthorized": "unauth",
                           "offline": "offline"}.get(d["status"], d["status"])
            self._tree.insert("", "end",
                               values=(d["serial"], d["model"], status_icon),
                               tags=(tag,))
            if d["status"] == "device":
                online_serials.append(d["serial"])

        count = len(devices)
        online = len(online_serials)
        self._lbl_count.configure(
            text=f"{count} device(s) found  /  {online} online")
        self._lbl_scan_status.configure(
            text=f"Found {count} device(s)" if count else "No devices detected",
            fg=GREEN if online else RED,
        )
        self._btn_scan.configure(state="normal")

        # update combobox options
        options = ["not assigned"] + online_serials
        for role, combo in self._role_combos.items():
            combo["values"] = options
            if self._role_vars[role].get() not in options:
                self._role_vars[role].set(options[0])

# GPS source combobox
        gps_options = ["not set"] + online_serials
        self._gps_combo["values"] = gps_options
        if self._gps_var.get() not in gps_options:
            self._gps_var.set(gps_options[0])

        # auto-assign if exactly 2 or 4 devices
        if online_serials and not any(
            v.get() != "not assigned"
            for v in self._role_vars.values()
        ):
            self._auto_assign(online_serials)

    # ── APK management ───────────────────────────────────────
    def _add_apk_file(self):
        """Open file dialog to select APK file(s)."""
        paths = filedialog.askopenfilenames(
            parent=self,
            title="Select APK File(s)",
            filetypes=[("Android APK", "*.apk"), ("All files", "*.*")],
        )
        if paths:
            for p in paths:
                if p not in self._apk_paths:
                    self._apk_paths.append(p)
            self._refresh_apk_list()

    def _remove_apk(self):
        """Remove selected APK from the list."""
        sel = self._apk_listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        if 0 <= idx < len(self._apk_paths):
            self._apk_paths.pop(idx)
            self._refresh_apk_list()

    def _install_selected_apk(self):
        """Install the selected APK on all devices."""
        sel = self._apk_listbox.curselection()
        if not sel:
            return
        
        self._selected_apk_path = self._apk_paths[sel[0]]
        apk_path = self._selected_apk_path
        if not apk_path or not os.path.isfile(apk_path):
            messagebox.showerror("Error", f"APK file not found:\n{apk_path}", parent=self)
            return
        
        serials = [v.get() for v in self._role_vars.values() if v.get() not in ("not assigned",)]
        if not serials:
            messagebox.showwarning("No Devices", "Assign devices first before installing APK.", parent=self)
            return
        
        self._btn_install.configure(state="disabled", text="  Installing...")
        self._apk_listbox.configure(state="disabled")
        
        def install_task():
            from core.adb_controller import install_apk
            results = []
            for serial in serials:
                ok, msg = install_apk(serial, apk_path, replace=True)
                results.append((serial, ok, msg))
            
            self.after(0, lambda: self._show_install_results(results))
        
        threading.Thread(target=install_task, daemon=True).start()

    def _show_install_results(self, results):
        """Show APK installation results."""
        self._btn_install.configure(text="  Install", state="normal")
        self._apk_listbox.configure(state="normal")
        
        installed = sum(1 for _, ok, _ in results if ok)
        total = len(results)
        apk_path = self._selected_apk_path
        
        for serial, ok, msg in results:
            status = "OK" if ok else f"FAIL: {msg}"
            self.after(0, lambda s=serial, m=status: self._log_install_status(s, m))
        
        if installed == total:
            messagebox.showinfo("Installation Complete", 
                f"APK installed successfully on all {total} devices!\n\n"
                f"File: {os.path.basename(apk_path)}", 
                parent=self)
        else:
            failed = [r[0] for r in results if not r[1]]
            messagebox.showwarning("Installation Partial", 
                f"APK installed on {installed}/{total} devices.\n\n"
                f"Failed on: {', '.join(failed)}", 
                parent=self)

    def _log_install_status(self, serial, status):
        """Log installation status to parent's log (if available)."""
        try:
            if hasattr(self, '_parent_log'):
                self._parent_log(f"APK install {'OK' if 'OK' in status else 'FAIL'}: {serial} - {status}")
        except Exception:
            pass

    def _on_apk_select(self):
        """Handle APK listbox selection change."""
        sel = self._apk_listbox.curselection()
        self._btn_install.configure(state="normal" if sel else "disabled")

    def _on_drop_apk(self, event):
        """Handle drag-and-drop of APK file(s)."""
        raw = str(event.data).strip("{}")
        # tkinter DND_FILES may return multiple files separated by braces
        # or a single file. Handle both cases.
        if raw.startswith("{") and raw.endswith("}"):
            # Multiple files: {file1}{file2}
            files = re.findall(r'\{([^}]+)\}', raw)
            for f in files:
                if f not in self._apk_paths:
                    self._apk_paths.append(f)
        else:
            self._apk_paths.append(raw)
        self._refresh_apk_list()
        # Hide drop zone after successful drop
        self._apk_drop_zone.pack_forget()

    def _refresh_apk_list(self):
        """Refresh the APK listbox with current paths."""
        self._apk_listbox.delete(0, tk.END)
        for path in self._apk_paths:
            name = os.path.basename(path)
            try:
                size_mb = os.path.getsize(path) / (1024 * 1024)
                display = f"{name} ({size_mb:.1f} MB)"
            except OSError:
                display = name
            self._apk_listbox.insert(tk.END, display)
        
        if self._apk_paths:
            sel = self._apk_listbox.curselection()
            self._btn_install.configure(state="normal" if sel else "disabled")
        else:
            self._btn_install.configure(state="disabled")

    def _auto_assign(self, serials: list[str]):
        """Best-effort auto-assignment when dialog opens with fresh devices."""
        if len(serials) == 4:
            for role, serial in zip(ROLES, serials):
                self._role_vars[role].set(serial)
        elif len(serials) == 2:
            # Two devices: assign both pairs to the same two serials
            self._role_vars["dut_MO"].set(serials[0])
            self._role_vars["dut_MT"].set(serials[1])
            self._role_vars["ref_MO"].set(serials[0])
            self._role_vars["ref_MT"].set(serials[1])

    # ── confirm ──────────────────────────────────────────────
    def _do_confirm(self):
        result = {}
        role_pair_map = {
            "dut_MO": "dut", "dut_MT": "dut",
            "ref_MO": "ref", "ref_MT": "ref",
        }
        for role, var in self._role_vars.items():
            val = var.get()
            pair = role_pair_map[role]
            if val == "not assigned" and pair in self._enabled_pairs:
                messagebox.showwarning(
                    "Incomplete",
                    f"Role '{role}' has no device assigned.\n"
                    "Please assign all required roles before confirming.",
                    parent=self,
                )
                return
            result[role] = val

        # warn about duplicate assignments
        serials = list(result.values())
        if len(set(serials)) < len(serials):
            if not messagebox.askyesno(
                "Duplicate assignment",
                "Some roles share the same serial.\n"
                "This is unusual - are you sure?",
                parent=self,
            ):
                return

        self.result = result
        self.result["gps_source"] = self._gps_var.get()
        self.result["apk_paths"] = list(self._apk_paths)
        self.destroy()
