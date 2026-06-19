from fastapi import WebSocket
from typing import Dict, List
import json


class WebSocketManager:
    """
    Gestiona conexiones WebSocket activas.
    Los clientes se suscriben a canales por OF (ej: "of_826501").
    Cuando hay un avance, se broadcast al canal correspondiente.
    """

    def __init__(self):
        # canal → lista de conexiones activas
        self._connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, canal: str):
        await websocket.accept()
        self._connections.setdefault(canal, []).append(websocket)

    def disconnect(self, websocket: WebSocket, canal: str):
        if canal in self._connections:
            self._connections[canal] = [
                ws for ws in self._connections[canal] if ws != websocket
            ]

    async def broadcast(self, canal: str, mensaje: dict):
        """Envía un mensaje a todos los conectados al canal."""
        if canal not in self._connections:
            return
        dead = []
        for ws in self._connections[canal]:
            try:
                await ws.send_text(json.dumps(mensaje))
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws, canal)

    async def broadcast_of(self, of_numero: str, tipo: str, data: dict):
        """Shortcut para broadcast de eventos de una OF."""
        await self.broadcast(f"of_{of_numero}", {"tipo": tipo, "data": data})


# Instancia global
ws_manager = WebSocketManager()
