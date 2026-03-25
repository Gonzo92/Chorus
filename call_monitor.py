# ============================================================
#  Call Automator v1.0  –  call_monitor.py
#  Orchestrates one call cycle. MO always calls, MT always answers.
#  Sends per-second countdown callbacks so the UI can show a timer.
# ============================================================

import time
import threading
from typing import Callable
import config

StatusCB = Callable[[str, int, str, str], None]
from adb_controller import start_call, end_call, answer_call, get_call_state, get_signal_info, wait_for_device_reconnection, check_devices
from report import log_call

def _check_device_connection(serial: str, pair: str, cycle: int, stage: str, 
                            status_callback: StatusCB) -> bool:
    """
    Check if a device is connected and wait for reconnection if not.
    
    Returns:
        True if device is connected (or reconnected), False if not
    """
    devices_status = check_devices([serial])
    if devices_status[serial]:
        return True
    
    # Device is disconnected, notify and wait for reconnection
    status_callback(pair, cycle, "WAITING", f"Device {serial} disconnected, waiting for reconnection...")
    
    # Wait for device to reconnect (with 60 second timeout)
    if wait_for_device_reconnection(serial, timeout=60):
        status_callback(pair, cycle, "RESUMING", f"Device {serial} reconnected, resuming test...")
        return True
    else:
        status_callback(pair, cycle, "FAIL", f"Device {serial} did not reconnect within timeout")
        return False


def _tick(seconds: int, pair: str, cycle: int, stage: str,
          cb: StatusCB, stop: threading.Event, dut_mo: str = None, dut_mt: str = None) -> bool:
    """
    Sleep *seconds* in 1-second steps, calling cb each tick with
    a live countdown.  Returns True when completed normally,
    False if stop was set early.
    
    If dut_mo and dut_mt are provided, checks device connections during ticks.
    """
    for remaining in range(seconds, 0, -1):
        if stop.is_set():
            return False
        cb(pair, cycle, stage, f"{remaining}s")
        
        # Check device connections every 5 seconds if devices are provided
        if dut_mo and dut_mt and remaining % 5 == 0:
            if not _check_device_connection(dut_mo, pair, cycle, stage, cb) or \
               not _check_device_connection(dut_mt, pair, cycle, stage, cb):
                return False
        
        time.sleep(1)
    return not stop.is_set()


def run_cycle(
    pair: str,
    dut_mo: str,
    dut_mt: str,
    phone_number: str,
    cycle: int,
    status_callback: StatusCB,
    stop_event: threading.Event | None = None,
) -> dict:
    stop = stop_event or threading.Event()   # fallback: never stops

    result_data = {
        "pair": pair, "mo_serial": dut_mo, "mt_serial": dut_mt,
        "cycle": cycle, "result": "FAIL", "error_type": "",
        "duration_ms": 0,
    }

    # ── 1. IDLE ──────────────────────────────────────────────
    if not _tick(config.IDLE_SECONDS, pair, cycle, "IDLE", status_callback, stop, dut_mo, dut_mt):
        log_call(result_data)
        return result_data

    # ── 2. Start call (MO) ───────────────────────────────────
    # Check device connection before starting call
    if not _check_device_connection(dut_mo, pair, cycle, "CALLING", status_callback):
        result_data["error_type"] = "DEVICE_DISCONNECTED"
        status_callback(pair, cycle, "FAIL", "MO device disconnected")
        log_call(result_data)
        return result_data
        
    status_callback(pair, cycle, "CALLING", f"→ {phone_number}")
    if not start_call(dut_mo, phone_number):
        result_data["error_type"] = "ADB_ERROR"
        status_callback(pair, cycle, "FAIL", "start_call failed")
        log_call(result_data)
        return result_data

    # short wait for phone to ring
    if not _tick(2, pair, cycle, "RINGING", status_callback, stop, dut_mo, dut_mt):
        end_call(dut_mo)
        log_call(result_data)
        return result_data

    # ── 3. Answer (MT) ───────────────────────────────────────
    # Check device connection before answering call
    if not _check_device_connection(dut_mt, pair, cycle, "ANSWERING", status_callback):
        end_call(dut_mo)
        result_data["error_type"] = "DEVICE_DISCONNECTED"
        status_callback(pair, cycle, "FAIL", "MT device disconnected")
        log_call(result_data)
        return result_data
        
    status_callback(pair, cycle, "ANSWERING", dut_mt)
    if not answer_call(dut_mt):
        end_call(dut_mo)
        result_data["error_type"] = "NO_ANSWER"
        status_callback(pair, cycle, "FAIL", "answer failed")
        log_call(result_data)
        return result_data

    call_start = time.monotonic()

    # ── 4. Active call window ────────────────────────────────
    if not _tick(config.CALL_SECONDS, pair, cycle, "ACTIVE", status_callback, stop, dut_mo, dut_mt):
        # Try to end calls if stopped early
        end_call(dut_mo)
        end_call(dut_mt)
        log_call(result_data)
        return result_data

    # ── 5. Check state ───────────────────────────────────────
    status_callback(pair, cycle, "CHECKING", "...")
    
    # Check device connections before getting call state
    if not _check_device_connection(dut_mo, pair, cycle, "CHECKING", status_callback) or \
       not _check_device_connection(dut_mt, pair, cycle, "CHECKING", status_callback):
        result_data["error_type"] = "DEVICE_DISCONNECTED"
        status_callback(pair, cycle, "FAIL", "Device disconnected during call check")
        end_call(dut_mo)
        end_call(dut_mt)
        log_call(result_data)
        return result_data
    
    state_mo = get_call_state(dut_mo)
    state_mt = get_call_state(dut_mt)
    result_data["duration_ms"] = int((time.monotonic() - call_start) * 1000)

    if state_mo == "OFFHOOK" and state_mt == "OFFHOOK":
        result_data["result"] = "PASS"
    else:
        result_data["result"] = "FAIL"
        result_data["error_type"] = "DROPPED"

    # ── 6. Hang up ───────────────────────────────────────────
    # Check device connections before ending calls
    if not _check_device_connection(dut_mo, pair, cycle, "HANGING UP", status_callback) or \
       not _check_device_connection(dut_mt, pair, cycle, "HANGING UP", status_callback):
        result_data["error_type"] = "DEVICE_DISCONNECTED"
        status_callback(pair, cycle, "FAIL", "Device disconnected during hang up")
        log_call(result_data)
        return result_data
    
    end_call(dut_mo)
    end_call(dut_mt)
    if not _tick(config.CALL_END_WAIT, pair, cycle, "HANGING UP", status_callback, stop, dut_mo, dut_mt):
        log_call(result_data)
        return result_data

    # ── 7. Signal info (from MO) ─────────────────────────────
    # Check device connection before getting signal info
    if _check_device_connection(dut_mo, pair, cycle, "SIGNAL_INFO", status_callback):
        result_data.update(get_signal_info(dut_mo))
    else:
        # Add default signal info if device disconnected
        result_data.update({"rat": "N/A", "rsrp": "N/A", "rsrq": "N/A", "sinr": "N/A", "scg_state": "N/A"})

    # ── 8. Done ──────────────────────────────────────────────
    status_callback(pair, cycle, result_data["result"], result_data.get("error_type", ""))
    log_call(result_data)
    return result_data
