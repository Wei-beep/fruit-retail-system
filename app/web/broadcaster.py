"""线程安全的 WebSocket 广播器。

业务回调在 GUIController 后台线程触发，需经事件循环把消息发给所有前端连接。
publish() 可在任意线程调用，通过 loop.call_soon_threadsafe 切回事件循环发送。
"""
from __future__ import annotations

import asyncio
import json
from typing import Any

from fastapi import WebSocket


class Broadcaster:
    def __init__(self) -> None:
        self._connections: set[WebSocket] = set()
        self._loop: asyncio.AbstractEventLoop | None = None
        # 最近一次"状态类"事件（非 weight），新连接补发，避免刷新后白屏
        self._last_state: dict[str, Any] | None = None

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    async def register(self, websocket: WebSocket) -> None:
        self._connections.add(websocket)
        if self._last_state is not None:
            await websocket.send_text(json.dumps(self._last_state, ensure_ascii=False))

    def unregister(self, websocket: WebSocket) -> None:
        self._connections.discard(websocket)

    def publish(self, message: dict[str, Any]) -> None:
        """任意线程调用：把消息排进事件循环异步广播。"""
        if message.get("type") != "weight":
            self._last_state = message
        loop = self._loop
        if loop is None or loop.is_closed():
            return
        try:
            loop.call_soon_threadsafe(self._schedule_send, message)
        except RuntimeError:
            # 关停过程中后台 daemon 线程可能仍在收尾，循环已关闭则静默跳过
            pass

    def _schedule_send(self, message: dict[str, Any]) -> None:
        asyncio.create_task(self._broadcast(message))

    async def _broadcast(self, message: dict[str, Any]) -> None:
        if not self._connections:
            return
        text = json.dumps(message, ensure_ascii=False)
        dead: list[WebSocket] = []
        for websocket in list(self._connections):
            try:
                await websocket.send_text(text)
            except Exception:
                dead.append(websocket)
        for websocket in dead:
            self._connections.discard(websocket)
