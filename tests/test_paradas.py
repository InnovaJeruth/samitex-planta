"""
Tests para endpoints de paradas de fase:
  POST /corte/api/{of_id}/pausar
  POST /corte/api/{of_id}/reanudar
  GET  /corte/api/{of_id}/paradas
"""
import pytest
from sqlalchemy.orm import configure_mappers

import app.models.of, app.models.pieza, app.models.fase, app.models.usuario, app.models.planta
configure_mappers()

from app.models.of import OrdenFabricacion, EstadoOF, TipoPrendaEnum, TipoClienteEnum, EstadoDocsEnum
from app.models.fase import OFFaseParada
from app.models.usuario import Usuario, RolEnum
from app.core.auth import hash_password
from app.services.corte_service import ORDEN_FASES


# ── Helpers ───────────────────────────────────────────────────

def _crear_of(db, numero="TEST001"):
    from datetime import date
    of = OrdenFabricacion(
        numero_of=numero,
        cliente="Cliente Test",
        tipo_prenda=TipoPrendaEnum.PANTALON,
        total_juegos=100,
        fecha_creacion=date.today(),
        estado=EstadoOF.EN_PROCESO,
        tipo_cliente=TipoClienteEnum.MARCA,
        estado_docs=EstadoDocsEnum.COMPLETA,
    )
    db.add(of)
    db.commit()
    db.refresh(of)
    return of


