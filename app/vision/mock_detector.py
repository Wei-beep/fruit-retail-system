from __future__ import annotations
import numpy as np
from app.vision.yolo_interface import FruitVegetableDetector

class MockFruitVegetableDetector(FruitVegetableDetector):
    def predict(self, frame: np.ndarray) -> dict:
        """Mock 识别器：忽略输入的内存矩阵，固定返回预设结果"""
        return {"label": "apple", "confidence": 0.97}