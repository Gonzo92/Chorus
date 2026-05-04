# ============================================================
#  Chorus v2.2  –  utils/phone_history.py
#  Manages recently used phone numbers for Chorus application
# ============================================================

from __future__ import annotations

import json
import os
from typing import List

# Path to the history file
HISTORY_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "phone_history.json")

# Maximum number of history entries to keep
MAX_HISTORY_ENTRIES = 10

def load_history() -> dict:
    """
    Load phone number history from file.
    
    Returns:
        dict: Dictionary with 'dut' and 'ref' lists of phone numbers
    """
    try:
        with open(HISTORY_FILE, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        # Return default empty history if file doesn't exist or is invalid
        return {"dut": [], "ref": []}

def save_history(history: dict) -> None:
    """
    Save phone number history to file.
    
    Args:
        history: Dictionary with 'dut' and 'ref' lists of phone numbers
    """
    try:
        # Ensure we don't exceed maximum entries
        for key in history:
            if isinstance(history[key], list):
                history[key] = history[key][-MAX_HISTORY_ENTRIES:]
        
        with open(HISTORY_FILE, 'w') as f:
            json.dump(history, f, indent=2)
    except Exception:
        # Silently fail if we can't save history
        pass

def add_to_history(pair: str, number: str) -> None:
    """
    Add a phone number to history for the specified pair.
    
    Args:
        pair: Either 'dut' or 'ref'
        number: Phone number to add to history
    """
    if pair not in ['dut', 'ref'] or not number:
        return
        
    history = load_history()
    
    # Remove the number if it already exists in history
    if number in history[pair]:
        history[pair].remove(number)
    
    # Add the number to the beginning of the list
    history[pair].insert(0, number)
    
    # Save the updated history
    save_history(history)

def get_history(pair: str) -> List[str]:
    """
    Get phone number history for the specified pair.
    
    Args:
        pair: Either 'dut' or 'ref'
        
    Returns:
        List of phone numbers in history
    """
    if pair not in ['dut', 'ref']:
        return []
        
    history = load_history()
    return history.get(pair, [])