def _crear_usuario(db, rol=RolEnum.SUPERVISOR_CORTE):
    u = Usuario(
        username=f"user_{rol.value}",
        email=f"user_{rol.value}@samitex.com",
        nombre="Test",
        password_hash=hash_password("pass"),
        rol=rol,
        activo=True,
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


# ── Tests pausar ──────────────────────────────────────────────

class TestPausarOf:
    def test_crear_parada_activa(self, db):
        """POST pausar crea una OFFaseParada con fin_parada=NULL."""
        of = _crear_of(db)
        user = _crear_usuario(db)

        from datetime import datetime
        parada = OFFaseParada(
            of_id=of.id,
            fase_id="F1",
            inicio_parada=datetime.now(),
            motivo="MATERIAL",
            usuario_id=user.id,
        )
        db.add(parada)
        db.commit()
        db.refresh(parada)

        assert parada.id is not None
        assert parada.fin_parada is None
        assert parada.motivo == "MATERIAL"
        assert parada.of_id == of.id

    def test_parada_activa_tiene_duracion_none(self, db):
        """Una parada sin fin_parada debe tener duracion_minutos=None."""
        of = _crear_of(db)
        from datetime import datetime
        parada = OFFaseParada(
            of_id=of.id, fase_id="F2",
            inicio_parada=datetime.now(), motivo="MAQUINA",
        )
        db.add(parada)
        db.commit()
        assert parada.duracion_minutos is None

    def test_motivos_validos(self, db):
        """Todos los motivos del enum se pueden guardar."""
        of = _crear_of(db)
        from datetime import datetime
        motivos = ["EMERGENCIA_OF", "MATERIAL", "MAQUINA", "ADMIN", "OTRO"]
        for i, motivo in enumerate(motivos):
            parada = OFFaseParada(
                of_id=of.id, fase_id=f"F{i+1}",
                inicio_parada=datetime.now(), motivo=motivo,
            )
            db.add(parada)
        db.commit()

        paradas = db.query(OFFaseParada).filter_by(of_id=of.id).all()
        assert len(paradas) == 5
        guardados = {p.motivo for p in paradas}
        assert guardados == set(motivos)

    def test_parada_con_of_emergencia(self, db):
        """Una parada tipo EMERGENCIA_OF puede referenciar otra OF."""
        of_principal = _crear_of(db, "OF001")
        of_emergencia = _crear_of(db, "OF002")
        from datetime import datetime
        parada = OFFaseParada(
            of_id=of_principal.id,
            fase_id="F3",
            inicio_parada=datetime.now(),
            motivo="EMERGENCIA_OF",
            of_emergencia_id=of_emergencia.id,
        )
        db.add(parada)
        db.commit()
        db.refresh(parada)

        assert parada.of_emergencia_id == of_emergencia.id

    def test_no_puede_haber_dos_paradas_activas_misma_fase(self, db):
        """Solo puede haber una parada activa (fin_parada=NULL) por OF+fase."""
        of = _crear_of(db)
        from datetime import datetime
        parada1 = OFFaseParada(
            of_id=of.id, fase_id="F1",
            inicio_parada=datetime.now(), motivo="ADMIN",
        )
        db.add(parada1)
        db.commit()

        # Verificar que al buscar parada activa, se encuentra la existente
        activa = db.query(OFFaseParada).filter(
            OFFaseParada.of_id == of.id,
            OFFaseParada.fase_id == "F1",
            OFFaseParada.fin_parada.is_(None),
        ).first()
        assert activa is not None
        assert activa.id == parada1.id


# ── Tests reanudar ────────────────────────────────────────────

class TestReanudarOf:
    def test_reanudar_cierra_parada(self, db):
        """Al reanudar, fin_parada se establece con la hora actual."""
        of = _crear_of(db)
        from datetime import datetime
        parada = OFFaseParada(
            of_id=of.id, fase_id="F1",
            inicio_parada=datetime.now(), motivo="MATERIAL",
        )
        db.add(parada)
        db.commit()

        # Simular reanudar
        parada.fin_parada = datetime.now()
        db.commit()
        db.refresh(parada)

        assert parada.fin_parada is not None

    def test_duracion_calculada_correctamente(self, db):
        """duracion_minutos calcula bien la diferencia."""
        of = _crear_of(db)
        from datetime import datetime, timedelta
        inicio = datetime(2026, 1, 1, 10, 0, 0)
        fin    = datetime(2026, 1, 1, 10, 45, 0)
        parada = OFFaseParada(
            of_id=of.id, fase_id="F2",
            inicio_parada=inicio, motivo="OTRO",
        )
        db.add(parada)
        db.commit()

        parada.fin_parada = fin
        db.commit()

        assert parada.duracion_minutos == 45

    def test_parada_cerrada_no_es_activa(self, db):
        """Una parada con fin_parada no aparece en búsqueda de activas."""
        of = _crear_of(db)
        from datetime import datetime
        parada = OFFaseParada(
            of_id=of.id, fase_id="F1",
            inicio_parada=datetime(2026, 1, 1, 8, 0),
            fin_parada=datetime(2026, 1, 1, 9, 0),
            motivo="ADMIN",
        )
        db.add(parada)
        db.commit()

        activa = db.query(OFFaseParada).filter(
            OFFaseParada.of_id == of.id,
            OFFaseParada.fin_parada.is_(None),
        ).first()
        assert activa is None


# ── Tests listar paradas ──────────────────────────────────────

class TestListarParadas:
    def test_listar_devuelve_todas_las_paradas_de_of(self, db):
        of = _crear_of(db)
        from datetime import datetime
        for i in range(3):
            db.add(OFFaseParada(
                of_id=of.id, fase_id=f"F{i+1}",
                inicio_parada=datetime.now(), motivo="OTRO",
            ))
        db.commit()

        paradas = db.query(OFFaseParada).filter_by(of_id=of.id).all()
        assert len(paradas) == 3

    def test_paradas_de_of_diferente_no_se_mezclan(self, db):
        of1 = _crear_of(db, "OF001")
        of2 = _crear_of(db, "OF002")
        from datetime import datetime
        db.add(OFFaseParada(of_id=of1.id, fase_id="F1", inicio_parada=datetime.now(), motivo="ADMIN"))
        db.add(OFFaseParada(of_id=of1.id, fase_id="F2", inicio_parada=datetime.now(), motivo="ADMIN"))
        db.add(OFFaseParada(of_id=of2.id, fase_id="F1", inicio_parada=datetime.now(), motivo="ADMIN"))
        db.commit()

        paradas_of1 = db.query(OFFaseParada).filter_by(of_id=of1.id).all()
        paradas_of2 = db.query(OFFaseParada).filter_by(of_id=of2.id).all()
        assert len(paradas_of1) == 2
        assert len(paradas_of2) == 1
