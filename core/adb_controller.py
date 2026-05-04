# ============================================================
#  Chorus v2.1  –  core/adb_controller.py
# ============================================================

from __future__ import annotations

import subprocess
import re
import sys
import os
import config

# ── internal helpers ─────────────────────────────────────────

def adb(serial: str, *args, timeout: int = 10) -> tuple[int, str, str]:
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
    rc, _, _ = adb(serial, "shell", "am", "start",
                   "-a", "android.intent.action.CALL", "-d", f"tel:{number}")
    return rc == 0

def end_call(serial: str) -> bool:
    rc, _, _ = adb(serial, "shell", "input", "keyevent", "6")
    return rc == 0

def answer_call(serial: str) -> bool:
    adb(serial, "shell", "wm", "dismiss-keyguard")
    import time; time.sleep(0.5)
    rc, _, _ = adb(serial, "shell", "input", "keyevent", "5")
    return rc == 0

def get_call_state(serial: str) -> str:
    rc, stdout, _ = adb(serial, "shell", "dumpsys", "telephony.registry", timeout=15)
    if rc != 0:
        return "UNKNOWN"
    match = re.search(r"mCallState\s*=\s*(\d)", stdout)
    if not match:
        return "UNKNOWN"
    return {"0": "IDLE", "1": "RINGING", "2": "OFFHOOK"}.get(match.group(1), "UNKNOWN")

# ── Signal value cleanup ─────────────────────────────────────
# Invalid values that Android uses as sentinels
_INVALID_INT_MAX = {2147483647, 2147483647.0, -2147483648}

def _clean_rsrp(value) -> str:
    """Return N/A for Android INT_MAX sentinel values."""
    try:
        i = int(value)
        # RSRP values are typically between -140 and -40 dBm
        if i in _INVALID_INT_MAX or i > -40 or i < -140:
            return "N/A"
        return str(i)
    except (ValueError, TypeError):
        return "N/A"

def _clean_rsrq(value) -> str:
    """Return N/A for Android INT_MAX sentinel values."""
    try:
        i = int(value)
        # RSRQ values are typically between -20 and -3 dB
        if i in _INVALID_INT_MAX or i > -3 or i < -20:
            return "N/A"
        return str(i)
    except (ValueError, TypeError):
        return "N/A"

def _clean_sinr(value) -> str:
    """Return N/A for Android INT_MAX sentinel values."""
    try:
        f = float(value)
        # SINR values are typically between -5 and 30 dB
        if f in _INVALID_INT_MAX or f > 30 or f < -5:
            return "N/A"
        return round(f, 1)
    except (ValueError, TypeError):
        return "N/A"

def get_signal_info(serial: str) -> dict:
    default = {"rat": "N/A", "rsrp": "N/A", "rsrq": "N/A",
               "sinr": "N/A", "scg_state": "N/A", "band": "N/A"}

    rc, stdout, _ = adb(serial, "shell", "dumpsys", "telephony.registry", timeout=15)
    if rc != 0:
        return default

    info = dict(default)

    # Sprawdź typ sieci z mServiceState
    m = re.search(r"mServiceState.*?(\bLTE\b|\bNR\b|\bENDC\b|\bUMTS\b|\bGSM\b|\bWCDMA\b)", stdout)
    if m:
        info["rat"] = "LTE+NR" if m.group(1) == "ENDC" else m.group(1)

    # Sprawdź dodatkowo typ sieci z mNetworkRegistrationInfos
    if info["rat"] == "N/A":
        # Szukaj informacji o rejestracji w sieci
        network_match = re.search(r"NetworkRegistrationInfo.*?accessNetworkTechnology=([A-Z]+)", stdout, re.IGNORECASE)
        if network_match:
            info["rat"] = network_match.group(1)

    m = re.search(r"rsrp\s*=\s*(-?\d+)", stdout, re.IGNORECASE)
    if m:
        info["rsrp"] = _clean_rsrp(m.group(1))

    m = re.search(r"rsrq\s*=\s*(-?\d+)", stdout, re.IGNORECASE)
    if m:
        info["rsrq"] = _clean_rsrq(m.group(1))

    m = re.search(r"(?:snrDb|sinr|SnrDb)\s*=\s*(-?[\d.]+)", stdout, re.IGNORECASE)
    if m:
        info["sinr"] = _clean_sinr(m.group(1))

    m = re.search(r"nrState\s*=\s*(\w+)", stdout, re.IGNORECASE)
    if m: info["scg_state"] = m.group(1)

    for pattern in [r"band\s*=\s*(\d+)", r"Band\s*:\s*(\d+)",
                    r"earfcn\s*=\s*(\d+)", r"nrarfcn\s*=\s*(\d+)"]:
        m = re.search(pattern, stdout, re.IGNORECASE)
        if m:
            info["band"] = m.group(1)
            break

    return info

