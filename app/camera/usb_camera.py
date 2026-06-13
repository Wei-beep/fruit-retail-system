from __future__ import annotations
import numpy as np
import time
from pathlib import Path

from app.camera.camera_interface import Camera
from app.core.config import resolve_project_path
from app.core.exceptions import CameraError


class USBCamera(Camera):
    """
    智能生鲜秤真实 USB 摄像头驱动 (树莓派优化版)
    常开设备，按需抓拍，支持内存直传和实时视频流。
    """
    def __init__(self, device_index: int, image_save_dir: str, width: int, height: int) -> None:
        # 1. 保留队友的参数契约
        self.device_index = device_index
        # 零硬盘模式下不用写硬盘了，但保留参数防崩
        self.image_save_dir = resolve_project_path(image_save_dir) 
        self.width = width
        self.height = height

        # 2. 检查 OpenCV
        try:
            import cv2
            self.cv2 = cv2
        except ImportError as exc:
            raise CameraError("opencv-python 未安装，无法使用真实 USB 摄像头") from exc

        # 3. 核心优化：常开设备
        # 不要把启动关机写在 capture 函数里面
        print(f"正在预热 USB 摄像头 (ID: {self.device_index})...")
        self.camera = self.cv2.VideoCapture(self.device_index)

        # 4. 核心优化：降维，拯救带宽和 CPU
        # 使用 config 里配的是 640x480
        self.camera.set(self.cv2.CAP_PROP_FRAME_WIDTH, self.width)
        self.camera.set(self.cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        
        # 5. 核心优化：缓冲区设为 1，防止拍到过期历史画面
        self.camera.set(self.cv2.CAP_PROP_BUFFERSIZE, 1)

        if not self.camera.isOpened():
            raise CameraError(f"USB 摄像头 (ID: {self.device_index}) 打开失败，请检查连线或端口占用")
        
        # 让曝光飞飞
        time.sleep(1)
        print("✅ USB 摄像头处于就绪状态！")

    def capture(self) -> 'np.ndarray':
        """
        零存硬盘重构：AI 推理触发
        零存硬盘
        """
        if not self.camera.isOpened():
            raise CameraError("摄像头已意外断开")

        # 连读 3 次，清空操作系统的滞留缓存，确保拿到新鲜最新的画面
        for _ in range(3):
            self.camera.read()

        ok, frame = self.camera.read()
        if not ok:
            raise CameraError("USB 摄像头采集失败")

        # 🚀 内存直传核心：直接返回矩阵数据，不在硬盘保存测试图片
        #print(f"📸 咔嚓！AI 分离式抓拍成功，内存直传数据流启动。")
        return frame

    def get_stream_frame(self) -> 'np.ndarray':
        """
        🌟 专门为主界面 UI 视频流提供的实时画面
        Tkinter 调用此方法。不要在 capture 方法里也读它。
        """
        if not self.camera.isOpened():
            return None
        
        # 实时流不需要清缓冲区，读最新帧即可
        ok, frame = self.camera.read()
        if not ok:
            return None
            
        return frame

    def __del__(self):
        """
        安全兜底：程序退出时释放硬件
        """
        if hasattr(self, 'camera') and self.camera.isOpened():
            self.camera.release()
            print("🔌 摄像头硬件已安全释放")