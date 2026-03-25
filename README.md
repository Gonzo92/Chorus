# Call Automator v1.0

Automated voice-call tester for Android devices over ADB.
Runs two device pairs in parallel threads with a Rich terminal dashboard.

---

## Directory layout

```
call_automator/
├── config.py          ← edit this before each session
├── adb_controller.py
├── sdm_logger.py
├── report.py
├── call_monitor.py
├── main.py
└── logs/
    ├── exynos/        ← SDM pulls land here
    ├── mediatek/      ← reserved for future use
    └── results.csv    ← created automatically on first run
```

## Requirements

```
pip install rich
```
Python 3.10+ (uses `X | Y` union types and `match`).

## Quick start

1. Connect all 4 devices via USB and authorise ADB.
2. Edit `config.py` – set `DEVICES`, `PHONE_NUMBERS`, and `DRY_RUN=False`.
3. Run:
   ```
   cd call_automator
   python main.py
   ```

## Dry-run mode

`DRY_RUN=True` (default) simulates all ADB calls with random but realistic values.
No devices required. Useful for UI / CI testing.

## Pair definitions

| Key          | Role | Chipset   |
|--------------|------|-----------|
| `exynos_MO`  | DUT  | Exynos    |
| `exynos_MT`  | DUT  | Exynos    |
| `ref_MO`     | REF  | MediaTek  |
| `ref_MT`     | REF  | MediaTek  |

Direction is hard-coded: **MO always dials MT** in every cycle.

## Call cycle

```
IDLE (5 s) → start_call (MO) → answer_call (MT)
          → wait CALL_SECONDS → check call state
          → PASS (OFFHOOK) | FAIL (IDLE/DROPPED)
          → end_call both sides → log CSV → [SDM pull if threshold]
          → repeat
```

## SDM log pulling (Exynos only)

- Triggered when on-device log dir exceeds `SDM_CHUNK_SIZE_MB` (default 300 MB).
- Set `SDM_PULL_PER_CALL=True` to pull after every call.
- Local destination: `logs/exynos/cycle_NNN_TIMESTAMP/`
- Source dir is deleted on device after each pull to free storage.

## CSV columns

`timestamp, pair, dut_mo_serial, dut_mt_serial, cycle, result, error_type,
 duration_ms, rat, rsrp, rsrq, sinr, scg_state, sdm_file`