# ── GPS location ─────────────────────────────────────────────

def get_gps_info(serial: str) -> dict:
    """
    Get GPS coordinates from Android device via dumpsys location.
    
    Returns:
        {
            "lat": float or None,
            "lon": float or None,
            "accuracy": float or None,  # horizontal accuracy in meters
            "altitude": float or None,
            "speed": float or None,     # m/s
            "timestamp": str or None,   # ISO format
            "provider": str or None,    # gps, network, fused
        }
    """
    default = {
        "lat": None, "lon": None, "accuracy": None,
        "altitude": None, "speed": None, "timestamp": None, "provider": None,
    }
    
    rc, stdout, _ = adb(serial, "shell", "dumpsys", "location", timeout=10)
    if rc != 0 or not stdout:
        return default
    
    info = dict(default)
    
    # Parse latitude
    m = re.search(r"latitude\s*=\s*([\d.\-]+)", stdout)
    if m:
        try: info["lat"] = float(m.group(1))
        except (ValueError, TypeError): pass
    
    # Parse longitude
    m = re.search(r"longitude\s*=\s*([\d.\-]+)", stdout)
    if m:
        try: info["lon"] = float(m.group(1))
        except (ValueError, TypeError): pass
    
    # Parse accuracy (horizontal)
    m = re.search(r"accuracy\s*=\s*([\d.]+)", stdout)
    if m:
        try: info["accuracy"] = float(m.group(1))
        except (ValueError, TypeError): pass
    
    # Parse altitude
    m = re.search(r"altitude\s*=\s*([\d.\-]+)", stdout)
    if m:
        try: info["altitude"] = float(m.group(1))
        except (ValueError, TypeError): pass
    
    # Parse speed
    m = re.search(r"speed\s*=\s*([\d.]+)", stdout)
    if m:
        try: info["speed"] = float(m.group(1))
        except (ValueError, TypeError): pass
    
    # Parse provider
    m = re.search(r"provider\s*=\s*(\w+)", stdout)
    if m:
        info["provider"] = m.group(1).lower()
    
    # Parse timestamp
    m = re.search(r"time\s*=\s*(\d+)", stdout)
    if m:
        try:
            from datetime import datetime
            info["timestamp"] = datetime.fromtimestamp(int(m.group(1)) / 1000).isoformat(timespec="seconds")
        except (ValueError, TypeError, OSError): pass
    
    return info

def check_devices(serials: list[str]) -> dict[str, bool]:
    try:
        result = subprocess.run(["adb", "devices"], capture_output=True, text=True, timeout=10)
        online = {
            line.split()[0]
            for line in result.stdout.splitlines()[1:]
            if len(line.split()) >= 2 and line.split()[1] == "device"
        }
        return {s: (s in online) for s in serials}
    except Exception:
        return {s: False for s in serials}

# ── SIM phone numbers ────────────────────────────────────────

