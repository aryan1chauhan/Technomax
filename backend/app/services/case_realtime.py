from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import DefaultDict

from fastapi import WebSocket


class CaseRealtimeManager:
    def __init__(self) -> None:
        self._case_connections: DefaultDict[int, set[WebSocket]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def connect(self, case_id: int, websocket: WebSocket) -> None:
        async with self._lock:
            self._case_connections[case_id].add(websocket)

    async def disconnect(self, case_id: int, websocket: WebSocket) -> None:
        async with self._lock:
            listeners = self._case_connections.get(case_id)
            if not listeners:
                return
            listeners.discard(websocket)
            if not listeners:
                self._case_connections.pop(case_id, None)

    async def broadcast(self, case_id: int, payload: dict, *, exclude: WebSocket | None = None) -> None:
        async with self._lock:
            listeners = list(self._case_connections.get(case_id, set()))

        stale: list[WebSocket] = []
        for websocket in listeners:
            if exclude is not None and websocket is exclude:
                continue
            try:
                await websocket.send_json(payload)
            except Exception:
                stale.append(websocket)

        for websocket in stale:
            await self.disconnect(case_id, websocket)


case_realtime_manager = CaseRealtimeManager()
