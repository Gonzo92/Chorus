# ============================================================
#  Call Automator v1.0  –  device_picker.py
#  Scans connected ADB devices and lets the user assign each
#  to one of the four roles: dut_MO, dut_MT, ref_MO, ref_MT
# ============================================================

import subprocess
import threading
import tkinter as tk
from tkinter import ttk, messagebox

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
MONO    = "Consolas"
SANS    = "Segoe UI"

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

    def __init__(self, parent, prefill: dict | None = None):
        super().__init__(parent)
        self.title("Device Picker — Call Automator")
        self.configure(bg=BG)
        self.resizable(False, False)
        self.grab_set()          # modal
        self.result = None
        self._devices: list[dict] = []
        self._prefill = prefill or {}

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
                        fieldbackground=BG3, font=(SANS, 10), relief="flat")
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

    # ── UI ───────────────────────────────────────────────────
    def _build_ui(self):
        # ── header ───────────────────────────────────────────
        hdr = tk.Frame(self, bg=BG2, height=44)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        tk.Label(hdr, text="  🔌  ADB Device Picker",
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
                         fieldbackground=BG2, rowheight=24,  # Increased row height
                         font=(MONO, 10))  # Larger font
        style.configure("Treeview.Heading", background=BG3,
                         foreground=FG, font=(SANS, 10, "bold"))  # Brighter heading text
        style.map("Treeview", background=[("selected", BLUE_SEL := "#2a4a7f")],  # Brighter selection
                  foreground=[("selected", "white")])  # White text when selected

        self._tree.pack(fill="x", padx=4, pady=(4, 2))

        self._tree.tag_configure("online", foreground=GREEN, font=(MONO, 10, "bold"))
        self._tree.tag_configure("offline", foreground=RED, font=(MONO, 10, "bold"))
        self._tree.tag_configure("unauth", foreground=YELLOW, font=(MONO, 10, "bold"))

        scan_row = tk.Frame(list_frame, bg=BG)
        scan_row.pack(fill="x", padx=4, pady=(0, 4))
        self._btn_scan = ttk.Button(scan_row, text="🔄  Refresh",
                                     style="Scan.TButton",
                                     command=self._do_scan)
        self._btn_scan.pack(side="left")
        self._lbl_scan_status = tk.Label(scan_row, text="Scanning…",
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

        tk.Frame(role_frame, bg=BG, height=4).pack()

        # ── direction reminder ───────────────────────────────
        hint = tk.Frame(body, bg=BG3, padx=10, pady=6)
        hint.pack(fill="x", pady=(0, 8))
        tk.Label(hint,
                 text="ℹ   MO (caller)  →  MT (answerer).  Direction is fixed in both pairs.",
                 font=(SANS, 9), bg=BG3, fg=FG_DIM).pack(anchor="w")

        # ── buttons ──────────────────────────────────────────
        btn_row = tk.Frame(body, bg=BG)
        btn_row.pack(fill="x")
        ttk.Button(btn_row, text="Cancel",
                   command=self.destroy).pack(side="right", padx=(4, 0))
        self._btn_confirm = ttk.Button(btn_row, text="✔  Confirm & Apply",
                                        style="Confirm.TButton",
                                        command=self._do_confirm)
        self._btn_confirm.pack(side="right")

    def _add_role_row(self, parent, role: str):
        color = ROLE_COLORS[role]
        f = tk.Frame(parent, bg=BG)
        f.pack(fill="x", padx=8, pady=3)

        tk.Label(f, text=f"●", font=(MONO, 9), bg=BG, fg=color).pack(side="left")
        tk.Label(f, text=f"  {ROLE_LABELS[role]:<34}",
                 font=(MONO, 9), bg=BG, fg=FG).pack(side="left")

        var = tk.StringVar(value=self._prefill.get(role, "— not assigned —"))
        self._role_vars[role] = var

        combo = ttk.Combobox(f, textvariable=var, font=(MONO, 9),
                              state="readonly", width=26)
        combo.pack(side="left", padx=(6, 0))
        self._role_combos[role] = combo

    # ── scan ─────────────────────────────────────────────────
    def _do_scan(self):
        self._lbl_scan_status.configure(text="Scanning…", fg=FG_DIM)
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
            status_icon = {"device": "✅ online",
                           "unauthorized": "⚠ unauth",
                           "offline": "❌ offline"}.get(d["status"], d["status"])
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
        options = ["— not assigned —"] + online_serials
        for role, combo in self._role_combos.items():
            combo["values"] = options
            # keep current value if still valid, else reset
            if self._role_vars[role].get() not in options:
                self._role_vars[role].set(options[0])

        # auto-assign if exactly 2 or 4 devices
        if online_serials and not any(
            v.get() != "— not assigned —"
            for v in self._role_vars.values()
        ):
            self._auto_assign(online_serials)

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
        for role, var in self._role_vars.items():
            val = var.get()
            if val == "— not assigned —":
                messagebox.showwarning(
                    "Incomplete",
                    f"Role '{role}' has no device assigned.\n"
                    "Please assign all four roles before confirming.",
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
                "This is unusual – are you sure?",
                parent=self,
            ):
                return

        self.result = result
        self.destroy()