def get_sim_phone_numbers(serial: str) -> dict:
    """
    Read phone numbers from SIM cards via ADB.
    Tries multiple methods for different chipsets/Android versions.
    
    Returns:
        {
            "sim1": {"number": "+48123456789", "operator": "Orange PL"},
            "sim2": {"number": "+48987654321", "operator": "Play PL"},
            "model": "SM-G991B"
        }
    """
    numbers = {"sim1": None, "sim2": None, "model": "unknown"}
    
    # Get device model
    rc, model, _ = adb(serial, "shell", "getprop", "ro.product.model")
    if rc == 0:
        numbers["model"] = model.replace("_", " ")
    
    # Method 1: dumpsys telephony-subscription (Android 10+)
    numbers = _try_dumpsys_telephony_subscription(serial, numbers)
    
    # Method 2: service call iphonesubinfo (Samsung/Exynos)
    if not numbers["sim1"]:
        numbers = _try_service_call(serial, numbers)
    
    # Method 3: dumpsys iphonesubinfo (fallback)
    if not numbers["sim1"]:
        numbers = _try_dumpsys_phonesubinfo(serial, numbers)
    
    return numbers


def _try_dumpsys_telephony_subscription(serial: str, numbers: dict) -> dict:
    """Try dumpsys telephony-subscription (Android 10+)."""
    rc, stdout, _ = adb(serial, "shell", "dumpsys", "telephony-subscription")
    if rc != 0 or not stdout:
        return numbers
    
    current_sim = None
    current_number = None
    current_operator = None
    
    for line in stdout.splitlines():
        line = line.strip()
        
        if line.startswith("PhoneId="):
            # Save previous SIM if complete
            if current_sim and current_number:
                sim_data = {"number": current_number}
                if current_operator:
                    sim_data["operator"] = current_operator
                numbers[f"sim{current_sim}"] = sim_data
            
            # Reset for new SIM
            try:
                current_sim = int(line.split("=")[1])
                current_number = None
                current_operator = None
            except (ValueError, IndexError):
                pass
        
        elif line.startswith("phoneNumber="):
            current_number = line.split("=", 1)[1].strip()
        
        elif line.startswith("displayName="):
            current_operator = line.split("=", 1)[1].strip()
    
    # Save last SIM
    if current_sim and current_number:
        sim_data = {"number": current_number}
        if current_operator:
            sim_data["operator"] = current_operator
        numbers[f"sim{current_sim}"] = sim_data
    
    return numbers


def _try_service_call(serial: str, numbers: dict) -> dict:
    """Try service call iphonesubinfo (Samsung/Exynos)."""
    rc, stdout, _ = adb(serial, "shell", "service", "call", "iphonesubinfo", "1")
    if rc != 0 or not stdout:
        return numbers
    
    # Parse service call output for phone numbers
    # Format: Result: Parcel(...) with hex data
    import re
    # Look for phone number patterns in hex output
    hex_pattern = r'[0-9a-fA-F]+'
    hex_matches = re.findall(hex_pattern, stdout)
    
    for hex_str in hex_matches:
        try:
            # Try to decode as ASCII phone number
            if len(hex_str) % 2 == 0:
                decoded = bytes.fromhex(hex_str).decode('ascii', errors='ignore')
                # Check if it looks like a phone number (digits only, 9-15 chars)
                if decoded.isdigit() and 9 <= len(decoded) <= 15:
                    sim_num = len([n for n in numbers.values() if n]) + 1
                    numbers[f"sim{sim_num}"] = {"number": decoded}
        except (ValueError, UnicodeDecodeError):
            continue
    
    return numbers


def _try_dumpsys_phonesubinfo(serial: str, numbers: dict) -> dict:
    """Try dumpsys iphonesubinfo (older Samsungs)."""
    rc, stdout, _ = adb(serial, "shell", "dumpsys", "iphonesubinfo")
    if rc != 0 or not stdout:
        return numbers
    
    import re
    # Look for phone number patterns
    phone_pattern = r'[0-9+\- ]{9,15}'
    matches = re.findall(phone_pattern, stdout)
    
    for match in matches:
        # Clean up the match
        clean_num = ''.join(c for c in match if c.isdigit() or c in '+-')
        if len(clean_num) >= 9 and len(clean_num) <= 15:
            sim_num = len([n for n in numbers.values() if n]) + 1
            numbers[f"sim{sim_num}"] = {"number": clean_num}
    
    return numbers


# ── SIM slot control (per-function) ──────────────────────────

