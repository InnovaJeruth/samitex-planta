"""Fase B · Guardarraíl de tareas en segundo plano (sesión propia + logging)."""
import logging

from app.core import background as bg


class _FakeSession:
    def __init__(self):
        self.commits = 0
        self.rollbacks = 0
        self.closed = False

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        self.closed = True


def test_abre_sesion_propia_y_commit(monkeypatch):
    """El trabajo recibe una sesión NUEVA (no la del request); commit + close."""
    inst = _FakeSession()
    monkeypatch.setattr(bg, "SessionLocal", lambda: inst)
    visto = {}

    def trabajo(db, of_id):
        visto["db"] = db
        visto["of_id"] = of_id

    bg.ejecutar_en_fondo(trabajo, 42)

    assert visto["db"] is inst          # sesión propia inyectada
    assert visto["of_id"] == 42
    assert inst.commits == 1
    assert inst.rollbacks == 0
    assert inst.closed is True


def test_rollback_y_log_ante_error(monkeypatch, caplog):
    """Si el trabajo falla: rollback, log del traceback, close, y NO propaga."""
    inst = _FakeSession()
    monkeypatch.setattr(bg, "SessionLocal", lambda: inst)

    def trabajo(db):
        raise ValueError("boom")

    with caplog.at_level(logging.ERROR, logger="background"):
        bg.ejecutar_en_fondo(trabajo)   # no debe lanzar

    assert inst.commits == 0
    assert inst.rollbacks == 1
    assert inst.closed is True
    assert any("segundo plano falló" in r.getMessage() for r in caplog.records)
