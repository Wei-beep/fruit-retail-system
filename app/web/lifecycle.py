"""进程级关停信号。

前端点击"退出"后，Web 应用置位此事件；launcher 监听到后终止 Chromium 并退出，
从而结束整个 kiosk 任务。模块级单例，launcher 与 server 共享同一个事件对象。
"""
from __future__ import annotations

import threading

shutdown_event = threading.Event()


def request_shutdown() -> None:
    shutdown_event.set()
