# ============================================================
#  Chorus v2.5  –  core/adb_commands.py
#  ADB commands: device check, SIM numbers, signal info, call
#  control, GPS, scrcpy launch.
# ============================================================

from __future__ import annotations

import os
import re
import subprocess
import config as cfg

# ── ADB helper ─────────────────────────────────────────────────
def adb(*args, timeout=10):
    """Run an ADB command and return (returncode, stdout, stderr)."""
    cmd = ["adb"] + list(args)
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return result.returncode, result.stdout, result.stderr
    except FileNotFoundError:
        return 1, "", "adb not found"
    except subprocess.TimeoutExpired:
        return 1, "", "timeout"


# ── device check ──────────────────────────────────────────────
def check_devices(serials):
    """Check if ADB devices are reachable. Returns {serial: bool}."""
    results = {}
    for serial in serials:
        if not serial or serial in ("YOUR_SERIAL_HERE", ""):
            results[serial] = False
            continue
        rc, _, _ = adb("-s", serial, "shell", "echo", "ok", timeout=5)
        results[serial] = rc == 0
    return results


# ── SIM phone numbers ─────────────────────────────────────────
def get_sim_phone_numbers(serial):
    """Read SIM phone numbers from device via Samsung diagnostic menu."""
    result = {"sim1": None, "sim2": None, "model": "N/A"}

    rc, stdout, _ = adb(serial, "shell", "getprop", "gsm.sim.operator.alpha", timeout=5)
    if rc == 0 and stdout.strip():
        model = stdout.strip().split("\n")[-1]
        result["model"] = model

    # Try Samsung diagnostic menu
    rc, stdout, _ = adb(serial, "shell", "dumpsys", "telephony.subscription", timeout=5)
    if rc == 0:
        match = re.search(r"mNumber\s*=\s*(.+)", stdout)
        if match:
            result["sim1"] = {"number": match.group(1).strip()}

    return result


# ── signal info ───────────────────────────────────────────────
def get_signal_info(serial):
    """Get current signal information from device."""
    default = {"rat": "N/A", "rsrp": "N/A", "rsrq": "N/A",
               "sinr": "N/A", "band": "N/A", "call_type": "UNKNOWN"}

    rc, stdout, _ = adb(serial, "shell", "dumpsys", "telephony.registry", timeout=15)
    if rc != 0:
        return default

    # RAT
    match = re.search(r"mCellStatus\s*=\s*(.+)", stdout)
    if match:
        status = match.group(1)
        if "LTE" in status or "LTE+" in status:
            default["rat"] = "LTE"
        elif "NR" in status or "ENDC" in status:
            default["rat"] = "NR"
        elif "UMTS" in status or "HSPA" in status:
            default["rat"] = "UMTS"
        elif "GSM" in status:
            default["rat"] = "GSM"

    # RSRP
    match = re.search(r"mRsrp\s*=\s*(-?\d+)", stdout)
    if match:
        rsrp = int(match.group(1))
        if rsrp != 2147483647:  # INT_MAX sentinel
            default["rsrp"] = str(rsrp)

    # RSRQ
    match = re.search(r"mRsrq\s*=\s*(-?\d+)", stdout)
    if match:
        rsrq = int(match.group(1))
        if rsrq != 2147483647:
            default["rsrq"] = str(rsrq)

    # SINR
    match = re.search(r"mSinr\s*=\s*(-?\d+)", stdout)
    if match:
        sinr = int(match.group(1))
        if sinr != 2147483647:
            default["sinr"] = str(sinr)

    # Band
    match = re.search(r"mDataConnectionType\s*=\s*(.+)", stdout)
    if match:
        default["band"] = match.group(1).strip()

    return default


# ── IMS state check ───────────────────────────────────────────
def check_ims_state(serial):
    """Check if IMS (VoLTE) is enabled and registered on device.
    
    Returns dict:
        enabled: bool/None  – settings global ims_enabled
        registered: bool/None – True if IMS registered in dumpsys
        property: str/None  – ril.ims.ltevoicesupport property value
    """
    result = {"enabled": None, "registered": None, "property": None}
    
    # Method 1: settings global ims_enabled
    rc, output, _ = adb(serial, "shell", "settings", "get", "global", "ims_enabled", timeout=5)
    if rc == 0 and output.strip() in ("0", "1"):
        result["enabled"] = output.strip() == "1"
    
    # Method 2: check dumpsys for IMS registration
    rc, output, _ = adb(serial, "shell", "dumpsys", "telephony.registry", timeout=10)
    if rc == 0:
        if "ims" in output.lower() and "disabled" not in output.lower():
            result["registered"] = True
        elif "ims" in output.lower() and "disabled" in output.lower():
            result["registered"] = False
    
    # Method 3: Samsung property
    rc, output, _ = adb(serial, "shell", "getprop", "ril.ims.ltevoicesupport", timeout=5)
    if rc == 0 and output.strip():
        result["property"] = output.strip()
    
    return result


# ── scrcpy launcher ───────────────────────────────────────────
def find_scrcpy():
    """Find scrcpy executable in PATH or common locations."""
    candidates = ["scrcpy", "scrcpy.exe"]
    for candidate in candidates:
        try:
            subprocess.run(["where", candidate], capture_output=True, check=True)
            return candidate
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass

    # Check common installation paths
    common_paths = [
        os.path.join(os.environ.get("LOCALAPPDIR", ""), "Programs", "scrcpy", "scrcpy.exe"),
        os.path.join(os.environ.get("PROGRAMFILES", ""), "scrcpy", "scrcpy.exe"),
        os.path.join(os.environ.get("USERPROFILE"), "scrcpy", "scrcpy.exe"),
    ]
    for path in common_paths:
        if os.path.exists(path):
            return path

    return None


def launch_scrcpy(serial, title="scrcpy", scrcpy_path=None):
    """Launch scrcpy for a device. Returns True on success."""
    if not scrcpy_path:
        scrcpy_path = find_scrcpy()
    if not scrcpy_path:
        return False

    cmd = [scrcpy_path, "-s", serial, "--no-audio", "--window-title", title]
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except Exception:
        return False