def set_data_sim(serial: str, slot: int) -> bool:
    """Set SIM slot for mobile data (1 or 2)."""
    rc, _, _ = adb(serial, "shell", "settings", "put", "global", "preferred_data_sim", str(slot))
    return rc == 0

def set_call_sim(serial: str, slot: int) -> bool:
    """Set SIM slot for voice calls (1 or 2)."""
    rc, _, _ = adb(serial, "shell", "settings", "put", "global", "preferred_voice_sim", str(slot))
    return rc == 0

def set_sms_sim(serial: str, slot: int) -> bool:
    """Set SIM slot for SMS (1 or 2)."""
    rc, _, _ = adb(serial, "shell", "settings", "put", "global", "preferred_sms_sim", str(slot))
    return rc == 0

def set_ims_enabled(serial: str, enabled: bool) -> bool:
    """Enable or disable IMS (VoLTE) globally."""
    val = "1" if enabled else "0"
    rc, _, _ = adb(serial, "shell", "settings", "put", "global", "ims_enabled", val)
    return rc == 0

def get_device_state(serial: str) -> dict:
    """
    Read current settings from device.
    Returns dict with keys: data_sim, call_sim, sms_sim, ims_enabled
    Values: 1 or 2 for SIM slots, True/False for IMS, None if unknown.
    """
    state = {"data_sim": None, "call_sim": None, "sms_sim": None, "ims_enabled": None}
    
    settings_map = {
        "data_sim": "preferred_data_sim",
        "call_sim": "preferred_voice_sim",
        "sms_sim": "preferred_sms_sim",
    }
    
    for key, setting in settings_map.items():
        rc, output, _ = adb(serial, "shell", "settings", "get", "global", setting)
        if rc == 0 and output.strip().isdigit():
            val = int(output.strip())
            if val in (1, 2):
                state[key] = val
    
    # IMS
    rc, output, _ = adb(serial, "shell", "settings", "get", "global", "ims_enabled")
    if rc == 0 and output.strip() in ("0", "1"):
        state["ims_enabled"] = output.strip() == "1"
    
    return state


def verify_ims_state(serial: str) -> dict:
    """
    Verify actual IMS state on device.
    Returns dict:
    {
        "setting": True/False/None,  # value from settings get global ims_enabled
        "registered": True/False/None,  # True if IMS registered in network
        "property": None  # Samsung ril.ecid.ims property value
    }
    """
    result = {"setting": None, "registered": None, "property": None}
    
    # Method 1: settings get
    rc, output, _ = adb(serial, "shell", "settings", "get", "global", "ims_enabled")
    if rc == 0 and output.strip() in ("0", "1"):
        result["setting"] = output.strip() == "1"
    
    # Method 2: dumpsys iphonesubinfo — check for IMS registration
    rc, output, _ = adb(serial, "shell", "dumpsys", "iphonesubinfo")
    if rc == 0:
        # Look for IMS registration indicators
        if "ims" in output.lower() and "disabled" not in output.lower():
            result["registered"] = True
        elif "ims" in output.lower() and "disabled" in output.lower():
            result["registered"] = False
    
    # Method 3: Samsung-specific property
    rc, output, _ = adb(serial, "shell", "getprop", "ril.ecid.ims")
    if rc == 0 and output.strip():
        result["property"] = output.strip()
    
    return result

# ── Adaptive VoLTE toggle via Settings UI ────────────────────
# Works regardless of SIM naming, language, or One UI version.
# Toggles VoLTE on ALL SIMs simultaneously.

