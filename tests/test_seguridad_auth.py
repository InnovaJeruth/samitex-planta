"""Auditoría DevSecOps · endurecimiento de auth/CSRF.
Cubre: rate limit no bypassa por X-Forwarded-For, hash señuelo anti-enumeración,
y config de expiración/TRUST_PROXY.
"""
from app.config import Settings


def _settings(**kw):
    base = dict(SECRET_KEY="x", DB_SERVER="s", DB_NAME="d", JWT_SECRET_KEY="y")
    base.update(kw)
    return Settings(**base)


def test_trust_proxy_default_false():
    assert _settings().TRUST_PROXY is False


def test_jwt_expiracion_4h_por_defecto():
    assert _settings().JWT_EXPIRE_MINUTES == 240


def test_get_ip_ignora_xff_sin_trust_proxy(monkeypatch):
    from app.routers import auth
    monkeypatch.setattr(auth.settings, "TRUST_PROXY", False, raising=False)

    class _Req:
        headers = {"x-forwarded-for": "9.9.9.9"}
        class client:  # noqa: N801
            host = "10.0.0.5"
    ip = auth._get_ip(_Req())
    assert ip == "10.0.0.5"        # usa el socket real, NO el header spoofeable


def test_get_ip_usa_xff_solo_con_trust_proxy(monkeypatch):
    from app.routers import auth
    monkeypatch.setattr(auth.settings, "TRUST_PROXY", True, raising=False)

    class _Req:
        headers = {"x-forwarded-for": "9.9.9.9, 10.0.0.1"}
        class client:  # noqa: N801
            host = "10.0.0.5"
    assert auth._get_ip(_Req()) == "9.9.9.9"


def test_hash_dummy_existe_y_es_bcrypt():
    from app.routers import auth
    from app.core.auth import verify_password
    # el señuelo es un hash válido y NO valida cualquier contraseña
    assert auth._DUMMY_HASH.startswith("$2")
    assert verify_password("no-such-user", auth._DUMMY_HASH) is True
    assert verify_password("otra", auth._DUMMY_HASH) is False


# ── RBAC a nivel de endpoint (of.py) ─────────────────────────────────────────
class _FakeUser:
    def __init__(self, rol): self.rol = rol


def test_require_bloquea_rol_no_autorizado():
    import pytest
    from fastapi import HTTPException
    from app.routers.of import _require
    from app.roles import ROLES_PLANEAMIENTO

    with pytest.raises(HTTPException) as e:
        _require(_FakeUser("CORTE"), ROLES_PLANEAMIENTO, "crear OFs")
    assert e.value.status_code == 403


def test_require_permite_rol_autorizado():
    from app.routers.of import _require
    from app.roles import ROLES_PLANEAMIENTO
    # ADMIN y PLANEADOR pasan sin excepción
    _require(_FakeUser("ADMIN"), ROLES_PLANEAMIENTO)
    _require(_FakeUser("PLANEADOR"), ROLES_PLANEAMIENTO)
