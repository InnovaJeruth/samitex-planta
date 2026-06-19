import os

os.environ["SECRET_KEY"]           = "test-secret-key-samitex-tests"
os.environ["JWT_SECRET_KEY"]       = "test-jwt-secret-samitex-tests"
os.environ["DB_SERVER"]            = "localhost"
os.environ["DB_NAME"]              = "testdb"
os.environ["APP_ENV"]              = "test"
os.environ["TELEGRAM_TOKEN"]       = ""
os.environ["GEMINI_API_KEY"]       = ""
os.environ["NGROK_URL"]            = ""
os.environ["TELEGRAM_ALLOWED_IDS"] = ""
os.environ["BOT_SECRET_KEY"]       = ""

# Patch DATABASE_URL BEFORE connection.py is imported
from app.config import Settings
Settings.DATABASE_URL = property(lambda self: "sqlite:///:memory:")

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, configure_mappers
from app.database.connection import Base

# Register all models so SQLAlchemy knows all relationships
import app.models.of
import app.models.pieza
import app.models.fase
import app.models.usuario
import app.models.planta

# Pre-configure all mappers so tests that don't use 'db' fixture can
# instantiate model objects without triggering mapper init errors
configure_mappers()

_engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
_SessionLocal = sessionmaker(bind=_engine, autoflush=False)


@pytest.fixture()
def db():
    Base.metadata.create_all(bind=_engine)
    session = _SessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=_engine)
