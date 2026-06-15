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

    def close(self) -> None:
        """释放底层资源（如停止取帧线程、release 摄像头设备）。

        默认无操作；持有真实硬件的子类（USBCamera）覆盖。供前端退出路径确定性调用，
        无需关心当前是 mock 还是 real。
        """
        pass