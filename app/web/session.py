"""Web kiosk 运行期会话。

组装业务流程(create_transaction_flow)+ 回调式 GUIController，把控制器事件
推给 Broadcaster；并维护一个单生产者取帧线程，把最新帧编码为 JPEG 供 MJPEG 流消费。
单进程内只此一处持有摄像头/HX711，避免并发位操作。
"""
from __future__ import annotations

import threading
import time

import cv2

from app.gui.gui_controller import GUIController
from app.web.broadcaster import Broadcaster
from app.workflow.factory import create_transaction_flow


class KioskSession:
    def __init__(self, config: dict, broadcaster: Broadcaster) -> None:
        self.config = config
        self.broadcaster = broadcaster
        self.flow = create_transaction_flow(config)
        self.camera = self.flow.camera
        self.controller = GUIController(
            transaction_flow=self.flow,
            on_status=lambda text: broadcaster.publish({"type": "status", "text": text}),
            on_transaction_ready=self._on_ready,
            on_error=lambda text: broadcaster.publish({"type": "error", "text": text}),
            on_cleared=lambda: broadcaster.publish({"type": "cleared"}),
            on_reading=self._on_reading,
            include_candidates=True,
            auto_restart_after_confirm=False,
        )
        self._latest_jpeg: bytes | None = None
        self._frame_lock = threading.Lock()
        self._grab_thread: threading.Thread | None = None
        self._running = False
        self._recognizing_sent = False

    # ------------------------------------------------------------------
    # 业务回调 → 广播
    # ------------------------------------------------------------------
    def _on_reading(self, weight_kg: float, is_stable: bool) -> None:
        self.broadcaster.publish(
            {"type": "weight", "weight_g": int(weight_kg * 1000), "stable": bool(is_stable)}
        )
        # 稳定达成瞬间预告"识别中"（capture + 推理即将开始）
        if is_stable and not self._recognizing_sent:
            self._recognizing_sent = True
            self.broadcaster.publish({"type": "recognizing"})

    def _on_ready(self, transaction: dict) -> None:
        self._recognizing_sent = False
        self.broadcaster.publish({"type": "transaction_ready", "data": transaction})

    # ------------------------------------------------------------------
    # 客户端指令
    # ------------------------------------------------------------------
    def confirm(self) -> None:
        data = dict(self.controller.current_transaction or {})
        transaction_id = self.controller.confirm_current()
        if transaction_id is not None:
            self.broadcaster.publish(
                {"type": "confirmed", "transaction_id": transaction_id, "data": data}
            )

    def clear(self) -> None:
        self.controller.clear_current()

    def select(self, label: str) -> None:
        self.controller.select_label(label)

    # ------------------------------------------------------------------
    # MJPEG 单生产者取帧线程
    # ------------------------------------------------------------------
    def _grab_loop(self) -> None:
        while self._running:
            frame = None
            try:
                frame = self.camera.get_stream_frame()
            except Exception:
                frame = None
            if frame is not None:
                ok, buffer = cv2.imencode(".jpg", frame)
                if ok:
                    with self._frame_lock:
                        self._latest_jpeg = buffer.tobytes()
            time.sleep(0.03)  # ~30 FPS

    def latest_jpeg(self) -> bytes | None:
        with self._frame_lock:
            return self._latest_jpeg

    # ------------------------------------------------------------------
    # 生命周期
    # ------------------------------------------------------------------
    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._grab_thread = threading.Thread(target=self._grab_loop, daemon=True)
        self._grab_thread.start()
        self.controller.start_waiting()

    def stop(self) -> None:
        self._running = False
        self.controller.stop()
