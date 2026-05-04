# ============================================================
#  Chorus v2.1  –  map_generator.py
#  Generate GPS test maps: interactive HTML (folium) + static PNG (matplotlib)
#  Background feature — no GUI changes required
# ============================================================

from __future__ import annotations

import csv
import os
from datetime import datetime
from pathlib import Path


def generate_all(csv_path: str, output_dir: str, test_name: str) -> tuple[str, str]:
    """
    Generate both HTML and PNG maps from GPS CSV data.
    
    Returns:
        (html_path, png_path) — paths to generated files
    """
    html_path = os.path.join(output_dir, "gps_map.html")
    png_path = os.path.join(output_dir, "gps_map.png")
    
    try:
        generate_html(csv_path, html_path, test_name)
    except Exception as e:
        print(f"[WARN] GPS HTML map generation failed: {e}")
        html_path = None
    
    try:
        generate_png(csv_path, png_path)
    except Exception as e:
        print(f"[WARN] GPS PNG map generation failed: {e}")
        png_path = None
    
    return html_path, png_path


def generate_html(csv_path: str, output_path: str, test_name: str) -> str:
    """
    Generate interactive HTML map with folium (Leaflet.js).
    
    Features:
    - Circle markers: green for PASS, red for FAIL
    - Marker size proportional to RSRP signal strength
    - PolyLine connecting all points (test route)
    - Popup on click with cycle details
    - Legend in bottom-right corner
    """
    import folium
    
    # Read CSV data with GPS coordinates
    data = _read_gps_data(csv_path)
    if not data:
        return output_path
    
    # Calculate map center (average of all GPS points)
    valid_lats = [d["lat"] for d in data if d["lat"] is not None]
    valid_lons = [d["lon"] for d in data if d["lon"] is not None]
    
    if not valid_lats or not valid_lons:
        return output_path
    
    center_lat = sum(valid_lats) / len(valid_lats)
    center_lon = sum(valid_lons) / len(valid_lons)
    
    # Create map
    m = folium.Map(location=[center_lat, center_lon], zoom_start=15, tiles=None)
    
    # Add OSM tile layer (local bundle)
    folium.TileLayer(
        tiles='https://tile.openstreetmap.org/{z}/{x}/{y}.png',
        attr='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
        name='OpenStreetMap',
    ).add_to(m)
    
    # Add markers
    for d in data:
        if d["lat"] is None or d["lon"] is None:
            continue
        
        # Determine color and radius based on result and RSRP
        result = d.get("result", "UNKNOWN")
        rsrp = d.get("rsrp", "N/A")
        
        if result == "PASS":
            try:
                rsrp_val = int(rsrp) if rsrp and rsrp != "N/A" else -80
                # Strong signal (> -90): large marker, weak (<= -90): small marker
                radius = 15 if rsrp_val > -90 else 8
                color = "green"
            except (ValueError, TypeError):
                radius = 15
                color = "green"
        else:
            radius = 12
            color = "red"
        
        # Build popup content
        popup_html = f"""
        <div style="font-family:Segoe UI;font-size:12px;min-width:180px">
            <b>Cycle {d["cycle"]}</b> — {d["pair"].upper()}<br>
            <hr style="margin:4px 0">
            <b>Result:</b> <span style="color:{"#5aff9d" if result == "PASS" else "#ff8585"}">{result}</span><br>
            <b>Time:</b> {d.get("timestamp", "N/A")}
        """
        
        if d.get("call_type") and d["call_type"] != "UNKNOWN":
            popup_html += f'<b>Call Type:</b> {d["call_type"]}<br>'
        
        if d.get("rat") and d["rat"] != "N/A":
            popup_html += f'<b>RAT:</b> {d["rat"]}<br>'
        
        if d.get("rsrp") and d["rsrp"] != "N/A":
            popup_html += f'<b>RSRP:</b> {d["rsrp"]} dBm<br>'
        
        if d.get("rsrq") and d["rsrq"] != "N/A":
            popup_html += f'<b>RSRQ:</b> {d["rsrq"]}<br>'
        
        if d.get("sinr") and d["sinr"] != "N/A":
            popup_html += f'<b>SINR:</b> {d["sinr"]}<br>'
        
        if d.get("band") and d["band"] != "N/A":
            popup_html += f'<b>Band:</b> {d["band"]}<br>'
        
        if d.get("error_type") and d["error_type"]:
            popup_html += f'<b>Error:</b> {d["error_type"]}<br>'
        
        if d.get("lat") is not None:
            popup_html += f'<b>Lat:</b> {d["lat"]:.6f}<br>'
        if d.get("lon") is not None:
            popup_html += f'<b>Lon:</b> {d["lon"]:.6f}<br>'
        
        if d.get("gps_accuracy") and d["gps_accuracy"] is not None:
            popup_html += f'<b>GPS Acc:</b> {d["gps_accuracy"]:.0f}m<br>'
        
        popup_html += "</div>"
        
        folium.CircleMarker(
            location=[d["lat"], d["lon"]],
            radius=radius,
            color=color,
            fill=True,
            fill_color=color,
            fill_opacity=0.7,
            popup=folium.Popup(popup_html, max_width=300),
            tooltip=f"Cycle {d['cycle']} — {result}",
        ).add_to(m)
    
    # Add route line
    route_lats = [d["lat"] for d in data if d["lat"] is not None]
    route_lons = [d["lon"] for d in data if d["lon"] is not None]
    
    if len(route_lats) >= 2:
        route = list(zip(route_lats, route_lons))
        folium.PolyLine(
            locations=route,
            color="gray",
            weight=2,
            opacity=0.4,
            dash_array="5, 10",
        ).add_to(m)
    
    # Add legend
    legend_html = """
    <div style="
        position: fixed;
        bottom: 30px;
        right: 30px;
        width: 180px;
        background: white;
        border: 2px solid grey;
        z-index: 9999;
        font-size: 11px;
        padding: 10px;
        border-radius: 5px;
        box-shadow: 2px 2px 6px rgba(0,0,0,0.3);
    ">
        <b style="font-size:13px">Chorus v2.1 GPS</b><br>
        <hr style="margin:5px 0">
        <div style="display:flex;align-items:center;margin:3px 0">
            <div style="width:14px;height:14px;border-radius:50%;background:green;margin-right:6px;flex-shrink:0"></div>
            PASS (strong RSRP)
        </div>
        <div style="display:flex;align-items:center;margin:3px 0">
            <div style="width:10px;height:10px;border-radius:50%;background:green;margin-right:6px;flex-shrink:0"></div>
            PASS (weak RSRP)
        </div>
        <div style="display:flex;align-items:center;margin:3px 0">
            <div style="width:12px;height:12px;border-radius:50%;background:red;margin-right:6px;flex-shrink:0"></div>
            FAIL
        </div>
        <div style="display:flex;align-items:center;margin:3px 0">
            <div style="width:20px;height:2px;background:gray;margin-right:6px;flex-shrink:0;border-bottom:2px dashed"></div>
            Route
        </div>
    </div>
    """
    m.get_root().html.add_child(folium.Element(legend_html))
    
    # Add title
    title_html = f"""
    <div style="
        position: fixed;
        top: 10px;
        left: 50%;
        transform: translateX(-50%);
        background: white;
        padding: 8px 16px;
        z-index: 9999;
        font-size: 14px;
        font-weight: bold;
        border-radius: 5px;
        box-shadow: 2px 2px 6px rgba(0,0,0,0.3);
    ">
        Chorus v2.1 — {test_name} — {datetime.now().strftime("%Y-%m-%d %H:%M")}
    </div>
    """
    m.get_root().html.add_child(folium.Element(title_html))
    
    # Save
    m.save(output_path)
    return output_path


