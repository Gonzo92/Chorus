# Chorus v2.10

Automated voice-call testing tool for Android devices over ADB.  
Dark-mode desktop dashboard built with tkinter — runs two device pairs in parallel with live status, charts, and CSV reporting.

---

## Features

- **tkinter GUI** — dark-mode dashboard with live status, progress bars, per-cycle timers, and signal charts
- **Parallel testing** — two independent device pairs (DUT + REF) running in separate threads with synchronized barrier sync
- **Device Picker** — interactive dialog to scan ADB-connected devices and assign roles (`dut_MO`, `dut_MT`, `ref_MO`, `ref_MT`)
- **Live Pass/Fail chart** — real-time bar chart tracking pass/fail counts per pair
- **Signal strength charts** — per-cycle RSRP/RSRQ/SINR/Band visualization during ACTIVE stage
- **GPS tracking** — background GPS collection with HTML (folium) and PNG (matplotlib) map generation
- **Synchronized testing** — `threading.Barrier(2)` ensures both pairs start and finish each cycle simultaneously
- **scrcpy mirroring** — one-click screen mirror for MO and MT devices of each pair
- **RAT settings** — dialog to set Radio Access Technology (5G/4G/3G/2G) per SIM slot
- **SIM stack control** — toggle DATA/CALL/SMS/IMS states per device
- **SIM number reading** — auto-read phone numbers from device (`*#0##` Samsung diagnostic)
- **Phone number history** — remembers recently used numbers per pair (dropdown with refresh/history buttons)
- **Persistent config** — device serials and phone numbers saved to `chorus_config.json` between runs
- **Timestamps file** — per-cycle time log with full signal info: RAT, RSRP, RSRQ, SINR, Band, call type, GPS coords
- **Device info file** — exports test configuration and device details to the output folder
- **CSV reporting** — detailed per-call results with signal metrics and GPS coordinates
- **Summary report** — aggregated stats: pass/fail counts, success rate, average duration, error distribution
- **System sounds** — audio feedback on PASS/FAIL/WARN events
- **Dry-run mode** — simulate all ADB calls with random but realistic values (no devices needed)
- **Dropped-call detection** — monitors call state every second during ACTIVE; ends call immediately if either device drops
- **CSFB/VoLTE classification** — automatic call type detection (VoLTE for LTE/ENDC, CSFB for UMTS/GSM)
- **Early RINGING exit** — exits RINGING stage early if MT already answers (OFFHOOK)
- **APK installation** — multi-APK support with drag & drop, background installation on all devices
- **Uppercase text toggle** — configurable display mode for all UI text

---

## Directory layout

```
Chorus/
├── main.py                    ← tkinter GUI entry point
├── config.py                  ← default configuration values
├── check_deps.py              ← pre-flight dependency checker
├── requirements.txt           ← Python dependencies
├── .gitignore
├── Chorus.ico                 ← application icon
│
├── core/                      ← core logic modules
│   ├── adb_controller.py      ← ADB commands (call, answer, signal, GPS, scrcpy)
│   ├── call_monitor.py        ← call cycle orchestration with per-second callbacks
│   ├── report.py              ← CSV logging + summary generation
│   ├── sync_coordinator.py    ← synchronized lockstep testing (barrier)
│   ├── apk_parser.py          ← APK manifest parser
│   └── csv_parser.py          ← CSV parsing and analysis
│
├── gui/                       ← GUI components
│   ├── device_picker.py       ← ADB device scanning & role assignment
│   ├── device_controls.py     ← SIM stack control dialog (DATA/CALL/SMS/IMS)
│   ├── rat_dialog.py          ← RAT settings dialog
│   ├── config_tab.py          ← Configuration panel
│   ├── pair_tab.py            ← Pair status panels
│   ├── log_tab.py             ← Live log panel
│   ├── summary_dialog.py      ← Summary dialog
│   ├── chart_panel.py         ← Signal strength charts
│   └── ...
│
├── utils/                     ← utility modules
│   ├── theme.py               ← Centralized theme constants
│   ├── phone_history.py       ← phone number history manager
│   ├── rat_controller.py      ← RAT setting functions
│   └── map_generator.py       ← GPS map generation (HTML + PNG)
│
├── tools/                     ← development tools
│   ├── investigate_ims.py     ← IMS/VoLTE investigation script
│   └── _analyze_excel.py      ← Excel analysis tool
│
├── scripts/                   ← build/install scripts
│   ├── install.bat            ← dependency installer
│   ├── run_chorus.bat         ← quick launcher
│   └── call_automator.spec    ← PyInstaller spec
│
├── docs/                      ← documentation
│
└── Logs/                      ← output (auto-created)
    ├── results.csv            ← per-call detailed results
    ├── timestamps.txt         ← per-cycle timestamp log
    ├── device_info.txt        ← exported test configuration
    ├── summary_*.csv          ← aggregated summary reports
    ├── gps_map.html           ← interactive GPS map (folium)
    └── gps_map.png            ← static GPS map (matplotlib)
```

