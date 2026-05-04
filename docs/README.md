# Chorus v2.2

Automated voice-call testing tool for Android devices over ADB.  
Dark-mode desktop dashboard built with tkinter — runs two device pairs in parallel with live status, charts, and CSV reporting.

---

## Features

- **tkinter GUI** — dark-mode dashboard with live status, progress bars, and per-cycle timers
- **Parallel testing** — two independent device pairs (DUT + REF) running in separate threads
- **Device Picker** — interactive dialog to scan ADB-connected devices and assign roles (`dut_MO`, `dut_MT`, `ref_MO`, `ref_MT`)
- **Live Pass/Fail chart** — real-time bar chart tracking pass/fail counts per pair
- **Synchronized testing** — optional barrier mode so both pairs start and finish each cycle at the same time
- **scrcpy mirroring** — one-click screen mirror for MO and MT devices of each pair
- **RAT settings** — dialog to set Radio Access Technology (5G/4G/3G/2G) per SIM slot
- **SIM number reading** — auto-read phone numbers from device (`*#0##` Samsung diagnostic)
- **Phone number history** — remembers recently used numbers per pair (dropdown)
- **Persistent config** — device serials and phone numbers saved to `chorus_config.json` between runs
- **Timestamps file** — per-cycle time log with RAT, RSRP, RSRQ, SINR, Band, and call type
- **Device info file** — exports test configuration and device details to the output folder
- **CSV reporting** — detailed per-call results with signal metrics
- **Summary report** — aggregated stats: pass/fail counts, success rate, average duration, error distribution
- **System sounds** — audio feedback on PASS/FAIL/WARN events
- **Dry-run mode** — simulate all ADB calls with random but realistic values (no devices needed)

---

## Directory layout

```
Chorus/
├── main.py              ← tkinter GUI entry point
├── config.py            ← default configuration values
├── check_deps.py        ← pre-flight dependency checker
├── chorus_config.json   ← persistent config (auto-created on first run)
├── phone_history.json   ← phone number history (auto-created)
├── requirements.txt     ← Python dependencies
├── run.bat              ← launcher (checks deps, starts app)
├── build.bat            ← PyInstaller build script → Chorus.exe
├── install_deps.bat     ← dependency installer
├── Chorus.ico           ← satellite dish icon
├── core/                ← ADB controller, call monitor, report
├── gui/                 ├── device_picker, rat_dialog, device_controls
├── utils/               ├── rat_controller, phone_history, map_generator
├── tools/               ├── generate_icon.py
├── docs/
│   ├── README.md
│   └── SETUP.md
└── .gitignore
```

---

## Requirements

| Requirement  | Version  | Notes                          |
|-------------|----------|--------------------------------|
| Python      | 3.9+     | Uses `from __future__ import annotations` |
| matplotlib  | 3.7+     | Installed via `install_deps.bat` |
| folium      | 0.14+    | GPS map generation             |
| ADB         | any      | Android Platform Tools         |
| scrcpy      | any      | Optional — screen mirroring    |

---

## Quick start

1. **Connect all 4 devices** via USB and enable USB Debugging. Authorise ADB when prompted.
2. **Install dependencies** (first time only):
   ```
   install_deps.bat
   ```
   or manually: `pip install matplotlib folium`
3. **Launch Chorus:**
   ```
   run.bat
   ```
   or
   ```
   python main.py
   ```
4. **Build standalone .exe** (optional):
   ```
   build.bat
   ```
   Output: `Chorus.exe` — works without Python installed.

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

During ACTIVE stage the call state is monitored every second. If either device drops, the call is ended immediately and the cycle is marked FAIL.

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
| call_type     | Voice / VoLTE / etc.                       |
| rat           | Radio Access Technology (5G/LTE/...)       |
| rscp          | Received Signal Code Power                 |
| rsrp          | Reference Signal Receive Power             |
| rsrq          | Reference Signal Received Quality          |
| sinr          | Signal-to-Interference-plus-Noise Ratio    |
| scg_state     | Secondary Cell Group state                 |
| band          | Carrier band                               |
| sdm_file      | SDM log file path (if pulled)              |

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

---

## License

Created by m.galazka2
