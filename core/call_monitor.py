# ============================================================
#  Chorus v2.2  –  core/call_monitor.py
#  Orchestrates one call cycle. MO always calls, MT always answers.
#  Sends per-second countdown callbacks so the UI can show a timer.
# ============================================================

from __future__ import annotations

import time
import threading
from typing import Callable
import config as cfg

StatusCB = Callable[[str, int, str, str], None]
from core.adb_controller import start_call, end_call, answer_call, get_call_state, get_signal_info, get_gps_info
from core.report import log_call

def _tick(seconds: int, pair: str, cycle: int, stage: str,
          cb: StatusCB, stop: threading.Event, dut_mo: str = None, dut_mt: str = None) -> bool:
    """
    Sleep *seconds* in 1-second steps, calling cb each tick with
    a live countdown.  Returns True when completed normally,
    False if stop was set early.
    
    For ACTIVE stage, checks call state every second to detect dropped calls.
    """
    import time as time_module
    start_time = time_module.monotonic()
    
    for remaining in range(seconds, 0, -1):
        if stop.is_set():
            return False
        cb(pair, cycle, stage, f"{remaining}s")
        
        # For ACTIVE stage, check call state every second to detect dropped calls
        if stage == "ACTIVE" and dut_mo and dut_mt:
            state_mo = get_call_state(dut_mo)
            state_mt = get_call_state(dut_mt)
            
            # If either call is dropped, end both calls and return early
            if state_mo != "OFFHOOK" or state_mt != "OFFHOOK":
                end_call(dut_mo)
                end_call(dut_mt)
                return False
        
        # For RINGING stage, check if MT already answered (OFFHOOK) – exit early
        if stage == "RINGING" and dut_mo and dut_mt:
            state_mt = get_call_state(dut_mt)
            if state_mt == "OFFHOOK":
                return True
        
        # Calculate how long we should sleep to maintain accurate timing
        elapsed = time_module.monotonic() - start_time
        target_time = (seconds - remaining + 1)
        sleep_time = target_time - elapsed
        
        # Only sleep if we have time left and sleep_time is positive
        if sleep_time > 0 and not stop.is_set():
            time_module.sleep(min(sleep_time, 1.0))
    
    return not stop.is_set()


