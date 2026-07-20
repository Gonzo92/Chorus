# AGENTS.md — Instructions for AI Agents

> **Chorus** is an automated voice-call testing tool for Android devices controlled via ADB.
> It runs a dark-mode tkinter dashboard that tests two device pairs (DUT + REF) in parallel,
> with live status, charts, and CSV reporting.

---

## ⚡ Quick Reference (READ FIRST — 30 seconds)

| What | Value |
|---|---|
| **Project** | Chorus — automated voice-call testing (Android via ADB) |
| **Entry** | `main.py` (tkinter GUI, ~600 lines, modular v2.6) |
| **Pause/Resume** | `_pause_event` in main.py — pause/resume testing |
| **Config** | `config.py` — all defaults live here |
| **Call cycle** | `core/call_monitor.py` → `run_cycle()` |
| **Test mode** | Enable **DRY_RUN** in GUI to test without physical devices |
| **Threading** | Background threads → `_ui_queue` → main thread updates |
| **CRITICAL** | Never touch tkinter widgets from worker threads. Never block main thread. |
| **Colors** | `BG="#0f1117"` `BLUE="#6daaff"` `GREEN="#5aff9d"` `RED="#ff8585"` `CYAN="#33e3ff"` |
| **Fonts** | `MONO="Consolas"` `SANS="Segoe UI"` |
| **Call flow** | `IDLE → CALLING → RINGING → ACTIVE → CHECKING → HANGING UP → IDLE` |
| **Device roles** | `dut_MO`, `dut_MT`, `ref_MO`, `ref_MT` — never rename |
| **StatusCB** | `Callable[[str, int, str, str], None]` → `(pair, cycle, stage, detail)` |
| **ADB return** | `tuple[int, str, str]` → `(returncode, stdout, stderr)` |

---

## 📝 Session State

> Update this section at the end of every session. Next session's AI will read this first.

