from __future__ import annotations

import time
from typing import Callable

from app.camera.camera_interface import Camera
from app.core.exceptions import ProductNotFoundError
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
        trigger_threshold_kg: float = 0.0,
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
        # 触发阈值：秤上物重超过此值才算「有物品」，进入累积稳定窗口的称重流程。
        # 低于阈值（含轻微触碰回落）视为空秤，重置窗口 → 不会稳定 → 不触发识别。
        # 默认 0.0=不设门槛（既有测试直接构造 TransactionFlow 时即此值，保持原行为）。
        # 注意：Web 与 Tk 都经 create_transaction_flow 读 config 的 trigger_threshold_kg
        # （默认 0.02），故两套前端实际都启用该门槛，起触下限为 20g。
        self.trigger_threshold_kg = trigger_threshold_kg
        self.poll_interval_seconds = poll_interval_seconds

    def wait_for_stable_weight(
        self,
        on_reading: Callable[[float, bool, bool], None] | None = None,
    ) -> float:
        """等待重量稳定并返回稳定值（kg）。

        on_reading（可选）：每读到一次重量就回调 (weight_kg, is_stable, triggered)，
        供 Web 前端做实时重量推送与「空秤/已触发」状态切换。triggered 表示当前读数
        是否超过触发阈值。默认 None 时不回调，行为与原实现一致。

        仅在「已触发且落在有效量程内」时累积稳定窗口；否则（空秤或轻碰回落）重置窗口，
        从而保证只有真正放稳物品后才会稳定并进入后续识别。
        """
        self.stability_detector.reset()
        while True:
            weight = self.weight_sensor.read_weight()
            is_stable = False
            triggered = weight >= self.trigger_threshold_kg
            if triggered and self.min_valid_weight_kg <= weight <= self.max_valid_weight_kg:
                is_stable = self.stability_detector.add_reading(weight)
            else:
                self.stability_detector.reset()
            if on_reading is not None:
                on_reading(weight, is_stable, triggered)
            if is_stable:
                return round(self.stability_detector.get_stable_value(), 3)
            time.sleep(self.poll_interval_seconds)

    def wait_for_release(self) -> None:
        """阻塞至秤面重量回落到触发阈值以下（上一件商品被取走）。

        期间不回调 on_reading（前端停留在「请放置」引导，不显示残留克重）。
        触发阈值为 0 时立即返回（无门槛）。
        """
        if self.trigger_threshold_kg <= 0:
            return
        while self.weight_sensor.read_weight() >= self.trigger_threshold_kg:
            time.sleep(self.poll_interval_seconds)

    def prepare_transaction(
        self,
        include_candidates: bool = False,
        on_reading: Callable[[float, bool, bool], None] | None = None,
        wait_for_release_first: bool = False,
    ) -> dict:
        """生成待确认交易。

        include_candidates=False（默认，Tk 路径）：行为与原实现一致，
        识别为 unknown/未登记商品时由 PriceService 抛错向上传递。
        include_candidates=True（Web 路径）：返回值附带识别 top-3 候选与
        low_confidence 标志；低置信/未登记商品不报错，价格字段置空，等用户手动选品。

        wait_for_release_first=True（Web 完成上一笔交易后）：先等秤面清空（重量低于
        触发阈值）再开始称重，避免已购商品仍在秤上时立刻触发下一轮识别。
        """
        if wait_for_release_first:
            self.wait_for_release()
        weight_kg = self.wait_for_stable_weight(on_reading=on_reading)

        # 内存直传：从摄像头拿到 ndarray 后直接喂给模型
        frame = self.camera.capture()
        recognition = self.detector.predict(frame)

        label = recognition["label"]
        confidence = float(recognition["confidence"])

        if not include_candidates:
            product = self.price_service.get_price(label)
            total_price = self.transaction_service.calculate_total(
                weight_kg,
                product["price_per_kg"],
            )
            return {
                "label": label,
                "name_cn": product["name_cn"],
                "confidence": confidence,
                "weight_kg": weight_kg,
                "price_per_kg": product["price_per_kg"],
                "total_price": total_price,
                # 已移除 image_path 硬盘落盘依赖
            }

        # Web 路径：低置信/未登记不报错，转候选/手动选择
        candidates = recognition.get("candidates", [])
        product = None
        low_confidence = label in ("unknown", "error")
        if not low_confidence:
            try:
                product = self.price_service.get_price(label)
            except ProductNotFoundError:
                low_confidence = True

        if product is not None:
            name_cn = product["name_cn"]
            price_per_kg = product["price_per_kg"]
            total_price = self.transaction_service.calculate_total(weight_kg, price_per_kg)
        else:
            name_cn = recognition.get("zh_name")
            price_per_kg = None
            total_price = None

        return {
            "label": label,
            "name_cn": name_cn,
            "confidence": confidence,
            "weight_kg": weight_kg,
            "price_per_kg": price_per_kg,
            "total_price": total_price,
            "low_confidence": low_confidence,
            "candidates": candidates,
        }

    def confirm_transaction(self, prepared_transaction: dict) -> int:
        return self.transaction_service.create_transaction(
            prepared_transaction["label"],
            prepared_transaction["weight_kg"],
            prepared_transaction["price_per_kg"],
            prepared_transaction["total_price"],
        )