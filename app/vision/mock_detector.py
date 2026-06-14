from __future__ import annotations
import numpy as np
from app.vision.yolo_interface import FruitVegetableDetector

class MockFruitVegetableDetector(FruitVegetableDetector):
    def predict(self, frame: np.ndarray) -> dict:
        """Mock 识别器：忽略输入的内存矩阵，固定返回预设结果（含 top-3 候选）"""
        return {
            "label": "apple",
            "confidence": 0.97,
            "zh_name": "苹果",
            "candidates": [
                {"label": "apple", "zh_name": "苹果", "confidence": 0.97},
                {"label": "banana", "zh_name": "香蕉", "confidence": 0.02},
                {"label": "orange", "zh_name": "橙子", "confidence": 0.01},
            ],
        }
