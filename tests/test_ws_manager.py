"""Fase A · Observabilidad de la notificación WS (fire-and-forget).

Verifica que los fallos del broadcast diferido se loguean (no se descartan) y
que notify_of es no-op seguro cuando no hay loop o no hay suscriptores.
"""
import asyncio
import logging
from concurrent.futures import Future

from app.core.websocket_manager import WebSocketManager


def test_log_future_error_loguea_excepcion(caplog):
    """Si el broadcast falla en segundo plano, su excepción se loguea."""
    fut = Future()
    fut.set_exception(ValueError("boom"))
    with caplog.at_level(logging.WARNING, logger="ws_manager"):
        WebSocketManager._log_future_error(fut)
    assert any("Broadcast WS" in r.getMessage() for r in caplog.records)


def test_log_future_error_no_loguea_si_ok(caplog):
    """Si el broadcast terminó bien, no se loguea nada."""
    fut = Future()
    fut.set_result(None)
    with caplog.at_level(logging.WARNING, logger="ws_manager"):
        WebSocketManager._log_future_error(fut)
    assert not caplog.records


def test_notify_of_sin_loop_es_noop():
    """Sin loop capturado, notify_of no lanza (no rompe el request)."""
    m = WebSocketManager()            # _loop = None
    m.notify_of("123", "avance", {"x": 1})   # no debe lanzar


def test_notify_of_sin_suscriptores_es_noop():
    """Con loop pero sin nadie suscrito al canal, es no-op de costo cero."""
    m = WebSocketManager()
    loop = asyncio.new_event_loop()
    try:
        m.set_loop(loop)
        m.notify_of("999", "avance", {})     # canal sin conexiones → no-op
    finally:
        loop.close()