def run_cycle(
    pair: str,
    dut_mo: str,
    dut_mt: str,
    phone_number: str,
    cycle: int,
    status_callback: StatusCB,
    stop_event: threading.Event | None = None,
    max_answer_retries: int = 3,
    answer_retry_delay: int = 1,
) -> dict:
    stop = stop_event or threading.Event()   # fallback: never stops

    result_data = {
        "pair": pair, "mo_serial": dut_mo, "mt_serial": dut_mt,
        "cycle": cycle, "result": "FAIL", "error_type": "",
        "duration_ms": 0,
        "call_type": "UNKNOWN",  # Dodatkowe pole do śledzenia typu połączenia
    }
    
    # Initialize signal data
    signal_data = {}

    # ── 1. IDLE ──────────────────────────────────────────────
    if not _tick(cfg.IDLE_SECONDS, pair, cycle, "IDLE", status_callback, stop):
        log_call(result_data)
        return result_data

    # ── 1b. GPS collection (background, every N cycles) ──────
    if cfg.GPS_ENABLED and cycle % cfg.GPS_EVERY_N == 0:
        gps_serial = cfg.GPS_SERIAL or dut_mo
        gps_data = get_gps_info(gps_serial)
        result_data.update({
            "lat": gps_data.get("lat"),
            "lon": gps_data.get("lon"),
            "gps_accuracy": gps_data.get("accuracy"),
            "gps_time": gps_data.get("timestamp"),
            "gps_provider": gps_data.get("provider"),
        })

    # ── 2. Start call (MO) ───────────────────────────────────
    status_callback(pair, cycle, "CALLING", f"→ {phone_number}")
    if not start_call(dut_mo, phone_number):
        result_data["error_type"] = "ADB_ERROR"
        status_callback(pair, cycle, "FAIL", "start_call failed")
        log_call(result_data)
        return result_data

    # short wait for phone to ring
    _tick(20, pair, cycle, "RINGING", status_callback, stop)
    if stop.is_set():
        end_call(dut_mo)
        log_call(result_data)
        return result_data

    # ── 3. Answer (MT) with retry ───────────────────────────────────────
    status_callback(pair, cycle, "ANSWERING", dut_mt)
    
    # Try to answer the call with retries
    answer_success = False
    for attempt in range(max_answer_retries):
        if answer_call(dut_mt):
            answer_success = True
            break
        elif attempt < max_answer_retries - 1:  # If not the last attempt
            # Wait before retrying
            for i in range(answer_retry_delay, 0, -1):
                if stop.is_set():
                    end_call(dut_mo)
                    result_data["error_type"] = "NO_ANSWER"
                    status_callback(pair, cycle, "FAIL", "answer failed (stopped)")
                    log_call(result_data)
                    return result_data
                status_callback(pair, cycle, "ANSWERING", f"retry in {i}s")
                time.sleep(1)
    
    if not answer_success:
        end_call(dut_mo)
        result_data["error_type"] = "NO_ANSWER"
        status_callback(pair, cycle, "FAIL", "answer failed")
        log_call(result_data)
        return result_data

    call_start = time.monotonic()

    # ── 4. Active call window ────────────────────────────────
    if not _tick(cfg.CALL_SECONDS, pair, cycle, "ACTIVE", status_callback, stop, dut_mo, dut_mt):
        # Check if this was due to a dropped call
        state_mo = get_call_state(dut_mo)
        state_mt = get_call_state(dut_mt)
        
        # Jeśli połączenie się zakończyło, sprawdź typ połączenia przed oceną wyniku
        signal_info = get_signal_info(dut_mo)
        result_data.update(signal_info)
        
        # Jeśli połączenie było VoLTE i się zakończyło, to może być CSFB
        # W takim przypadku uznajemy to za poprawne zakończenie
        if signal_info.get("rat") in ["LTE", "LTE+NR", "ENDC"]:
            result_data["call_type"] = "VoLTE"
            result_data["result"] = "FAIL"
            result_data["error_type"] = "DROPPED"
            status_callback(pair, cycle, "FAIL", "call dropped")
        elif signal_info.get("rat") in ["UMTS", "GSM", "WCDMA"]:
            result_data["call_type"] = "CSFB"
            result_data["result"] = "PASS"  # CSFB jest akceptowalne
            result_data["error_type"] = "CSFB_COMPLETED"
            status_callback(pair, cycle, "PASS", "CSFB completed")
        else:
            result_data["result"] = "FAIL"
            result_data["error_type"] = "DROPPED"
            status_callback(pair, cycle, "FAIL", "call dropped")
        
        log_call(result_data)
        return result_data

    # ── 5. Check state ───────────────────────────────────────
    status_callback(pair, cycle, "CHECKING", "...")
    state_mo = get_call_state(dut_mo)
    state_mt = get_call_state(dut_mt)
    result_data["duration_ms"] = int((time.monotonic() - call_start) * 1000)

    # Pobierz informacje o sygnale przed zakończeniem połączenia
    signal_info = get_signal_info(dut_mo)
    result_data.update(signal_info)
    
    # Określ typ połączenia na podstawie informacji o sygnale
    if signal_info.get("rat") in ["LTE", "LTE+NR", "ENDC"]:
        result_data["call_type"] = "VoLTE"
    elif signal_info.get("rat") in ["UMTS", "GSM", "WCDMA"]:
        result_data["call_type"] = "CSFB"
    else:
        result_data["call_type"] = "UNKNOWN"

    if state_mo == "OFFHOOK" and state_mt == "OFFHOOK":
        result_data["result"] = "PASS"
    else:
        # Jeśli połączenie się zakończyło, ale było CSFB, to uznajemy za poprawne
        if result_data["call_type"] == "CSFB":
            result_data["result"] = "PASS"
            result_data["error_type"] = "CSFB_COMPLETED"
        else:
            result_data["result"] = "FAIL"
            result_data["error_type"] = "DROPPED"

    # ── 6. Hang up ───────────────────────────────────────────
    end_call(dut_mo)
    end_call(dut_mt)
    if not _tick(cfg.CALL_END_WAIT, pair, cycle, "HANGING UP", status_callback, stop):
        log_call(result_data)
        return result_data

    # ── 7. Signal info (from MO) ─────────────────────────────
    # Już pobrane wcześniej

    # ── 8. Done ──────────────────────────────────────────────
    status_callback(pair, cycle, result_data["result"], result_data.get("error_type", ""))
    log_call(result_data)
    return result_data