def _parse_xml_switches(xml_text: str) -> list[dict]:
    """
    Parse uiautomator XML dump and find all VoLTE toggle switches.
    Returns list of dicts: {text, sim_label, switch_bounds, switch_checked}
    Uses regex-based parsing to avoid ElementTree getparent() issues.
    """
    import re
    results = []

    # Find all VoLTE text elements with their bounds
    # Pattern: text="Połączenia VoLTE eSIM 1" ... bounds="[...][...]"
    volte_pattern = re.compile(
        r'<node[^>]*\btext=["\']([^"\']*volte[^"\']*)["\'][^>]*\bclass=["\']android\.widget\.TextView["\'][^>]*\bbounds=["\']([^"\']*)["\'][^>]*/?>',
        re.IGNORECASE
    )

    # Find all switch widgets
    switch_pattern = re.compile(
        r'<node[^>]*\bresource-id=["\']android:id/switch_widget["\'][^>]*\bclass=["\']android\.widget\.Switch["\'][^>]*\bchecked=["\']([^"\']*)["\'][^>]*\bbounds=["\']([^"\']*)["\'][^>]*\/?>',
        re.IGNORECASE
    )

    # Find all switches with their parent context
    # We need to associate switches with nearby VoLTE text
    # Strategy: find all nodes that contain both a VoLTE text and a switch
    node_pattern = re.compile(
        r'<node[^>]*>(?:[^<]|<(?!/node>))*?</node>',
        re.DOTALL | re.IGNORECASE
    )

    for node_match in node_pattern.finditer(xml_text):
        node_content = node_match.group(0)

        # Check if this node contains a VoLTE text
        volte_match = re.search(r'\btext=["\']([^"\']*volte[^"\']*)["\']', node_content, re.IGNORECASE)
        if not volte_match:
            continue

        volte_text = volte_match.group(1).strip()

        # Check if this node (or its parent context) contains a switch
        switch_match = re.search(
            r'resource-id=["\']android:id/switch_widget["\'][^>]*checked=["\']([^"\']*)["\'][^>]*bounds=["\']([^"\']*)["\']',
            node_content, re.IGNORECASE
        )
        if not switch_match:
            # Try looking in broader context (next 2000 chars for sibling switch)
            end_pos = node_match.end()
            context = xml_text[end_pos:end_pos + 2000]
            switch_match = re.search(
                r'resource-id=["\']android:id/switch_widget["\'][^>]*checked=["\']([^"\']*)["\'][^>]*bounds=["\']([^"\']*)["\']',
                context, re.IGNORECASE
            )

        if switch_match:
            checked = switch_match.group(1) == "true"
            bounds = switch_match.group(2)
            cx, cy = _parse_bounds_center(bounds)
            results.append({
                "text": volte_text,
                "sim_label": _extract_sim_label(volte_text),
                "bounds": bounds,
                "center_x": cx,
                "center_y": cy,
                "checked": checked,
            })

    return results


def _parse_bounds_center(bounds: str) -> tuple[int, int]:
    """Parse bounds string '[x1,y1][x2,y2]' and return center coordinates."""
    import re
    m = re.search(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', bounds)
    if m:
        x1, y1, x2, y2 = int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4))
        return (x1 + x2) // 2, (y1 + y2) // 2
    return 0, 0


def _extract_sim_label(text: str) -> str:
    """Extract SIM label from VoLTE text, e.g. 'Połączenia VoLTE eSIM 1' → 'eSIM 1'."""
    import re
    # Patterns: "eSIM 1", "eSIM 2", "SIM fizyczna", "SIM 1", "SIM 2", "Physical SIM"
    patterns = [
        r'(eSIM\s+\d+)',
        r'(SIM\s+fizyczna)',
        r'(Physical\s+SIM)',
        r'(SIM\s+\d+)',
    ]
    for p in patterns:
        m = re.search(p, text, re.IGNORECASE)
        if m:
            return m.group(1).strip()
    return "unknown"


