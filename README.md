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
- 📲 **APK installation** — drag & drop multi-APK support on all devices
- 🛡️ **Dropped-call detection** — monitors ACTIVE stage, ends call if either device drops
- 📞 **CSFB/VoLTE classification** — automatic call type detection
- ⚡ **Early RINGING exit** — exits RINGING when MT already answers
- 🔠 **Uppercase text toggle** — configurable display mode

---

## Screenshots

> [![Chorus dark-mode dashboard](https://private-user-images.githubusercontent.com/78420870/568968400-f8b131c6-acd3-4eef-b4b5-1fd1be78dea3.png?jwt=eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpc3MiOiJnaXRodWIuY29tIiwiYXVkIjoicmF3LmdpdGh1YnVzZXJjb250ZW50LmNvbSIsImtleSI6ImtleTUiLCJleHAiOjE3ODQ1NTE4OTIsIm5iZiI6MTc4NDU1MTU5MiwicGF0aCI6Ii83ODQyMDg3MC81Njg5Njg0MDAtZjhiMTMxYzYtYWNkMy00ZWVmLWI0YjUtMWZkMWJlNzhkZWEzLnBuZz9YLUFtei1BbGdvcml0aG09QVdTNC1ITUFDLVNIQTI1NiZYLUFtei1DcmVkZW50aWFsPUFLSUFWQ09EWUxTQTUzUFFLNFpBJTJGMjAyNjA3MjAlMkZ1cy1lYXN0LTElMkZzMyUyRmF3czRfcmVxdWVzdCZYLUFtei1EYXRlPTIwMjYwNzIwVDEyNDYzMlomWC1BbXotRXhwaXJlcz0zMDAmWC1BbXotU2lnbmF0dXJlPTEzYjRjM2FjOTllODE4YzYyZWY1YmQyYmVmNTE0ZGQxMzg4MmVmODBkYmNiMTRiZmYyMWI4MTY4ZjVmZTA3MGImWC1BbXotU2lnbmVkSGVhZGVycz1ob3N0JnJlc3BvbnNlLWNvbnRlbnQtdHlwZT1pbWFnZSUyRnBuZyJ9.FqmiHUAlltr7GbaMai9oVjlaXnZqC_kR66OCQDDk-dU)](https://private-user-images.githubusercontent.com/78420870/568968400-f8b131c6-acd3-4eef-b4b5-1fd1be78dea3.png?jwt=eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpc3MiOiJnaXRodWIuY29tIiwiYXVkIjoicmF3LmdpdGh1YnVzZXJjb250ZW50LmNvbSIsImtleSI6ImtleTUiLCJleHAiOjE3ODQ1NTE4OTIsIm5iZiI6MTc4NDU1MTU5MiwicGF0aCI6Ii83ODQyMDg3MC81Njg5Njg0MDAtZjhiMTMxYzYtYWNkMy00ZWVmLWI0YjUtMWZkMWJlNzhkZWEzLnBuZz9YLUFtei1BbGdvcml0aG09QVdTNC1ITUFDLVNIQTI1NiZYLUFtei1DcmVkZW50aWFsPUFLSUFWQ09EWUxTQTUzUFFLNFpBJTJGMjAyNjA3MjAlMkZ1cy1lYXN0LTElMkZzMyUyRmF3czRfcmVxdWVzdCZYLUFtei1EYXRlPTIwMjYwNzIwVDEyNDYzMlomWC1BbXotRXhwaXJlcz0zMDAmWC1BbXotU2lnbmF0dXJlPTEzYjRjM2FjOTllODE4YzYyZWY1YmQyYmVmNTE0ZGQxMzg4MmVmODBkYmNiMTRiZmYyMWI4MTY4ZjVmZTA3MGImWC1BbXotU2lnbmVkSGVhZGVycz1ob3N0JnJlc3BvbnNlLWNvbnRlbnQtdHlwZT1pbWFnZSUyRnBuZyJ9.FqmiHUAlltr7GbaMai9oVjlaXnZqC_kR66OCQDDk-dU)

---

## Requirements

| Requirement  | Version  | Notes                          |
|-------------|----------|--------------------------------|
| Python      | 3.10+    | Uses `X | Y` union types       |
| matplotlib  | 3.7+     | Charts & static GPS maps       |
| folium      | 0.14+    | Interactive GPS HTML maps      |
| ADB         | any      | Android Platform Tools in PATH |
| scrcpy      | any      | Optional — screen mirroring    |

---

## Quick start

```bash
git clone https://github.sec.samsung.net/SDV-SQE/Chorus.git
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
IDLE (5s) → start_call (MO) → answer_call (MT)
         → wait CALL_SECONDS → check call state
         → PASS (OFFHOOK) | FAIL (IDLE/DROPPED)
         → end_call both sides → log CSV → log timestamps → repeat
```

**v2.4+ enhancements:**
- **Dropped-call detection**: During ACTIVE, checks both MO/MT every second; ends call if either drops
- **CSFB/VoLTE classification**: Automatically detects call type (VoLTE for LTE/ENDC, CSFB for UMTS/GSM)
- **Early RINGING exit**: If MT already answers (OFFHOOK) during RINGING, exits early
- **GPS tracking**: Background GPS collection during call with coordinate logging
- **Signal monitoring**: RSRP/RSRQ/SINR/Band collected during ACTIVE stage

---

## Output

Results saved to `Logs/results.csv`:

| Field        | Description                                |
|-------------|--------------------------------------------|
| `timestamp` | ISO-8601 start time                        |
| `pair`      | `dut` or `ref`                             |
| `mo_serial` | Calling device serial                      |
| `mt_serial` | Answering device serial                    |
| `cycle`     | Cycle number                               |
| `result`    | PASS / FAIL / ERROR                        |
| `error_type`| Error category (or empty)                  |
| `duration_ms`| Measured call duration in ms              |
| `call_type` | Voice / VoLTE / CSFB / etc.                |
| `rat`       | 5G / LTE / WCDMA / GSM                     |
| `rsrp`      | Reference Signal Receive Power             |
| `rsrq`      | Reference Signal Received Quality          |
| `sinr`      | Signal-to-Interference-plus-Noise Ratio    |
| `band`      | Carrier band (e.g. n78)                    |
| `lat` / `lon`| GPS coordinates (if GPS enabled)          |

Additional files: `Logs/timestamps.txt`, `Logs/device_info.txt`, `Logs/summary_report.html`, `Logs/gps_map.html`, `Logs/gps_map.png`

---

## Project structure

```
Chorus/
├── main.py                    # tkinter GUI entry point
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
│   ├── report.py              # CSV logging + summary + map generation
│   ├── sync_coordinator.py    # Synchronized lockstep testing (barrier)
│   ├── apk_parser.py          # APK manifest parser
│   └── csv_parser.py          # CSV parsing and analysis
│
├── gui/                       # GUI components
│   ├── device_picker.py       # ADB scanner + role assignment dialog
│   ├── device_controls.py     # SIM stack control dialog
│   ├── rat_dialog.py          # RAT settings dialog
│   ├── config_tab.py          # Configuration panel
│   ├── pair_tab.py            # Pair status panels
│   ├── log_tab.py             # Live log panel
│   ├── summary_dialog.py      # Summary dialog
│   ├── chart_panel.py         # Signal strength charts
│   └── ...
│
├── utils/                     # Utilities
│   ├── theme.py               # Centralized theme constants
│   ├── phone_history.py       # Phone number history manager
│   ├── rat_controller.py      # RAT ADB commands
│   └── map_generator.py       # GPS map generation (HTML + PNG)
│
├── tools/                     # Dev tools
│   ├── investigate_ims.py     # IMS/VoLTE investigation script
│   └── _analyze_excel.py      # Excel analysis tool
│
├── scripts/                   # Build/install scripts
│   ├── install.bat            # Dependency installer
│   ├── run_chorus.bat         # Quick launcher
│   └── call_automator.spec    # PyInstaller spec
│
├── docs/
│   ├── README.md              # This file
│   └── SETUP.md               # Setup guide
│
└── Logs/                      # Output (auto-created)
    ├── results.csv
    ├── timestamps.txt
    ├── device_info.txt
    ├── summary_*.csv
    ├── gps_map.html
    └── gps_map.png
```

---

## Configuration

All defaults are in `config.py`. The GUI overrides these at runtime.

| Parameter        | Default | Description                              |
|-----------------|---------|------------------------------------------|
| `LOOP_COUNT`    | 50      | Cycles per pair                          |
| `IDLE_SECONDS`  | 5       | Wait between cycles                      |
| `CALL_SECONDS`  | 5       | Call window duration                     |
| `CALL_END_WAIT` | 3       | Grace period after end_call              |
| `UPPERCASE_TEXT`| False   | Uppercase display                        |
| `GPS_ENABLED`   | False   | Enable GPS tracking                      |
| `GPS_EVERY_N`   | 5       | Collect GPS every N cycles               |
| `SYNC_TIMEOUT`  | 30      | Barrier sync timeout (seconds)           |

---

## Pair definitions

| Key       | Role  | Description     |
|-----------|-------|-----------------|
| `dut_MO`  | DUT   | Calling device  |
| `dut_MT`  | DUT   | Answering device|
| `ref_MO`  | REF   | Calling device  |
| `ref_MT`  | REF   | Answering device|

Direction is hard-coded: **MO always dials MT** in every cycle.

---

## GPS tracking

During ACTIVE stage, GPS coordinates are collected in the background and plotted on:
- **Interactive HTML map** (`gps_map.html`) — generated with folium, shows all test points
- **Static PNG map** (`gps_map.png`) — generated with matplotlib for documentation

GPS data is also logged in `results.csv` (lat, lon, accuracy columns).

---

## APK installation

Chorus supports installing APK files on all connected devices:
- **Drag & drop** APK files onto the APK tile in Device Picker
- **Multi-APK support** — install multiple APKs in sequence
- **Background installation** — runs in a separate thread, doesn't block UI
- **Result reporting** — success/failure shown per device with log panel updates

---

## Background

Built to automate voice call regression testing on Android devices — replacing a fully manual process that required an operator to place and monitor calls throughout each test session. Chorus runs unattended, handles both pairs in parallel, and produces a clean CSV report at the end.

---

## License

Created by m.galazka2