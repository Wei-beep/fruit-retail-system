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
    readings: list[tuple[float, bool]] = []
    _make_flow().prepare_transaction(
        include_candidates=True, on_reading=lambda w, s: readings.append((w, s))
    )
    assert len(readings) > 0
    assert readings[-1][1] is True  # 最后一次为稳定


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
