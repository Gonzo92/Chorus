# Chorus — Setup Guide

## Requirements

| Requirement | Version | Required |
|---|---|---|
| Python | 3.9+ | Yes |
| matplotlib | 3.7+ | Yes |
| folium | 0.14+ | Yes |
| ADB (Platform Tools) | any | Yes |
| scrcpy | any | Optional |

---

## Quick Setup (Windows)

1. **Install Python 3.9+**
   - Download from https://www.python.org/downloads/
   - ⚠️ During install: check **"Add Python to PATH"**

2. **Install ADB**
   - Download Platform Tools: https://developer.android.com/tools/releases/platform-tools
   - Extract ZIP to `C:\platform-tools`
   - Add `C:\platform-tools` to system PATH, or place `adb.exe` next to `main.py`

3. **Run the dependency installer**
   ```
   install_deps.bat
   ```
   This installs all Python packages automatically.

4. **Launch Chorus**
   ```
   run.bat
   ```
   or
   ```
   python main.py
   ```

5. **(Optional) Build standalone .exe**
   ```
   build.bat
   ```
   Creates `Chorus.exe` — distributable without Python.

---

## Install scrcpy (optional — screen mirroring)

Download from: https://github.com/Genymobile/scrcpy/releases

Either:
- Add `scrcpy.exe` to PATH, or
- Place it in `C:\scrcpy\scrcpy.exe`, or
- Place it next to `main.py`

Chorus will find it automatically in any of these locations.

---

## Enable USB Debugging on Android

1. Go to **Settings → About phone**
2. Tap **Build number** 7 times to unlock Developer Options
3. Go to **Settings → Developer Options**
4. Enable **USB Debugging**
5. Connect device via USB and accept the ADB authorisation prompt

Verify with: `adb devices` — device should show as `device` (not `unauthorized`)

---

## Troubleshooting

**`python` not recognised**
→ Python not in PATH. Reinstall and check "Add to PATH".

**`adb devices` shows `unauthorized`**
→ Accept the USB debugging prompt on the phone screen.

**Calls not going through in LIVE mode**
→ Make sure DRY_RUN checkbox is unchecked (indicator shows ● LIVE in green).

**scrcpy not launching**
→ Run `install.bat` to check if scrcpy is detected, or browse to `scrcpy.exe` manually when prompted.
