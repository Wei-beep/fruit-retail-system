"""Web kiosk 后端及业务层扩展测试（全部 mock 模式，不依赖 GPIO/真摄像头）。"""
from __future__ import annotations

import numpy as np
from fastapi.testclient import TestClient

from app.camera.mock_camera import MockCamera
from app.core.config import load_config
from app.db import repositories
from app.db.init_db import initialize_database
from app.gui.gui_controller import GUIController
from app.pricing.price_service import PriceService
from app.pricing.transaction_service import TransactionService
from app.vision.mock_detector import MockFruitVegetableDetector
from app.vision.yolo_interface import FruitVegetableDetector
from app.weighing.hx711_interface import WeightSensor
from app.weighing.mock_sensor import MockWeightSensor
from app.weighing.stability import StabilityDetector
from app.web.server import create_web_app
from app.workflow.transaction_flow import TransactionFlow


def _make_flow(detector=None, poll: float = 0.0) -> TransactionFlow:
    return TransactionFlow(
        weight_sensor=MockWeightSensor(),
        stability_detector=StabilityDetector(window_size=10, threshold=0.005),
        camera=MockCamera("data/images/test", "data/images/captured"),
        detector=detector or MockFruitVegetableDetector(),
        price_service=PriceService(),
        transaction_service=TransactionService(),
        poll_interval_seconds=poll,
    )


class _LowConfDetector(FruitVegetableDetector):
    def predict(self, frame: np.ndarray) -> dict:
        return {
            "label": "unknown",
            "confidence": 0.31,
            "zh_name": "置信度过低",
            "candidates": [
                {"label": "apple", "zh_name": "苹果", "confidence": 0.31},
                {"label": "banana", "zh_name": "香蕉", "confidence": 0.28},
                {"label": "orange", "zh_name": "橙子", "confidence": 0.20},
            ],
        }


def test_prepare_with_candidates_confident() -> None:
    initialize_database()
    prepared = _make_flow().prepare_transaction(include_candidates=True)
    assert prepared["label"] == "apple"
    assert prepared["low_confidence"] is False
    assert prepared["total_price"] > 0
    assert len(prepared["candidates"]) == 3


def test_prepare_with_candidates_low_confidence_does_not_raise() -> None:
    initialize_database()
    prepared = _make_flow(detector=_LowConfDetector()).prepare_transaction(include_candidates=True)
    assert prepared["low_confidence"] is True
    assert prepared["total_price"] is None
    assert prepared["price_per_kg"] is None
    assert len(prepared["candidates"]) == 3


def test_on_reading_callback_invoked() -> None:
    initialize_database()
    readings: list[tuple[float, bool, bool]] = []
    _make_flow().prepare_transaction(
        include_candidates=True, on_reading=lambda w, s, t: readings.append((w, s, t))
    )
    assert len(readings) > 0
    assert readings[-1][1] is True  # 最后一次为稳定


class _RampWeightSensor(WeightSensor):
    """先给两次低于触发阈值的读数，再持续给同一稳定重量。"""

    def __init__(self) -> None:
        self._vals = iter([0.005, 0.008] + [0.30] * 11)

    def read_weight(self) -> float:
        return next(self._vals)


def test_trigger_threshold_gates_stability_and_reports_flag() -> None:
    """低于触发阈值的读数不累积稳定窗口，且回调 triggered=False。"""
    flow = TransactionFlow(
        weight_sensor=_RampWeightSensor(),
        stability_detector=StabilityDetector(window_size=5, threshold=0.005),
        camera=MockCamera("data/images/test", "data/images/captured"),
        detector=MockFruitVegetableDetector(),
        price_service=PriceService(),
        transaction_service=TransactionService(),
        trigger_threshold_kg=0.02,
        poll_interval_seconds=0.0,
    )
    readings: list[tuple[float, bool, bool]] = []
    stable = flow.wait_for_stable_weight(
        on_reading=lambda w, s, t: readings.append((w, s, t))
    )
    # 前两次 5g/8g 低于 20g 阈值 → 未触发、不稳定
    assert readings[0][2] is False and readings[0][1] is False
    assert readings[1][2] is False
    # 触发后累积满 5 个 300g 才稳定
    assert readings[-1][2] is True and readings[-1][1] is True
    assert stable == 0.3


