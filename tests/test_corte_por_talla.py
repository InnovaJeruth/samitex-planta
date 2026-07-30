"""
Fase B — generación de fases por pieza × talla (F4–F7).
SQLite en memoria (fixture `db` de conftest.py).
"""
from datetime import date
from app.models.of import OrdenFabricacion, EstadoOF, TipoClienteEnum, EstadoDocsEnum, OFTallaDistribucion
from app.models.catalogo import PrendaCatalogo, PrendaSku
from app.models.pieza import OFPieza
from app.models.fase import OFFaseEstado
from app.services.of_service import crear_fases_pieza


def _mk(db, por_talla):
    prenda = PrendaCatalogo(codigo="CB", nombre="Cam", tipo_base="CAMISA", tipo_cliente="MARCA")
    db.add(prenda); db.flush()
    skus = {}
    for t, c in [("S", 10), ("M", 20), ("L", 15)]:
        sk = PrendaSku(prenda_catalogo_id=prenda.id, talla=t, activo=True)
        db.add(sk); db.flush(); skus[t] = (sk.id, c)
    of = OrdenFabricacion(
        numero_of="OFB", cliente="C", tipo_prenda="CAMISA", total_juegos=45,
        fecha_creacion=date.today(), estado=EstadoOF.ACTIVA, tipo_cliente=TipoClienteEnum.MARCA,
        estado_docs=EstadoDocsEnum.COMPLETA, prenda_catalogo_id=prenda.id, corte_por_talla=por_talla,
    )
    db.add(of); db.flush()
    for t, (sid, c) in skus.items():
        db.add(OFTallaDistribucion(of_id=of.id, sku_id=sid, cantidad=c))
    p = OFPieza(of_id=of.id, nombre="Delantero", material="TELA", cantidad_x_prenda=1, fusionado=False)
    db.add(p); db.flush(); db.commit()
    return of, p, skus


def test_genera_f4_por_talla(db):
    of, p, skus = _mk(db, True)
    crear_fases_pieza(p, of, db); db.commit()
    f1 = db.query(OFFaseEstado).filter_by(of_id=of.id, fase_id="F1").all()
    f4 = db.query(OFFaseEstado).filter_by(of_id=of.id, fase_id="F4").all()
    assert len(f1) == 1 and f1[0].sku_id is None           # tela: por pieza
    assert len(f4) == 3                                     # F4: por talla
    assert {e.talla: e.max_cantidad for e in f4} == {"S": 10, "M": 20, "L": 15}


def test_por_pieza_una_fila(db):
    of, p, skus = _mk(db, False)
    crear_fases_pieza(p, of, db); db.commit()
    f4 = db.query(OFFaseEstado).filter_by(of_id=of.id, fase_id="F4").all()
    assert len(f4) == 1 and f4[0].sku_id is None and f4[0].max_cantidad == 45


# ── Motor por talla (B4) ──────────────────────────────────────────────────────
import pytest
from fastapi import HTTPException
from app.services.corte_service import registrar_avance, completar_fase


def _prep(db):
    of, p, skus = _mk(db, True)
    crear_fases_pieza(p, of, db); db.commit()
    return of, p, skus


def test_f4_talla_requiere_tela_completa(db):
    of, p, skus = _prep(db)
    with pytest.raises(HTTPException) as e:
        registrar_avance(of, p, "F4", 1, 1, None, db, sku_id=skus["S"][0])
    assert e.value.status_code == 400  # F3 (tela) aún no completa


def test_f4_talla_tras_tela_y_respeta_tope(db):
    of, p, skus = _prep(db)
    for f in ("F1", "F2", "F3"):
        completar_fase(of, p, f, 1, db)          # tela por pieza
    sS = skus["S"][0]
    est = registrar_avance(of, p, "F4", 5, 1, None, db, sku_id=sS)
    assert est.cantidad_actual == 5
    with pytest.raises(HTTPException) as e:       # 5+6 = 11 > meta 10 de la talla S
        registrar_avance(of, p, "F4", 6, 1, None, db, sku_id=sS)
    assert e.value.status_code == 400


def test_regenerar_cuando_curva_llega_despues(db):
    """Piezas creadas sin curva → F4 por pieza; al vincular la curva se regenera por talla."""
    from app.services.of_service import regenerar_fases_talla
    from datetime import date
    prenda = PrendaCatalogo(codigo="CR", nombre="Cam", tipo_base="CAMISA", tipo_cliente="MARCA")
    db.add(prenda); db.flush()
    skus = {}
    for t, c in [("S", 10), ("M", 20), ("L", 15)]:
        sk = PrendaSku(prenda_catalogo_id=prenda.id, talla=t, activo=True); db.add(sk); db.flush()
        skus[t] = (sk.id, c)
    of = OrdenFabricacion(numero_of="OFR", cliente="C", tipo_prenda="CAMISA", total_juegos=45,
        fecha_creacion=date.today(), estado=EstadoOF.ACTIVA, tipo_cliente=TipoClienteEnum.MARCA,
        estado_docs=EstadoDocsEnum.COMPLETA, prenda_catalogo_id=prenda.id, corte_por_talla=True)
    db.add(of); db.flush()
    p = OFPieza(of_id=of.id, nombre="Delantero", material="TELA", cantidad_x_prenda=1, fusionado=False)
    db.add(p); db.flush()
    crear_fases_pieza(p, of, db); db.commit()          # SIN distribución → F4 por pieza
    f4 = db.query(OFFaseEstado).filter_by(of_id=of.id, fase_id="F4").all()
    assert len(f4) == 1 and f4[0].sku_id is None
    for t, (sid, c) in skus.items():
        db.add(OFTallaDistribucion(of_id=of.id, sku_id=sid, cantidad=c))
    db.commit()
    regenerar_fases_talla(of, db)
    f4 = db.query(OFFaseEstado).filter_by(of_id=of.id, fase_id="F4").all()
    assert len(f4) == 3 and all(e.sku_id is not None for e in f4)


def test_log_guarda_talla(db):
    """El registro de avance guarda la talla (trazabilidad por talla)."""
    from app.models.fase import AvanceRegistro
    of, p, skus = _prep(db)
    for f in ("F1", "F2", "F3"):
        completar_fase(of, p, f, 1, db)
    registrar_avance(of, p, "F4", 3, 1, None, db, sku_id=skus["S"][0])
    reg = db.query(AvanceRegistro).filter_by(of_id=of.id, fase_id="F4").first()
    assert reg is not None and reg.talla == "S" and reg.sku_id == skus["S"][0]