def generate_png(csv_path: str, output_path: str) -> str:
    """
    Generate static map PNG with matplotlib.
    
    Features:
    - Scatter plot: lat (Y) vs lon (X)
    - Color: green=PASS, red=FAIL
    - Marker size: proportional to RSRP signal strength
    - Line connecting points (test route)
    - Cycle numbers as labels
    - Grid, axis labels, title, legend
    """
    import matplotlib
    matplotlib.use("Agg")  # Non-interactive backend
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    
    # Read CSV data with GPS coordinates
    data = _read_gps_data(csv_path)
    if not data:
        return output_path
    
    # Separate valid and invalid data
    pass_lats, pass_lons, pass_sizes = [], [], []
    fail_lats, fail_lons, fail_sizes = [], [], []
    route_lats, route_lons = [], []
    
    for d in data:
        if d["lat"] is None or d["lon"] is None:
            continue
        
        rsrp = d.get("rsrp", "N/A")
        try:
            rsrp_val = int(rsrp) if rsrp and rsrp != "N/A" else -80
            size = max(30, min(200, abs(rsrp_val) * 3))
        except (ValueError, TypeError):
            size = 100
        
        result = d.get("result", "UNKNOWN")
        
        if result == "PASS":
            pass_lats.append(d["lat"])
            pass_lons.append(d["lon"])
            pass_sizes.append(size)
        else:
            fail_lats.append(d["lat"])
            fail_lons.append(d["lon"])
            fail_sizes.append(size)
        
        route_lats.append(d["lat"])
        route_lons.append(d["lon"])
    
    # Create figure
    fig, ax = plt.subplots(1, 1, figsize=(16, 9), dpi=100)
    
    # Plot route line
    if len(route_lats) >= 2:
        ax.plot(route_lons, route_lats, "gray", alpha=0.3, linewidth=1.5, zorder=1,
                label="Route", linestyle="--")
    
    # Plot PASS points
    if pass_lats:
        ax.scatter(pass_lons, pass_lats, c="green", s=pass_sizes, alpha=0.7,
                   edgecolors="darkgreen", linewidths=0.5, zorder=3, label="PASS")
    
    # Plot FAIL points
    if fail_lats:
        ax.scatter(fail_lons, fail_lats, c="red", s=fail_sizes, alpha=0.8,
                   edgecolors="darkred", linewidths=0.5, zorder=4, label="FAIL")
    
    # Add cycle numbers as text
    for i, d in enumerate(data):
        if d["lat"] is not None and d["lon"] is not None:
            ax.annotate(
                str(d["cycle"]),
                (d["lon"], d["lat"]),
                textcoords="offset points",
                xytext=(6, 4),
                fontsize=7,
                color="black",
                fontweight="bold",
                zorder=5,
            )
    
    # Styling
    ax.set_xlabel("Longitude", fontsize=11)
    ax.set_ylabel("Latitude", fontsize=11)
    ax.set_title(f"Chorus v2.1 — {data[0].get('pair', 'test').upper()} GPS Tracking", fontsize=13, fontweight="bold")
    ax.grid(True, alpha=0.3, linestyle="-")
    ax.legend(loc="upper right", fontsize=9, framealpha=0.9)
    
    # Add version and timestamp
    fig.text(0.98, 0.02, f"Chorus v2.1 | {datetime.now().strftime('%Y-%m-%d %H:%M')}",
             ha="right", fontsize=8, color="gray", transform=ax.transAxes)
    
    plt.tight_layout(rect=[0, 0.03, 1, 0.95])
    fig.savefig(output_path, bbox_inches="tight", dpi=150, facecolor="white")
    plt.close(fig)
    
    return output_path


def _read_gps_data(csv_path: str) -> list[dict]:
    """
    Read CSV and return rows with GPS coordinates.
    
    Returns:
        List of dicts with GPS + call data for each cycle
    """
    results = []
    
    try:
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Only include rows with GPS data
                if row.get("lat") and row["lat"] not in ("", "N/A", "None"):
                    try:
                        results.append({
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
                            "gps_accuracy": row.get("gps_accuracy"),
                            "gps_time": row.get("gps_time"),
                            "gps_provider": row.get("gps_provider"),
                        })
                    except (ValueError, TypeError):
                        continue
    except FileNotFoundError:
        pass
    
    return results
