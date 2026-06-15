"""Chromium kiosk Web 前端的 FastAPI 应用。

与 app/api（对外 REST 契约）职责分离：此应用专为本地 kiosk UI 服务，
提供静态页托管、实时状态 WebSocket、MJPEG 视频流和品类列表接口。

用 uvicorn 工厂模式启动（factory=True），避免 import 期触发硬件初始化：
    uvicorn app.web.server:create_web_app --factory
"""
from __future__ import annotations

import asyncio
import json
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from app.core.config import load_config
from app.db.init_db import initialize_database
from app.pricing.price_service import PriceService
from app.web.broadcaster import Broadcaster
from app.web.lifecycle import request_shutdown
from app.web.session import KioskSession

STATIC_DIR = Path(__file__).parent / "static"


def create_web_app(config: dict | None = None) -> FastAPI:
    initialize_database()
    config = config if config is not None else load_config()

    broadcaster = Broadcaster()
    session = KioskSession(config, broadcaster)
    price_service = PriceService()

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        broadcaster.bind_loop(asyncio.get_running_loop())
        session.start()
        try:
            yield
        finally:
            session.stop()

    app = FastAPI(title="Fruit Retail Kiosk", lifespan=lifespan)

    @app.middleware("http")
    async def _no_cache_ui(request: Request, call_next):
        """单机本地 kiosk：UI 资源禁用浏览器缓存，确保改版/冷启动后总是加载最新前端。
        否则 Chromium（--user-data-dir 持久）会用磁盘缓存里的旧 index.html/app.js，
        导致「改了页面看不到」。仅作用于首页与 /static，不影响 /stream/video、/ws。"""
        response = await call_next(request)
        path = request.url.path
        if path == "/" or path.startswith("/static"):
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        return response

    @app.get("/healthz")
    def healthz() -> dict:
        return {"status": "ok"}

    @app.get("/api/ui/products")
    def products() -> list[dict]:
        return price_service.list_products()

    @app.post("/api/exit")
    def exit_app() -> dict:
        """前端确认退出：置位关停信号，由 launcher 终止 Chromium 并结束进程。"""
        request_shutdown()
        return {"status": "exiting"}

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    @app.get("/stream/video")
    def video() -> StreamingResponse:
        boundary = "frame"

        def generate():
            while True:
                jpeg = session.latest_jpeg()
                if jpeg is not None:
                    yield (
                        b"--"
                        + boundary.encode()
                        + b"\r\nContent-Type: image/jpeg\r\nContent-Length: "
                        + str(len(jpeg)).encode()
                        + b"\r\n\r\n"
                        + jpeg
                        + b"\r\n"
                    )
                time.sleep(0.05)

        return StreamingResponse(
            generate(), media_type=f"multipart/x-mixed-replace; boundary={boundary}"
        )

    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket) -> None:
        await websocket.accept()
        await broadcaster.register(websocket)
        try:
            while True:
                raw = await websocket.receive_text()
                try:
                    message = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                kind = message.get("type")
                if kind == "confirm":
                    session.confirm()
                elif kind == "clear":
                    session.clear()
                elif kind == "select":
                    label = message.get("label")
                    if label:
                        session.select(label)
        except WebSocketDisconnect:
            pass
        finally:
            broadcaster.unregister(websocket)

    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
    return app
