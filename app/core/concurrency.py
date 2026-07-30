"""Limitador de concurrencia para tareas pesadas (CPU-bound).

Generar PDF (xhtml2pdf), parsear Excel (openpyxl) o correr los algoritmos de
process mining son operaciones intensivas en CPU. Corren en el threadpool de
FastAPI, así que no bloquean el event loop *directamente*, pero por el GIL de
Python varias a la vez frenan a todo el proceso (y consumen hilos del pool
compartido con el resto de endpoints).

Este helper acota cuántas de esas tareas corren en paralelo. Si se supera el
cupo, se rechaza de inmediato con 429 en vez de encolar y degradar el ERP.
El tope se configura con `settings.HEAVY_MAX_CONCURRENCIA`.
"""
import threading
from contextlib import contextmanager

from fastapi import HTTPException

from app.config import settings

# Semáforo global para tareas pesadas. Uno solo, compartido: el objetivo es
# limitar la CPU total dedicada a trabajo pesado, no por-tipo.
_SLOTS = max(1, int(settings.HEAVY_MAX_CONCURRENCIA))
_heavy_sem = threading.BoundedSemaphore(_SLOTS)


@contextmanager
def limite_pesado(detalle: str = None):
    """Context manager: toma un cupo de tarea pesada o lanza HTTP 429.

    Uso:
        with limite_pesado("Generando el PDF"):
            ... trabajo CPU-bound ...
    """
    if not _heavy_sem.acquire(blocking=False):
        raise HTTPException(
            status_code=429,
            detail=(detalle or "El sistema está procesando otras tareas pesadas") +
                   ". Espera unos segundos y reintenta.",
        )
    try:
        yield
    finally:
        _heavy_sem.release()
