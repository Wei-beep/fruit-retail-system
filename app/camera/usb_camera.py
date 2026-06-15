from __future__ import annotations
import atexit
import threading
import numpy as np
import time

from app.camera.camera_interface import Camera
from app.core.config import resolve_project_path
from app.core.exceptions import CameraError


class USBCamera(Camera):
    """
    智能生鲜秤真实 USB 摄像头驱动 (树莓派优化版)
    常开设备，按需抓拍，支持内存直传和实时视频流。

    单读取者模型：cv2.VideoCapture 非线程安全，而本系统里抓拍(capture，AI 推理)
    与取流(get_stream_frame，UI/MJPEG)分处不同线程，若各自直接 read() 同一设备会
    并发抢占导致花屏/崩溃。故此处由内部唯一一个后台守护线程持续读取设备并缓存最新帧；
    capture() 与 get_stream_frame() 都只返回该缓存帧、不再直接碰设备，从根本上消除
    并发 read。这样无论 Web(KioskSession 取帧线程)、Tk(主线程取帧 + 后台抓拍线程)还是
    脚本直接调用，都只有这一个线程在读硬件。
    """

    # capture() 等待首帧就绪的上限（秒）。常开+预热后缓存通常已就绪，仅作冷启动兜底。
    _FIRST_FRAME_TIMEOUT = 3.0
    # 缓存帧最大允许「陈旧」时长（秒）。超过仍无新帧说明设备掉线，capture() 据此报错，
    # 保留原实现「摄像头已意外断开则抛错」的安全语义。
    _STALE_FRAME_SECONDS = 3.0

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

        # 6. 唯一读取者：后台守护线程持续抓帧入缓存，capture/取流均复用此缓存帧
        self._latest_frame: 'np.ndarray | None' = None
        self._last_ok_monotonic = 0.0
        self._frame_lock = threading.Lock()
        self._running = True
        self._grab_thread = threading.Thread(target=self._grab_loop, daemon=True)
        self._grab_thread.start()
        # 进程正常退出时（在守护线程被强杀、解释器收尾之前）于主线程确定性停线程+放设备。
        # 实测：显式停线程后退出干净；仅靠 __del__ 在收尾期 join 会触发 cv2 abort。
        atexit.register(self.close)

        # 让曝光飞飞（同时给抓帧线程时间填满首帧缓存）
        time.sleep(1)
        print("✅ USB 摄像头处于就绪状态！")

    def _grab_loop(self) -> None:
        """唯一直接读设备的线程：持续抓取最新帧写入缓存，并在退出时负责释放设备。

        BUFFERSIZE=1 + 连续读取使缓存帧始终为最新；read() 本身按相机帧率阻塞，
        无需精确限频，仅在失败时退避，避免设备异常时空转占满 CPU。
        release() 也放在本线程：设备的 read 与 release 全程同一线程串行，杜绝
        「主线程 release 时本线程仍在 read」的并发，避免进程收尾时 cv2 abort。
        """
        try:
            while self._running:
                try:
                    ok, frame = self.camera.read()
                except Exception:
                    ok, frame = False, None
                if ok and frame is not None:
                    with self._frame_lock:
                        self._latest_frame = frame
                        self._last_ok_monotonic = time.monotonic()
                    time.sleep(0.005)  # 让出 GIL，避免纯 CPU 自旋
                else:
                    time.sleep(0.1)    # 读取失败（掉线/未就绪）退避后重试
        finally:
            try:
                if self.camera.isOpened():
                    self.camera.release()
            except Exception:
                pass

    def capture(self) -> 'np.ndarray':
        """
        零存硬盘：AI 推理触发点。复用后台抓帧线程缓存的最新帧（不直接读设备），
        从而与取流线程零并发。read() 每次分配新数组，缓存帧为独立对象，可安全返回引用。
        """
        deadline = time.monotonic() + self._FIRST_FRAME_TIMEOUT
        while True:
            with self._frame_lock:
                frame = self._latest_frame
                last_ok = self._last_ok_monotonic
            if frame is not None:
                # 缓存帧过于陈旧 → 设备已掉线，沿用原「意外断开」语义抛错
                if time.monotonic() - last_ok > self._STALE_FRAME_SECONDS:
                    raise CameraError("摄像头已意外断开（画面长时间未更新）")
                return frame
            if time.monotonic() >= deadline:
                raise CameraError("USB 摄像头采集失败：未获取到画面")
            time.sleep(0.01)

    def get_stream_frame(self) -> 'np.ndarray | None':
        """
        🌟 供 UI 实时视频流（Tk / Web MJPEG）使用：返回后台线程缓存的最新帧。
        同样不直接读设备，未就绪/短暂掉线时返回 None 或上一帧，由上层平滑处理。
        """
        with self._frame_lock:
            return self._latest_frame

    def close(self) -> None:
        """显式停止抓帧线程并释放设备（由抓帧线程自行 release）。

        建议在前端退出路径（KioskSession.stop / Tk 关闭）确定性调用，避免依赖 __del__
        在解释器收尾时的不确定时机。可重复调用。
        """
        self._running = False
        thread = getattr(self, "_grab_thread", None)
        if thread is not None and thread.is_alive():
            thread.join(timeout=2.0)  # 线程退出时会在 finally 中 release
        try:
            atexit.unregister(self.close)
        except Exception:
            pass

    def __del__(self):
        """安全兜底：未显式 close 时也停止线程并释放硬件。"""
        try:
            self.close()
        except Exception:
            pass
