"""R1 · RAG Text-to-SQL. Config de solo lectura y dependencia get_db_ro."""
from sqlalchemy import text

from app.config import Settings


def _settings(**kw):
    base = dict(SECRET_KEY="x", DB_SERVER="srv", DB_NAME="db", JWT_SECRET_KEY="y")
    base.update(kw)
    return Settings(**base)


def test_rag_url_cae_a_principal_si_no_hay_dedicada():
    s = _settings()
    assert s.RAG_DATABASE_URL == s.DATABASE_URL


def test_rag_url_usa_login_dedicado_si_existe():
    s = _settings(RAG_DB_URL="sqlite:///ro.db")
    assert s.RAG_DATABASE_URL == "sqlite:///ro.db"


def test_rag_defaults_sensatos():
    s = _settings()
    assert s.RAG_MAX_ROWS > 0
    assert s.RAG_QUERY_TIMEOUT > 0 and s.RAG_LLM_TIMEOUT > 0
    assert s.RAG_MODEL
    assert s.RAG_INCLUIR_RESUMEN is True
    assert s.RAG_LLM_PROVIDER in ("gemini", "ollama")


def test_openapi_y_docs_ocultos_en_produccion():
    # dev: expuestos
    s = _settings(APP_ENV="development")
    assert s.DOCS_URL and s.REDOC_URL and s.OPENAPI_URL
    # producción: los tres None (sin enumeración de endpoints)
    p = _settings(APP_ENV="production")
    assert p.DOCS_URL is None and p.REDOC_URL is None and p.OPENAPI_URL is None


def test_get_db_ro_entrega_sesion(monkeypatch):
    # Apunta el engine read-only a un sqlite temporal en memoria
    import app.database.readonly as ro
    monkeypatch.setattr(ro.settings, "RAG_DB_URL", "sqlite://", raising=False)
    ro._engine_ro = None
    ro._SessionRO = None

    gen = ro.get_db_ro()
    db = next(gen)
    try:
        assert db.execute(text("SELECT 1")).scalar() == 1
    finally:
        gen.close()
    # limpia estado global para no afectar otros tests
    ro._engine_ro = None
    ro._SessionRO = None
