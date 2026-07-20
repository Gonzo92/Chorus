# ============================================================
#  Chorus v2.4  –  core/call_monitor.py
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
from core.adb_commands import check_ims_state

def _tick(seconds: int, pair: str, cycle: int, stage: str,
          cb: StatusCB, stop: threading.Event, dut_mo: str = None, dut_mt: str = None, start_time: float = None) -> bool:
    """
    Sleep *seconds* in 1-second steps, calling cb each tick with
    a live countdown based on actual elapsed time.  Returns True when
    completed normally, False if stop was set early.
    
    For ACTIVE stage, checks call state every 2 seconds to detect dropped calls.
    For RINGING stage, checks if MT becomes OFFHOOK to detect ringing.
    """
    import time as time_module
    if start_time is None:
        start_time = time_module.monotonic()
    t_start = start_time
    
    elapsed = 0
    while elapsed < seconds:
        if stop.is_set():
            return False
        
        remaining = max(0, seconds - round(elapsed))
        cb(pair, cycle, stage, f"{remaining}s")
        
        # For ACTIVE stage, check call state every 2 seconds to detect dropped/ended calls
        if stage == "ACTIVE" and dut_mo and dut_mt:
            if round(elapsed) % 2 == 0:
                state_mo = get_call_state(dut_mo)
                state_mt = get_call_state(dut_mt)
                
                # Drop = one side OFFHOOK, other side suddenly IDLE (before time)
                if (state_mo == "OFFHOOK" and state_mt == "IDLE") or \
                   (state_mo == "IDLE" and state_mt == "OFFHOOK"):
                    print(f"[CYCLE] 🚨 {pair} cycle={cycle} DROP detected: MO={state_mo} MT={state_mt}")
                    end_call(dut_mo)
                    end_call(dut_mt)
                    return False
                
                # Both IDLE = natural end, exit early
                if state_mo == "IDLE" and state_mt == "IDLE":
                    print(f"[CYCLE] ✅ {pair} cycle={cycle} call ended naturally (both IDLE)")
                    return False
        
        # For RINGING stage, check if MT is ringing (OFFHOOK) – exit early
        if stage == "RINGING" and dut_mo and dut_mt:
            if round(elapsed) % 2 == 0:
                state_mt = get_call_state(dut_mt)
                if state_mt == "OFFHOOK":
                    return True
        
        # Sleep for 1 second, accounting for ADB overhead
        time_module.sleep(1.0)
        elapsed = time_module.monotonic() - start_time
    
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
    sync=None,
) -> dict:
    stop = stop_event or threading.Event()   # fallback: never stops

    result_data = {
        "pair": pair, "mo_serial": dut_mo, "mt_serial": dut_mt,
        "cycle": cycle, "result": "FAIL", "error_type": "",
        "duration_ms": 0,
        "call_type": "UNKNOWN",
    }
    
    # ── 1. IDLE ──────────────────────────────────────────────
    if not _tick(cfg.IDLE_SECONDS, pair, cycle, "IDLE", status_callback, stop):
        log_call(result_data)
        return result_data

    # ── 1b. GPS collection (background, every N cycles) ──────
    if cfg.GPS_ENABLED and cycle % cfg.GPS_EVERY_N == 0:
        gps_serial = cfg.GPS_SOURCE or cfg.GPS_SERIAL or dut_mo
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
    print(f"[CALL] 📞 {pair} MO={dut_mo} → {phone_number}")
    if not start_call(dut_mo, phone_number):
        result_data["error_type"] = "ADB_ERROR"
        status_callback(pair, cycle, "FAIL", "start_call failed")
        print(f"[CALL] ❌ {pair} start_call FAILED")
        log_call(result_data)
        return result_data
    print(f"[CALL] ✅ {pair} start_call OK")

    # ── 3. RINGING – wait for call to ring ───────────────────
    # Wait for MT to enter RINGING state, then answer.
    # Poll MT state every 0.5s until RINGING or timeout.
    status_callback(pair, cycle, "RINGING", "waiting for MT...")
    print(f"[CYCLE] ⏱️ {pair} cycle={cycle} waiting for MT={dut_mt} to enter RINGING state...")
    ring_start = time.monotonic()
    mt_in_ringing = False
    while (time.monotonic() - ring_start) < cfg.RINGING_TIMEOUT:
        if stop.is_set():
            end_call(dut_mo)
            log_call(result_data)
            return result_data
        
        state_mt = get_call_state(dut_mt)
        state_mo = get_call_state(dut_mo)
        print(f"[CYCLE] ⏱️ {pair} cycle={cycle} MT={state_mt} MO={state_mo} elapsed={time.monotonic()-ring_start:.1f}s")
        
        if state_mt == "RINGING":
            mt_in_ringing = True
            print(f"[CYCLE] ⏱️ {pair} cycle={cycle} MT is RINGING after {(time.monotonic()-ring_start):.1f}s")
            break
        
        if state_mt == "OFFHOOK":
            # Already answered somehow, skip answer
            print(f"[CYCLE] ⏱️ {pair} cycle={cycle} MT already OFFHOOK, skipping answer")
            mt_in_ringing = True
            break
        
        time.sleep(0.5)
    
    if not mt_in_ringing:
        print(f"[CYCLE] ⏱️ {pair} cycle={cycle} MT never entered RINGING, timeout after {cfg.RINGING_TIMEOUT}s")
        end_call(dut_mo)
        result_data["error_type"] = "NO_RINGING"
        status_callback(pair, cycle, "FAIL", "MT never rang")
        log_call(result_data)
        return result_data

    # ── 4. Answer (MT) with retry ────────────────────────────
    # Program controls answering – MT never answers automatically.
    print(f"[CYCLE] ⏱️ {pair} cycle={cycle} starting answer_call for MT={dut_mt}")
    
    answer_success = False
    for attempt in range(max_answer_retries):
        if answer_call(dut_mt):
            answer_success = True
            status_callback(pair, cycle, "ANSWERED", "Connection accepted ✓")
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

    # ── Check IMS state (for CS vs CSFB classification) ──────
    ims_state = check_ims_state(dut_mo)
    ims_enabled = ims_state.get("enabled")
    ims_registered = ims_state.get("registered")
    
    call_start = time.monotonic()
    print(f"[CYCLE] ⏱️ {pair} cycle={cycle} answer done at {time.strftime('%H:%M:%S')}, call_start={call_start:.1f}")

    # ── 5. Active call window ────────────────────────────────
    print(f"[CYCLE] ⏱️ {pair} cycle={cycle} starting ACTIVE stage for {cfg.CALL_SECONDS}s")
    active_start = time.monotonic()
    tick_result = _tick(cfg.CALL_SECONDS, pair, cycle, "ACTIVE", status_callback, stop, dut_mo, dut_mt)
    active_duration = time.monotonic() - active_start
    print(f"[CYCLE] ⏱️ {pair} cycle={cycle} ACTIVE stage {'ended early' if not tick_result else 'completed'} after {active_duration:.1f}s")
    
    # Force end if call is still active after window
    if active_duration >= 8.0:
        print(f"[CYCLE] ⏱️ {pair} cycle={cycle} force end after {active_duration:.1f}s")
        end_call(dut_mo)
        end_call(dut_mt)
        time.sleep(1.0)

    # ── 6. Check state ───────────────────────────────────────
    status_callback(pair, cycle, "CHECKING", "...")
    state_mo = get_call_state(dut_mo)
    state_mt = get_call_state(dut_mt)
    result_data["duration_ms"] = int((time.monotonic() - call_start) * 1000)

    # Get signal info
    signal_info = get_signal_info(dut_mo)
    result_data.update(signal_info)
    
    # Determine call type with IMS check to distinguish CS from CSFB
    rat = signal_info.get("rat", "N/A")
    ims_state = check_ims_state(dut_mo)
    ims_enabled = ims_state.get("enabled", None)
    ims_registered = ims_state.get("registered", None)
    
    if rat in ["LTE", "LTE+NR", "ENDC", "NR"]:
        result_data["call_type"] = "VoLTE"
    elif rat in ["UMTS", "GSM", "WCDMA"]:
        if ims_enabled is True or ims_registered is True:
            result_data["call_type"] = "CSFB"
        else:
            result_data["call_type"] = "CS"
    else:
        result_data["call_type"] = "UNKNOWN"
    
    # Update log with final call type
    status_callback(pair, cycle, "SIGNAL", f"RAT: {rat} | {result_data['call_type']}")

    # Determine result based on call state
    if state_mo == "IDLE" and state_mt == "IDLE":
        # Both ended naturally
        result_data["result"] = "PASS"
        result_data["error_type"] = ""
    elif state_mo == "OFFHOOK" or state_mt == "OFFHOOK":
        # Still active after window – not a drop, just end it
        result_data["result"] = "PASS"
        result_data["error_type"] = ""
    elif (state_mo == "OFFHOOK" and state_mt == "IDLE") or \
         (state_mo == "IDLE" and state_mt == "OFFHOOK"):
        # One side dropped mid-call
        result_data["result"] = "FAIL"
        result_data["error_type"] = "DROPPED"
    else:
        # Both RINGING, UNKNOWN, or other – treat as PASS (not a drop)
        result_data["result"] = "PASS"
        result_data["error_type"] = ""

    # ── 7. Hang up with timeout ──────────────────────────────
    end_call(dut_mo)
    end_call(dut_mt)
    
    # Wait for call to end with timeout (max 5s)
    hang_start = time.monotonic()
    while (time.monotonic() - hang_start) < 5.0:
        s_mo = get_call_state(dut_mo)
        s_mt = get_call_state(dut_mt)
        if s_mo == "IDLE" and s_mt == "IDLE":
            break
        time.sleep(0.5)
    
    # Final force end if still active
    state_mo = get_call_state(dut_mo)
    state_mt = get_call_state(dut_mt)
    if state_mo != "IDLE" or state_mt != "IDLE":
        print(f"[CYCLE] ⚠️ {pair} cycle={cycle} call still active after hangup, forcing...")
        for _ in range(3):
            end_call(dut_mo)
            end_call(dut_mt)
            time.sleep(0.5)
            if get_call_state(dut_mo) == "IDLE" and get_call_state(dut_mt) == "IDLE":
                break

    # ── 8. Done ──────────────────────────────────────────────
    
    status_callback(pair, cycle, result_data["result"], result_data.get("error_type", ""))
    log_call(result_data)
    return result_data
