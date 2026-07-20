# ============================================================
#  Chorus v2.5  –  core/csv_parser.py
#  CSV parsing and analysis for Chorus test results.
# ============================================================

from __future__ import annotations

import csv
import os
from datetime import datetime


def parse_csv(csv_path):
    """Parse results.csv and return list of row dicts."""
    rows = []
    if not os.path.exists(csv_path):
        return rows

    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(dict(row))
    return rows


def analyze_results(rows):
    """Analyze parsed CSV rows and return summary statistics."""
    if not rows:
        return {
            "total_cycles": 0,
            "passed_cycles": 0,
            "failed_cycles": 0,
            "success_rate": 0.0,
            "call_durations": [],
            "error_types": {},
        }

    passed = sum(1 for r in rows if r.get("result") == "PASS")
    failed = sum(1 for r in rows if r.get("result") == "FAIL")
    total = len(rows)
    success_rate = (passed / total * 100) if total > 0 else 0.0

    # Extract call durations
    durations = []
    for r in rows:
        dur = r.get("duration_ms")
        if dur and dur != "N/A":
            try:
                durations.append(float(dur))
            except (ValueError, TypeError):
                pass

    # Extract error types
    error_types = {}
    for r in rows:
        error = r.get("error_type")
        if error and error != "N/A" and error != "None":
            error_types[error] = error_types.get(error, 0) + 1

    return {
        "total_cycles": total,
        "passed_cycles": passed,
        "failed_cycles": failed,
        "success_rate": success_rate,
        "call_durations": durations,
        "error_types": error_types,
    }


def generate_summary(rows, output_path):
    """Generate a summary CSV from parsed rows."""
    if not rows:
        return

    summary_fields = ["total_cycles", "passed_cycles", "failed_cycles", "success_rate"]
    summary = analyze_results(rows)

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=summary_fields)
        writer.writeheader()
        writer.writerow(summary)
