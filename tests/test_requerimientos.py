"""Fase 1 · Requerimientos comerciales. Verifica modelos, curva de tallas y
la relación cabecera→líneas→tallas. (Servicio/validaciones llegan en RP-3.)
"""
import pytest
from fastapi import HTTPException

from app.models.requerimiento import (
    Requerimiento, RequerimientoLinea, RequerimientoLineaTalla, TALLAJES,
)
from app.services import requerimiento_service as svc


def _cab(numero="014-2026", tipo="PRODUCCION"):
    return {"numero_req": numero, "tipo": tipo, "cliente": "ELECTROCENTRO"}


def _linea(total=None, tallaje="C", tallas=None):
    return {"descripcion": "BLUSA", "articulo": "LYI278", "tallaje": tallaje,
            "total": total, "tallas": tallas or [{"talla": "M", "cantidad": 30},
                                                  {"talla": "L", "cantidad": 29}]}


def test_crear_requerimiento_con_lineas_y_curva(db):
    r = Requerimiento(numero_req="014-2026", tipo="PRODUCCION",
                      cliente="ELECTROCENTRO", estado="BORRADOR")
    db.add(r); db.flush()

    ln = RequerimientoLinea(requerimiento_id=r.id, grupo="PRIMER TERNO",
                            articulo="LYI278", descripcion="BLUSA MANGA LARGA",
                            tallaje="C", total=59, orden=0)
    db.add(ln); db.flush()
    for talla, cant in [("S", 10), ("M", 30), ("L", 19)]:
        db.add(RequerimientoLineaTalla(linea_id=ln.id, talla=talla, cantidad=cant))
    db.commit(); db.refresh(r); db.refresh(ln)

    assert ln.total_curva == 59          # Σ curva
    assert ln.total == ln.total_curva    # total declarado coincide
    assert r.total_general == 59
    assert r.lineas[0].descripcion == "BLUSA MANGA LARGA"
    assert r.lineas[0].prenda_catalogo_id is None   # prenda opcional


def test_tallajes_definidos():
    assert set(TALLAJES) == {"A", "B", "C"}
    assert TALLAJES["A"][0] == "14.5"     # cuello
    assert TALLAJES["B"][0] == "28"       # numérico
    assert TALLAJES["C"][0] == "XS"       # letra


def test_cascade_borra_lineas_y_tallas(db):
    r = Requerimiento(numero_req="015-2026", tipo="STOCK", cliente="X")
    db.add(r); db.flush()
    ln = RequerimientoLinea(requerimiento_id=r.id, descripcion="POLO", tallaje="C", total=5)
    db.add(ln); db.flush()
    db.add(RequerimientoLineaTalla(linea_id=ln.id, talla="M", cantidad=5))
    db.commit()

    db.delete(r); db.commit()
    assert db.query(RequerimientoLinea).count() == 0
    assert db.query(RequerimientoLineaTalla).count() == 0


# ── Servicio (RP-3) ──────────────────────────────────────────────────────────
def test_svc_crear_calcula_total(db):
    req = svc.crear_requerimiento(db, _cab(), [_linea()], usuario_id=1)
    assert req.estado == "BORRADOR"
    assert req.lineas[0].total == 59          # total = Σ curva (30+29)
    assert req.total_general == 59


def test_svc_numero_duplicado_falla(db):
    svc.crear_requerimiento(db, _cab("D-1"), [_linea()], usuario_id=1)
    with pytest.raises(HTTPException) as e:
        svc.crear_requerimiento(db, _cab("D-1"), [_linea()], usuario_id=1)
    assert e.value.status_code == 409


def test_svc_total_declarado_no_coincide_falla(db):
    with pytest.raises(HTTPException) as e:
        svc.crear_requerimiento(db, _cab("D-2"), [_linea(total=100)], usuario_id=1)
    assert e.value.status_code == 400


def test_svc_talla_fuera_de_tallaje_falla(db):
    mala = _linea(tallaje="C", tallas=[{"talla": "36", "cantidad": 5}])  # 36 es tallaje B
    with pytest.raises(HTTPException) as e:
        svc.crear_requerimiento(db, _cab("D-3"), [mala], usuario_id=1)
    assert e.value.status_code == 400


def test_svc_editar_reemplaza_lineas(db):
    req = svc.crear_requerimiento(db, _cab("D-4"), [_linea()], usuario_id=1)
    nueva = _linea(tallas=[{"talla": "S", "cantidad": 5}])
    svc.actualizar_requerimiento(db, req.id, _cab("D-4"), [nueva], usuario_id=1)
    r2 = svc.obtener_requerimiento(db, req.id)
    assert len(r2.lineas) == 1 and r2.lineas[0].total == 5


def test_svc_registrar_bloquea_edicion(db):
    req = svc.crear_requerimiento(db, _cab("D-5"), [_linea()], usuario_id=1)
    svc.registrar_requerimiento(db, req.id)
    with pytest.raises(HTTPException) as e:
        svc.actualizar_requerimiento(db, req.id, _cab("D-5"), [_linea()], usuario_id=1)
    assert e.value.status_code == 409


def test_svc_listar_filtra_por_tipo(db):
    svc.crear_requerimiento(db, _cab("D-6", "MUESTRA"), [_linea()], usuario_id=1)
    svc.crear_requerimiento(db, _cab("D-7", "STOCK"), [_linea()], usuario_id=1)
    assert len(svc.listar_requerimientos(db, tipo="MUESTRA")) == 1
    assert len(svc.listar_requerimientos(db)) >= 2


# ── Router (RP-4): wiring ────────────────────────────────────────────────────
def test_router_expone_rutas():
    from app.routers import requerimientos as r
    paths = {route.path for route in r.router.routes}
    assert "/" in paths and "/nuevo" in paths
    assert "/api/crear" in paths and "/api/lista" in paths
    assert "/api/{req_id}/registrar" in paths