---

## Requirements

| Requirement  | Version  | Notes                          |
|-------------|----------|--------------------------------|
| Python      | 3.10+    | Uses `X | Y` union types       |
| matplotlib  | 3.7+     | Installed via `install.bat`    |
| ADB         | any      | Android Platform Tools         |
| scrcpy      | any      | Optional — screen mirroring    |

---

## Quick start

1. **Connect all 4 devices** via USB and enable USB Debugging. Authorise ADB when prompted.
2. **Run the installer:**
   ```
   install.bat
   ```
3. **Launch Chorus:**
   ```
   run_chorus.bat
   ```
   or
   ```
   python main.py
   ```

---

## Using the GUI

### Configuration panel (left sidebar)

| Field             | Description                                         |
|-------------------|-----------------------------------------------------|
| **DUT / REF**     | Enable/disable each pair independently              |
| **MO serial**     | Serial of the calling device                        |
| **MT serial**     | Serial of the answering device                      |
| **MT number**     | Phone number to dial — combobox with SIM numbers    |
| **Loop count**    | Total call cycles per pair                          |
| **Idle (s)**      | Wait time between cycles                            |
| **Call (s)**      | Duration to keep the call active                    |
| **End wait (s)**  | Grace period after end_call before next cycle       |
| **Test case**     | Test case name (used for output folder naming)      |
| **Timestamp path**| Output directory for logs, CSV, timestamps          |
| **UPPERCASE TEXT**| Toggle uppercase display                            |
| **SYNCHRONIZED**  | Enable barrier-sync between pairs                   |

### Buttons

| Button            | Action                                                |
|-------------------|-------------------------------------------------------|
| **🔌 Pick Devices** | Open device picker — auto-fills serials from ADB    |
| **🔍 Check Devices** | Verify all assigned devices are connected via ADB    |
| **📶 Ustaw RAT**    | Open RAT settings dialog                              |
| **▶ Start Test**   | Begin the test run                                    |
| **⏹ Stop**         | Abort the running test                                |
| **🗑 Clear Log**    | Clear the live log panel                              |

### Pair panels (right side)

Each pair shows:
- **MO / MT serial** — assigned device serials
- **Cycle** — current cycle number and progress percentage
- **Progress bar** — visual progress indicator
- **Stage** — current phase (IDLE → CALLING → RINGING → ACTIVE → CHECKING → HANGING UP → IDLE)
- **Timer** — per-stage countdown
- **Last result** — PASS / FAIL / –
- **PASS / FAIL counters** — running totals
- **Success rate** — percentage
- **📺 Mirror buttons** — launch scrcpy for MO and MT devices

### Live Log

Scrollable log panel showing timestamped events per pair, colour-coded:
- **CYAN** — active stages
- **GREEN** — PASS
- **RED** — FAIL
- **YELLOW** — REF pair events

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

## Call cycle

```
IDLE (5 s) → start_call (MO) → answer_call (MT)
          → wait CALL_SECONDS → check call state
          → PASS (OFFHOOK) | FAIL (IDLE/DROPPED)
          → end_call both sides → log CSV → log timestamps
          → repeat
```

