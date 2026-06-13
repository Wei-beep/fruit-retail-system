from __future__ import annotations

import itertools
import random

from app.weighing.hx711_interface import WeightSensor


class MockWeightSensor(WeightSensor):
    def __init__(self) -> None:
        self._readings = iter(
            [
                0.48,
                0.50,
                0.515,
                0.523,
                0.519,
                0.521,
                0.520,
                0.522,
                0.519,
                0.521,
                0.520,
                0.521,
                0.520,
                0.522,
                0.520,
            ]
        )
        self._fallback = itertools.count()

    def read_weight(self) -> float:
        try:
            return next(self._readings)
        except StopIteration:
            next(self._fallback)
            return round(0.52 + random.uniform(-0.001, 0.001), 3)
