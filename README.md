# 📡 Chorus

**Automated parallel voice call testing tool for Android devices over ADB.**

Chorus runs two device pairs simultaneously in separate threads, monitors call state in real time, and logs every result to CSV — replacing tedious manual call testing.

---

## Features

- 🔌 **ADB device scanner** — detects connected devices and lets you assign roles via GUI
- 📞 **Parallel execution** — two pairs (DUT + REF) run independently, each in its own thread
- ⏱️ **Live countdown** — per-second stage timer (IDLE → CALLING → ACTIVE → result)
- ✅ **Pass/Fail detection** — reads `dumpsys telephony.registry` to verify call state
- 📊 **CSV reporting** — every cycle timestamped and logged with signal metrics
- 🌙 **Dark-mode GUI** — built with tkinter, live status, progress bars, and charts
- 🧪 **Dry-run mode** — simulate full test runs without physical devices
- 🔄 **Synchronized testing** — barrier mode so both pairs start/finish each cycle together
- 📺 **scrcpy mirroring** — one-click screen mirror for MO and MT devices
- 📶 **RAT settings** — set Radio Access Technology (5G/4G/3G/2G) per SIM slot
- 📱 **SIM number reading** — auto-read phone numbers via Samsung diagnostic (`*#0##`)
- 📝 **Phone history** — remembers recently used numbers per pair
- 📈 **Signal metrics** — logs RAT, RSRP, RSRQ, SINR, Band per cycle
- 📍 **GPS tracking** — optional location logging with interactive HTML + static PNG maps

---

## Screenshots

> <img width="1049" height="779" alt="Chorus dark-mode dashboard" src="https://github.com/user-attachments/assets/f8b131c6-acd3-4eef-b4b5-1fd1be78dea3" />

---

## Requirements

| Requirement | Version | Notes |
|---|---|---|
| Python | 3.9+ | Uses `from __future__ import annotations` |
| `matplotlib` | 3.7+ | Charts & static GPS maps |
| `folium` | 0.14+ | Interactive GPS HTML maps |
| `adb` | any | Android Platform Tools in PATH |
| `scrcpy` | any | Optional — screen mirroring |

---

## Quick start

```bash
git clone https://github.com/Gonzo92/Chorus.git
cd Chorus
python main.py
```

1. Click **🔌 Pick Devices** — scans ADB and lets you assign MO/MT roles to each pair
2. Enter phone numbers for each pair (or use SIM auto-read)
3. Set loop count and timing
4. Click **▶ Start Test**

---

## Call cycle

```
IDLE (5s) → CALLING (MO dials MT) → RINGING (2s) → ANSWERING
         → ACTIVE (5-15s) → CHECK state → PASS / FAIL
         → HANG UP → log CSV + timestamps → next cycle
```

- **PASS** — both devices in OFFHOOK state after call window
- **FAIL** — DROPPED (call ended early) or ADB_ERROR / NO_ANSWER

---

## Output

Results saved to `Logs/results.csv`:

| Field | Description |
|---|---|
| `timestamp` | ISO-8601 datetime of the attempt |
| `pair` | `dut` or `ref` |
| `mo_serial` | Serial of the calling device |
| `mt_serial` | Serial of the answering device |
| `cycle` | Cycle index (1-based) |
| `result` | `PASS` / `FAIL` / `ERROR` |
| `error_type` | `DROPPED` / `NO_ANSWER` / `ADB_ERROR` |
| `duration_ms` | Measured call duration in ms |
| `call_type` | Voice / VoLTE / etc. |
| `rat` | 5G / LTE / WCDMA / GSM |
| `rsrp` | Reference Signal Receive Power |
| `rsrq` | Reference Signal Received Quality |
| `sinr` | Signal-to-Interference-plus-Noise Ratio |
| `band` | Carrier band (e.g. n78) |
| `lat` / `lon` | GPS coordinates (if GPS enabled) |

Additional files: `Logs/timestamps.txt`, `Logs/device_info.txt`, `Logs/summary_report.html`, `Logs/gps_map.html`, `Logs/gps_map.png`

---

## Project structure

```
Chorus/
├── main.py                    # GUI dashboard + thread orchestration
├── config.py                  # Default parameters
├── check_deps.py              # Pre-flight dependency checker
├── requirements.txt           # Python dependencies
├── run.bat                    # Launcher (checks deps, starts app)
├── chorus_config.json         # Persistent device serials (auto-created)
├── phone_history.json         # Recent phone numbers (auto-created)
│
├── core/                      # Core logic
│   ├── adb_controller.py      # ADB wrappers (call, signal, GPS, scrcpy)
│   ├── call_monitor.py        # Call cycle logic with live countdown
│   └── report.py              # CSV logging + summary + map generation
│
├── gui/                       # GUI components
│   ├── device_picker.py       # ADB scanner + role assignment dialog
│   ├── rat_dialog.py          # RAT settings dialog
│   └── device_controls.py     # Device controls dialog
│
├── utils/                     # Utilities
│   ├── rat_controller.py      # RAT ADB commands
│   ├── phone_history.py       # Phone number history manager
│   └── map_generator.py       # GPS map generation (HTML + PNG)
│
├── tools/                     # Dev tools
│   └── generate_icon.py       # Generates Chorus.ico
│
├── docs/
│   ├── README.md              # This file
│   └── SETUP.md               # Setup guide
│
└── Logs/                      # Output (auto-created)
    ├── results.csv
    ├── timestamps.txt
    ├── device_info.txt
    ├── summary_report.html
    ├── gps_map.html
    └── gps_map.png
```

---

## Configuration

All defaults are in `config.py`. The GUI overrides these at runtime.

| Parameter | Default | Description |
|---|---|---|
| `LOOP_COUNT` | 50 | Cycles per pair |
| `IDLE_SECONDS` | 5 | Wait between cycles |
| `CALL_SECONDS` | 5 | Call window duration |
| `CALL_END_WAIT` | 3 | Grace period after hang-up |
| `UPPERCASE_TEXT` | False | Uppercase display |
| `GPS_ENABLED` | False | Enable GPS tracking |
| `GPS_EVERY_N` | 5 | Collect GPS every N cycles |

---

## Background

Built to automate voice call regression testing on Android devices — replacing a fully manual process that required an operator to place and monitor calls throughout each test session. Chorus runs unattended, handles both pairs in parallel, and produces a clean CSV report at the end.

---

## License

MIT
