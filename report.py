# ============================================================
#  Call Automator v1.0  –  report.py
#  CSV result logging – one row per call cycle.
# ============================================================

import csv
import os
from datetime import datetime
from pathlib import Path
from config import CSV_OUTPUT_PATH, LOG_OUTPUT_PATH

# ── CSV schema ───────────────────────────────────────────────

HEADERS = [
    "timestamp",     # ISO-8601 datetime of the call attempt
    "pair",          # "dut" | "ref"
    "mo_serial",     # serial of the MO device
    "mt_serial",     # serial of the MT device
    "cycle",         # integer cycle index (1-based)
    "result",        # "PASS" | "FAIL"
    "error_type",    # "" | "DROPPED" | "NO_ANSWER" | "ADB_ERROR" | ...
    "duration_ms",   # measured call duration in milliseconds
    "rat",           # radio access technology (LTE / NR / LTE+NR / …)
    "rsrp",          # Reference Signal Received Power (dBm)
    "rsrq",          # Reference Signal Received Quality (dB)
    "sinr",          # Signal-to-Interference-plus-Noise Ratio (dB)
    "scg_state",     # Secondary Cell Group state (NR)
    "sdm_file",      # local path of pulled SDM log, or ""
]


# ── public API ───────────────────────────────────────────────

def init_csv() -> None:
    """
    Create the CSV file with headers if it does not already exist.
    Parent directories are created automatically.
    """
    path = Path(CSV_OUTPUT_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)

    if not path.exists():
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=HEADERS)
            writer.writeheader()


def log_call(data: dict) -> None:
    """
    Append a single result row to the CSV file.

    *data* should be a dict whose keys are a subset of HEADERS.
    Missing keys are filled with empty strings; extra keys are ignored.
    The 'timestamp' field is automatically set to the current time if
    not provided.
    """
    if "timestamp" not in data or not data["timestamp"]:
        data["timestamp"] = datetime.now().isoformat(timespec="seconds")

    # Ensure all required fields have values to prevent empty columns
    required_fields = ["pair", "mo_serial", "mt_serial", "cycle", "result"]
    for field in required_fields:
        if field not in data or data[field] == "":
            data[field] = "N/A" if field != "result" else "ERROR"
    
    # Fill missing fields with empty strings
    row = {h: data.get(h, "") for h in HEADERS}

    path = Path(CSV_OUTPUT_PATH)
    # Guard: initialise if the file was somehow removed mid-run
    if not path.exists():
        init_csv()

    with open(path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=HEADERS)
        writer.writerow(row)


def generate_summary_report() -> str:
    """
    Generate a summary report from the detailed CSV results.
    Returns the path to the generated summary report.
    """
    from collections import defaultdict
    from datetime import datetime
    
    # Define summary report headers
    summary_headers = [
        "timestamp",
        "pair",
        "total_cycles",
        "passed_cycles",
        "failed_cycles",
        "success_rate_pct",
        "average_duration_ms",
        "error_distribution",
        "sdm_logs_pulled"
    ]
    
    # Read detailed results
    detailed_path = Path(CSV_OUTPUT_PATH)
    if not detailed_path.exists():
        raise FileNotFoundError(f"CSV results file not found: {CSV_OUTPUT_PATH}")
    
    # Parse data and calculate statistics
    stats = defaultdict(lambda: {
        "total": 0,
        "passed": 0,
        "failed": 0,
        "durations": [],
        "errors": defaultdict(int),
        "sdm_pulled": 0
    })
    
    first_timestamp = None
    last_timestamp = None
    
    with open(detailed_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Track timestamps
            if not first_timestamp:
                first_timestamp = row["timestamp"]
            last_timestamp = row["timestamp"]
            
            pair = row["pair"]
            stats[pair]["total"] += 1
            
            if row["result"] == "PASS":
                stats[pair]["passed"] += 1
            else:
                stats[pair]["failed"] += 1
                error_type = row["error_type"] or "UNKNOWN"
                stats[pair]["errors"][error_type] += 1
            
            if row["duration_ms"] and row["duration_ms"].isdigit():
                stats[pair]["durations"].append(int(row["duration_ms"]))
            
            if row["sdm_file"] and row["sdm_file"] != "PULL_FAILED":
                stats[pair]["sdm_pulled"] += 1
    
    # Generate summary report path with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    summary_path = Path(LOG_OUTPUT_PATH) / f"summary_{timestamp}.csv"
    
    # Write summary report
    with open(summary_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=summary_headers)
        writer.writeheader()
        
        for pair, data in stats.items():
            # Calculate statistics
            success_rate = (data["passed"] / data["total"] * 100) if data["total"] > 0 else 0
            avg_duration = sum(data["durations"]) / len(data["durations"]) if data["durations"] else 0
            
            # Format error distribution
            error_dist = "; ".join([f"{k}:{v}" for k, v in data["errors"].items()]) if data["errors"] else ""
            
            # Write summary row
            summary_row = {
                "timestamp": f"{first_timestamp} to {last_timestamp}" if first_timestamp else timestamp,
                "pair": pair,
                "total_cycles": data["total"],
                "passed_cycles": data["passed"],
                "failed_cycles": data["failed"],
                "success_rate_pct": f"{success_rate:.2f}",
                "average_duration_ms": f"{avg_duration:.2f}",
                "error_distribution": error_dist,
                "sdm_logs_pulled": data["sdm_pulled"]
            }
            writer.writerow(summary_row)
    
    return str(summary_path)
