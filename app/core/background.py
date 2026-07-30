"""Guardarraíl para tareas en segundo plano (BackgroundTasks / hilos).

REGLA DE ORO: una tarea que corre FUERA del ciclo request-response NUNCA debe
reutilizar la sesión de BD inyectada por `get_db`. Esa sesión se cierra en el
`finally` de `get_db` en cuanto se envía la respuesta HTTP; si la tarea la usa
después, dará errores intermitentes de "session is closed" / DetachedInstanceError.

`ejecutar_en_fondo` abre una sesión NUEVA, la pasa al trabajo, hace commit si
todo sale bien, rollback + log si falla, y siempre la cierra. Así las tareas de
fondo no fallan en silencio ni arrastran estado del request.

Uso típico con FastAPI:

    from fastapi import BackgroundTasks
    from app.core.background import ejecutar_en_fondo

    @router.post("/algo")
    def endpoint(bg: BackgroundTasks, ...):
        # NO pases `db` del request; pasa datos primitivos (ids, valores).
        bg.add_task(ejecutar_en_fondo, mi_trabajo, of_id, otro_dato)
        return {"status": "encolado"}

    def mi_trabajo(db, of_id, otro_dato):
        # `db` es una sesión propia y fresca; usa of_id/otro_dato (no objetos ORM
        # del request). El commit lo hace ejecutar_en_fondo.
        ...
"""
import logging
from typing import Callable

from app.database.connection import SessionLocal

logger = logging.getLogger("background")


def ejecutar_en_fondo(trabajo: Callable, *args, **kwargs) -> None:
    """Ejecuta `trabajo(db, *args, **kwargs)` con una sesión de BD PROPIA.

    - Abre una `SessionLocal()` nueva (nunca la del request).
    - `commit()` si el trabajo termina sin excepción.
    - `rollback()` + log del traceback si falla (no se propaga: es fondo).
    - Siempre `close()`.
    """
    nombre = getattr(trabajo, "__name__", repr(trabajo))
    db = SessionLocal()
    try:
        trabajo(db, *args, **kwargs)
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Tarea en segundo plano falló: %s", nombre)
    finally:
        db.close()
