# ============================================================
#  Chorus v2.5  –  config.py (cross-machine compatible)
#  Central configuration – edit this file before each session
# ============================================================

from __future__ import annotations

import os
import sys

# Get the directory where this config file is located
APP_DIR = os.path.dirname(os.path.abspath(__file__))

# User-writable data directory (AppData\Local\Chorus)
if sys.platform == "win32":
    _data_dir = os.path.join(os.path.expanduser("~"), "AppData", "Local", "Chorus")
else:
    _data_dir = os.path.join(os.path.expanduser("~"), ".chorus")
os.makedirs(_data_dir, exist_ok=True)

# --------------- Device serials (adb devices) ---------------
DEVICES = {
    "dut_MO": "R3CR1234ABC",   # DUT pair – calling side
    "dut_MT": "R3CR5678DEF",   # DUT pair – answering side
    "ref_MO": "ZY2A9ABCDE12",  # REF pair – calling side
    "ref_MT": "ZY2A9FGHIJ34",  # REF pair – answering side
}

# --------------- Phone numbers (MT side) --------------------
PHONE_NUMBERS = {
    "dut": "500100200",   # number dialled by dut_MO  → dut_MT
    "ref": "500300400",   # number dialled by ref_MO  → ref_MT
}

# --------------- Test loop parameters -----------------------
LOOP_COUNT       = 50   # total call cycles per pair
IDLE_SECONDS     = 5    # wait between cycles (idle)
CALL_SECONDS     = 5    # how long to keep the call active
RINGING_TIMEOUT  = 30    # max time to wait for MT to ring before answer_call (CSFB can take 15-30s)
ANSWER_RETRIES   = 3    # max retries for answer_call
ANSWER_RETRY_DELAY = 1  # delay between answer retries in seconds

# --------------- Log output path ----------------------------
LOG_OUTPUT_PATH = os.path.join(_data_dir, "Logs")  # root directory for all logs
os.makedirs(LOG_OUTPUT_PATH, exist_ok=True)

# --------------- CSV output ---------------------------------
CSV_OUTPUT_PATH = os.path.join(LOG_OUTPUT_PATH, "results.csv")  # will be updated by app

# --------------- Display options -----------------------------
UPPERCASE_TEXT = True  # Display all text in uppercase

# --------------- Sync timeout (seconds) ──────────────────────
SYNC_TIMEOUT = 300  # Max seconds to wait for both pairs before timeout

# --------------- GPS tracking (background) ──────────────────
GPS_ENABLED    = False      # Enable GPS tracking during test
GPS_SERIAL     = ""         # Device serial for GPS (empty = use dut_MO)
GPS_EVERY_N    = 5          # Collect GPS every N cycles (1=every cycle, 5=every 5th)
GPS_SOURCE     = ""         # GPS source device serial (empty = use GPS_SERIAL or dut_MO)

# --------------- APK installation ──────────────────────────
APK_PATH       = ""         # Path to APK file for installation on all devices

# --------------- APK installation ──────────────────────────
APK_PATHS = []              # List of APK file paths for installation on all devices
