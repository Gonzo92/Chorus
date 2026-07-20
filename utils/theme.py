# ============================================================
#  Chorus v2.5  –  utils/theme.py
#  Centralized theme constants for all GUI modules.
# ============================================================

from __future__ import annotations

# ── colors ─────────────────────────────────────────────────────
BG     = "#0f1117"   # Main background
BG2    = "#2a2d3a"   # Lighter background (panels, frames)
BG3    = "#747579"   # Even lighter (borders, inactive elements)
FG     = "#ffffff"   # Primary text
FG_DIM = "#B0B2B6"   # Dimmed/inactive text

BLUE   = "#6daaff"   # DUT pair accent
YELLOW = "#8a440b"   # REF pair accent
GREEN  = "#5aff9d"   # PASS / success
RED    = "#ff8585"   # FAIL / error
CYAN   = "#33e3ff"   # Active / in-progress

# ── fonts ──────────────────────────────────────────────────────
MONO   = "Consolas"  # Log panel, monospace text
SANS   = "Segoe UI"  # UI elements

# ── stage colors ───────────────────────────────────────────────
STAGE_COLOR = {
    "PASS": GREEN, "FAIL": RED, "ACTIVE": CYAN,
    "COMPLETE": GREEN, "CALLING": YELLOW, "RINGING": YELLOW,
    "ANSWERING": YELLOW,
    "IDLE": FG_DIM, "CHECKING": FG, "HANGING UP": FG_DIM,
}

# ── log tag colors ─────────────────────────────────────────────
LOG_TAGS = {
    "ts":     FG_DIM,
    "ref":    YELLOW,
    "PASS":   GREEN,
    "FAIL":   RED,
    "ACTIVE": CYAN,
    "dim":    FG_DIM,
    "info":   FG,
}
