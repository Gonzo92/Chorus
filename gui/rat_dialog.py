# ============================================================
#  Chorus v2.2  –  gui/rat_dialog.py
#  Dialog for setting Radio Access Technology (RAT) on devices
# ============================================================

from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox
import threading
from utils.rat_controller import set_rat_for_all_devices, RAT_VALUES
import config as cfg

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

# ═══════════════════════════════════════════════════════════
#  DIALOG
# ═══════════════════════════════════════════════════════════
class RatSettingsDialog(tk.Toplevel):
    """
    Modal dialog for setting RAT (Radio Access Technology) on devices.
    """

    def __init__(self, parent, devices: dict):
        super().__init__(parent)
        self.title("Ustawienia RAT — Chorus")
        self.configure(bg=BG)
        self.resizable(False, False)
        self.grab_set()          # modal
        self.devices = devices   # devices dictionary from main app
        self.result = None

        self._configure_styles()
        self._build_ui()

        self.transient(parent)
        self.geometry(f"+{parent.winfo_x()+60}+{parent.winfo_y()+60}")

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
        s.configure("Apply.TButton", background=BLUE, foreground="white")
        s.map("Apply.TButton", background=[("active", "#2563eb"),
                                              ("disabled", BG3)],
              foreground=[("disabled", FG_DIM)])

    # ── UI ───────────────────────────────────────────────────
    def _build_ui(self):
        # ── header ───────────────────────────────────────────
        hdr = tk.Frame(self, bg=BG2, height=44)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        tk.Label(hdr, text="  📶  Ustawienia RAT",
                 font=(SANS, 12, "bold"), bg=BG2, fg=FG).pack(side="left", padx=10, pady=8)

        body = tk.Frame(self, bg=BG)
        body.pack(fill="both", padx=12, pady=8)

        # ── SIM-1 settings ──────────────────────────────────────
        sim1_frame = tk.LabelFrame(body, text="  SIM-1  ",
                                   bg=BG, fg=BLUE, font=(SANS, 9),
                                   bd=1, relief="groove")
        sim1_frame.pack(fill="x", pady=(0, 10))

        self._add_sim_settings(sim1_frame, "sim1", "SIM-1")

        # ── SIM-2 settings ──────────────────────────────────────
        sim2_frame = tk.LabelFrame(body, text="  SIM-2  ",
                                   bg=BG, fg=YELLOW, font=(SANS, 9),
                                   bd=1, relief="groove")
        sim2_frame.pack(fill="x", pady=(0, 10))

        self._add_sim_settings(sim2_frame, "sim2", "SIM-2")

        # ── buttons ──────────────────────────────────────────
        btn_row = tk.Frame(body, bg=BG)
        btn_row.pack(fill="x")
        ttk.Button(btn_row, text="Anuluj",
                   command=self.destroy).pack(side="right", padx=(4, 0))
        self._btn_apply = ttk.Button(btn_row, text="✔  Zastosuj",
                                     style="Apply.TButton",
                                     command=self._do_apply)
        self._btn_apply.pack(side="right")

        # ── status ───────────────────────────────────────────
        self._status_frame = tk.Frame(body, bg=BG)
        self._status_frame.pack(fill="x", pady=(10, 0))
        self._status_label = tk.Label(self._status_frame, text="", font=(MONO, 9),
                                      bg=BG, fg=FG_DIM)
        self._status_label.pack(side="left")

    def _add_sim_settings(self, parent, var_prefix: str, label: str):
        f = tk.Frame(parent, bg=BG)
        f.pack(fill="x", padx=8, pady=8)

        tk.Label(f, text=label, font=(MONO, 9), bg=BG, fg=FG).pack(side="left")

        # Zmienna do przechowywania wyboru technologii
        var = tk.StringVar(value="5G/4G/3G/2G")
        setattr(self, f"{var_prefix}_var", var)

        # Combobox z dostępnymi technologiami
        combo = ttk.Combobox(f, textvariable=var, font=(MONO, 9),
                             state="readonly", width=20)
        combo["values"] = list(RAT_VALUES.keys())
        combo.pack(side="left", padx=(10, 0))

    # ── apply settings ──────────────────────────────────────────────
    def _do_apply(self):
        # Pobierz ustawienia dla obu SIM-ów
        sim1_setting = self.sim1_var.get()
        sim2_setting = self.sim2_var.get()
        
        # Przygotuj ustawienia SIM
        sim_settings = {
            0: sim1_setting,  # SIM-1
            1: sim2_setting   # SIM-2
        }
        
        # Wyłącz przycisk na czas operacji
        self._btn_apply.configure(state="disabled")
        self._status_label.configure(text="Ustawianie RAT...", fg=CYAN)
        self.update()
        
        # Uruchom operację w osobnym wątku, aby nie blokować UI
        def task():
            try:
                results = set_rat_for_all_devices(self.devices, sim_settings)
                self.after(0, lambda: self._on_apply_complete(results))
            except Exception as e:
                self.after(0, lambda: self._on_apply_error(str(e)))
        
        threading.Thread(target=task, daemon=True).start()

    def _on_apply_complete(self, results):
        """Wywoływane po zakończeniu ustawiania RAT."""
        # Włącz przycisk
        self._btn_apply.configure(state="normal")
        
        # Sprawdź wyniki i wyświetl odpowiedni komunikat
        success_count = 0
        total_count = 0
        
        for serial, sim_results in results.items():
            for sim_slot, success in sim_results.items():
                total_count += 1
                if success:
                    success_count += 1
        
        if success_count == total_count:
            self._status_label.configure(text=f"✔ Ustawiono RAT dla {success_count}/{total_count} urządzeń", fg=GREEN)
            # Pokaż komunikat i zamknij po chwili
            messagebox.showinfo("Sukces", f"Pomyślnie ustawiono RAT dla {success_count} urządzeń.", parent=self)
            self.destroy()
        else:
            self._status_label.configure(text=f"⚠ Ustawiono RAT dla {success_count}/{total_count} urządzeń", fg=YELLOW)
            # Pokaż komunikat o błędzie
            messagebox.showwarning("Częściowy sukces", 
                                 f"Ustawiono RAT dla {success_count} z {total_count} urządzeń.\n"
                                 "Niektóre operacje się nie powiodły.", parent=self)

    def _on_apply_error(self, error_msg):
        """Wywoływane w przypadku błędu podczas ustawiania RAT."""
        # Włącz przycisk
        self._btn_apply.configure(state="normal")
        self._status_label.configure(text="❌ Błąd podczas ustawiania RAT", fg=RED)
        messagebox.showerror("Błąd", f"Nie udało się ustawić RAT:\n{error_msg}", parent=self)