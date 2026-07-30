"""Infra · Fase 4: ALLOWED_HOSTS + TrustedHostMiddleware (anti Host injection)."""
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.config import Settings


def _settings(**kw):
    base = dict(SECRET_KEY="x", DB_SERVER="s", DB_NAME="d", JWT_SECRET_KEY="y")
    base.update(kw)
    return Settings(**base)


def test_allowed_hosts_wildcard_por_defecto():
    assert _settings().ALLOWED_HOSTS_LIST == ["*"]


def test_allowed_hosts_csv_se_parsea():
    s = _settings(ALLOWED_HOSTS="erp.samitex.local, 10.0.0.5 ")
    assert s.ALLOWED_HOSTS_LIST == ["erp.samitex.local", "10.0.0.5"]


def _app(hosts):
    app = FastAPI()
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=hosts)

    @app.get("/x")
    def x():
        return {"ok": True}
    return TestClient(app)


def test_host_permitido_pasa():
    c = _app(["erp.samitex.local"])
    r = c.get("/x", headers={"host": "erp.samitex.local"})
    assert r.status_code == 200


def test_host_no_permitido_rechazado():
    c = _app(["erp.samitex.local"])
    r = c.get("/x", headers={"host": "evil.com"})
    assert r.status_code == 400   # Invalid host header
