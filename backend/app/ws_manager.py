import json
from typing import Dict, List, Optional
from uuid import UUID

from fastapi import WebSocket


class ConnectionManager:
    def __init__(self) -> None:
        self.connections: Dict[UUID, List[WebSocket]] = {}

    async def connect(self, session_id: UUID, websocket: WebSocket) -> None:
        await websocket.accept()
        self.connections.setdefault(session_id, []).append(websocket)

    def remove(self, session_id: UUID, websocket: WebSocket) -> None:
        if session_id in self.connections:
            self.connections[session_id] = [ws for ws in self.connections[session_id] if ws != websocket]
            if not self.connections[session_id]:
                self.connections.pop(session_id, None)

    async def broadcast(self, session_id: UUID, message: dict, exclude: Optional[WebSocket] = None) -> None:
        data = json.dumps(message)
        for ws in list(self.connections.get(session_id, [])):
            if ws is exclude:
                continue
            try:
                await ws.send_text(data)
            except Exception:
                # Drop dead connections quietly
                self.remove(session_id, ws)

    async def send(self, websocket: WebSocket, message: dict) -> None:
        await websocket.send_text(json.dumps(message))


manager = ConnectionManager()
