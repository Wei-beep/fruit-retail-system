"""GUI 性能监控工具（FPS、CPU、内存），由 config.yaml 的 gui.monitor_performance 控制开关。"""
from __future__ import annotations

import threading
import time


class PerformanceMonitor:
    """每 interval_seconds 秒向终端打印一次渲染帧率和资源占用。

    依赖 psutil，缺失时静默跳过不做任何输出。
    """

    def __init__(self, interval_seconds: float = 2.0) -> None:
        self._interval = interval_seconds
        self._thread: threading.Thread | None = None
        self._running = False

        # 外部持有的计数器引用，由 MainWindow.start_video_stream 驱动
        self._frame_count = 0
        self._last_time = time.time()

        # 延迟导入 psutil，缺失时不启动监控
        self._psutil = None
        self._process = None
        try:
            import psutil
            import os
            self._psutil = psutil
            self._process = psutil.Process(os.getpid())
        except ImportError:
            pass

    def tick(self) -> None:
        """每渲染一帧调用一次，增加帧计数。"""
        self._frame_count += 1

    def start(self) -> None:
        """启动后台监控线程。若 psutil 不可用则静默跳过。"""
        if self._psutil is None:
            return
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False

    def _loop(self) -> None:
        # 预热 CPU 百分比计算
        self._process.cpu_percent()
        self._psutil.cpu_percent()

        while self._running:
            time.sleep(self._interval)

            now = time.time()
            elapsed = now - self._last_time

            fps = self._frame_count / elapsed if elapsed > 0 else 0.0
            app_cpu = self._process.cpu_percent()
            sys_cpu = self._psutil.cpu_percent()
            mem_mb = self._process.memory_info().rss / (1024 * 1024)

            print(
                f"🖥️ [性能监控] 渲染 FPS: {fps:.1f} | "
                f"App CPU: {app_cpu:.1f}% (系统总计: {sys_cpu}%) | "
                f"占用内存: {mem_mb:.1f} MB"
            )

            self._frame_count = 0
            self._last_time = now
