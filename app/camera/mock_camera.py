from __future__ import annotations

from pathlib import Path
import numpy as np

from app.camera.camera_interface import Camera
from app.core.config import resolve_project_path


class MockCamera(Camera):
    """
    Mock 模式摄像头驱动 (内存直传适配版)
    严格保持 Mock 模式可运行，不要接入真实硬件
    不要依赖 OpenCV
    """
    def __init__(self, test_image_dir: str, image_save_dir: str) -> None:
        self.test_image_dir = resolve_project_path(test_image_dir)
        # 内存直传模式下，其实不需要往 image_save_dir 存东西了，但保留参数遵守契约

    def capture(self) -> np.ndarray:
        """
        Mock 抓拍 (内存直传适配版)
        返回: numpy.ndarray (模拟 OpenCV 读出的 BGR 矩阵)
        """
        image_path = self._find_test_image()
        
        # 🌟 核心适配：如果找到了真实的测试图片，将其读取为 numpy 矩阵
        if image_path:
            # 在 Mock 模式，我们不强依赖 OpenCV
            # 这里我们动态导入
            try:
                import cv2
                frame = cv2.imread(str(image_path))
                if frame is not None:
                    return frame
            except ImportError:
                print("⚠️ 环境中未安装 opencv-python，MockCamera 将生成黑色测试图")
                    
        # 如果没找到图片，或者没装 OpenCV，生成一张 640x480 的黑色占位矩阵
        # 兼容 CLAUDE.md 的规则：不要擅自引入新的 lint/format 工具配置
        return np.zeros((480, 640, 3), dtype=np.uint8)

    def get_stream_frame(self) -> np.ndarray:
        """
        🌟 占位方法：为主界面的实时视频流提供数据
        Tkinter 需要定期调用此方法，哪怕只返回纯黑图，防止崩掉。
        """
        return np.zeros((480, 640, 3), dtype=np.uint8)

    def _find_test_image(self) -> Path | None:
        if not self.test_image_dir.exists():
            return None
        for pattern in ("*.jpg", "*.jpeg", "*.png"):
            images = sorted(self.test_image_dir.glob(pattern))
            if images:
                return images[0]
        return None