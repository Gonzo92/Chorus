# 📡 Chorus

**Automated parallel voice call testing tool for Android devices over ADB.**

Chorus runs two device pairs simultaneously in separate threads, monitors call state in real time, and logs every result to CSV — replacing tedious manual call testing.

---

## Features

- 🔌 **ADB device scanner** — detects connected devices and lets you assign roles via GUI
- 📞 **Parallel execution** — two pairs run independently, each in its own thread
- ⏱️ **Live countdown** — per-second stage timer (IDLE → CALLING → ACTIVE → result)
- ✅ **Pass/Fail detection** — reads `dumpsys telephony.registry` to verify call state
- 📊 **CSV reporting** — every cycle timestamped and logged automatically
- 🌙 **Dark-mode GUI** — built with tkinter, no external UI dependencies
- 🧪 **Dry-run mode** — simulate full test runs without physical devices

---

## Screenshots

> <img width="1049" height="779" alt="{34CBE4A3-DF58-43B6-80F9-FD47F3AFC7A4}" src="https://github.com/user-attachments/assets/f8b131c6-acd3-4eef-b4b5-1fd1be78dea3" />


---

## Requirements

- Python 3.10+
- `adb` available in system PATH
- Android devices with USB debugging enabled

No third-party Python packages required — stdlib only.

---

## Quick start

```bash
git clone https://github.com/Gonzo92/Chorus.git
cd Chorus
python main.py
```

1. Click **🔌 Pick Devices** — scans ADB and lets you assign MO/MT roles to each pair
2. Enter phone numbers for each pair
3. Set loop count and timing
4. Uncheck **DRY_RUN** for live mode
5. Click **▶ Start Test**

---

## Call cycle

```
IDLE (5s) → CALLING (MO dials MT) → RINGING (2s) → ANSWERING
         → ACTIVE (15s) → CHECK state → PASS / FAIL
         → HANG UP → next cycle
```

- **PASS** — both devices in OFFHOOK state after call window
- **FAIL** — DROPPED (call ended early) or ADB_ERROR / NO_ANSWER

---

## Output

Results saved to `logs/results.csv`:

| Field | Description |
|---|---|
| `timestamp` | ISO-8601 datetime of the attempt |
| `pair` | `pair_a` or `pair_b` |
| `mo_serial` | Serial of the calling device |
| `mt_serial` | Serial of the answering device |
| `cycle` | Cycle index (1-based) |
| `result` | `PASS` or `FAIL` |
| `error_type` | `DROPPED` / `NO_ANSWER` / `ADB_ERROR` |
| `duration_ms` | Measured call duration in ms |

---

## Project structure

```
Chorus/
├── main.py            # GUI dashboard + thread orchestration
├── config.py          # Default parameters
├── adb_controller.py  # ADB wrappers (start/end/answer call, signal info)
├── call_monitor.py    # Single cycle logic with live countdown callbacks
├── device_picker.py   # ADB scanner + role assignment dialog
├── report.py          # CSV init and logging
└── logs/
    └── results.csv    # Auto-created on first run
```

---

## Configuration

All defaults are in `config.py`. The GUI overrides these at runtime — no need to edit the file between sessions.

| Parameter | Default | Description |
|---|---|---|
| `LOOP_COUNT` | 50 | Cycles per pair |
| `IDLE_SECONDS` | 5 | Wait between cycles |
| `CALL_SECONDS` | 15 | Call window duration |
| `CALL_END_WAIT` | 3 | Grace period after hang-up |


---

## Background

Built to automate voice call regression testing on Android devices — replacing a fully manual process that required an operator to place and monitor calls throughout each test session. Chorus runs unattended, handles both pairs in parallel, and produces a clean CSV report at the end.

---

## License

MIT
