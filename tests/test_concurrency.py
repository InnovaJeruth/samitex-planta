"""Fase 3A · Limitador de concurrencia de tareas pesadas (CPU-bound)."""
import threading

import pytest
from fastapi import HTTPException

from app.core import concurrency as c


def test_limite_pesado_libera_al_salir(monkeypatch):
    """Tras usar el context manager, el cupo vuelve a estar disponible."""
    sem = threading.BoundedSemaphore(1)
    monkeypatch.setattr(c, "_heavy_sem", sem)
    with c.limite_pesado("tarea"):
        assert sem.acquire(blocking=False) is False   # ocupado dentro del bloque
    assert sem.acquire(blocking=False) is True         # liberado al salir
    sem.release()


def test_limite_pesado_rechaza_sin_cupo_con_429(monkeypatch):
    """Si no hay cupo, lanza HTTP 429 (no encola)."""
    sem = threading.BoundedSemaphore(1)
    sem.acquire()                                      # agota el único slot
    monkeypatch.setattr(c, "_heavy_sem", sem)
    with pytest.raises(HTTPException) as ei:
        with c.limite_pesado("PDF"):
            pass
    assert ei.value.status_code == 429
    sem.release()


def test_limite_pesado_libera_ante_excepcion(monkeypatch):
    """Aunque el trabajo falle, el cupo se libera (no queda tomado)."""
    sem = threading.BoundedSemaphore(1)
    monkeypatch.setattr(c, "_heavy_sem", sem)
    with pytest.raises(ValueError):
        with c.limite_pesado("tarea"):
            raise ValueError("boom")
    assert sem.acquire(blocking=False) is True
    sem.release()
