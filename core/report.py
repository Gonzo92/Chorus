# ============================================================
#  Chorus v2.4  –  core/report.py
# ============================================================

from __future__ import annotations

import csv
import os
from datetime import datetime
from pathlib import Path
import config   # always read via config.X — never cache at import
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def _extract_test_name(csv_path: str) -> str:
    """Extract test name from CSV path. Returns folder name or 'test'."""
    p = Path(csv_path)
    if p.parent.name.lower() in ("logs", "output", ""):
        return p.parent.parent.name if p.parent.parent.name else "test"
    return p.parent.name if p.parent.name else "test"

HEADERS = [
    "timestamp", "pair", "mo_serial", "mt_serial", "cycle",
    "result", "error_type", "duration_ms", "call_type",
    "rat", "rsrp", "rsrq", "sinr", "scg_state", "band", "sdm_file",
    "lat", "lon", "gps_accuracy", "gps_time", "gps_provider",
]

def init_csv() -> None:
    path = Path(config.CSV_OUTPUT_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        with open(path, "w", newline="", encoding="utf-8") as f:
            csv.DictWriter(f, fieldnames=HEADERS).writeheader()

def log_call(data: dict) -> None:
    if not data.get("timestamp"):
        data["timestamp"] = datetime.now().isoformat(timespec="seconds")
    for field in ("pair", "mo_serial", "mt_serial", "cycle", "result"):
        if not data.get(field):
            data[field] = "N/A" if field != "result" else "ERROR"
    row = {h: data.get(h, "") for h in HEADERS}
    path = Path(config.CSV_OUTPUT_PATH)
    if not path.exists():
        init_csv()
    with open(path, "a", newline="", encoding="utf-8") as f:
        csv.DictWriter(f, fieldnames=HEADERS).writerow(row)

def generate_summary_report() -> str:
    from collections import defaultdict
    summary_headers = [
        "timestamp", "pair", "total_cycles", "passed_cycles",
        "failed_cycles", "success_rate_pct", "average_duration_ms",
        "error_distribution", "sdm_logs_pulled",
    ]
    detailed_path = Path(config.CSV_OUTPUT_PATH)
    if not detailed_path.exists():
        raise FileNotFoundError(f"CSV not found: {config.CSV_OUTPUT_PATH}")

    stats = defaultdict(lambda: {
        "total": 0, "passed": 0, "failed": 0,
        "durations": [], "errors": defaultdict(int), "sdm_pulled": 0,
    })
    first_ts = last_ts = None

    with open(detailed_path, "r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if not first_ts: first_ts = row["timestamp"]
            last_ts = row["timestamp"]
            pair = row["pair"]
            stats[pair]["total"] += 1
            if row["result"] == "PASS":
                stats[pair]["passed"] += 1
            else:
                stats[pair]["failed"] += 1
                stats[pair]["errors"][row["error_type"] or "UNKNOWN"] += 1
            if row["duration_ms"] and str(row["duration_ms"]).isdigit():
                stats[pair]["durations"].append(int(row["duration_ms"]))
            if row.get("sdm_file") and row["sdm_file"] not in ("", "PULL_FAILED"):
                stats[pair]["sdm_pulled"] += 1

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    summary_path = Path(config.LOG_OUTPUT_PATH) / f"summary_{timestamp}.csv"
    with open(summary_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=summary_headers)
        writer.writeheader()
        for pair, d in stats.items():
            total = d["total"]
            success_rate = (d["passed"] / total * 100) if total else 0
            avg_dur = sum(d["durations"]) / len(d["durations"]) if d["durations"] else 0
            writer.writerow({
                "timestamp": f"{first_ts} to {last_ts}" if first_ts else timestamp,
                "pair": pair,
                "total_cycles": total,
                "passed_cycles": d["passed"],
                "failed_cycles": d["failed"],
                "success_rate_pct": f"{success_rate:.2f}",
                "average_duration_ms": f"{avg_dur:.2f}",
                "error_distribution": "; ".join(f"{k}:{v}" for k, v in d["errors"].items()),
                "sdm_logs_pulled": d["sdm_pulled"],
            })
    return str(summary_path)

def generate_kml_report(csv_path: str, output_path: str) -> str:
    """
    Generate KML report from GPS CSV data for Google Maps/Earth.
    
    Features:
    - Green placemarks for PASS, red for FAIL
    - Clickable markers with cycle details
    - Timestamps and error types
    - Route line connecting all points
    
    Args:
        csv_path: Path to results.csv
        output_path: Path for output KML file
        
    Returns:
        Path to generated KML file
    """
    import csv
    from datetime import datetime
    
    # Read CSV data
    data = []
    try:
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Only include rows with GPS data
                if row.get("lat") and row["lat"] not in ("", "N/A", "None"):
                    try:
                        data.append({
                            "cycle": int(row.get("cycle", 0)),
                            "pair": row.get("pair", ""),
                            "timestamp": row.get("timestamp", ""),
                            "result": row.get("result", ""),
                            "error_type": row.get("error_type", ""),
                            "call_type": row.get("call_type", ""),
                            "rat": row.get("rat", ""),
                            "rsrp": row.get("rsrp", ""),
                            "rsrq": row.get("rsrq", ""),
                            "sinr": row.get("sinr", ""),
                            "band": row.get("band", ""),
                            "lat": float(row["lat"]),
                            "lon": float(row["lon"]),
                        })
                    except (ValueError, TypeError):
                        continue
    except FileNotFoundError:
        print(f"[WARN] KML generation failed: CSV not found at {csv_path}")
        return output_path
    
    if not data:
        print("[WARN] KML generation skipped: No GPS data found")
        return output_path
    
    # Generate KML
    kml_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <name>Chorus v2.4 - Test Report</name>
    <description>Test report generated at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</description>
    <Style id="passStyle">
      <IconStyle>
        <Icon>
          <href>http://maps.google.com/mapfiles/kml/shapes/range.png</href>
        </Icon>
      </IconStyle>
      <LineStyle>
        <color>ff00ff00</color>
        <width>3</width>
      </LineStyle>
    </Style>
    <Style id="failStyle">
      <IconStyle>
        <Icon>
          <href>http://maps.google.com/mapfiles/kml/shapes/square.png</href>
        </Icon>
      </IconStyle>
      <LineStyle>
        <color>ffff0000</color>
        <width>3</width>
      </LineStyle>
    </Style>
    <Style id="routeStyle">
      <LineStyle>
        <color>7f888888</color>
        <width>2</width>
      </LineStyle>
    </Style>
"""
    
    # Add route line
    kml_content += """    <Placemark>
      <name>Test Route</name>
      <styleUrl>#routeStyle</styleUrl>
      <LineString>
        <coordinates>
"""
    
    route_coords = []
    for d in data:
        route_coords.append(f"          {d['lon']},{d['lat']},0")
    
    kml_content += "\n".join(route_coords) + "\n"
    kml_content += """        </coordinates>
      </LineString>
    </Placemark>
"""
    
    # Add placemarks for each cycle
    for d in data:
        style = "#passStyle" if d["result"] == "PASS" else "#failStyle"
        color = "00ff00" if d["result"] == "PASS" else "ff0000"
        
        kml_content += f"""    <Placemark>
      <name>Cycle {d['cycle']} - {d['pair'].upper()}</name>
      <description>
        <![CDATA[
          <b>Cycle:</b> {d['cycle']}<br>
          <b>Pair:</b> {d['pair'].upper()}<br>
          <b>Result:</b> <font color="{color}">{d['result']}</font><br>
          <b>Time:</b> {d['timestamp']}<br>
          <b>Call Type:</b> {d.get('call_type', 'N/A')}<br>
          <b>RAT:</b> {d.get('rat', 'N/A')}<br>
          <b>RSRP:</b> {d.get('rsrp', 'N/A')} dBm<br>
          <b>RSRQ:</b> {d.get('rsrq', 'N/A')}<br>
          <b>SINR:</b> {d.get('sinr', 'N/A')}<br>
          <b>Band:</b> {d.get('band', 'N/A')}<br>
          <b>Error:</b> {d.get('error_type', 'N/A')}
        ]]>
      </description>
      <styleUrl>{style}</styleUrl>
      <Point>
        <coordinates>
          {d['lon']},{d['lat']},0
        </coordinates>
      </Point>
    </Placemark>
"""
    
    kml_content += """  </Document>
</kml>"""
    
    # Write KML file
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(kml_content)
    
    print(f"[KML] Report generated: {output_path}")
    return output_path

def generate_detailed_summary() -> dict:
    from collections import defaultdict
    detailed_path = Path(config.CSV_OUTPUT_PATH)
    if not detailed_path.exists():
        raise FileNotFoundError(f"CSV not found: {config.CSV_OUTPUT_PATH}")

    stats = defaultdict(lambda: {
        "total": 0, "passed": 0, "failed": 0,
        "durations": [], "errors": defaultdict(int), "sdm_pulled": 0,
        "error_timeline": [],
        "signal_data": {
            "rat_distribution": defaultdict(int),
            "rsrp_values": [], "rsrq_values": [], "sinr_values": [],
            "band_distribution": defaultdict(int),
        },
    })
    first_ts = last_ts = None
    cycle_results = defaultdict(list)

    with open(detailed_path, "r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if not first_ts: first_ts = row["timestamp"]
            last_ts = row["timestamp"]
            pair = row["pair"]
            cycle = int(row["cycle"])
            result = row["result"]
            cycle_results[cycle].append({"pair": pair, "result": result,
                                         "error_type": row["error_type"], "timestamp": row["timestamp"]})
            stats[pair]["total"] += 1
            if result == "PASS":
                stats[pair]["passed"] += 1
            else:
                stats[pair]["failed"] += 1
                stats[pair]["errors"][row["error_type"] or "UNKNOWN"] += 1
                stats[pair]["error_timeline"].append(
                    {"cycle": cycle, "error_type": row["error_type"], "timestamp": row["timestamp"]})
            if row["duration_ms"] and str(row["duration_ms"]).isdigit():
                stats[pair]["durations"].append(int(row["duration_ms"]))
            if row.get("sdm_file") and row["sdm_file"] not in ("", "PULL_FAILED"):
                stats[pair]["sdm_pulled"] += 1

            sig = stats[pair]["signal_data"]
            if row.get("rat") and row["rat"] != "N/A":
                sig["rat_distribution"][row["rat"]] += 1
            for key, typ in (("rsrp", int), ("rsrq", int), ("sinr", float)):
                val = row.get(key, "N/A")
                if val and val != "N/A":
                    try: sig[f"{key}_values"].append(typ(val))
                    except ValueError: pass
            if row.get("band") and row["band"] != "N/A":
                sig["band_distribution"][row["band"]] += 1

    for d in stats.values():
        total = d["total"]
        d["success_rate"] = (d["passed"] / total * 100) if total else 0
        d["average_duration"] = sum(d["durations"]) / len(d["durations"]) if d["durations"] else 0
        d["error_distribution"] = dict(d["errors"])
        sig = d["signal_data"]
        for key in ("rsrp", "rsrq", "sinr"):
            vals = sig[f"{key}_values"]
            if vals: sig[f"avg_{key}"] = sum(vals) / len(vals)

    overall = {
        "total_cycles":  sum(d["total"]   for d in stats.values()),
        "passed_cycles": sum(d["passed"]  for d in stats.values()),
        "failed_cycles": sum(d["failed"]  for d in stats.values()),
        "total_sdm_pulled": sum(d["sdm_pulled"] for d in stats.values()),
    }
    t = overall["total_cycles"]
    overall["success_rate"] = (overall["passed_cycles"] / t * 100) if t else 0

    rate_by_cycle = []
    for cycle in range(1, max(cycle_results.keys(), default=0) + 1):
        cd = cycle_results.get(cycle, [])
        passed = sum(1 for r in cd if r["result"] == "PASS")
        total  = len(cd)
        rate_by_cycle.append({"cycle": cycle, "success_rate": (passed/total*100) if total else 0,
                               "passed": passed, "total": total})

    duration = "Unknown"
    if first_ts and last_ts:
        try:
            from datetime import datetime as dt
            delta = dt.fromisoformat(last_ts) - dt.fromisoformat(first_ts)
            duration = str(delta)
        except ValueError:
            pass

    # ── Generate GPS maps if enabled ─────────────────────────
    import config as cfg
    if cfg.GPS_ENABLED:
        from utils.map_generator import generate_all
        test_name = _extract_test_name(str(detailed_path))
        generate_all(str(detailed_path), cfg.LOG_OUTPUT_PATH, test_name)
    
    # ── Generate KML report ──────────────────────────────────
    kml_path = os.path.join(os.path.dirname(str(detailed_path)), "gps_map.kml")
    generate_kml_report(str(detailed_path), kml_path)

    return {
        "stats_by_pair": dict(stats),
        "overall_stats": overall,
        "call_success_rate_by_cycle": rate_by_cycle,
        "test_duration": duration,
        "first_timestamp": first_ts,
        "last_timestamp": last_ts,
        "csv_path": str(detailed_path),
        "summary_csv_path": generate_summary_report(),
    }
