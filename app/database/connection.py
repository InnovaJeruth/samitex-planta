from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from app.config import settings

_url = settings.DATABASE_URL

# SQLite (tests) no soporta pool_size ni max_overflow
# Capacidad del pool (20+30 = 50) > threadpool de FastAPI (40 hilos) → ningún
# request sync se queda esperando una conexión bajo concurrencia máxima.
_pool_kwargs = (
    {}
    if _url.startswith("sqlite")
    else {
        "pool_pre_ping": True,   # descarta conexiones muertas
        "pool_size": 20,
        "max_overflow": 30,
        "pool_timeout": 10,      # falla rápido en vez de colgar 30 s si el pool se agota
        "pool_recycle": 1800,    # recicla conexiones cada 30 min (evita cortes del server)
    }
)

engine = create_engine(_url, echo=settings.DEBUG, **_pool_kwargs)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    """Dependency para inyectar sesión de BD en cada request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
