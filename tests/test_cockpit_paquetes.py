"""
Q5.1 — el cockpit (franja + grilla por talla) deriva F4/F6/F7 de los paquetes.
Llama a los endpoints reales de corte con la BD de test.
"""
from types import SimpleNamespace
from datetime import date
import pytest
from fastapi import HTTPException

from app.models.of import (OrdenFabricacion, EstadoOF, TipoClienteEnum,
                           EstadoDocsEnum, OFTallaDistribucion)
from app.models.catalogo import PrendaCatalogo, PrendaSku
from app.models.pieza import OFPieza
from app.models.paquete import (ESTADO_POR_VALIDAR, ESTADO_FUSIONADO,
                                ESTADO_ENTREGADO, MotivoRechazo)
from app.services.of_service import crear_fases_pieza
from app.services import paquete_service as svc
from app.routers import corte

USER = SimpleNamespace(id=1, rol="SUPERVISOR_CORTE", nombre="Tester")


def _setup(db):
    prenda = PrendaCatalogo(codigo="CB", nombre="Cam", tipo_base="CAMISA", tipo_cliente="MARCA")
    db.add(prenda); db.flush()
    sku = PrendaSku(prenda_catalogo_id=prenda.id, talla="M", activo=True)
    db.add(sku); db.flush()
    of = OrdenFabricacion(
        numero_of="OFC", cliente="C", tipo_prenda="CAMISA", total_juegos=100,
        fecha_creacion=date.today(), estado=EstadoOF.ACTIVA, tipo_cliente=TipoClienteEnum.MARCA,
        estado_docs=EstadoDocsEnum.COMPLETA, prenda_catalogo_id=prenda.id, corte_por_talla=True,
    )
    db.add(of); db.flush()
    db.add(OFTallaDistribucion(of_id=of.id, sku_id=sku.id, cantidad=100))
    p = OFPieza(of_id=of.id, nombre="Delantero", material="TELA", cantidad_x_prenda=1, fusionado=False)
    db.add(p); db.flush()
    crear_fases_pieza(p, of, db); db.commit()
    return of, sku.id


def _entregar(db, paqs):
    for pq in paqs:
        svc.set_estado_paquete(pq.id, ESTADO_POR_VALIDAR, db)
        svc.validar_paquete(pq.id, [], db)


def test_estado_talla_deriva_calidad(db):
    of, sku_id = _setup(db)
    paqs = svc.generar_paquetes(of, [{"sku_id": sku_id, "cantidad": 100}], db)  # 49+49+2
    _entregar(db, paqs[:2])                                                     # 98/100
    data = corte.estado_talla(of.id, db=db, current_user=USER)
    t = data["tallas"][0]
    # F4 numerado = bultos enviados (fuera de HABILITADO): 2 de 3 paquetes → 67%
    assert t["fases"]["F4"] == {"pct": 67, "done": False}
    # F7 "Liberado" sigue a Calidad: 98% sin completar (2 de 3 paquetes)
    assert t["fases"]["F7"]["pct"] == 98 and t["fases"]["F7"]["done"] is False
    assert t["fases"]["F6"]["pct"] == 98 and t["fases"]["F6"]["done"] is False
    # el detalle por pieza ya no lleva F4/F5/F6/F7 (son por talla)
    for pz in t["piezas"]:
        assert not ({"F4", "F5", "F6", "F7"} & set(pz["fases"].keys()))
    assert t["calidad"]["entregado"] == 98 and t["calidad"]["total"] == 100


def test_strip_deriva_calidad(db):
    of, sku_id = _setup(db)
    paqs = svc.generar_paquetes(of, [{"sku_id": sku_id, "cantidad": 100}], db)
    _entregar(db, paqs)                                                        # 100/100
    strip = corte.fases_strip(of.id, db=db, current_user=USER)
    by = {c["fase_id"]: c for c in strip}
    assert by["F4"]["pct"] == 100 and by["F4"]["estado"] == "completada"
    assert by["F6"]["pct"] == 100 and by["F6"]["estado"] == "completada"
    assert by["F7"]["pct"] == 100 and by["F7"]["estado"] == "completada"
    # controles viejos desactivados en la franja
    assert by["F4"]["puede_iniciar"] is False and by["F6"]["puede_iniciar"] is False


def test_numeracion_avanza_por_bultos_enviados(db):
    """F4 arranca en 0% (hoja generada, nada enviado) y sube al enviar bultos."""
    of, sku_id = _setup(db)
    paqs = svc.generar_paquetes(of, [{"sku_id": sku_id, "cantidad": 100}], db)  # 3 bultos, todos HABILITADO
    strip = corte.fases_strip(of.id, db=db, current_user=USER)
    f4 = {c["fase_id"]: c for c in strip}["F4"]
    assert f4["pct"] == 0 and f4["estado"] == "en_proceso"       # inicio marcado, 0 enviado
    _entregar(db, paqs[:2])                                       # 2 de 3 enviados
    strip = corte.fases_strip(of.id, db=db, current_user=USER)
    f4 = {c["fase_id"]: c for c in strip}["F4"]
    assert f4["pct"] == 67 and f4["estado"] == "en_proceso"
    _entregar(db, paqs[2:])                                       # el último → 100% + fin
    strip = corte.fases_strip(of.id, db=db, current_user=USER)
    f4 = {c["fase_id"]: c for c in strip}["F4"]
    assert f4["pct"] == 100 and f4["estado"] == "completada"


