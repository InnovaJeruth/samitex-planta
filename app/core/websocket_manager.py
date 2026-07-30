from fastapi import WebSocket
from typing import Dict, List, Optional
import asyncio
import json
import logging

logger = logging.getLogger("ws_manager")


class WebSocketManager:
    """
    Gestiona conexiones WebSocket activas.
    Los clientes se suscriben a canales por OF (ej: "of_826501").
    Cuando hay un avance, se broadcast al canal correspondiente.
    """

    def __init__(self):
        # canal → lista de conexiones activas
        self._connections: Dict[str, List[WebSocket]] = {}
        # loop principal de asyncio (capturado al arrancar) para poder
        # emitir desde endpoints síncronos que corren en threadpool.
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def set_loop(self, loop: asyncio.AbstractEventLoop):
        self._loop = loop

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
            except Exception as e:
                logger.debug("WS envío fallido en %s (se descarta conexión): %s", canal, e)
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws, canal)

    async def broadcast_of(self, of_numero: str, tipo: str, data: dict):
        """Shortcut para broadcast de eventos de una OF."""
        await self.broadcast(f"of_{of_numero}", {"tipo": tipo, "data": data})

    def notify_of(self, of_numero: str, tipo: str, data: Optional[dict] = None):
        """Versión sync-friendly: agenda el broadcast en el loop principal.
        Pensada para llamarse desde endpoints síncronos. No-op si no hay loop
        listo o si nadie está suscrito al canal (cero costo)."""
        if self._loop is None:
            return
        canal = f"of_{of_numero}"
        if canal not in self._connections or not self._connections[canal]:
            return
        try:
            fut = asyncio.run_coroutine_threadsafe(
                self.broadcast_of(str(of_numero), tipo, data or {}),
                self._loop,
            )
            # No descartar la excepción del broadcast: si la corrutina falla,
            # su error queda en el Future; lo logueamos vía callback.
            fut.add_done_callback(self._log_future_error)
        except Exception as e:
            # Nunca romper la petición por un fallo al AGENDAR la notificación
            logger.warning("No se pudo agendar notificación WS (%s/%s): %s", of_numero, tipo, e)

    @staticmethod
    def _log_future_error(fut: "asyncio.Future"):
        try:
            fut.result()
        except Exception as e:  # error ocurrido dentro del broadcast
            logger.warning("Broadcast WS falló en segundo plano: %s", e)


# Instancia global
ws_manager = WebSocketManager()
