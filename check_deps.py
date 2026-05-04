# ============================================================
#  Chorus v2.2  –  check_deps.py
#  Pre-flight dependency checker.
#  Run: python check_deps.py
#  Exit codes: 0 = all OK, 1 = missing deps (with install instructions)
# ============================================================

from __future__ import annotations

import sys
import subprocess
import os
import platform

# ── colors (Windows ANSI) ──────────────────────────────────
_USE_COLOR = sys.platform == "win32"
try:
    subprocess.run(
        ["color"], shell=True, capture_output=True, timeout=2
    )
    _USE_COLOR = True
except Exception:
    _USE_COLOR = False

if _USE_COLOR:
    class C:
        OK = "\033[92m"    # green
        FAIL = "\033[91m"  # red
        WARN = "\033[93m"  # yellow
        INFO = "\033[96m"  # cyan
        BOLD = "\033[1m"
        RESET = "\033[0m"
else:
    class C:
        OK = FAIL = WARN = INFO = BOLD = RESET = ""

# ── requirements ───────────────────────────────────────────
REQUIRED_PACKAGES = {
    "matplotlib": "matplotlib>=3.7.0",
    "folium": "folium>=0.14.0",
}

MIN_PYTHON = (3, 9)  # minimum (3, 9) — future annotations needed
PYTHON_OK = sys.version_info >= MIN_PYTHON


def _check_python() -> tuple[bool, str]:
    """Check Python version."""
    ver = sys.version_info
    if ver < MIN_PYTHON:
        return False, (
            f"Python {ver.major}.{ver.minor}.{ver.micro} detected. "
            f"Chorus requires Python {MIN_PYTHON[0]}.{MIN_PYTHON[1]}+.\n"
            f"  Download: https://www.python.org/downloads/"
        )
    return True, f"Python {ver.major}.{ver.minor}.{ver.micro} OK"


def _check_adb() -> tuple[bool, str]:
    """Check if ADB is installed and in PATH."""
    try:
        result = subprocess.run(
            ["adb", "version"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            return True, f"ADB found: {result.stdout.strip().splitlines()[0]}"
        return False, "ADB returned non-zero exit code"
    except FileNotFoundError:
        return False, (
            "ADB not found in PATH.\n"
            "  Install Android SDK Platform-Tools:\n"
            "  https://developer.android.com/studio/releases/platform-tools\n"
            "  Then add to PATH or restart terminal."
        )
    except subprocess.TimeoutExpired:
        return False, "ADB command timed out"
    except Exception as e:
        return False, f"ADB check failed: {e}"


def _check_packages() -> tuple[bool, list[tuple[str, bool, str]]]:
    """Check if all required pip packages are installed."""
    results = []
    all_ok = True
    for module_name, pip_spec in REQUIRED_PACKAGES.items():
        try:
            mod = __import__(module_name)
            version = getattr(mod, "__version__", "unknown")
            results.append((module_name, True, f"v{version}"))
        except ImportError:
            all_ok = False
            results.append((module_name, False, "NOT INSTALLED"))
    return all_ok, results


def _check_font_availability() -> tuple[bool, list[tuple[str, bool]]]:
    """Check if required fonts are available."""
    results = []
    fonts_to_check = ["Consolas", "Segoe UI", "Arial", "Courier New"]
    all_ok = True
    for font in fonts_to_check:
        try:
            from tkinter import font as tkfont
            available = tkfont.families()
            if font in available:
                results.append((font, True))
            else:
                results.append((font, False))
        except Exception:
            results.append((font, False))
    return all_ok, results


def main() -> int:
    """Run all checks. Return 0 on success, 1 on failure."""
    width = 60
    sep = "=" * width

    print()
    print(f"{C.BOLD}Chorus v2.2 — Dependency Check{C.RESET}")
    print(sep)
    print()

    errors = []

    # 1. Python version
    print(f"  [1/4] Python version... ", end="")
    ok, msg = _check_python()
    if ok:
        print(f"{C.OK}{msg}{C.RESET}")
    else:
        print(f"{C.FAIL}{msg}{C.RESET}")
        errors.append(msg)

    # 2. ADB
    print(f"  [2/4] ADB... ", end="")
    ok, msg = _check_adb()
    if ok:
        print(f"{C.OK}{msg}{C.RESET}")
    else:
        print(f"{C.FAIL}{msg}{C.RESET}")
        errors.append(msg)

    # 3. Pip packages
    print(f"  [3/4] pip packages... ")
    all_pkgs_ok, pkg_results = _check_packages()
    for name, installed, version in pkg_results:
        if installed:
            print(f"      {C.OK}[OK]{C.RESET}   {name} {version}")
        else:
            print(f"      {C.FAIL}[MISSING]{C.RESET}  {name}  →  pip install {REQUIRED_PACKAGES[name]}")
            errors.append(f"pip package '{name}' not installed. Run: pip install {REQUIRED_PACKAGES[name]}")

    # 4. Font availability (warning only)
    print(f"  [4/4] Fonts... ", end="")
    fonts_ok, font_results = _check_font_availability()
    missing_fonts = [f for f, ok in font_results if not ok]
    available_fonts = [f for f, ok in font_results if ok]

    if available_fonts:
        fallback = available_fonts[0] if not fonts_ok else ""
        if fonts_ok:
            print(f"{C.OK}All fonts available{C.RESET}")
        else:
            print(f"{C.WARN}Some fonts missing — using fallbacks{C.RESET}")
            print(f"      Available: {', '.join(available_fonts)}")
            if fallback:
                print(f"      Recommended fallback: {fallback}")
    else:
        print(f"{C.WARN}No recognized fonts — UI may use defaults{C.RESET}")

    # ── Summary ──────────────────────────────────────────────
    print()
    print(sep)
    if errors:
        print(f"{C.FAIL}FAILED — {len(errors)} issue(s) found.{C.RESET}")
        print()
        print("To fix, run:")
        print(f"  {C.BOLD}pip install matplotlib folium{C.RESET}")
        print()
        print("Then verify ADB is in PATH:")
        print(f"  {C.BOLD}adb version{C.RESET}")
        print()
        return 1
    else:
        print(f"{C.OK}ALL CHECKS PASSED — ready to run Chorus!{C.RESET}")
        print()
        return 0


if __name__ == "__main__":
    sys.exit(main())