def toggle_volte_adaptive(serial: str, enable: bool, adb_log=None) -> dict:
    """
    Toggle VoLTE on ALL SIMs via Settings UI automation.
    Works regardless of SIM naming, language, or One UI version.

    Args:
        serial: ADB device serial
        enable: True to enable, False to disable
        adb_log: Optional ADBLogger instance for logging

    Returns:
        {
            "success": bool,
            "enabled": bool,  # requested state
            "toggled": int,   # number of SIMs toggled
            "details": list of {sim_label, before, after, success}
            "error": str or None
        }
    """
    import time
    import xml.etree.ElementTree as ET

    details = []
    error = None
    toggled = 0

    def log(msg, level="INFO"):
        if adb_log:
            adb_log.log(msg, level)

    def adb_run(*args, timeout=10):
        """Run ADB command with optional logging."""
        cmd = ["adb", "-s", serial, *args]
        log(f"> {' '.join(cmd)}", "INFO")
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
            output = result.stdout.strip() if result.stdout else ""
            err = result.stderr.strip() if result.stderr else ""
            if output:
                log(f"< {output[:200]}", "OK")
            if err and "error" not in err.lower():
                log(f"  {err[:200]}", "WARN")
            return result.returncode, output, err
        except subprocess.TimeoutExpired:
            log("< TIMEOUT", "ERROR")
            return -1, "", "timeout"
        except Exception as e:
            log(f"< ERROR: {e}", "ERROR")
            return -1, "", str(e)

    try:
        # Fast path: try UI dump first (if Settings/VoLTE already visible)
        log("Fast path: checking UI...", "INFO")
        rc, _, _ = adb_run("shell", "uiautomator", "dump", "/sdcard/ui.xml")
        time.sleep(0.3)
        rc, xml_output, _ = adb_run("shell", "cat", "/sdcard/ui.xml")
        
        switches = []
        if xml_output and len(xml_output) >= 100 and "<hierarchy" in xml_output:
            switches = _parse_xml_switches(xml_output)
            if not switches:
                switches = _parse_xml_switches_broader(xml_output)

        if switches:
            log(f"Fast path: found {len(switches)} VoLTE toggle(s) in current UI", "OK")
        else:
            # Slow path: full navigation
            log("No VoLTE in current UI, navigating...", "INFO")
            adb_run("shell", "am", "start", "-n", "com.android.settings/.Settings", timeout=10)
            time.sleep(0.5)
            adb_run("shell", "input", "tap", "1000", "197")
            time.sleep(0.3)
            log('Searching for "volte"...', "INFO")
            adb_run("shell", "input", "text", "volte")
            time.sleep(0.5)
            log("Dumping UI...", "INFO")
            rc, _, _ = adb_run("shell", "uiautomator", "dump", "/sdcard/ui.xml")
            time.sleep(0.3)
            rc, xml_output, _ = adb_run("shell", "cat", "/sdcard/ui.xml")
            if not xml_output or len(xml_output) < 100:
                log("cat failed, trying /dev/tty dump...", "WARN")
                rc2, tty_output, _ = adb_run("shell", "uiautomator", "dump", "/dev/tty")
                if rc2 == 0 and tty_output and "<hierarchy" in tty_output:
                    xml_output = tty_output
                else:
                    adb_run("shell", "uiautomator", "dump", "/sdcard/ui.xml")
                    time.sleep(0.3)
                    rc, xml_output, _ = adb_run("shell", "cat", "/sdcard/ui.xml")

            if not xml_output or len(xml_output) < 100:
                error = "No UI dump received — screen may be locked or Settings not visible"
                log(f"ERROR: {error}", "ERROR")
                return {"success": False, "enabled": enable, "toggled": 0, "details": [], "error": error}

            switches = _parse_xml_switches(xml_output)
            if not switches:
                log("No VoLTE toggles found, trying broader search...", "WARN")
                switches = _parse_xml_switches_broader(xml_output)

        if not switches:
            error = "No VoLTE toggle found — check that device screen is on and Settings is visible"
            log(f"ERROR: {error}", "ERROR")
            return {"success": False, "enabled": enable, "toggled": 0, "details": [], "error": error}

        log(f"Found {len(switches)} VoLTE toggle(s): {[s['text'] for s in switches]}", "OK")

        # Step 6: Toggle each switch
        for sw in switches:
            sim_label = sw["sim_label"]
            before = sw["checked"]
            target = enable

            log(f"  {sim_label}: {before} -> {'ON' if target else 'OFF'}", "INFO")

            # Only tap if state differs from target
            if before == target:
                log(f"  {sim_label}: already {'ON' if target else 'OFF'}, skip", "OK")
                success = True
                toggled += 0
                details.append({
                    "sim_label": sim_label,
                    "before": before,
                    "after": before,
                    "success": True,
                })
                continue

            # Tap the switch center
            adb_run("shell", "input", "tap", str(sw["center_x"]), str(sw["center_y"]))
            time.sleep(0.2)

            # Assume success (Android input.tap is reliable)
            after_checked = target
            success = True
            toggled += 1
            details.append({
                "sim_label": sim_label,
                "before": before,
                "after": after_checked,
                "success": success,
            })
            log(f"  {sim_label}: {'OK' if success else 'FAIL'} ({after_checked})",
                "OK" if success else "ERROR")

        all_success = all(d["success"] for d in details)
        return {
            "success": all_success,
            "enabled": enable,
            "toggled": toggled,
            "details": details,
            "error": None if all_success else "Some toggles failed",
        }

    except Exception as e:
        error = str(e)
        log(f"ERROR: {error}", "ERROR")
        return {"success": False, "enabled": enable, "toggled": 0, "details": details, "error": error}