class _ReleaseThenPlaceSensor(WeightSensor):
    """上一件商品仍在秤上(>阈值)→被取走(<阈值)→放上新商品并稳定。"""

    def __init__(self) -> None:
        self._vals = iter([0.30, 0.30, 0.30, 0.005] + [0.25] * 10)

    def read_weight(self) -> float:
        try:
            return next(self._vals)
        except StopIteration:
            return 0.25


def test_wait_for_release_then_stabilize() -> None:
    """wait_for_release_first：先等秤面清空再称重，已购商品的残留读数不参与稳定。"""
    initialize_database()
    flow = TransactionFlow(
        weight_sensor=_ReleaseThenPlaceSensor(),
        stability_detector=StabilityDetector(window_size=5, threshold=0.005),
        camera=MockCamera("data/images/test", "data/images/captured"),
        detector=MockFruitVegetableDetector(),
        price_service=PriceService(),
        transaction_service=TransactionService(),
        trigger_threshold_kg=0.02,
        poll_interval_seconds=0.0,
    )
    readings: list[tuple[float, bool, bool]] = []
    prepared = flow.prepare_transaction(
        include_candidates=True,
        on_reading=lambda w, s, t: readings.append((w, s, t)),
        wait_for_release_first=True,
    )
    # 释放期(0.30)读数既不回调也不参与稳定；稳定值来自取走后放上的新商品 0.25
    assert prepared["weight_kg"] == 0.25
    assert readings and all(w <= 0.25 for (w, _s, _t) in readings)


def test_select_label_recomputes_total() -> None:
    initialize_database()
    events: list[dict] = []
    controller = GUIController(
        transaction_flow=_make_flow(),
        on_status=lambda _t: None,
        on_transaction_ready=lambda d: events.append(d),
        on_error=lambda _t: None,
        on_cleared=lambda: None,
        include_candidates=True,
    )
    controller.current_transaction = {
        "label": "unknown", "name_cn": None, "confidence": 0.3,
        "weight_kg": 0.5, "price_per_kg": None, "total_price": None,
        "low_confidence": True, "candidates": [],
    }
    controller.select_label("apple")
    assert events, "select_label 应触发 on_transaction_ready"
    updated = events[-1]
    assert updated["label"] == "apple"
    assert updated["low_confidence"] is False
    apple = repositories.get_product_by_label("apple")
    assert updated["total_price"] == round(0.5 * float(apple["price_per_kg"]), 2)


def test_list_products() -> None:
    initialize_database()
    products = PriceService().list_products()
    labels = {p["label"] for p in products}
    assert {"apple", "banana", "orange"}.issubset(labels)
    assert all("price_per_kg" in p and "name_cn" in p for p in products)


def _mock_config() -> dict:
    config = load_config()
    config["camera"]["mode"] = "mock"
    config["weighing"]["mode"] = "mock"
    config["vision"]["mode"] = "mock"
    return config


def test_web_rest_endpoints() -> None:
    app = create_web_app(_mock_config())
    with TestClient(app) as client:
        assert client.get("/healthz").json() == {"status": "ok"}
        products = client.get("/api/ui/products").json()
        assert any(p["label"] == "apple" for p in products)


def test_web_exit_endpoint_sets_shutdown() -> None:
    from app.web.lifecycle import shutdown_event
    shutdown_event.clear()
    app = create_web_app(_mock_config())
    with TestClient(app) as client:
        assert client.post("/api/exit").json() == {"status": "exiting"}
        assert shutdown_event.is_set()
    shutdown_event.clear()


def test_web_ws_full_flow() -> None:
    app = create_web_app(_mock_config())
    with TestClient(app) as client:
        with client.websocket_connect("/ws") as ws:
            ready = None
            for _ in range(200):
                msg = ws.receive_json()
                if msg["type"] == "transaction_ready":
                    ready = msg["data"]
                    break
            assert ready is not None and ready["label"] == "apple"

            ws.send_json({"type": "confirm"})
            confirmed = None
            for _ in range(200):
                msg = ws.receive_json()
                if msg["type"] == "confirmed":
                    confirmed = msg
                    break
            assert confirmed is not None
            assert confirmed["transaction_id"] > 0
            assert confirmed["data"]["label"] == "apple"
