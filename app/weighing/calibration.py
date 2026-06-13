from __future__ import annotations

from app.db import repositories


class CalibrationService:
    def get_calibration(self) -> dict:
        calibration = repositories.get_calibration()
        return calibration or {"scale_factor": 1.0, "offset": 0.0}

    def save_calibration(self, scale_factor: float, offset: float) -> None:
        repositories.save_calibration(scale_factor, offset)
