from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.core.websocket_manager import ws_manager

router = APIRouter()


@router.websocket("/of/{numero_of}")
async def websocket_of(websocket: WebSocket, numero_of: str):
    """Canal WebSocket por OF. Clientes suscritos reciben actualizaciones en tiempo real."""
    await ws_manager.connect(websocket, numero_of)
    try:
        while True:
            # Mantener conexión viva; los broadcasts vienen desde los endpoints REST
            data = await websocket.receive_text()
            # Eco de ping/pong para keepalive
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, numero_of)
