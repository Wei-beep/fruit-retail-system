from __future__ import annotations
import numpy as np
from app.core.constants import MOCK_PRODUCT_LABEL, MOCK_PRODUCT_NAME_CN
from app.vision.yolo_interface import FruitVegetableDetector


class MockFruitVegetableDetector(FruitVegetableDetector):
    def predict(self, frame: np.ndarray) -> dict:
        """Mock 识别器：忽略输入的内存矩阵，固定返回预设的测试商品（含 top-3 候选）。

        固定返回的 label 即 init_db 种子化的 MOCK_PRODUCT_LABEL，products 表中已有其价格，
        故走高置信正常计价路径。
        """
        return {
            "label": MOCK_PRODUCT_LABEL,
            "confidence": 0.97,
            "zh_name": MOCK_PRODUCT_NAME_CN,
            "count": 1,
            "candidates": [
                {"label": MOCK_PRODUCT_LABEL, "zh_name": MOCK_PRODUCT_NAME_CN, "confidence": 0.97},
                {"label": "banana_yellow", "zh_name": "黄香蕉", "confidence": 0.02},
                {"label": "orange", "zh_name": "橙子", "confidence": 0.01},
            ],
            "detected_labels": [
                {"label": MOCK_PRODUCT_LABEL, "zh_name": MOCK_PRODUCT_NAME_CN, "confidence": 0.97, "count": 1},
            ],
        }
