from __future__ import annotations

import time

from app.camera.camera_interface import Camera
from app.pricing.price_service import PriceService
from app.pricing.transaction_service import TransactionService
from app.vision.yolo_interface import FruitVegetableDetector
from app.weighing.hx711_interface import WeightSensor
from app.weighing.stability import StabilityDetector


class TransactionFlow:
    def __init__(
        self,
        weight_sensor: WeightSensor,
        stability_detector: StabilityDetector,
        camera: Camera,
        detector: FruitVegetableDetector,
        price_service: PriceService,
        transaction_service: TransactionService,
        min_valid_weight_kg: float = 0.01,
        max_valid_weight_kg: float = 5.0,
        poll_interval_seconds: float = 0.1,
    ) -> None:
        self.weight_sensor = weight_sensor
        self.stability_detector = stability_detector
        self.camera = camera
        self.detector = detector
        self.price_service = price_service
        self.transaction_service = transaction_service
        self.min_valid_weight_kg = min_valid_weight_kg
        self.max_valid_weight_kg = max_valid_weight_kg
        self.poll_interval_seconds = poll_interval_seconds

    def wait_for_stable_weight(self) -> float:
        self.stability_detector.reset()
        while True:
            weight = self.weight_sensor.read_weight()
            if self.min_valid_weight_kg <= weight <= self.max_valid_weight_kg:
                if self.stability_detector.add_reading(weight):
                    return round(self.stability_detector.get_stable_value(), 3)
            else:
                self.stability_detector.reset()
            time.sleep(self.poll_interval_seconds)

    def prepare_transaction(self) -> dict:
        weight_kg = self.wait_for_stable_weight()
        
        # 内存直传：从摄像头拿到 ndarray 后直接喂给模型
        frame = self.camera.capture()
        recognition = self.detector.predict(frame)
        
        label = recognition["label"]
        product = self.price_service.get_price(label)
        total_price = self.transaction_service.calculate_total(
            weight_kg,
            product["price_per_kg"],
        )
        return {
            "label": label,
            "name_cn": product["name_cn"],
            "confidence": float(recognition["confidence"]),
            "weight_kg": weight_kg,
            "price_per_kg": product["price_per_kg"],
            "total_price": total_price,
            # 已移除 image_path 硬盘落盘依赖
        }

    def confirm_transaction(self, prepared_transaction: dict) -> int:
        return self.transaction_service.create_transaction(
            prepared_transaction["label"],
            prepared_transaction["weight_kg"],
            prepared_transaction["price_per_kg"],
            prepared_transaction["total_price"],
        )