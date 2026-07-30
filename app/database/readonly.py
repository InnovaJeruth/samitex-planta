"""Conexión de SOLO LECTURA para el chat analítico (RAG Text-to-SQL).

Engine y sesión separados del transaccional. Idealmente apuntan a un login
`db_datareader` dedicado (settings.RAG_DB_URL); si no está configurado, caen a
DATABASE_URL y la garantía de solo-lectura queda a nivel de aplicación (guardas
de R3). La sesión nunca hace commit: se hace rollback al cerrar.

Init perezoso: importar este módulo NO abre conexión (útil en tests y arranque).
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import settings

_engine_ro = None
_SessionRO = None


def _init():
    global _engine_ro, _SessionRO
    if _SessionRO is not None:
        return
    url = settings.RAG_DATABASE_URL
    pool_kwargs = (
        {}
        if url.startswith("sqlite")
        else {"pool_pre_ping": True, "pool_size": 5, "max_overflow": 10}
    )
    _engine_ro = create_engine(url, echo=False, **pool_kwargs)
    _SessionRO = sessionmaker(autocommit=False, autoflush=False, bind=_engine_ro)


def get_engine_ro():
    """Engine de solo lectura (perezoso)."""
    _init()
    return _engine_ro


def get_db_ro():
    """Dependencia FastAPI: sesión de solo lectura. Rollback + close al terminar.
    NO usar para escribir; es exclusiva del chat analítico."""
    _init()
    db = _SessionRO()
    try:
        yield db
    finally:
        db.rollback()
        db.close()
