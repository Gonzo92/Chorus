# ============================================================
#  Chorus v2.6  –  core/apk_parser.py
#  Parse APK files (pure Python, no aapt needed).
#  Extracts package name, versionName, and versionCode from
#  the AndroidManifest.xml inside the APK ZIP archive.
# ============================================================

from __future__ import annotations

import os
import re
import zipfile


def parse_apk(apk_path: str) -> dict | None:
    """
    Parse an APK file and extract metadata.

    Returns:
        {
            "package": "com.example.app",
            "version_name": "1.2.3",
            "version_code": "42",
            "file_name": "my_app.apk",
            "file_size_mb": 15.7,
        }
        or None on failure.
    """
    if not apk_path or not os.path.isfile(apk_path):
        return None

    result = {
        "package": "N/A",
        "version_name": "N/A",
        "version_code": "N/A",
        "file_name": os.path.basename(apk_path),
        "file_size_mb": 0.0,
    }

    # File size
    try:
        result["file_size_mb"] = round(os.path.getsize(apk_path) / (1024 * 1024), 1)
    except OSError:
        pass

    try:
        with zipfile.ZipFile(apk_path, "r") as zf:
            if "AndroidManifest.xml" not in zf.namelist():
                return result

            manifest_data = zf.read("AndroidManifest.xml")

            # Try text XML first (debug builds, most cases)
            try:
                text = manifest_data.decode("utf-8", errors="ignore")
                if "<?xml" in text or text.strip().startswith("<"):
                    _parse_text_manifest(text, result)
                    return result
            except Exception:
                pass

            # Binary XML — best-effort regex fallback
            _parse_binary_manifest(manifest_data, result)

    except Exception:
        pass

    return result


def _parse_text_manifest(xml_text: str, result: dict) -> None:
    """Parse a text-based AndroidManifest.xml using regex."""
    # package attribute on <manifest>
    m = re.search(r'package\s*=\s*["\']([^"\']+)["\']', xml_text)
    if m:
        result["package"] = m.group(1)

    # versionName on <application>
    m = re.search(r'versionName\s*=\s*["\']([^"\']+)["\']', xml_text)
    if m:
        result["version_name"] = m.group(1)

    # versionCode on <application>
    m = re.search(r'versionCode\s*=\s*["\']?(\d+)["\']?', xml_text)
    if m:
        result["version_code"] = m.group(1)


def _parse_binary_manifest(data: bytes, result: dict) -> None:
    """
    Parse a binary AndroidManifest.xml using regex on raw bytes.
    Best-effort fallback for binary XML.
    """
    try:
        text = data.decode("utf-8", errors="ignore")
    except Exception:
        text = data.decode("latin-1", errors="ignore")

    # Look for package/version patterns in raw bytes
    m = re.search(r'package\s*=\s*["\']([^"\']+)["\']', text)
    if m:
        result["package"] = m.group(1)

    m = re.search(r'versionName\s*=\s*["\']([^"\']+)["\']', text)
    if m:
        result["version_name"] = m.group(1)

    m = re.search(r'versionCode\s*=\s*["\']?(\d+)["\']?', text)
    if m:
        result["version_code"] = m.group(1)