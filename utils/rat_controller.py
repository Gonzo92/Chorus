# ============================================================
#  Chorus v2.2  –  utils/rat_controller.py
#  Functions for setting Radio Access Technology (RAT) on devices
# ============================================================

from __future__ import annotations

import subprocess
import threading
from typing import Dict, List
from core.adb_controller import adb

# Mapowanie technologii na wartości binarne
RAT_VALUES = {
    "5G/4G/3G/2G": "11001101001110000111",
    "4G/3G/2G": "01001101001110000111",
    "3G/2G": "00001100001110000111",
    "2G": "00001000000000000011"
}

def set_rat_for_device(serial: str, sim_slot: int, rat_value: str) -> bool:
    """
    Ustawia RAT dla danego urządzenia i slotu SIM.
    
    Args:
        serial: Numer seryjny urządzenia
        sim_slot: Slot SIM (0 dla SIM-1, 1 dla SIM-2)
        rat_value: Wartość binarna określająca dozwolone technologie
    
    Returns:
        True jeśli operacja się powiodła, False w przeciwnym przypadku
    """
    if sim_slot not in [0, 1]:
        raise ValueError("sim_slot musi być 0 (SIM-1) lub 1 (SIM-2)")
    
    rc, _, _ = adb(serial, "shell", "cmd", "phone", "set-allowed-network-types-for-users", "-s", str(sim_slot), rat_value)
    return rc == 0

def set_rat_for_all_devices(devices: Dict[str, str], sim_settings: Dict[int, str]) -> Dict[str, Dict[int, bool]]:
    """
    Ustawia RAT dla wszystkich urządzeń.
    
    Args:
        devices: Słownik z mapowaniem ról na numery seryjne urządzeń
        sim_settings: Słownik z ustawieniami dla każdego slotu SIM
    
    Returns:
        Słownik z wynikami operacji dla każdego urządzenia i slotu SIM
    """
    results = {}
    
    # Płaskie mapowanie wszystkich numerów seryjnych (unikalne)
    serials = list(set(devices.values()))
    
    for serial in serials:
        results[serial] = {}
        for sim_slot, rat_value in sim_settings.items():
            if rat_value in RAT_VALUES:
                success = set_rat_for_device(serial, sim_slot, RAT_VALUES[rat_value])
                results[serial][sim_slot] = success
            else:
                results[serial][sim_slot] = False
    
    return results