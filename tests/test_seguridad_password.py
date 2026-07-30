"""Auditoría DevSecOps · política de contraseñas en gestión de usuarios (admin)."""
import pytest
from pydantic import ValidationError


def test_password_corta_se_rechaza():
    from app.routers.admin import UsuarioCreate
    with pytest.raises(ValidationError):
        UsuarioCreate(nombre="A", username="a", email="a@a.com", password="abc12", rol="ADMIN")


def test_password_sin_numero_se_rechaza():
    from app.routers.admin import CambiarPasswordBody
    with pytest.raises(ValidationError):
        CambiarPasswordBody(password="sololetras")


def test_password_sin_letra_se_rechaza():
    from app.routers.admin import CambiarPasswordBody
    with pytest.raises(ValidationError):
        CambiarPasswordBody(password="12345678")


def test_password_valida_pasa():
    from app.routers.admin import CambiarPasswordBody
    assert CambiarPasswordBody(password="Samitex2026").password == "Samitex2026"
