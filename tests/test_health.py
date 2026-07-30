"""Infra · Fase 1: endpoint /health (liveness) público y sin auth."""
import os

os.environ.setdefault("SECRET_KEY",     "test-secret-key-samitex-tests")
os.environ.setdefault("JWT_SECRET_KEY", "test-jwt-secret-samitex-tests")
os.environ.setdefault("BOT_SECRET_KEY", "test-bot-key")
os.environ.setdefault("GEMINI_API_KEY", "")
os.environ.setdefault("APP_ENV",        "test")

from app.config import Settings
Settings.DATABASE_URL = property(lambda self: "sqlite:///:memory:")

from fastapi.testclient import TestClient
from app.main import app

_client = TestClient(app, raise_server_exceptions=False)


def test_health_responde_200_sin_auth():
    r = _client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["db"] in ("up", "down")   # nunca falla aunque la BD no responda


def test_health_es_get_publico():
    # No debe redirigir a login ni pedir credenciales
    r = _client.get("/health")
    assert r.status_code == 200
    assert "location" not in {k.lower() for k in r.headers}
