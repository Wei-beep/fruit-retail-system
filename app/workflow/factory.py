"""交易流程组装工厂。

按 config.yaml 各模块的 mode 实例化 camera / weight_sensor / detector，
组装出一个 TransactionFlow。从 GUI 层抽出到此中性模块，使得 Tk 前端
（app/gui）与 Web 前端（app/web）都能复用，且 Web 后端无需 import tkinter。
"""
from __future__ import annotations

from app.camera.mock_camera import MockCamera
from app.camera.usb_camera import USBCamera
from app.pricing.price_service import PriceService
from app.pricing.transaction_service import TransactionService
from app.vision.detector import YOLODetector
from app.vision.mock_detector import MockFruitVegetableDetector
from app.weighing.hx711_sensor import HX711Sensor
from app.weighing.mock_sensor import MockWeightSensor
from app.weighing.stability import StabilityDetector
from app.workflow.transaction_flow import TransactionFlow


def create_transaction_flow(config: dict) -> TransactionFlow:
    camera_config = config["camera"]
    weighing_config = config["weighing"]
    vision_config = config["vision"]

    if camera_config["mode"] == "mock":
        camera = MockCamera(camera_config["test_image_dir"], camera_config["image_save_dir"])
    else:
        camera = USBCamera(
            camera_config["device_index"],
            camera_config["image_save_dir"],
            camera_config["width"],
            camera_config["height"],
        )

    if weighing_config["mode"] == "mock":
        weight_sensor = MockWeightSensor()
    else:
        weight_sensor = HX711Sensor(
            dout_pin=weighing_config["dout_pin"],
            sck_pin=weighing_config["sck_pin"],
            gain=weighing_config.get("gain", 128),
        )

    if vision_config["mode"] == "mock":
        detector = MockFruitVegetableDetector()
    else:
        detector = YOLODetector(vision_config["model_path"], vision_config["confidence_threshold"])

    return TransactionFlow(
        weight_sensor=weight_sensor,
        stability_detector=StabilityDetector(
            weighing_config["stable_window_size"],
            weighing_config["stable_threshold_kg"],
        ),
        camera=camera,
        detector=detector,
        price_service=PriceService(),
        transaction_service=TransactionService(),
        min_valid_weight_kg=weighing_config["min_valid_weight_kg"],
        max_valid_weight_kg=weighing_config["max_valid_weight_kg"],
        trigger_threshold_kg=weighing_config.get("trigger_threshold_kg", 0.0),
    )
