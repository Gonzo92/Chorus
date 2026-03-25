# ============================================================
#  Call Automator v1.0  –  config.py
#  Central configuration – edit this file before each session
# ============================================================

import os

# Get the directory where this config file is located
APP_DIR = os.path.dirname(os.path.abspath(__file__))

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
LOOP_COUNT    = 50   # total call cycles per pair
IDLE_SECONDS  = 5    # wait between cycles (idle)
CALL_SECONDS  = 15   # how long to keep the call active
CALL_END_WAIT = 3    # grace period after end_call before next cycle

# --------------- Log output path ----------------------------
LOG_OUTPUT_PATH = os.path.join(APP_DIR, "Logs")  # root directory for all logs

# --------------- CSV output ---------------------------------
CSV_OUTPUT_PATH = os.path.join(APP_DIR, "Logs", "results.csv")  # will be updated by app

# --------------- Display options -----------------------------
UPPERCASE_TEXT = False  # Display all text in uppercase
