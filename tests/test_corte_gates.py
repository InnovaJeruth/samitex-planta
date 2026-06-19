"""
Tests para la lógica de gates y cascada en app/services/corte_service.py.

Usan SQLite en memoria (fixture `db` de conftest.py).
"""
import pytest
from datetime import date
from fastapi import HTTPException

from app.models.of import OrdenFabricacion, EstadoOF, TipoPrendaEnum, TipoClienteEnum, EstadoDocsEnum
from app.models.pieza import OFPieza
from app.models.fase import OFFaseEstado
from app.services.corte_service import (
    _orden_fases_activo,
    _fase_anterior,
    _fase_anterior_pieza,
    registrar_avance,
)
from app.constants import ORDEN_FASES


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_of(db, estampado_activo: bool = False, estado=EstadoOF.ACTIVA) -> OrdenFabricacion:
    of = OrdenFabricacion(
        numero_of=f"OF-TEST-{id(db)}",
        cliente="Cliente Test",
        tipo_prenda=TipoPrendaEnum.SACO,
        total_juegos=10,
        fecha_creacion=date.today(),
        estado=estado,
        tipo_cliente=TipoClienteEnum.MARCA,
        estado_docs=EstadoDocsEnum.COMPLETA,
        estampado_activo=estampado_activo,
    )
    db.add(of)
    db.flush()
    return of


def _make_pieza(db, of: OrdenFabricacion, nombre: str, fusionado: bool = False) -> OFPieza:
    pieza = OFPieza(
        of_id=of.id,
        nombre=nombre,
        material="TELA",
        cantidad_x_prenda=1,
        fusionado=fusionado,
    )
    db.add(pieza)
    db.flush()
    return pieza


def _make_fase_estado(
    db, of: OrdenFabricacion, pieza: OFPieza, fase_id: str,
    cantidad_actual: int = 0, max_cantidad: int = 10, completada: bool = False,
) -> OFFaseEstado:
    fe = OFFaseEstado(
        of_id=of.id,
        pieza_id=pieza.id,
        fase_id=fase_id,
        cantidad_actual=cantidad_actual,
        max_cantidad=max_cantidad,
        completada=completada,
    )
    db.add(fe)
    db.flush()
    return fe


# ── Tests: _orden_fases_activo ────────────────────────────────────────────────

class TestOrdenFasesActivo:
    def test_sin_estampado_excluye_f8_f9(self):
        of = OrdenFabricacion(estampado_activo=False)
        orden = _orden_fases_activo(of)
        assert "F8" not in orden
        assert "F9" not in orden

    def test_con_estampado_incluye_f8_f9(self):
        of = OrdenFabricacion(estampado_activo=True)
        orden = _orden_fases_activo(of)
        assert "F8" in orden
        assert "F9" in orden

    def test_orden_base_sin_estampado(self):
        of = OrdenFabricacion(estampado_activo=False)
        assert _orden_fases_activo(of) == ["F1", "F2", "F3", "F4", "F5", "F6", "F7"]

    def test_orden_completo_con_estampado(self):
        of = OrdenFabricacion(estampado_activo=True)
        assert _orden_fases_activo(of) == ORDEN_FASES


# ── Tests: _fase_anterior ─────────────────────────────────────────────────────

class TestFaseAnterior:
    def setup_method(self):
        self.of = OrdenFabricacion(estampado_activo=False)

    def test_primera_fase_no_tiene_anterior(self):
        assert _fase_anterior("F1", self.of) is None

    def test_f2_anterior_es_f1(self):
        assert _fase_anterior("F2", self.of) == "F1"

    def test_f5_anterior_es_f4_sin_estampado(self):
        # Sin estampado: F4 → F5
        assert _fase_anterior("F5", self.of) == "F4"

    def test_f6_anterior_es_f5(self):
        assert _fase_anterior("F6", self.of) == "F5"

    def test_f7_anterior_es_f6(self):
        assert _fase_anterior("F7", self.of) == "F6"

    def test_fase_desconocida_retorna_none(self):
        assert _fase_anterior("F99", self.of) is None


# ── Tests: _fase_anterior_pieza ───────────────────────────────────────────────

class TestFaseAnteriorPieza:
    def setup_method(self):
        self.of = OrdenFabricacion(estampado_activo=False)

    def test_pieza_no_fusionable_f6_anterior_es_f4(self, db):
        """Una pieza sin fusionado salta F5 → F6 viene después de F4."""
        pieza = OFPieza(fusionado=False)
        result = _fase_anterior_pieza("F6", self.of, pieza, db)
        assert result == "F4"

    def test_pieza_fusionable_f6_anterior_es_f5(self, db):
        """Una pieza con fusionado: F6 viene después de F5."""
        pieza = OFPieza(fusionado=True)
        result = _fase_anterior_pieza("F6", self.of, pieza, db)
        assert result == "F5"

    def test_primera_fase_no_tiene_anterior(self, db):
        pieza = OFPieza(fusionado=False)
        assert _fase_anterior_pieza("F1", self.of, pieza, db) is None

    def test_pieza_no_fusionable_f5_no_existe_en_orden(self, db):
        """Para pieza sin fusionado, F5 no está en su orden → retorna None."""
        pieza = OFPieza(fusionado=False)
        # F5 no está en orden_pieza para pieza sin fusionado
        result = _fase_anterior_pieza("F5", self.of, pieza, db)
        # F5 no aplica a esta pieza → retorna None (idx=-1)
        assert result is None


# ── Tests: Gate Fusionado → Calidad ──────────────────────────────────────────

