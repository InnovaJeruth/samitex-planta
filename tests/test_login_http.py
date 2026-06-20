"""
Tests HTTP para POST /auth/login.
Cubre: credenciales inválidas, correctas, rate limiting (429).
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, configure_mappers

# ── setup idéntico al conftest ────────────────────────────────
import os
os.environ.setdefault("SECRET_KEY",           "test-secret-key-samitex-tests")
os.environ.setdefault("JWT_SECRET_KEY",       "test-jwt-secret-samitex-tests")
os.environ.setdefault("BOT_SECRET_KEY",       "test-bot-key")
os.environ.setdefault("TELEGRAM_TOKEN",       "")
os.environ.setdefault("GEMINI_API_KEY",       "")
os.environ.setdefault("NGROK_URL",            "")
os.environ.setdefault("TELEGRAM_ALLOWED_IDS", "")
os.environ.setdefault("APP_ENV",              "test")

from app.config import Settings
Settings.DATABASE_URL = property(lambda self: "sqlite:///:memory:")

import app.models.of, app.models.pieza, app.models.fase, app.models.usuario, app.models.planta
configure_mappers()

from sqlalchemy.pool import StaticPool
from app.database.connection import Base, get_db
from app.core.auth import hash_password
from app.models.usuario import Usuario, RolEnum

_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
_Session = sessionmaker(bind=_engine, autoflush=False)


@pytest.fixture()
def client():
    Base.metadata.create_all(bind=_engine)
    session = _Session()
    try:
        # Crear usuario de prueba
        user = Usuario(
            username="testuser",
            email="test@samitex.com",
            nombre="Test User",
            password_hash=hash_password("password123"),
            rol=RolEnum.ADMIN,
            activo=True,
        )
        session.add(user)
        session.commit()

        # Override de dependencia get_db
        from app.main import app
        app.dependency_overrides[get_db] = lambda: session

        # Reset rate limiter para no contaminar entre tests
        from app.routers.auth import _login_intentos
        _login_intentos.clear()

        with TestClient(app, raise_server_exceptions=False) as c:
            yield c

        app.dependency_overrides.clear()
    finally:
        session.close()
        Base.metadata.drop_all(bind=_engine)


class TestLoginCredenciales:
    def test_credenciales_correctas_devuelve_200(self, client):
        r = client.post("/auth/login", data={"username": "testuser", "password": "password123"})
        assert r.status_code == 200
        body = r.json()
        assert "access_token" in body
        assert body["username"] == "testuser"

    def test_cookie_set_en_login_exitoso(self, client):
        r = client.post("/auth/login", data={"username": "testuser", "password": "password123"})
        assert r.status_code == 200
        assert "samitex_token" in r.cookies or "access_token" in r.cookies or len(r.cookies) > 0

    def test_password_incorrecto_devuelve_401(self, client):
        r = client.post("/auth/login", data={"username": "testuser", "password": "wrongpassword"})
        assert r.status_code == 401

    def test_usuario_inexistente_devuelve_401(self, client):
        r = client.post("/auth/login", data={"username": "noexiste", "password": "cualquiera"})
        assert r.status_code == 401

    def test_password_vacio_devuelve_401(self, client):
        r = client.post("/auth/login", data={"username": "testuser", "password": ""})
        assert r.status_code == 401

    def test_response_incluye_rol_y_nombre(self, client):
        r = client.post("/auth/login", data={"username": "testuser", "password": "password123"})
        assert r.status_code == 200
        body = r.json()
        assert "rol" in body
        assert "nombre" in body


class TestLoginRateLimiting:
    def test_cinco_fallos_seguidos_bloquea_429(self, client):
        """Después de 5 intentos fallidos, el 6° debe devolver 429."""
        for _ in range(5):
            r = client.post("/auth/login", data={"username": "testuser", "password": "wrong"})
            assert r.status_code == 401

        r = client.post("/auth/login", data={"username": "testuser", "password": "wrong"})
        assert r.status_code == 429

    def test_mensaje_429_incluye_tiempo_espera(self, client):
        for _ in range(5):
            client.post("/auth/login", data={"username": "testuser", "password": "wrong"})

        r = client.post("/auth/login", data={"username": "testuser", "password": "wrong"})
        assert r.status_code == 429
        assert "min" in r.json()["detail"].lower()

    def test_login_exitoso_resetea_contador(self, client):
        """4 fallos + 1 éxito → el contador se resetea → no hay bloqueo."""
        for _ in range(4):
            client.post("/auth/login", data={"username": "testuser", "password": "wrong"})

        r = client.post("/auth/login", data={"username": "testuser", "password": "password123"})
        assert r.status_code == 200

        # Ahora podemos fallar de nuevo sin estar bloqueados
        r2 = client.post("/auth/login", data={"username": "testuser", "password": "wrong"})
        assert r2.status_code == 401  # 401, no 429
