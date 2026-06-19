from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from app.config import settings

_url = settings.DATABASE_URL

# SQLite (tests) no soporta pool_size ni max_overflow
_pool_kwargs = (
    {}
    if _url.startswith("sqlite")
    else {"pool_pre_ping": True, "pool_size": 10, "max_overflow": 20}
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
