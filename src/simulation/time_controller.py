"""Time acceleration controller for simulation."""

import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class TimeController:
    """Controls simulated time for accelerated pattern detection testing."""

    def __init__(self):
        self._multiplier: float = 1.0
        self._offset: timedelta = timedelta()
        self._base_time: datetime = datetime.now()

    @property
    def multiplier(self) -> float:
        return self._multiplier

    def set_multiplier(self, multiplier: float) -> None:
        """Set time acceleration. 1x = real-time, 60x = 1 hour per minute."""
        self._base_time = self.now()
        self._offset = timedelta()
        self._multiplier = max(1.0, min(60.0, multiplier))
        logger.info(f"Time multiplier set to {self._multiplier}x")

    def now(self) -> datetime:
        """Get the current simulated time."""
        real_elapsed = datetime.now() - self._base_time
        sim_elapsed = real_elapsed * self._multiplier
        return self._base_time + self._offset + sim_elapsed

    def reset(self) -> None:
        """Reset to real-time."""
        self._multiplier = 1.0
        self._offset = timedelta()
        self._base_time = datetime.now()


# Singleton
time_controller = TimeController()
