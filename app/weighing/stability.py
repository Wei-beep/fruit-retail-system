from __future__ import annotations

from collections import deque


class StabilityDetector:
    def __init__(self, window_size: int, threshold: float) -> None:
        self.window_size = window_size
        self.threshold = threshold
        self._readings: deque[float] = deque(maxlen=window_size)

    def add_reading(self, value: float) -> bool:
        self._readings.append(value)
        if len(self._readings) < self.window_size:
            return False
        return max(self._readings) - min(self._readings) <= self.threshold

    def get_stable_value(self) -> float:
        if not self._readings:
            return 0.0
        return sum(self._readings) / len(self._readings)

    def reset(self) -> None:
        self._readings.clear()
