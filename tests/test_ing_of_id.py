"""
Normalización N2 — las fichas de ingeniería guardan of_id (FK) resuelto desde
of_numero cuando la OF existe, y None cuando no (llenado libre sigue funcionando).
"""
from datetime import date
from app.models.of import OrdenFabricacion, EstadoOF, TipoClienteEnum, EstadoDocsEnum
from app.models.ingenieria import IngTendidoFicha, IngSamRegistro


def _resolve(db, of_numero):
    row = db.query(OrdenFabricacion.id).filter(OrdenFabricacion.numero_of == of_numero).first()
    return row[0] if row else None


def _of(db, numero):
    of = OrdenFabricacion(
        numero_of=numero, cliente="C", tipo_prenda="CAMISA", total_juegos=10,
        fecha_creacion=date.today(), estado=EstadoOF.ACTIVA,
        tipo_cliente=TipoClienteEnum.MARCA, estado_docs=EstadoDocsEnum.COMPLETA,
    )
    db.add(of); db.commit()
    return of


def test_of_id_se_resuelve_cuando_existe(db):
    of = _of(db, "OF-100")
    fic = IngTendidoFicha(
        fecha=date.today(), of_numero="OF-100", of_id=_resolve(db, "OF-100"),
        tipo_prenda="CAMISA", tela_partida="T", largo_tender_m=5.0, num_capas=10,
        ancho_tela_m=1.5, num_prendas=20, area_tizado_m2=7.5,
    )
    db.add(fic); db.commit(); db.refresh(fic)
    assert fic.of_id == of.id


def test_of_id_none_si_of_no_existe(db):
    fic = IngSamRegistro(
        of_numero="OF-INEXISTENTE", of_id=_resolve(db, "OF-INEXISTENTE"),
        fecha=date.today(), operario="x", fase="F2", elemento="e",
    )
    db.add(fic); db.commit(); db.refresh(fic)
    assert fic.of_id is None            # ficha se guarda igual
    assert fic.of_numero == "OF-INEXISTENTE"
