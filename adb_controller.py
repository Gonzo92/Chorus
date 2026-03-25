# ============================================================
#  Call Automator v1.0  –  adb_controller.py
#  Low-level ADB helpers for controlling devices.
# ============================================================

import subprocess
import re
import config

# ── internal helpers ─────────────────────────────────────────

def adb(serial: str, *args, timeout: int = 10) -> tuple[int, str, str]:
    """Run an adb command for *serial* and return (returncode, stdout, stderr)."""
    cmd = ["adb", "-s", serial, *args]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except subprocess.TimeoutExpired:
        return -1, "", "timeout"
    except FileNotFoundError:
        return -1, "", "adb not found in PATH"

# ── public API ───────────────────────────────────────────────

def start_call(serial: str, number: str) -> bool:
    """Initiate an outgoing call from *serial* to *number*."""
    rc, _, _ = adb(
        serial,
        "shell", "am", "start",
        "-a", "android.intent.action.CALL",
        "-d", f"tel:{number}",
    )
    return rc == 0


def end_call(serial: str) -> bool:
    """Terminate an active or ringing call on *serial*."""
    rc, _, _ = adb(serial, "shell", "input", "keyevent", "6")
    return rc == 0


def answer_call(serial: str) -> bool:
    """Dismiss keyguard then answer call on *serial*."""
    adb(serial, "shell", "wm", "dismiss-keyguard")
    rc, _, _ = adb(serial, "shell", "input", "keyevent", "5")
    return rc == 0


def get_call_state(serial: str) -> str:
    """
    Parse `dumpsys telephony.registry` and return one of:
      IDLE | RINGING | OFFHOOK | UNKNOWN
    """
    rc, stdout, _ = adb(serial, "shell", "dumpsys", "telephony.registry", timeout=15)
    if rc != 0:
        return "UNKNOWN"

    # mCallState: 0=IDLE  1=RINGING  2=OFFHOOK
    match = re.search(r"mCallState\s*=\s*(\d)", stdout)
    if not match:
        return "UNKNOWN"
    return {"0": "IDLE", "1": "RINGING", "2": "OFFHOOK"}.get(match.group(1), "UNKNOWN")


def get_signal_info(serial: str) -> dict:
    """
    Return dict with: rat, rsrp, rsrq, sinr, scg_state.
    """
    default = {"rat": "N/A", "rsrp": "N/A", "rsrq": "N/A",
               "sinr": "N/A", "scg_state": "N/A"}

    rc, stdout, _ = adb(serial, "shell", "dumpsys", "telephony.registry", timeout=15)
    if rc != 0:
        return default

    info = dict(default)

    m = re.search(r"mServiceState.*?(\bLTE\b|\bNR\b|\bUMTS\b|\bGSM\b)", stdout)
    if m: info["rat"] = m.group(1)

    m = re.search(r"rsrp\s*=\s*(-?\d+)", stdout, re.IGNORECASE)
    if m: info["rsrp"] = int(m.group(1))

    m = re.search(r"rsrq\s*=\s*(-?\d+)", stdout, re.IGNORECASE)
    if m: info["rsrq"] = int(m.group(1))

    m = re.search(r"(?:snrDb|sinr)\s*=\s*(-?[\d.]+)", stdout, re.IGNORECASE)
    if m: info["sinr"] = float(m.group(1))

    m = re.search(r"nrState\s*=\s*(\w+)", stdout, re.IGNORECASE)
    if m: info["scg_state"] = m.group(1)

    return info


def check_devices(serials: list[str]) -> dict[str, bool]:
    """Check whether each serial is reachable via ADB."""
    try:
        result = subprocess.run(
            ["adb", "devices"], capture_output=True, text=True, timeout=10)
        online = {
            line.split()[0]
            for line in result.stdout.splitlines()[1:]
            if len(line.split()) >= 2 and line.split()[1] == "device"
        }
        return {s: (s in online) for s in serials}
    except Exception:
        return {s: False for s in serials}


def wait_for_device_reconnection(serial: str, timeout: int = 60) -> bool:
    """
    Wait for a device to reconnect via ADB.
    
    Args:
        serial: The device serial number to wait for
        timeout: Maximum time to wait in seconds (default: 60)
        
    Returns:
        True if device reconnected within timeout, False otherwise
    """
    import time
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        try:
            result = subprocess.run(
                ["adb", "devices"], capture_output=True, text=True, timeout=5)
            online = {
                line.split()[0]
                for line in result.stdout.splitlines()[1:]
                if len(line.split()) >= 2 and line.split()[1] == "device"
            }
            if serial in online:
                return True
        except Exception:
            pass
        
        time.sleep(2)  # Check every 2 seconds
    
    return False
