from abc import ABC, abstractmethod
import numpy as np

class Camera(ABC):
    @abstractmethod
    def capture(self) -> np.ndarray:
        """
        截取并返回当前帧矩阵 (供 AI 引擎推理使用)
        """
        pass

    @abstractmethod
    def get_stream_frame(self) -> np.ndarray | None:
        """
        获取当前流的最新帧矩阵 (供 GUI 实时渲染使用)
        """
        pass