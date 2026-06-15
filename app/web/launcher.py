"""Web 前端启动器：进程内起 uvicorn + 拉起 Chromium kiosk。

单进程内运行 uvicorn（守护线程）→ 探活 → 用 Chromium kiosk 全屏打开本地页面，
阻塞等待浏览器退出后收尾。HX711/摄像头由 Web 应用在本进程内创建一次（单属主）。
"""
from __future__ import annotations

import shutil
import subprocess
import threading
import time
import urllib.request

import uvicorn

from app.core.config import load_config
from app.core.display import configure_gui_display
from app.db.init_db import initialize_database
from app.web.lifecycle import shutdown_event


def _wait_until_ready(url: str, timeout: float = 30.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1) as response:
                if response.status == 200:
                    return True
        except Exception:
            pass
        time.sleep(0.3)
    return False


def _find_browser() -> str | None:
    for name in ("chromium-browser", "chromium"):
        path = shutil.which(name)
        if path:
            return path
    return None


def _idle_until_interrupt(thread: threading.Thread, server: uvicorn.Server, hint: str) -> None:
    print(hint)
    try:
        while thread.is_alive() and not shutdown_event.is_set():
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    server.should_exit = True


def run_web() -> None:
    initialize_database()
    config = load_config()
    gui = config["gui"]
    configure_gui_display(gui)
    shutdown_event.clear()

    host = "127.0.0.1"
    port = int(gui.get("web_port", 8000))
    base_url = f"http://{host}:{port}"

    server = uvicorn.Server(
        uvicorn.Config(
            "app.web.server:create_web_app",
            host=host,
            port=port,
            factory=True,
            log_level="info",
        )
    )
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    if not _wait_until_ready(f"{base_url}/healthz"):
        print("❌ Web 服务启动超时")
        server.should_exit = True
        return
    print(f"✅ Web kiosk 服务已就绪: {base_url}")

    if not gui.get("launch_browser", True):
        _idle_until_interrupt(thread, server, "ℹ️  launch_browser=false，仅运行服务。Ctrl+C 退出。")
        return

    browser = _find_browser()
    if browser is None:
        _idle_until_interrupt(
            thread, server, "⚠️ 未找到 chromium-browser/chromium，仅运行服务，请手动打开浏览器。"
        )
        return

    args = [
        browser,
        "--kiosk",
        "--noerrdialogs",
        "--disable-infobars",
        "--disable-translate",
        "--disable-session-crashed-bubble",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-background-networking",  # 关闭 GCM/推送等后台联网噪音
        "--disable-component-update",
        "--check-for-update-interval=31536000",
        "--autoplay-policy=no-user-gesture-required",
        # 冷启动时不去解锁 GNOME 登录密钥环（kiosk 无需存网站密码），避免弹密码框
        "--password-store=basic",
        "--user-data-dir=/tmp/fruit-kiosk-chromium",
        f"--app={base_url}",
    ]
    print(f"🚀 启动 Chromium kiosk: {browser}")
    # 屏蔽 Chromium 自身的内部日志（GCM/GPU 等噪音），不影响 python/uvicorn 日志
    proc = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        # 等待 Chromium 退出，或前端点击"退出"置位关停信号
        while proc.poll() is None:
            if shutdown_event.wait(timeout=0.3):
                break
    except KeyboardInterrupt:
        pass
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except Exception:
                proc.kill()
        server.should_exit = True
