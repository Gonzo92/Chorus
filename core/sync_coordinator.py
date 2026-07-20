# ============================================================
#  Chorus v2.6  –  core/sync_coordinator.py
#  Synchronizes testing of DUT and REF pairs
# ============================================================

from __future__ import annotations

import threading
import time


class SyncCoordinator:
    """
    Coordinates synchronized testing between DUT and REF pairs.
    
    Uses a single threading.Barrier(2) shared by both worker threads.
    At the end of each cycle, both pairs call wait_end() and block
    until BOTH arrive — then both proceed together.
    """
    
    def __init__(
        self,
        pair1: str = "dut",
        pair2: str = "ref",
        enabled: bool = False,
        timeout: int = 30,
    ) -> None:
        self.pair1 = pair1
        self.pair2 = pair2
        self.enabled = enabled
        self.timeout = timeout
        self._lock = threading.Lock()
        self._barrier: threading.Barrier | None = None
        if enabled:
            self._barrier = threading.Barrier(2, timeout=timeout)
    
    def reset(self) -> None:
        """Reset the barrier for the next cycle."""
        with self._lock:
            if self._barrier is not None:
                try:
                    self._barrier.reset()
                except Exception:
                    pass
                self._barrier = threading.Barrier(2, timeout=self.timeout)
    
    def wait_end(self, pair: str, cycle: int) -> None:
        """
        Block until both pairs have completed the current cycle.
        Both pairs call this at the end of their cycle — the barrier
        ensures neither proceeds until both arrive.
        
        Args:
            pair: The current pair name ("dut" or "ref")
            cycle: The current cycle number
        """
        if not self.enabled or self._barrier is None:
            return
        
        # Import pause_event here to avoid circular import
        from main import _pause_event, _stop_event
        
        try:
            self._barrier.wait()
        except Exception:
            pass  # timeout or broken barrier — proceed anyway
    
    def get_status(self) -> dict:
        """
        Get the current synchronization status.
        
        Returns:
            Dictionary with status information
        """
        return {
            "enabled": self.enabled,
        }