class TestGateFusionado:
    def test_avance_f6_bloqueado_cuando_fusionable_no_completo_f5(self, db):
        """
        Gate: ninguna pieza puede avanzar a F6 (Calidad) si alguna pieza
        con fusionado=True no ha completado F5 (Fusionado).
        """
        of = _make_of(db)
        p_fus  = _make_pieza(db, of, "Delantero", fusionado=True)
        p_norm = _make_pieza(db, of, "Espalda",   fusionado=False)

        # Crear estados de fase necesarios
        # Pieza fusionable: F5 sin completar
        _make_fase_estado(db, of, p_fus,  "F5", cantidad_actual=0, completada=False)
        # Pieza normal: F4 completada (prerequisito para F6)
        _make_fase_estado(db, of, p_norm, "F4", cantidad_actual=10, completada=True)
        # F6 de pieza normal: disponible para avanzar
        _make_fase_estado(db, of, p_norm, "F6", cantidad_actual=0, max_cantidad=10)

        db.commit()

        with pytest.raises(HTTPException) as exc_info:
            registrar_avance(
                of=of, pieza=p_norm, fase_id="F6",
                cantidad=5, usuario_id=1, observacion=None, db=db,
            )

        assert exc_info.value.status_code == 400
        assert "Fusionado" in exc_info.value.detail

    def test_avance_f6_permitido_cuando_fusionable_completo_f5(self, db):
        """
        Gate: cuando la pieza fusionable sí completó F5, cualquier pieza
        puede avanzar a F6.
        """
        of = _make_of(db)
        p_fus  = _make_pieza(db, of, "Delantero", fusionado=True)
        p_norm = _make_pieza(db, of, "Espalda",   fusionado=False)

        # Pieza fusionable: F5 completada ✓
        _make_fase_estado(db, of, p_fus,  "F5", cantidad_actual=10, completada=True)
        # Pieza normal: F4 completada y F6 disponible
        _make_fase_estado(db, of, p_norm, "F4", cantidad_actual=10, completada=True)
        _make_fase_estado(db, of, p_norm, "F6", cantidad_actual=0,  max_cantidad=10)

        db.commit()

        # No debe lanzar excepción
        estado = registrar_avance(
            of=of, pieza=p_norm, fase_id="F6",
            cantidad=5, usuario_id=1, observacion=None, db=db,
        )
        assert estado.cantidad_actual == 5

    def test_avance_f6_sin_piezas_fusionables_siempre_permitido(self, db):
        """
        Si la OF no tiene piezas con fusionado=True, el gate no aplica.
        """
        of = _make_of(db)
        p = _make_pieza(db, of, "Pieza Única", fusionado=False)

        _make_fase_estado(db, of, p, "F4", cantidad_actual=10, completada=True)
        _make_fase_estado(db, of, p, "F6", cantidad_actual=0,  max_cantidad=10)

        db.commit()

        estado = registrar_avance(
            of=of, pieza=p, fase_id="F6",
            cantidad=3, usuario_id=1, observacion=None, db=db,
        )
        assert estado.cantidad_actual == 3


# ── Tests: Restricción cascada de cantidades ──────────────────────────────────

class TestCascadaCantidades:
    def test_avance_no_puede_superar_cantidad_fase_anterior(self, db):
        """
        Cascada: la cantidad en F2 no puede superar la cantidad en F1.
        """
        of = _make_of(db)
        p  = _make_pieza(db, of, "Pieza", fusionado=False)

        _make_fase_estado(db, of, p, "F1", cantidad_actual=5, completada=False)
        _make_fase_estado(db, of, p, "F2", cantidad_actual=0, max_cantidad=10)

        db.commit()

        # F1 tiene 5 unidades → F2 no puede recibir más de 5
        with pytest.raises(HTTPException) as exc_info:
            registrar_avance(
                of=of, pieza=p, fase_id="F2",
                cantidad=6, usuario_id=1, observacion=None, db=db,
            )

        assert exc_info.value.status_code == 400
        assert "Solo puedes registrar" in exc_info.value.detail

    def test_avance_dentro_de_limite_de_cascada_permitido(self, db):
        of = _make_of(db)
        p  = _make_pieza(db, of, "Pieza", fusionado=False)

        _make_fase_estado(db, of, p, "F1", cantidad_actual=8, completada=False)
        _make_fase_estado(db, of, p, "F2", cantidad_actual=0, max_cantidad=10)

        db.commit()

        estado = registrar_avance(
            of=of, pieza=p, fase_id="F2",
            cantidad=8, usuario_id=1, observacion=None, db=db,
        )
        assert estado.cantidad_actual == 8

    def test_avance_rechazado_cuando_fase_ya_completada(self, db):
        of = _make_of(db)
        p  = _make_pieza(db, of, "Pieza", fusionado=False)

        _make_fase_estado(db, of, p, "F1", cantidad_actual=10, completada=True)

        db.commit()

        with pytest.raises(HTTPException) as exc_info:
            registrar_avance(
                of=of, pieza=p, fase_id="F1",
                cantidad=1, usuario_id=1, observacion=None, db=db,
            )

        assert exc_info.value.status_code == 400
        assert "completada" in exc_info.value.detail.lower()

    def test_avance_cambia_estado_of_a_en_proceso(self, db):
        of = _make_of(db, estado=EstadoOF.ACTIVA)
        p  = _make_pieza(db, of, "Pieza", fusionado=False)

        _make_fase_estado(db, of, p, "F1", cantidad_actual=0, max_cantidad=10)

        db.commit()

        registrar_avance(
            of=of, pieza=p, fase_id="F1",
            cantidad=3, usuario_id=1, observacion=None, db=db,
        )

        db.refresh(of)
        assert of.estado == EstadoOF.EN_PROCESO
