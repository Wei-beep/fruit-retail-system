from abc import ABC, abstractmethod
import numpy as np

class FruitVegetableDetector(ABC):
    @abstractmethod
    def predict(self, frame: np.ndarray) -> dict:
        """
        接收 numpy.ndarray 格式的图片矩阵并返回识别结果
        返回格式至少包含: {"label": str, "confidence": float}
        """
        pass