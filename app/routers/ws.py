from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.websocket_manager import ws_manager

router = APIRouter()


@router.websocket("/of/{of_numero}")
async def websocket_of(websocket: WebSocket, of_numero: str):
    canal = f"of_{of_numero}"
    await ws_manager.connect(websocket, canal)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, canal)