| Date | Session | What was done | Notes / Decisions |
|------|---------|---------------|-------------------|
| 2026-06-10 | Init analysis | Audited project, identified issues | 4 docs merged into 1 AGENTS.md v3.0 |
| 2026-06-10 | Refactoring | Split main.py (1936→600 lines), created utils/theme.py, gui/*.py, core/adb_commands.py, core/csv_parser.py | 8 new files created, 69% code reduction in main.py |
| 2026-06-11 | v2.6 Migration | Copied all v2.5 files to v2.6, added pause/resume, install.bat, fixed scrcpy params | main.py title "Chorus v2.6", pair_tab.update() fixed, install.bat created |
| 2026-06-24 | Sync fix | Replaced Event-based sync with threading.Barrier(2) in sync_coordinator.py. Removed duplicate sync.wait_end() from call_monitor.py. Removed sync.reset() from main.py — barrier jest jeden shared, reuse'owany w każdej iteracji. | Pary DUT/REF czekają na tym samym barierze na końcu każdego cyklu → startują razem |
| | | | |

---

## 1. Project Overview

### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    main.py (GUI Entry Point)                    │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────────────────┐  │
│  │ ConfigTab   │  │ PairTab      │  │   LogTab               │  │
│  │ (left side) │  │ (right side) │  │   (bottom)             │  │
│  └─────────────┘  └──────────────┘  └────────────────────────┘  │
│         │                   │                    │                │
│         ▼                   ▼                    ▼                │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │           UI Event Queue (_ui_queue)                     │    │
│  │           UI Processor (_process_ui_queue)               │    │
│  └────────────────────────┬─────────────────────────────────┘    │
│                           │                                        │
│         ┌─────────────────┴─────────────────┐                     │
│         ▼                                   ▼                     │
│  ┌──────────────────┐            ┌──────────────────┐            │
│  │ DUT Worker Thread │           │ REF Worker Thread │            │
│  │ (sync_worker)     │           │ (sync_worker)     │            │
│  └────────┬──────────┘            └────────┬──────────┘            │
│           │                                 │                      │
│           ▼                                 ▼                      │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │              call_monitor.py (core/)                       │    │
│  │  run_cycle() → IDLE→CALL→ACTIVE→CHECK→END                │    │
│  └────────────────────────┬─────────────────────────────────┘    │
│                           │                                        │
│           ┌───────────────┴───────────────┐                       │
│           ▼                               ▼                        │
│  ┌─────────────────┐            ┌─────────────────┐              │
│  │ adb_controller.py│           │   report.py      │              │
│  │  start/end/answer│           │  log_call()      │              │
│  │  get_call_state  │           │  generate_summary│              │
│  │  get_signal_info │           └─────────────────┘              │
│  │  launch_scrcpy   │                                            │
│  │  scan_adb / set_rat│                                            │
│  └─────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### Data Flow

1. **Initialization**: `main.py` → `config.py` → `device_picker.py` → `phone_history.py` → `report.init_csv()` → main loop
2. **Test Execution**: User clicks Start → `_stop_event.clear()` → worker threads → `run_cycle()` loop → `status_callback()` → `_ui_queue` → GUI update
3. **Call Cycle**: `IDLE` → `CALLING` → `RINGING` → `ACTIVE` → `CHECKING` → `HANGING UP` → `IDLE`

### Call Cycle Flow

```
1. IDLE     → _tick(config.IDLE_SECONDS, ...)
2. CALLING  → start_call()
3. RINGING  → _tick(20, "RINGING", ...) [early exit if MT answers]
4. ANSWERING→ answer_call() with retries (max 3)
5. ACTIVE   → _tick(config.CALL_SECONDS, ...) [drop detection runs here]
6. CHECKING → get_call_state() → PASS/FAIL
7. HANGING  → end_call() + _tick(config.CALL_END_WAIT, ...)
8. SIGNAL   → get_signal_info() [already fetched in ACTIVE or CHECKING]
9. DONE     → status_callback() + log_call()
```

**v2.5 features**:
- **Dropped-call detection**: During ACTIVE, checks both MO/MT every second; ends call if either drops
- **Early RINGING exit**: If MT already answers (OFFHOOK) during RINGING, exits early
- **Call type classification**: VoLTE (LTE/LTE+NR/ENDC) vs CSFB (UMTS/GSM/WCDMA)
- **CSFB handling**: CSFB completed calls treated as PASS with `error_type="CSFB_COMPLETED"`

### Threading Model

```
Main Thread (tkinter event loop)
  │
  ├── _process_ui_queue() — polls _ui_queue, updates widgets
  │
  ├── Worker Thread 1 (DUT pair)
  │     └── _sync_worker() → run_cycle() loop
  │
  ├── Worker Thread 2 (REF pair)
  │     └── _sync_worker() → run_cycle() loop
  │
  └── scrcpy subprocesses (launched from worker threads)
```

**Rules**:
- GUI updates MUST go through `_ui_queue` (never touch widgets from worker threads)
- ADB calls MUST run in worker threads (never block the main thread)
- `threading.Barrier` synchronizes both pairs at each cycle boundary when sync mode is on
- `_stop_event` is checked frequently to allow graceful shutdown

### Core Principles

1. **Preserve existing architecture** — Do not rewrite the tkinter GUI or threading model
2. **Keep modules focused** — Each module has a single responsibility
3. **Use config module for all defaults** — Never hard-code test parameters
4. **Respect the call cycle** — Any new feature affecting call flow must integrate with `call_monitor.py`
5. **Dry-run first for UI changes** — Test with DRY_RUN enabled before using physical devices

---

## 2. File Roles

| File | Responsibility | Do NOT |
|---|---|---|
| `main.py` | GUI orchestration, event loop, threading coordination | Put business logic here |
| `config.py` | All default values and constants | Import heavy modules |
| `utils/theme.py` | Centralized theme constants (BG, FG, colors, fonts) | — |
| `core/adb_controller.py` | All ADB subprocess calls | Touch GUI or threading |
| `core/adb_commands.py` | ADB helper commands (check_devices, get_signal_info, launch_scrcpy) | Touch GUI |
| `core/call_monitor.py` | Call cycle orchestration | Import main.py |
| `core/report.py` | CSV logging and summary reports | Touch ADB or GUI |
| `core/csv_parser.py` | CSV parsing and analysis | Touch GUI |
| `core/sync_coordinator.py` | Synchronized lockstep testing (barrier) | Import call_monitor |
| `gui/device_picker.py` | ADB device scanning & role assignment | Import call_monitor |
| `gui/device_controls.py` | SIM stack control dialog (DATA/CALL/SMS/IMS) | Import call_monitor |
| `gui/rat_dialog.py` | RAT settings dialog | Import call_monitor |
| `gui/config_tab.py` | Configuration panel (ConfigTab) | Import call_monitor |
| `gui/pair_tab.py` | Pair status panels (PairTab) | Import call_monitor |
| `gui/log_tab.py` | Live log panel (LogTab) | Import call_monitor |
| `gui/summary_dialog.py` | Summary dialog (SummaryDialog) | Import call_monitor |
| `utils/rat_controller.py` | RAT setting functions | Touch GUI |
| `utils/phone_history.py` | Phone number history manager | Touch ADB or GUI |
| `utils/map_generator.py` | GPS map generation (HTML + PNG) | Touch ADB or GUI |
| `tools/investigate_ims.py` | IMS/VoLTE investigation script | — (standalone) |
| `tools/_analyze_excel.py` | Excel analysis tool for test data | — (standalone) |
| `scripts/install.bat` | Dependency installer | — |
| `scripts/run_chorus.bat` | Quick launcher | — |

### Module Dependency Graph

```
main.py
  ├── config.py
  ├── theme.py
  ├── gui/config_tab.py
  ├── gui/pair_tab.py
  ├── gui/log_tab.py
  ├── gui/summary_dialog.py
  ├── core/adb_commands.py
  ├── core/csv_parser.py
  ├── adb_controller.py
  ├── call_monitor.py
  ├── report.py
  ├── device_picker.py
  ├── phone_history.py
  ├── rat_dialog.py
  ├── device_controls.py
  └── sync_coordinator.py (imports call_monitor)

call_monitor.py
  ├── adb_controller.py
  └── report.py

report.py
  └── config.py

device_picker.py
  └── (none — standalone)

adb_controller.py
  └── config.py

rat_dialog.py
  └── rat_controller.py

device_controls.py
  └── (none — standalone)

sync_coordinator.py
  └── call_monitor.py

map_generator.py
  └── (none — standalone, reads CSV)
```

**Circular dependency warning**: `main.py` imports from `call_monitor.py`, which imports from `adb_controller.py` and `report.py`. No module should import from `main.py`.

---

## 3. Directory Layout

```
Chorus/
├── main.py                    ← entry point (tkinter GUI, ~600 lines)
├── config.py                  ← configuration (all defaults)
├── check_deps.py              ← pre-flight dependency checker
├── requirements.txt           ← Python dependencies
├── .gitignore                 ← git ignore rules
├── Chorus.ico                 ← satellite dish icon
│
├── core/                      ← core logic modules
│   ├── adb_controller.py      ← ADB commands (call, answer, signal, GPS)
│   ├── adb_commands.py        ← ADB helper commands (check_devices, get_signal_info, launch_scrcpy)
│   ├── call_monitor.py        ← call cycle orchestration
│   ├── report.py              ← CSV logging + summary generation
│   ├── csv_parser.py          ← CSV parsing and analysis
│   └── sync_coordinator.py    ← synchronized lockstep testing
│
├── gui/                       ← GUI components
│   ├── device_picker.py       ← ADB device scanning & role assignment
│   ├── device_controls.py     ← SIM stack control dialog (DATA/CALL/SMS/IMS)
│   ├── rat_dialog.py          ← RAT settings dialog
│   ├── config_tab.py          ← Configuration panel (ConfigTab)
│   ├── pair_tab.py            ← Pair status panels (PairTab)
│   ├── log_tab.py             ← Live log panel (LogTab)
│   └── summary_dialog.py      ← Summary dialog (SummaryDialog)
│
├── utils/                     ← utility modules
│   ├── theme.py               ← Centralized theme constants (BG, FG, colors, fonts)
│   ├── phone_history.py       ← phone number history manager
│   ├── rat_controller.py      ← RAT setting functions
│   └── map_generator.py       ← GPS map generation (HTML + PNG)
│
├── tools/                     ← development tools
│   ├── investigate_ims.py     ← IMS/VoLTE investigation script
│   └── _analyze_excel.py      ← Excel analysis tool for test data
│
├── scripts/                   ← build/install scripts
│   ├── install.bat            ← dependency installer
│   ├── run_chorus.bat         ← quick launcher
│   └── call_automator.spec    ← PyInstaller spec
│
├── docs/                      ← documentation (README.md, SETUP.md)
│
└── Logs/                      ← output (auto-created)
    ├── results.csv            ← per-call detailed results
    ├── timestamps.txt         ← per-cycle timestamp log
    ├── device_info.txt        ← exported test configuration
    ├── summary_*.csv          ← aggregated summary reports
    ├── gps_map.html           ← interactive GPS map (folium)
    └── gps_map.png            ← static GPS map (matplotlib)
```

### Output Files

| File | Location | Description |
|---|---|---|
| `results.csv` | `Logs/results.csv` | Per-call detailed results |
| `timestamps.txt` | `Logs/timestamps.txt` | Per-cycle timestamp log |
| `device_info.txt` | `Logs/` | Exported test configuration |
| `summary_*.csv` | `Logs/` | Aggregated summary reports (timestamped) |
| `chorus_config.json` | Project root | Persistent device serials |
| `phone_history.json` | Project root | Recent phone numbers |
| `gps_map.html` | `Logs/` | Interactive GPS map (folium) — v2.1+ |
| `gps_map.png` | `Logs/` | Static GPS map (matplotlib) — v2.1+ |

---

## 4. Coding Standards

### Naming

| Element | Convention | Example |
|---|---|---|
| Module | `snake_case.py` | `adb_controller.py` |
| Class | `PascalCase` | `DevicePickerDialog` |
| Function | `snake_case` | `scan_adb_devices()` |
| Variable | `snake_case` | `loop_count` |
| Constant | `UPPER_SNAKE_CASE` | `LOOP_COUNT` |
| Private helper | `_leading_underscore` | `_clean_rsrp()` |
| Private attribute | `_leading_underscore` | `_ui_queue` |
| Theme constants | `UPPER_SNAKE_CASE` | `BG`, `FG`, `BLUE` |

### Type Hints

- All public functions must have type hints
- Use `from __future__ import annotations` for forward references (Python 3.9+)
- Use `X | Y` union syntax (Python 3.10+)
- Define callback type aliases at module level:

```python
StatusCB = Callable[[str, int, str, str], None]
```

### String Formatting

- **Use f-strings** for all string interpolation: `f"→ {phone_number}"`, `f"{remaining}s"`
- Use `.format()` only when f-strings are impractical
- **Never** use `%` formatting or string concatenation for dynamic strings

### File Headers

Every Python file must start with a block comment:

```python
# ============================================================
#  Chorus v1.0  –  module_name.py
#  One-line description of what this module does.
# ============================================================
```

### Code Organization (in each file)

1. Block comment header
2. Imports (standard library → third-party → local)
3. Type aliases (e.g., `StatusCB = ...`)
4. Constants / theme colors
5. Internal/private helpers (prefixed with `_`)
6. Public API functions
7. Classes (if any)

### Comment Style

- **No inline comments for obvious code** — comments should explain WHY, not WHAT
- **Module-level docstrings** are required (the block comment header)
- **Function docstrings** are required for all public functions
- **Section separators** using `# ──` to divide logical sections

```python
# ── internal helpers ─────────────────────────────────────────
# ── public API ───────────────────────────────────────────────
# ── Signal value cleanup ─────────────────────────────────────
```

---

## 5. Patterns & Conventions

### ADB Command Pattern

Always use the `adb()` helper — never call `subprocess.run` directly for ADB:

```python
# Standard pattern — always use this structure
rc, stdout, stderr = adb(serial, "shell", "dumpsys", "telephony.registry", timeout=15)
if rc != 0:
    return "UNKNOWN"  # or appropriate default

# Chaining ADB arguments
rc, _, _ = adb(serial, "shell", "am", "start",
               "-a", "android.intent.action.CALL", "-d", f"tel:{number}")
```

**Timeout defaults**: general commands `timeout=10`, dumpsys commands `timeout=15`

### Callback Pattern

```python
def _status_cb(pair: str, cycle: int, stage: str, detail: str) -> None:
    _ui_queue.put(("status", pair, cycle, stage, detail))
```

The `detail` field is often used for countdown timers (e.g., "5s", "4s", ...).

### Error Handling

```python
# ADB operations — return boolean, not raw tuple
def start_call(serial: str, number: str) -> bool:
    rc, _, _ = adb(serial, "shell", "am", "start", ...)
    return rc == 0

# GUI operations — silently ignore or log
try:
    # potentially failing operation
except Exception:
    pass

# Callback safety — never let callback failures crash worker thread
try:
    status_callback(pair, cycle, stage, detail)
except Exception:
    pass
```

### Stop Event Checking

Check `stop.is_set()` at every loop iteration and before long operations:

```python
for remaining in range(seconds, 0, -1):
    if stop.is_set():
        return False
    # ... do work ...
```

### UI Updates (NEVER from worker threads)

```python
# WRONG — called from worker thread
self.pair1_stage_label.config(text="ACTIVE")

# CORRECT — send to queue, main thread updates
_ui_queue.put(("status", "dut", cycle, "ACTIVE", "..."))
```

### GUI Theme

All GUI files share the same palette. Define at top of each GUI file:

```python
BG     = "#0f1117"   # Main background
BG2    = "#2a2d3a"   # Lighter background (panels, frames)
BG3    = "#747579"   # Even lighter (borders, inactive elements)
FG     = "#ffffff"   # Primary text
FG_DIM = "#B0B2B6"   # Dimmed/inactive text
BLUE   = "#6daaff"   # DUT pair accent
YELLOW = "#8a440b"   # REF pair accent
GREEN  = "#5aff9d"   # PASS / success
RED    = "#ff8585"   # FAIL / error
CYAN   = "#33e3ff"   # Active / in-progress

MONO   = "Consolas"  # Log panel, monospace text
SANS   = "Segoe UI"  # UI elements
```

### Regex Patterns

Signal parsing uses regex on Android `dumpsys` output:

- Use `re.search()` not `re.match()` or `re.fullmatch()`
- Use named groups for complex patterns
- Always handle the case where regex doesn't match:

```python
match = re.search(r"mCallState\s*=\s*(\d)", stdout)
if not match:
    return "UNKNOWN"
```

- Android sentinel values (INT_MAX) must be filtered in cleanup functions

---

## 6. Workflow — How to Add Things

### Adding a New ADB Command

1. Open `adb_controller.py`
2. Add the function after existing public API functions
3. Always use the `adb()` helper — never call subprocess directly

```python
def my_new_command(serial: str, arg: str) -> str:
    """
    Description of what this command does.
    Returns the relevant output string, or "UNKNOWN" on failure.
    """
    rc, stdout, stderr = adb(serial, "shell", "some", "command", arg, timeout=15)
    if rc != 0:
        return "UNKNOWN"
    match = re.search(r"pattern", stdout)
    return match.group(1) if match else "UNKNOWN"
```

4. If the command needs DRY_RUN support, add simulation in the DRY_RUN branch

### Modifying the Call Cycle

The call cycle is defined in `call_monitor.py:run_cycle()`.

**To add a new stage**: Insert it between existing stages. Use `_tick()` for timed stages, call `status_callback()` for instant stages.

**To add logic during ACTIVE**: Add additional checks inside the `if stage == "ACTIVE"` block in `_tick()`.

### Adding a New CSV Column

1. Add the column name to `HEADERS` in `report.py`
2. Populate the value in `call_monitor.py` before calling `log_call()`
3. The value flows automatically through `result_data.update(signal_info)`

### Adding a New Dialog

1. Create a new file (e.g., `my_dialog.py`) following the `rat_dialog.py` pattern
2. Use `tk.Toplevel` (not `tk.Tk`) — it's a child window
3. Mirror theme constants from `main.py`
4. Use `ttk` widgets for consistency
5. Return user choices via a method (e.g., `get_selection()`)
6. Wire it up in `main.py`:

```python
def on_my_dialog(self):
    dialog = MyDialog(self.parent)
    self.parent.wait_window(dialog.top)
    result = dialog.get_selection()
```

7. Add a button in the configuration panel that calls `on_my_dialog()`

### Adding a GUI Button

1. Define the button in `on_configure()` in `main.py`:

```python
btn = tk.Button(sidebar, text="My Button", command=self.on_my_action,
                bg=BLUE, fg=BG, font=(SANS, 10, "bold"),
                activebackground=BG2, activeforeground=FG,
                relief="flat", cursor="hand2", width=12)
```

2. Implement the callback:

```python
def on_my_action(self):
    _ui_queue.put(("status", "info", 0, "INFO", "Action triggered"))
```

### Adding DRY_RUN Support

1. Check `self.dry_run_var.get()` before executing real ADB calls
2. Provide a realistic simulated return value in the `else` branch
3. Ensure the simulated data flows through the same code path as real data

### Adding a New Signal Metric

1. Add parsing in `adb_controller.py:get_signal_info()`
2. Add the field to the `default` dict: `{"rat": "N/A", ..., "new_metric": "N/A"}`
3. Add regex parsing for the new metric from dumpsys output
4. Add to `HEADERS` in `report.py` if it should be logged to CSV
5. The value flows automatically through `result_data.update(signal_info)` in `call_monitor.py`

### Quick Reference — What File to Edit

| Task | Files to Edit | Key Functions |
|---|---|---|
| Add new ADB command | `adb_controller.py` | `adb()` |
| Modify call cycle | `call_monitor.py` | `run_cycle()`, `_tick()` |
| Add CSV column | `report.py` | `HEADERS`, `log_call()` |
| Add GUI button | `main.py` | `on_configure()` |
| Add new dialog | New file + `main.py` | Follow `rat_dialog.py` pattern |
| Change test parameters | `config.py` | `LOOP_COUNT`, `CALL_SECONDS`, etc. |
| Add phone number | `config.py` or GUI | `PHONE_NUMBERS` dict |
| Enable synchronized testing | `config.py` + `main.py` | `SYNC_TIMEOUT`, `v_sync` |
| Add SIM control | `gui/device_controls.py` | SIM stack toggles |

---

## 7. Debugging

### Debugging a Failed Call

1. Check the **Live Log** panel for the failure stage and error detail
2. Check `Logs/results.csv` for the `error_type` field
3. Common error types:
   - `ADB_ERROR` — ADB command failed
   - `NO_ANSWER` — MT didn't answer after retries
   - `DROPPED` — Call dropped during ACTIVE stage
   - `CSFB_COMPLETED` — CSFB fallback (treated as PASS)
4. Verify devices are connected: `adb devices` in terminal
5. Check that USB Debugging is enabled and devices are authorized

### Debugging GPS

- Check `adb shell dumpsys location` manually on the device
- GPS requires location services enabled on Android device
- Accuracy depends on GPS signal (outdoor > indoor)
- In DRY_RUN: simulated coordinates in Poland range
- If GPS fails silently: lat/lon = None, point skipped on map
- Check logs for: "GPS tracking enabled", "GPS point X/Y", "GPS maps saved"

### Debugging Synchronized Testing

- If one pair hangs, check for ADB errors or device issues
- `threading.BrokenBarrierError` is caught and handled gracefully
- Check `SYNC_TIMEOUT` — if test takes longer, barrier will timeout

### General Debugging Tips

- Enable DRY_RUN to test without devices
- The `_ui_queue` processes UI updates — if the GUI freezes, check for blocking calls in the background thread
- CSV output goes to `Logs/results.csv`. Timestamps go to `Logs/timestamps.txt`
- Use `sys.exit(0)` to cleanly exit the application during development

---

## 8. Deployment

### Standalone .exe Build

Each version of Chorus is built as a standalone `.exe` (no Python required on target machine).

**Build process (automatic):**

```powershell
cd Chorus_v{version}
.\build.bat
```

`build.bat` performs:
1. `pushd` on script directory (handles spaces in path)
2. Generates `Chorus.ico` (satellite dish icon) if not exists
3. Checks Python 3.9+ and PyInstaller
4. Checks dependencies (`check_deps.py`)
5. Cleans old builds (`build/`, `dist/`, `Chorus.spec`)
6. Runs PyInstaller: `--onefile --windowed --icon "Chorus.ico" --distpath "." --name "Chorus_v{version}"`
7. Result: `Chorus_v{version}.exe` (~55 MB)

**Distribution**: Copy only `Chorus_v{version}.exe` to target machine — works on any Windows 10/11.

### Deploy Script (`deploy.ps1`)

- Reads version from `AGENTS.md`
- Copies `Chorus/` to `Deployment/Chorus_v{version}/`
- Skips: `Logs/`, `__pycache__/`, `*.json`
- Asks before overwriting existing version

### Rules

- Before every significant update: `.\deploy.ps1`
- Update `AGENTS.md` (Version + Version History) BEFORE deploy
- `Deployment/` contains only code — no runtime data, logs, configs
- Every new version must have a generated `Chorus_v{version}.exe`

### Running

**Option A — Launcher folder (Python required):**
```powershell
cd Chorus_v{version}
.\run.bat
```

**Option B — Standalone .exe (no Python needed):**
```powershell
# Copy Chorus_v{version}.exe to target machine and run
```

**Option C — Manual:**
```powershell
python check_deps.py   # check dependencies first
python main.py          # then run
```

---

## 9. Known Issues

> These are known problems in the codebase. Do not introduce new ones. Fix these if you have time.

1. **`rat_controller.py`** — missing try/except around ADB calls
2. **`phone_history.py`** — silent `pass` on all exceptions
3. **`tools/_analyze_excel.py`** — hardcoded `D:\LOGI\...` path (dead code)
4. **`docs/README.md` and `docs/SETUP.md`** are empty (0 bytes)
5. **No `__init__.py`** in package directories (`core/`, `gui/`, `utils/`)
6. **`requirements.txt`** missing `pandas`, `openpyxl` (referenced in PROJECT.md)
7. **`summary_*.csv`** in project root instead of `Logs/`
8. **Version headers in source files** are inconsistent (v2.1, v2.4, v2.5 mixed)

---

## 10. Pending Tasks

> Prioritized backlog. Address in order unless user specifies otherwise.

### High Priority
- [x] Extract theme constants to shared `utils/theme.py` ✅ DONE
- [ ] Add try/except to `rat_controller.py` ADB calls
- [x] Extract GUI panels from `main.py` → `gui/config_tab.py`, `gui/pair_tab.py`, `gui/log_tab.py` ✅ DONE
- [x] Fix synchronized testing with `threading.Barrier(2)` ✅ DONE

### Medium Priority
- [ ] Create `__init__.py` in all package directories
- [ ] Fix hardcoded path in `tools/_analyze_excel.py`
- [ ] Populate `docs/README.md` and `docs/SETUP.md`
- [ ] Move `summary_*.csv` from root to `Logs/`
- [ ] Add `pandas`, `openpyxl` to `requirements.txt`
- [ ] Fix version headers in source files to match current version

### Low Priority
- [ ] Add unit tests for DRY_RUN mode
- [ ] Add `Backups/` folder structure (referenced in docs but doesn't exist)
- [ ] Standardize import paths across all files

---

## 11. Version History

| Version | Date       | Changes |
|---------|------------|---------|
| v1.0    | 2026-04-28 | Initial release |
| v2.1    | 2026-04-29 | GPS tracking (background), map generation (HTML + PNG), `folium` dependency |
| v2.2    | 2026-05-04 | Cross-machine compatibility: `from __future__ import annotations` (Python 3.9+), `check_deps.py` pre-flight checker, `run.bat` launcher, `build.bat` PyInstaller script, font fallback, fixed import paths, graceful matplotlib degradation |
| v2.3    | 2026-05-15 | Fix PermissionError on Windows Program Files — logs now saved to `%LOCALAPPDATA%\Chorus\Logs\` instead of app directory |
| v2.4    | 2026-06-10 | Dropped-call detection during ACTIVE stage, CSFB/VoLTE call type classification, early RINGING exit on MT answer, GPS collection in call cycle, `generate_detailed_summary()` in report.py, `_sync_worker` barrier sync in main.py, signal data storage per cycle, `_append_cycle_to_timestamp_file` with full signal info, `_create_test_folder` for per-test output, `_save_device_info` exporting config, SIM number combobox with refresh/history buttons, scrcpy mirroring, system sounds, tooltips, synchronized testing checkbox, uppercase text option, device controls dialog (SIM stack: DATA/CALL/SMS/IMS), `toggle_volte_adaptive` ADB command, `verify_ims_state` ADB command, `tools/investigate_ims.py`, `tools/_analyze_excel.py`, `scripts/install.bat`, `scripts/run_chorus.bat` |
| v2.5    | 2026-06-10 | Documentation updated to v2.5, backup system established in `Backups/` folder |
| v3.0    | 2026-06-10 | **Documentation consolidation** — merged 4 files (AGENTS.md, PROJECT.md, STYLE.md, TASKS.md) into single AGENTS.md v3.0. Added Quick Reference, Session State, Known Issues, Pending Tasks sections. |
| v3.1    | 2026-06-10 | **Code refactoring** — split main.py (1936→600 lines), created utils/theme.py, gui/config_tab.py, gui/pair_tab.py, gui/log_tab.py, gui/summary_dialog.py, core/adb_commands.py, core/csv_parser.py. 8 new files, 69% code reduction. |
| v3.2    | 2026-06-24 | **Sync fix** — replaced Event-based sync with `threading.Barrier(2)` in `sync_coordinator.py`. Removed duplicate `sync.wait_end()` from `call_monitor.py`. Removed `sync.reset()` from `main.py` — barrier jest jeden shared, reuse'owany w każdej iteracji. Pary DUT/REF czekają na tym samym barierze na końcu każdego cyklu → startują razem. |

### Dependencies

| Package | Required For |
|---|---|
| `matplotlib>=3.7.0` | Chart rendering (timeline, signal charts) |
| `folium` | GPS HTML map generation |
| `pandas` | Excel analysis tools (`tools/_analyze_excel.py`) |
| `openpyxl` | Excel file reading/writing |
| `pyinstaller` (optional) | Building standalone `.exe` |

Install: `pip install matplotlib folium pandas openpyxl`
For builds: `pip install pyinstaller`
