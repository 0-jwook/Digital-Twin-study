"""WebSocket connection registry and broadcast, per docs/protocol.md section
2. The only callers of broadcast() are OPC UA subscription callbacks and
ConnectionStateModel transitions (docs/architecture.md section 5) -- never a
REST handler, never a poll loop.
"""

from __future__ import annotations

import time

from fastapi import WebSocket

# 25Hz ceiling for `position` messages, coalesced: a notification landing
# inside this window is simply dropped rather than queued (docs/protocol.md
# section 2). The PLC's own 20Hz scan rate is comfortably below this ceiling,
# so in practice it is never the limiting factor.
POSITION_MIN_INTERVAL_SECONDS = 1 / 25


class WebSocketManager:
    def __init__(self) -> None:
        self._connections: set[WebSocket] = set()
        self._last_position_sent = 0.0

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections.add(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        self._connections.discard(websocket)

    async def send_to(self, websocket: WebSocket, message: dict) -> None:
        await websocket.send_json(message)

    async def broadcast(self, message: dict) -> None:
        if message.get("type") == "position":
            now = time.monotonic()
            if now - self._last_position_sent < POSITION_MIN_INTERVAL_SECONDS:
                return
            self._last_position_sent = now

        stale: list[WebSocket] = []
        for websocket in list(self._connections):
            try:
                await websocket.send_json(message)
            except Exception:
                stale.append(websocket)
        for websocket in stale:
            self.disconnect(websocket)