def test_of_se_cierra_cuando_todo_entregado(db):
    of, sku_id = _setup(db)
    paqs = svc.generar_paquetes(of, [{"sku_id": sku_id, "cantidad": 100}], db)  # 3 paquetes
    _entregar(db, paqs[:2])                       # 2 de 3 → OF sigue abierta
    db.refresh(of)
    assert of.estado != EstadoOF.COMPLETADA
    _entregar(db, paqs[2:])                       # el último → OF cerrada
    db.refresh(of)
    assert of.estado == EstadoOF.COMPLETADA


def _setup_fusiona(db):
    prenda = PrendaCatalogo(codigo="CBF", nombre="Cam", tipo_base="CAMISA", tipo_cliente="MARCA")
    db.add(prenda); db.flush()
    sku = PrendaSku(prenda_catalogo_id=prenda.id, talla="M", activo=True)
    db.add(sku); db.flush()
    of = OrdenFabricacion(
        numero_of="OFF", cliente="C", tipo_prenda="CAMISA", total_juegos=50,
        fecha_creacion=date.today(), estado=EstadoOF.ACTIVA, tipo_cliente=TipoClienteEnum.MARCA,
        estado_docs=EstadoDocsEnum.COMPLETA, prenda_catalogo_id=prenda.id, corte_por_talla=True,
    )
    db.add(of); db.flush()
    db.add(OFTallaDistribucion(of_id=of.id, sku_id=sku.id, cantidad=50))
    db.add(OFPieza(of_id=of.id, nombre="Cuello", material="TELA", cantidad_x_prenda=1, fusionado=True))
    db.commit()
    return of, sku.id


def test_flujo_con_fusionado(db):
    of, sku_id = _setup_fusiona(db)
    assert svc.requiere_fusionado(of) is True
    p = svc.generar_paquetes(of, [{"sku_id": sku_id, "cantidad": 50}], db)[0]
    # HABILITADO → POR_VALIDAR está bloqueado: la prenda debe fusionarse primero
    with pytest.raises(HTTPException) as e:
        svc.set_estado_paquete(p.id, ESTADO_POR_VALIDAR, db)
    assert e.value.status_code == 400
    # HABILITADO → FUSIONADO → POR_VALIDAR → entregar
    svc.set_estado_paquete(p.id, ESTADO_FUSIONADO, db)
    svc.set_estado_paquete(p.id, ESTADO_POR_VALIDAR, db)
    svc.validar_paquete(p.id, [], db)
    db.refresh(p)
    assert p.estado == ESTADO_ENTREGADO


def test_fusionado_en_curso_al_iniciar(db):
    """F5 debe mostrarse 'en curso' apenas se inicia un bulto (aunque 0% terminado),
    y el % sube al terminar cada bulto."""
    of, sku_id = _setup_fusiona(db)
    paqs = svc.generar_paquetes(of, [{"sku_id": sku_id, "cantidad": 100}], db)  # 3 bultos fusibles
    # enviar a fusionado (HABILITADO → FUSIONADO)
    for p in paqs:
        svc.set_estado_paquete(p.id, ESTADO_FUSIONADO, db)
    # iniciar el primer bulto (marca fusionado_inicio, aún sin terminar)
    svc.iniciar_fusionado(paqs[0].id, db)
    strip = corte.fases_strip(of.id, db=db, current_user=USER)
    f5 = {c["fase_id"]: c for c in strip}["F5"]
    assert f5["pct"] == 0 and f5["estado"] == "en_proceso" and f5["inicio_real"]
    # terminar 1 de 3 → 33%
    svc.terminar_fusionado(paqs[0].id, db)
    strip = corte.fases_strip(of.id, db=db, current_user=USER)
    f5 = {c["fase_id"]: c for c in strip}["F5"]
    assert f5["pct"] == 33 and f5["estado"] == "en_proceso"
    # terminar el resto → 100% completada + fin real
    svc.terminar_fusionado(paqs[1].id, db)
    svc.terminar_fusionado(paqs[2].id, db)
    strip = corte.fases_strip(of.id, db=db, current_user=USER)
    f5 = {c["fase_id"]: c for c in strip}["F5"]
    assert f5["pct"] == 100 and f5["estado"] == "completada" and f5["fin_real"]


def test_aprobar_talla_calidad(db):
    """'Aprobar toda la talla' valida sin rechazos todos los bultos por-validar → ENTREGADO."""
    of, sku_id = _setup(db)
    paqs = svc.generar_paquetes(of, [{"sku_id": sku_id, "cantidad": 100}], db)  # no fusible
    for p in paqs:                                # HABILITADO → POR_VALIDAR
        svc.set_estado_paquete(p.id, ESTADO_POR_VALIDAR, db)
    n = svc.aprobar_talla_calidad(of.id, sku_id, db)
    assert n == len(paqs)
    for p in paqs:
        db.refresh(p)
        assert p.estado == ESTADO_ENTREGADO
    db.refresh(of)
    assert of.estado == EstadoOF.COMPLETADA          # todo entregado → OF cerrada


def test_standby_no_cierra_of(db):
    of, sku_id = _setup(db)
    m = MotivoRechazo(codigo="CR31", descripcion="PIEZA FALTANTE", activo=True)
    db.add(m); db.commit()
    paqs = svc.generar_paquetes(of, [{"sku_id": sku_id, "cantidad": 100}], db)
    _entregar(db, paqs[:2])
    p = paqs[2]                                   # el último queda en stand-by
    svc.set_estado_paquete(p.id, ESTADO_POR_VALIDAR, db)
    svc.validar_paquete(p.id, [{"motivo_id": m.id, "cantidad": 1, "destino": "CORTE"}], db)
    db.refresh(of)
    assert of.estado != EstadoOF.COMPLETADA
