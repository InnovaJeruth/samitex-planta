"""Fase 3 · Process Mining. Verifica el event log (BULTO), el DFG y los KPIs
construidos en Python desde las tablas transaccionales (sin depender de la VIEW).
"""
from datetime import datetime, date

from app.models.of import OrdenFabricacion, EstadoOF, TipoClienteEnum, EstadoDocsEnum
from app.models.catalogo import PrendaCatalogo, PrendaSku
from app.models.pieza import OFPieza
from app.models.fase import OFFaseTiempos
from app.models.paquete import (
    OFPaquete, OFPaqueteEvento, OFPaqueteRechazo, OFReprocesoHito, MotivoRechazo,
    ESTADO_HABILITADO, ESTADO_FUSIONADO, ESTADO_POR_VALIDAR, ESTADO_ENTREGADO, ESTADO_STANDBY,
)
from app.services.process_mining import event_log as el
from app.services.process_mining import discovery, performance


def _dt(h, m):
    return datetime(2026, 7, 20, h, m, 0)


def _setup(db):
    prenda = PrendaCatalogo(codigo="PM", nombre="Cam", tipo_base="CAMISA", tipo_cliente="MARCA")
    db.add(prenda); db.flush()
    sku = PrendaSku(prenda_catalogo_id=prenda.id, talla="M", activo=True)
    db.add(sku); db.flush()
    of = OrdenFabricacion(
        numero_of="OFPM", cliente="C", tipo_prenda="CAMISA", total_juegos=10,
        fecha_creacion=date.today(), estado=EstadoOF.ACTIVA, tipo_cliente=TipoClienteEnum.MARCA,
        estado_docs=EstadoDocsEnum.COMPLETA, prenda_catalogo_id=prenda.id)
    db.add(of); db.flush()
    pz = OFPieza(of_id=of.id, nombre="Cuello", material="TELA", cantidad_x_prenda=1, fusionado=True)
    db.add(pz); db.flush()
    p1 = OFPaquete(of_id=of.id, sku_id=sku.id, pieza_id=pz.id, numero=1, numero_desde=1,
                   cantidad=10, estado=ESTADO_ENTREGADO,
                   fusionado_inicio=_dt(9, 0), fusionado_fin=_dt(9, 5))
    db.add(p1); db.flush()
    for est, t in [(ESTADO_HABILITADO, _dt(8, 0)), (ESTADO_FUSIONADO, _dt(8, 30)),
                   (ESTADO_POR_VALIDAR, _dt(9, 5)), (ESTADO_ENTREGADO, _dt(9, 40))]:
        db.add(OFPaqueteEvento(paquete_id=p1.id, estado=est, usuario_id=1, created_at=t))
    db.commit()
    return of, sku, pz, p1


def test_event_log_ordenado_y_actividades(db):
    of, sku, pz, p1 = _setup(db)
    evs = el.event_log_bulto(db, of_id=of.id)
    acts = [e["activity"] for e in evs if e["case_id"] == p1.id]
    assert acts[0] == "Numerado"
    assert "Fusionado (inicio)" in acts and "Fusionado (fin)" in acts
    assert acts[-1] == "Liberado (OK calidad)"
    ts = [e["ts"] for e in evs if e["case_id"] == p1.id]
    assert ts == sorted(ts)          # cronológico


def test_dfg_y_kpis(db):
    of, sku, pz, p1 = _setup(db)
    evs = el.event_log_bulto(db, of_id=of.id)
    g = discovery.dfg(evs)
    pares = {(e["from"], e["to"]) for e in g["edges"]}
    assert ("Numerado", "Enviado a fusionado") in pares
    k = performance.kpis(evs)
    assert k["casos"] == 1 and k["lead_time_min_prom"] > 0 and k["pct_rework"] == 0.0


def test_flujo_empieza_en_tizado(db):
    of, sku, pz, p1 = _setup(db)
    # Fases de tela en of_fase_tiempos (como las escriben las placas)
    for fase, ini, fin in [("F1", _dt(6, 0), _dt(7, 0)), ("F2", _dt(7, 0), _dt(7, 30)),
                           ("F3", _dt(7, 30), _dt(7, 50))]:
        db.add(OFFaseTiempos(of_id=of.id, fase_id=fase, inicio_real=ini, fin_real=fin))
    db.commit()
    evs = el.build_event_log(db, of_ids=[of.id])        # OF por defecto → con tela
    acts = [e["activity"] for e in evs]
    assert acts[0] == "Tizado (inicio)"                 # el flujo arranca en Tizado
    assert "Numerado" in acts and "Fusionado (inicio)" in acts
    assert "Enviado a calidad" in acts and "Liberado (OK calidad)" in acts
    # NO debe haber salto directo Numerado → Liberado en la traza del bulto
    seq = [e["activity"] for e in evs if e["case_id"] == p1.id]
    for a, b in zip(seq, seq[1:]):
        assert not (a == "Numerado" and b == "Liberado (OK calidad)")
    assert [e["ts"] for e in evs] == sorted(e["ts"] for e in evs)  # cronológico


def test_simulacion_of(db):
    from app.services.process_mining import simulation as sim
    of, sku, pz, p1 = _setup(db)
    for fase, ini, fin in [("F1", _dt(6, 0), _dt(7, 30)),   # 90 min → rojo
                           ("F2", _dt(7, 30), _dt(7, 35)),   # 5 min  → verde
                           ("F3", _dt(7, 35), _dt(8, 5))]:   # 30 min → amarillo
        db.add(OFFaseTiempos(of_id=of.id, fase_id=fase, inicio_real=ini, fin_real=fin))
    db.commit()
    r = sim.simulacion_of(db, of.id)
    d = {f["fase"]: f for f in r["fases"]}
    assert [f["fase"] for f in r["fases"]][0] == "Tizado"
    assert d["Tizado"]["color"] == "rojo"
    assert d["Tendido"]["color"] == "verde"
    assert d["Corte"]["color"] == "amarillo"
    assert "Fusionado" in d and "Calidad" in d
    assert r["total_min"] > 0
    # lead time real = reloj de pared (F1 inicio 06:00 → Calidad fin 09:40 = 220 min)
    assert r["lead_time_real_min"] == 220.0
    assert r["lead_time_real_min"] >= r["total_min"]   # el reloj incluye las esperas entre fases


def test_rework_detectado(db):
    of, sku, pz, p1 = _setup(db)
    m = MotivoRechazo(codigo="CR30", descripcion="PIEZA DEFORME", activo=True)
    db.add(m); db.flush()
    r = OFPaqueteRechazo(paquete_id=p1.id, motivo_id=m.id, cantidad=1,
                         estado="REINGRESADO", usuario_id=1)
    db.add(r); db.flush()
    db.add(OFPaqueteEvento(paquete_id=p1.id, estado=ESTADO_STANDBY, usuario_id=1, created_at=_dt(9, 10)))
    db.add(OFReprocesoHito(rechazo_id=r.id, etapa="REINGRESADO", usuario_id=1, at=_dt(9, 20)))
    db.commit()
    evs = el.event_log_bulto(db, of_id=of.id)
    acts = {e["activity"] for e in evs}
    assert "Rechazado (stand-by)" in acts and "Reingreso a calidad" in acts
    assert performance.kpis(evs)["pct_rework"] == 100.0