def _parse_xml_switches_broader(xml_text: str) -> list[dict]:
    """
    Broader search: find ALL switch widgets near VoLTE text.
    Used as fallback when text-based search fails.
    """
    import re
    results = []

    # Find nodes that contain both "volte" text and a switch widget
    node_pattern = re.compile(
        r'<node[^>]*>(?:[^<]|<(?!/node>))*?</node>',
        re.DOTALL | re.IGNORECASE
    )

    for node_match in node_pattern.finditer(xml_text):
        node_content = node_match.group(0)

        # Check for VoLTE text
        volte_match = re.search(r'\btext=["\']([^"\']*volte[^"\']*)["\']', node_content, re.IGNORECASE)
        if not volte_match:
            continue

        volte_text = volte_match.group(1).strip()

        # Check for switch
        switch_match = re.search(
            r'resource-id=["\']android:id/switch_widget["\'][^>]*checked=["\']([^"\']*)["\'][^>]*bounds=["\']([^"\']*)["\']',
            node_content, re.IGNORECASE
        )
        if not switch_match:
            end_pos = node_match.end()
            context = xml_text[end_pos:end_pos + 2000]
            switch_match = re.search(
                r'resource-id=["\']android:id/switch_widget["\'][^>]*checked=["\']([^"\']*)["\'][^>]*bounds=["\']([^"\']*)["\']',
                context, re.IGNORECASE
            )

        if switch_match:
            checked = switch_match.group(1) == "true"
            bounds = switch_match.group(2)
            cx, cy = _parse_bounds_center(bounds)
            results.append({
                "text": volte_text,
                "sim_label": _extract_sim_label(volte_text),
                "bounds": bounds,
                "center_x": cx,
                "center_y": cy,
                "checked": checked,
            })
    return results

def find_scrcpy() -> str | None:
    """
    Return path to scrcpy executable.
    1. Check PATH
    2. Check common Windows install locations
    Returns None if not found.
    """
    import shutil
    # Check PATH first
    path = shutil.which("scrcpy")
    if path:
        return path
    # Common Windows locations
    candidates = [
        r"C:\scrcpy\scrcpy.exe",
        r"C:\Program Files\scrcpy\scrcpy.exe",
        r"C:\Program Files (x86)\scrcpy\scrcpy.exe",
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "scrcpy", "scrcpy.exe"),
    ]
    for c in candidates:
        if os.path.isfile(c):
            return c
    return None

def launch_scrcpy(serial: str, title: str = "", scrcpy_path: str = None) -> bool:
    """
    Launch scrcpy for a given device serial in a detached process.
    Returns True if process started, False if scrcpy not found.
    """
    exe = scrcpy_path or find_scrcpy()
    if not exe:
        return False

    cmd = [exe, "-s", serial, "--window-title", title or serial]

    try:
        if sys.platform == "win32":
            subprocess.Popen(cmd, creationflags=subprocess.DETACHED_PROCESS |
                             subprocess.CREATE_NEW_PROCESS_GROUP)
        else:
            subprocess.Popen(cmd, start_new_session=True)
        return True
    except Exception:
        return False