**v2.4+ enhancements:**
- **Dropped-call detection**: During ACTIVE, checks both MO/MT every second; ends call if either drops
- **CSFB/VoLTE classification**: Automatically detects call type (VoLTE for LTE/ENDC, CSFB for UMTS/GSM)
- **Early RINGING exit**: If MT already answers (OFFHOOK) during RINGING, exits early
- **GPS tracking**: Background GPS collection during call with coordinate logging
- **Signal monitoring**: RSRP/RSRQ/SINR/Band collected during ACTIVE stage

---

## Output files

All output is written to the directory set in **Timestamp path** (defaults to `Logs/` next to `main.py`).

### `results.csv`

| Column        | Description                                |
|---------------|--------------------------------------------|
| timestamp     | ISO-8601 start time                        |
| pair          | `dut` or `ref`                             |
| mo_serial     | Calling device serial                      |
| mt_serial     | Answering device serial                    |
| cycle         | Cycle number                               |
| result        | PASS / FAIL / ERROR                        |
| error_type    | Error category (or empty)                  |
| duration_ms   | Call duration in milliseconds              |
| call_type     | Voice / VoLTE / CSFB / etc.                |
| rat           | Radio Access Technology (5G/LTE/...)       |
| rscp          | Received Signal Code Power                 |
| rsrp          | Reference Signal Receive Power             |
| rsrq          | Reference Signal Received Quality          |
| sinr          | Signal-to-Interference-plus-Noise Ratio    |
| scg_state     | Secondary Cell Group state                 |
| band          | Carrier band                               |
| lat           | GPS latitude (if available)                |
| lon           | GPS longitude (if available)               |
| accuracy      | GPS accuracy in meters                     |

### `timestamps.txt`

Per-cycle timestamp log with format:
```
Call_1   10:23:45   PASS   Voice   PASS   Voice   5G   -95   -11   12   n78
```

### `device_info.txt`

Exported test configuration: device serials, MT numbers, loop count, timing parameters, sync mode, and display settings.

---

## Synchronized testing

When **SYNCHRONIZED TESTING** is enabled, a threading barrier ensures both pairs start and finish each cycle simultaneously. This is useful for side-by-side comparison tests where timing alignment matters.

---

## RAT settings

Use the **📶 Ustaw RAT** button to set the allowed Radio Access Technology per SIM slot on all connected devices.

Supported modes:

| Mode           | Description              |
|----------------|--------------------------|
| 5G/4G/3G/2G   | All technologies allowed |
| 4G/3G/2G       | 5G blocked              |
| 3G/2G          | 5G/4G blocked           |
| 2G             | Only 2G allowed          |

Settings are applied independently per SIM slot (SIM-1 / SIM-2).

---

## Dry-run mode

Dry-run is **disabled by default** in live mode. When enabled:
- All ADB calls are simulated with random but realistic values
- No devices required — useful for UI / CI testing
- Signal metrics, call states, and results are generated randomly

---

## Persistent configuration

`chorus_config.json` is auto-created on first run and stores:
- Device serials for all 4 roles
- Phone numbers for both pairs

Values persist across app launches. The file is written on close.

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

## Troubleshooting

**`python` not recognised**
→ Python not in PATH. Reinstall and check "Add Python to PATH".

**`adb devices` shows `unauthorized`**
→ Accept the USB debugging prompt on the phone screen.

**Devices not appearing in picker**
→ Ensure USB Debugging is enabled and device is not in sleep mode. Try unplugging and re-plugging.

**scrcpy not launching**
→ Install scrcpy from https://github.com/Genymobile/scrcpy/releases and add to PATH, or place `scrcpy.exe` next to `main.py`.

**Calls not going through**
→ Make sure all 4 devices are connected and authorised. Verify serials in the config panel.

**matplotlib errors**
→ Run `install.bat` again, or: `pip install --upgrade matplotlib`

**GPS not collecting**
→ Ensure location services are enabled on the device. GPS requires location permissions.

**APK installation fails**
→ Verify device is connected and ADB is authorised. Check log panel for detailed error messages.

**Dropped-call detection triggering falsely**
→ Ensure devices are not entering sleep mode during test. Disable auto-lock/screensaver.

**Barrier timeout during sync testing**
→ Increase `SYNC_TIMEOUT` in config.py if tests take longer than expected.

---

## License

Created by m.galazka2
