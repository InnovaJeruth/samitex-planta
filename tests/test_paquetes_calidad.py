"""
Q2 — Calidad y Reprocesos de paquetes.
SQLite en memoria (fixture `db` de conftest.py).
"""
from datetime import date
import pytest
from fastapi import HTTPException

from app.models.of import (OrdenFabricacion, EstadoOF, TipoClienteEnum,
                            EstadoDocsEnum, OFTallaDistribucion)
from app.models.catalogo import PrendaCatalogo, PrendaSku
from app.models.pieza import OFPieza
from app.models.fase import OFFaseTiempos
from app.models.paquete import (
    OFPaquete, OFPaqueteRechazo, MotivoRechazo, OFNumeracionReapertura,
    ESTADO_HABILITADO, ESTADO_FUSIONADO, ESTADO_POR_VALIDAR, ESTADO_STANDBY, ESTADO_ENTREGADO,
    RECHAZO_PENDIENTE, RECHAZO_REINGRESADO, RECHAZO_MERMA,
)
from app.services import paquete_service as svc


def _mk(db, cantidad=100):
    prenda = PrendaCatalogo(codigo="CB", nombre="Cam", tipo_base="CAMISA", tipo_cliente="MARCA")
    db.add(prenda); db.flush()
    sku = PrendaSku(prenda_catalogo_id=prenda.id, talla="M", activo=True)
    db.add(sku); db.flush()
    of = OrdenFabricacion(
        numero_of="OFQ", cliente="C", tipo_prenda="CAMISA", total_juegos=cantidad,
        fecha_creacion=date.today(), estado=EstadoOF.ACTIVA, tipo_cliente=TipoClienteEnum.MARCA,
        estado_docs=EstadoDocsEnum.COMPLETA, prenda_catalogo_id=prenda.id,
    )
    db.add(of); db.flush()
    db.add(OFTallaDistribucion(of_id=of.id, sku_id=sku.id, cantidad=cantidad))
    # una pieza no fusible → 1 bulto por trozo (como el grano de bulto real)
    db.add(OFPieza(of_id=of.id, nombre="Delantero", material="TELA", cantidad_x_prenda=1, fusionado=False))
    m1 = MotivoRechazo(codigo="CR31", descripcion="PIEZA FALTANTE", activo=True)
    m2 = MotivoRechazo(codigo="CR12", descripcion="FUSIONADO MAL AFINADO", activo=True)
    db.add_all([m1, m2]); db.commit()
    return of, sku.id, m1, m2


def _generar(db, of, sku_id, cant, size=49):
    return svc.generar_paquetes(of, [{"sku_id": sku_id, "cantidad": cant}], db, size=size)


def _mk_multi(db, cantidad=50):
    prenda = PrendaCatalogo(codigo="CBM", nombre="Cam", tipo_base="CAMISA", tipo_cliente="MARCA")
    db.add(prenda); db.flush()
    sku = PrendaSku(prenda_catalogo_id=prenda.id, talla="M", activo=True)
    db.add(sku); db.flush()
    of = OrdenFabricacion(
        numero_of="OFM", cliente="C", tipo_prenda="CAMISA", total_juegos=cantidad,
        fecha_creacion=date.today(), estado=EstadoOF.ACTIVA, tipo_cliente=TipoClienteEnum.MARCA,
        estado_docs=EstadoDocsEnum.COMPLETA, prenda_catalogo_id=prenda.id,
    )
    db.add(of); db.flush()
    db.add(OFTallaDistribucion(of_id=of.id, sku_id=sku.id, cantidad=cantidad))
    db.add(OFPieza(of_id=of.id, nombre="Delantero", material="TELA", cantidad_x_prenda=1, fusionado=False))
    db.add(OFPieza(of_id=of.id, nombre="Cuello", material="TELA", cantidad_x_prenda=1, fusionado=True))
    db.commit()
    return of, sku.id


def test_generacion_por_pieza(db):
    of, sku_id = _mk_multi(db, cantidad=50)          # tope 49 → 2 trozos × 2 piezas = 4 bultos
    paqs = svc.generar_paquetes(of, [{"sku_id": sku_id, "cantidad": 50}], db)
    assert len(paqs) == 4
    assert svc.corte_real(of.id, db) == 50           # prendas, no piezas (dedup por pieza)
    delantero = next(p for p in paqs if p.pieza.nombre == "Delantero")
    cuello = next(p for p in paqs if p.pieza.nombre == "Cuello")
    # el bulto no fusible va directo a Calidad; el fusible debe pasar por Fusionado
    svc.set_estado_paquete(delantero.id, ESTADO_POR_VALIDAR, db)
    with pytest.raises(HTTPException):
        svc.set_estado_paquete(cuello.id, ESTADO_POR_VALIDAR, db)
    svc.set_estado_paquete(cuello.id, ESTADO_FUSIONADO, db)
    svc.set_estado_paquete(cuello.id, ESTADO_POR_VALIDAR, db)
    assert cuello.estado == ESTADO_POR_VALIDAR


def test_numeracion_multi_talla(db):
    """El correlativo del bulto es continuo por pieza a través de tallas (no choca el único)."""
    prenda = PrendaCatalogo(codigo="CB2", nombre="Cam", tipo_base="CAMISA", tipo_cliente="MARCA")
    db.add(prenda); db.flush()
    s1 = PrendaSku(prenda_catalogo_id=prenda.id, talla="S", activo=True)
    s2 = PrendaSku(prenda_catalogo_id=prenda.id, talla="M", activo=True)
    db.add_all([s1, s2]); db.flush()
    of = OrdenFabricacion(
        numero_of="OF2T", cliente="C", tipo_prenda="CAMISA", total_juegos=100,
        fecha_creacion=date.today(), estado=EstadoOF.ACTIVA, tipo_cliente=TipoClienteEnum.MARCA,
        estado_docs=EstadoDocsEnum.COMPLETA, prenda_catalogo_id=prenda.id,
    )
    db.add(of); db.flush()
    db.add(OFPieza(of_id=of.id, nombre="Delantero", material="TELA", cantidad_x_prenda=1, fusionado=False))
    db.commit()
    paqs = svc.generar_paquetes(of, [{"sku_id": s1.id, "cantidad": 50},
                                     {"sku_id": s2.id, "cantidad": 50}], db)
    assert len(paqs) == 4                       # 1 pieza, tope 49 → (49,1) por talla
    assert sorted(p.numero for p in paqs) == [1, 2, 3, 4]   # continuo, sin choque
    assert svc.corte_real(of.id, db) == 100


def test_avanzar_talla_en_lote(db):
    of, sku_id = _mk_multi(db, cantidad=40)      # 1 trozo × 2 piezas = 2 bultos
    svc.generar_paquetes(of, [{"sku_id": sku_id, "cantidad": 40}], db)
    n = svc.avanzar_talla(of.id, sku_id, "todo", db)
    assert n == 2
    est = {p.pieza.nombre: p.estado for p in svc.listar_paquetes(of.id, db)}
    assert est["Delantero"] == ESTADO_POR_VALIDAR      # no fusible → directo a Calidad
    assert est["Cuello"] == ESTADO_FUSIONADO           # fusible → a Fusionado
    m = svc.avanzar_talla(of.id, sku_id, "fusionado_listo", db)
    assert m == 1
    est = {p.pieza.nombre: p.estado for p in svc.listar_paquetes(of.id, db)}
    assert est["Cuello"] == ESTADO_POR_VALIDAR


def test_modulo_fusionado(db):
    of, sku_id = _mk_multi(db, cantidad=40)      # Delantero (no fus) + Cuello (fus)
    svc.generar_paquetes(of, [{"sku_id": sku_id, "cantidad": 40}], db)
    # mandar las fusibles a fusionado
    svc.avanzar_talla(of.id, sku_id, "fusion", db)
    fus = svc.listar_fusionado(db)
    assert len(fus) == 1 and fus[0].pieza.nombre == "Cuello"
    b = fus[0]
    assert not b.fusionado_en_proceso
    svc.iniciar_fusionado(b.id, db)
    db.refresh(b)
    assert b.fusionado_en_proceso and b.fusionado_inicio is not None
    svc.terminar_fusionado(b.id, db)
    db.refresh(b)
    assert b.estado == ESTADO_POR_VALIDAR and b.fusionado_fin is not None
    assert svc.listar_fusionado(db) == []        # ya no está en fusionado


def test_reingreso_va_a_calidad(db):
    of, sku_id = _mk_multi(db, cantidad=40)
    paqs = svc.generar_paquetes(of, [{"sku_id": sku_id, "cantidad": 40}], db)
    cuello = next(p for p in paqs if p.pieza.nombre == "Cuello")
    svc.set_estado_paquete(cuello.id, ESTADO_FUSIONADO, db)
    svc.terminar_fusionado(cuello.id, db)                 # → POR_VALIDAR
    m = MotivoRechazo(codigo="CRX", descripcion="x", activo=True); db.add(m); db.commit()
    svc.validar_paquete(cuello.id, [{"motivo_id": m.id, "cantidad": 2, "destino": "FUSIONADO"}], db)
    r = db.query(OFPaqueteRechazo).filter_by(paquete_id=cuello.id).one()
    svc.reingresar_rechazo(r.id, db)
    db.refresh(cuello)
    assert cuello.estado == ESTADO_POR_VALIDAR             # reingreso → Calidad


def test_reproceso_corte_fusible_pasa_a_fusionado(db):
    of, sku_id = _mk_multi(db, cantidad=40)               # Delantero (no fus) + Cuello (fus)
    paqs = svc.generar_paquetes(of, [{"sku_id": sku_id, "cantidad": 40}], db)
    cuello = next(p for p in paqs if p.pieza.nombre == "Cuello")
    svc.set_estado_paquete(cuello.id, ESTADO_FUSIONADO, db)
    svc.terminar_fusionado(cuello.id, db)
    m = MotivoRechazo(codigo="CRZ", descripcion="x", activo=True); db.add(m); db.commit()
    svc.validar_paquete(cuello.id, [{"motivo_id": m.id, "cantidad": 2, "destino": "CORTE", "rehacer": True}], db)
    r = db.query(OFPaqueteRechazo).filter_by(paquete_id=cuello.id).one()
    assert svc.estacion_de(r) == "CORTE"
    assert svc.punto_reinicio(r) == "TIZADO"              # rehacer → desde tizado (hint)
    # Corte: tomar (inicio) → terminar (pieza fusible → pasa sola a Fusionado)
    svc.tomar_reproceso(r.id, db); db.refresh(r)
    assert r.estado == "EN_REPROCESO"
    svc.terminar_reproceso(r.id, db); db.refresh(r)
    assert svc.estacion_de(r) == "FUSIONADO"              # handoff
    assert [x.id for x in svc.listar_refusionado(db)] == [r.id]
    assert svc.listar_reprocesos(db) == []                # ya no está en la bandeja de corte
    # Fusionado: iniciar (inicio) → terminar (fin) → reingresa a Calidad
    svc.iniciar_refusionado(r.id, db); db.refresh(r)
    assert svc._refusionado_iniciado(r) and svc.refusionado_desde(r) is not None
    svc.terminar_refusionado(r.id, db)
    db.refresh(r); db.refresh(cuello)
    assert r.estado == RECHAZO_REINGRESADO
    assert cuello.estado == ESTADO_POR_VALIDAR
    assert [h.etapa for h in r.hitos] == ["CORTE", "FUSIONADO", "REINGRESADO"]   # trazabilidad


def test_estacion_y_reinicio(db):
    """El destino define la estación (Corte agrupa tizado/tendido/corte/numerado)."""
    of, sku_id = _mk_multi(db, cantidad=40)               # Delantero (no fus) + Cuello (fus)
    paqs = svc.generar_paquetes(of, [{"sku_id": sku_id, "cantidad": 40}], db)
    delantero = next(p for p in paqs if p.pieza.nombre == "Delantero")
    cuello = next(p for p in paqs if p.pieza.nombre == "Cuello")
    m = MotivoRechazo(codigo="CRD", descripcion="x", activo=True); db.add(m); db.commit()

    def _r(paquete, destino, rehacer=False):
        r = OFPaqueteRechazo(paquete_id=paquete.id, motivo_id=m.id, cantidad=1,
                             destino=destino, rehacer=rehacer)
        db.add(r); db.flush()
        return r

    assert svc.estacion_de(_r(delantero, "TENDIDO")) == "CORTE"
    assert svc.estacion_de(_r(delantero, "CORTE")) == "CORTE"
    assert svc.estacion_de(_r(cuello, "FUSIONADO")) == "FUSIONADO"
    assert svc.estacion_de(_r(delantero, "DESMANCHADO")) == "DESMANCHADO"
    assert svc.estacion_de(_r(delantero, "HABILITADO")) == "HABILITADO"
    # punto de reinicio (hint) solo aplica a la estación de Corte
    assert svc.punto_reinicio(_r(delantero, "TENDIDO")) == "TENDIDO"
    assert svc.punto_reinicio(_r(delantero, "CORTE", rehacer=True)) == "TIZADO"
    assert svc.punto_reinicio(_r(delantero, "DESMANCHADO")) is None


def test_refusionado_directo_en_modulo(db):
    """Defecto con destino Fusionado → aparece en el módulo de Fusionado (no en la bandeja)."""
    of, sku_id = _mk_multi(db, cantidad=40)
    paqs = svc.generar_paquetes(of, [{"sku_id": sku_id, "cantidad": 40}], db)
    cuello = next(p for p in paqs if p.pieza.nombre == "Cuello")
    svc.set_estado_paquete(cuello.id, ESTADO_FUSIONADO, db)
    svc.terminar_fusionado(cuello.id, db)
    m = MotivoRechazo(codigo="CRF", descripcion="x", destino="FUSIONADO", activo=True)
    db.add(m); db.commit()
    svc.validar_paquete(cuello.id, [{"motivo_id": m.id, "cantidad": 1, "destino": "FUSIONADO"}], db)
    r = db.query(OFPaqueteRechazo).filter_by(paquete_id=cuello.id).one()
    assert svc.listar_reprocesos(db) == []                # no está en la bandeja de corte
    assert [x.id for x in svc.listar_refusionado(db)] == [r.id]
    svc.iniciar_refusionado(r.id, db)
    svc.terminar_refusionado(r.id, db)
    db.refresh(cuello)
    assert cuello.estado == ESTADO_POR_VALIDAR


def test_rehacer_cuenta_en_desvio(db):
    of, sku_id, m1, m2 = _mk(db, cantidad=30)              # pieza no fusible
    p = _generar(db, of, sku_id, 30)[0]
    svc.set_estado_paquete(p.id, ESTADO_POR_VALIDAR, db)
    svc.validar_paquete(p.id, [{"motivo_id": m1.id, "cantidad": 4, "destino": "CORTE", "rehacer": True}], db)
    assert svc.rehacer_of(of.id, db) == 4
    assert svc.resumen_desvio(of, db)["rehacer"] == 4
    r = db.query(OFPaqueteRechazo).filter_by(paquete_id=p.id).one()
    svc.reingresar_rechazo(r.id, db)
    assert svc.rehacer_of(of.id, db) == 0                  # ya reingresado, no pendiente de tela


def test_destino_autocompletado_del_defecto(db):
    of, sku_id, m1, m2 = _mk(db, cantidad=30)
    m1.destino = "FUSIONADO"; db.commit()          # el defecto sugiere FUSIONADO
    p = _generar(db, of, sku_id, 30)[0]
    svc.set_estado_paquete(p.id, ESTADO_POR_VALIDAR, db)
    svc.validar_paquete(p.id, [{"motivo_id": m1.id, "cantidad": 2}], db)   # sin destino explícito
    r = db.query(OFPaqueteRechazo).filter_by(paquete_id=p.id).one()
    assert r.destino == "FUSIONADO"


def test_destino_alternativas(db):
    of, sku_id, m1, m2 = _mk(db, cantidad=30)
    m1.destino = "CORTE"; m1.destinos_alt = "MODELISTA"; db.commit()
    assert set(svc.destinos_permitidos(m1)) == {"CORTE", "MODELISTA"}
    p = _generar(db, of, sku_id, 30)[0]
    svc.set_estado_paquete(p.id, ESTADO_POR_VALIDAR, db)
    svc.validar_paquete(p.id, [{"motivo_id": m1.id, "cantidad": 2, "destino": "MODELISTA"}], db)
    r = db.query(OFPaqueteRechazo).filter_by(paquete_id=p.id).one()
    assert r.destino == "MODELISTA"          # alternativa válida aceptada


def test_destino_invalido_usa_catalogo(db):
    of, sku_id, m1, m2 = _mk(db, cantidad=30)
    m1.destino = "FUSIONADO"; m1.destinos_alt = None; db.commit()
    p = _generar(db, of, sku_id, 30)[0]
    svc.set_estado_paquete(p.id, ESTADO_POR_VALIDAR, db)
    svc.validar_paquete(p.id, [{"motivo_id": m1.id, "cantidad": 2, "destino": "CORTE"}], db)  # no permitido
    r = db.query(OFPaqueteRechazo).filter_by(paquete_id=p.id).one()
    assert r.destino == "FUSIONADO"          # se fuerza al del catálogo


def test_generar_nace_habilitado(db):
    of, sku_id, *_ = _mk(db)
    paqs = _generar(db, of, sku_id, 100, size=49)
    assert len(paqs) == 3                       # 49 + 49 + 2
    assert all(p.estado == ESTADO_HABILITADO for p in paqs)
    assert svc.corte_real(of.id, db) == 100
    assert paqs[0].numero_desde == 1 and paqs[0].numero_hasta == 49
    assert paqs[2].numero_desde == 99 and paqs[2].cantidad == 2


def test_validar_sin_rechazos_entrega(db):
    of, sku_id, *_ = _mk(db)
    p = _generar(db, of, sku_id, 30)[0]
    svc.set_estado_paquete(p.id, ESTADO_POR_VALIDAR, db)
    p = svc.validar_paquete(p.id, [], db)
    assert p.estado == ESTADO_ENTREGADO
    assert svc.resumen_paquete(p, db)["aprobadas"] == 30


def test_validar_con_rechazos_standby(db):
    of, sku_id, m1, m2 = _mk(db)
    p = _generar(db, of, sku_id, 30)[0]
    svc.set_estado_paquete(p.id, ESTADO_POR_VALIDAR, db)
    p = svc.validar_paquete(p.id, [
        {"motivo_id": m1.id, "cantidad": 3, "destino": "CORTE"},
    ], db)
    assert p.estado == ESTADO_STANDBY
    r = db.query(OFPaqueteRechazo).filter_by(paquete_id=p.id).one()
    assert r.estado == RECHAZO_PENDIENTE and r.cantidad == 3
    res = svc.resumen_paquete(p, db)
    assert res["en_reproceso"] == 3 and res["aprobadas"] == 27


def test_reingreso_vuelve_a_por_validar(db):
    of, sku_id, m1, m2 = _mk(db)
    p = _generar(db, of, sku_id, 30)[0]
    svc.set_estado_paquete(p.id, ESTADO_POR_VALIDAR, db)
    p = svc.validar_paquete(p.id, [{"motivo_id": m1.id, "cantidad": 2, "destino": "CORTE"}], db)
    r = db.query(OFPaqueteRechazo).filter_by(paquete_id=p.id).one()
    svc.reingresar_rechazo(r.id, db)
    db.refresh(p)
    assert p.estado == ESTADO_POR_VALIDAR             # todas las piezas volvieron
    p = svc.validar_paquete(p.id, [], db)             # re-validación OK
    assert p.estado == ESTADO_ENTREGADO


def test_rehacer_espera_tela(db):
    of, sku_id, m1, m2 = _mk(db, cantidad=30)
    m1.destino = "CORTE"; db.commit()
    p = _generar(db, of, sku_id, 30)[0]
    svc.set_estado_paquete(p.id, ESTADO_POR_VALIDAR, db)
    svc.validar_paquete(p.id, [{"motivo_id": m1.id, "cantidad": 3, "destino": "CORTE", "rehacer": True}], db)
    r = db.query(OFPaqueteRechazo).filter_by(paquete_id=p.id).one()
    svc.marcar_falta_tela(r.id, db)                       # Corte: no hay tela
    db.refresh(r); assert r.estado == "ESPERA_TELA"
    assert svc.espera_tela_of(of.id, db) == 3
    with pytest.raises(HTTPException):                    # no reingresa mientras espera tela
        svc.reingresar_rechazo(r.id, db)
    svc.registrar_solped([r.id], "SP-1", db)              # Planeamiento registra la SOLPED
    svc.marcar_tela_recibida(r.id, db)                    # llega tela → a Corte
    db.refresh(r); assert r.estado == "EN_REPROCESO"
    svc.reingresar_rechazo(r.id, db)
    db.refresh(r); assert r.estado == RECHAZO_REINGRESADO


def test_espera_tela_no_esta_en_bandeja_corte(db):
    of, sku_id, m1, m2 = _mk(db, cantidad=30)
    m1.destino = "CORTE"; db.commit()
    p = _generar(db, of, sku_id, 30)[0]
    svc.set_estado_paquete(p.id, ESTADO_POR_VALIDAR, db)
    svc.validar_paquete(p.id, [{"motivo_id": m1.id, "cantidad": 3, "destino": "CORTE", "rehacer": True}], db)
    r = db.query(OFPaqueteRechazo).filter_by(paquete_id=p.id).one()
    assert len(svc.listar_reprocesos(db)) == 1        # en bandeja de Corte
    svc.marcar_falta_tela(r.id, db)
    assert svc.listar_reprocesos(db) == []            # sale de Corte
    assert [x.id for x in svc.listar_espera_tela(db)] == [r.id]   # aparece en Planeamiento


def test_solped_obligatoria_y_multiple(db):
    of, sku_id, m1, m2 = _mk(db, cantidad=30)
    m1.destino = "CORTE"; db.commit()
    p = _generar(db, of, sku_id, 30)[0]
    svc.set_estado_paquete(p.id, ESTADO_POR_VALIDAR, db)
    svc.validar_paquete(p.id, [
        {"motivo_id": m1.id, "cantidad": 2, "destino": "CORTE", "rehacer": True},
        {"motivo_id": m2.id, "cantidad": 1, "destino": "CORTE", "rehacer": True},
    ], db)
    rs = db.query(OFPaqueteRechazo).filter_by(paquete_id=p.id).all()
    for r in rs:
        svc.marcar_falta_tela(r.id, db)
    ids = [r.id for r in rs]
    # sin SOLPED no deja recibir
    with pytest.raises(HTTPException):
        svc.marcar_tela_recibida(ids[0], db)
    # una SOLPED cubre las 2 piezas
    n = svc.registrar_solped(ids, "SP-1001", db)
    assert n == 2
    for r in rs:
        db.refresh(r); assert r.solped == "SP-1001"
    svc.marcar_tela_recibida(ids[0], db)          # ahora sí
    db.refresh(rs[0]); assert rs[0].estado == "EN_REPROCESO"


def test_rehacer_default_irrecuperable(db):
    of, sku_id, m1, m2 = _mk(db, cantidad=30)
    m1.destino = "CORTE"; m1.rehacer_default = True; db.commit()   # tipo hueco
    p = _generar(db, of, sku_id, 30)[0]
    svc.set_estado_paquete(p.id, ESTADO_POR_VALIDAR, db)
    # aunque no se marque rehacer, se fuerza por ser irrecuperable
    svc.validar_paquete(p.id, [{"motivo_id": m1.id, "cantidad": 2, "destino": "CORTE"}], db)
    r = db.query(OFPaqueteRechazo).filter_by(paquete_id=p.id).one()
    assert r.rehacer is True
    assert svc.rehacer_of(of.id, db) == 2


def test_rehacer_mantiene_entregable_y_merma_material(db):
    of, sku_id, m1, m2 = _mk(db, cantidad=30)
    p = _generar(db, of, sku_id, 30)[0]
    svc.set_estado_paquete(p.id, ESTADO_POR_VALIDAR, db)
    # rehacer 4: la vieja se descarta (merma material) + se corta nueva → stand-by
    p = svc.validar_paquete(p.id, [{"motivo_id": m1.id, "cantidad": 4, "destino": "CORTE", "rehacer": True}], db)
    assert p.estado == ESTADO_STANDBY
    assert svc.merma_of(of.id, db) == 4               # material desperdiciado
    des = svc.resumen_desvio(of, db)
    assert des["real"] == 30 and des["entregable"] == 30 and des["merma"] == 4  # entregable no baja


def test_validar_estado_invalido(db):
    of, sku_id, *_ = _mk(db)
    p = _generar(db, of, sku_id, 30)[0]              # HABILITADO
    with pytest.raises(HTTPException) as e:
        svc.validar_paquete(p.id, [], db)
    assert e.value.status_code == 400


def test_rechazo_excede_cantidad(db):
    of, sku_id, m1, m2 = _mk(db)
    p = _generar(db, of, sku_id, 10)[0]
    svc.set_estado_paquete(p.id, ESTADO_POR_VALIDAR, db)
    with pytest.raises(HTTPException) as e:
        svc.validar_paquete(p.id, [{"motivo_id": m1.id, "cantidad": 11, "destino": "CORTE"}], db)
    assert e.value.status_code == 400


def test_no_entrega_con_rechazos_abiertos(db):
    of, sku_id, m1, m2 = _mk(db)
    p = _generar(db, of, sku_id, 30)[0]
    svc.set_estado_paquete(p.id, ESTADO_POR_VALIDAR, db)
    svc.validar_paquete(p.id, [{"motivo_id": m1.id, "cantidad": 2, "destino": "CORTE"}], db)
    with pytest.raises(HTTPException) as e:           # STAND_BY → ENTREGADO no permitido
        svc.set_estado_paquete(p.id, ESTADO_ENTREGADO, db)
    assert e.value.status_code == 400


def test_cola_calidad_transversal(db):
    of, sku_id, m1, m2 = _mk(db)
    paqs = _generar(db, of, sku_id, 100)          # 3 paquetes, todos HABILITADO
    # ninguno visible aún (siguen habilitados)
    assert svc.listar_cola_calidad(db, "pendientes") == []
    # enviar dos a calidad; uno queda en stand-by
    svc.set_estado_paquete(paqs[0].id, ESTADO_POR_VALIDAR, db)
    svc.set_estado_paquete(paqs[1].id, ESTADO_POR_VALIDAR, db)
    svc.validar_paquete(paqs[1].id, [{"motivo_id": m1.id, "cantidad": 2, "destino": "CORTE"}], db)
    pend = svc.listar_cola_calidad(db, "pendientes")
    assert len(pend) == 2                                       # por_validar + stand_by
    assert {p.estado for p in pend} == {ESTADO_POR_VALIDAR, ESTADO_STANDBY}
    assert [p.id for p in svc.listar_cola_calidad(db, "standby")] == [paqs[1].id]
    assert [p.id for p in svc.listar_cola_calidad(db, "por_validar")] == [paqs[0].id]


def test_bandeja_reprocesos(db):
    of, sku_id, m1, m2 = _mk(db)                    # pieza no fusible "Delantero"
    m1.destino = "CORTE"; m2.destino = "HABILITADO"; db.commit()
    p = _generar(db, of, sku_id, 30)[0]
    svc.set_estado_paquete(p.id, ESTADO_POR_VALIDAR, db)
    svc.validar_paquete(p.id, [
        {"motivo_id": m1.id, "cantidad": 2, "destino": "CORTE"},
        {"motivo_id": m2.id, "cantidad": 1, "destino": "HABILITADO"},
    ], db)
    abiertos = svc.listar_reprocesos(db)
    assert len(abiertos) == 2
    grupos = {svc.grupo_reproceso(r) for r in abiertos}    # estación actual
    assert grupos == {"CORTE", "HABILITADO"}
    assert len(svc.listar_reprocesos(db, area="CORTE")) == 1    # filtro por estación
    # Corte (no fusible): tomar → terminar → reingresa y sale de la bandeja
    rc = next(r for r in abiertos if r.destino == "CORTE")
    svc.tomar_reproceso(rc.id, db)
    svc.terminar_reproceso(rc.id, db); db.refresh(rc)
    assert rc.estado == RECHAZO_REINGRESADO
    assert len(svc.listar_reprocesos(db)) == 1             # queda el de habilitado
    # filtro por OF inexistente → vacío
    assert svc.listar_reprocesos(db, of_id=99999) == []


def test_desmanchado_va_a_dar_ok(db):
    of, sku_id, m1, m2 = _mk(db)
    m1.destino = "DESMANCHADO"; db.commit()
    p = _generar(db, of, sku_id, 30)[0]
    svc.set_estado_paquete(p.id, ESTADO_POR_VALIDAR, db)
    svc.validar_paquete(p.id, [{"motivo_id": m1.id, "cantidad": 2, "destino": "DESMANCHADO"}], db)
    r = db.query(OFPaqueteRechazo).filter_by(paquete_id=p.id).one()
    assert svc.listar_reprocesos(db) == []                 # ya no está en la bandeja de corte
    assert [x.id for x in svc.listar_para_ok(db)] == [r.id]
    svc.dar_ok(r.id, db)
    db.refresh(r); db.refresh(p)
    assert r.estado == RECHAZO_REINGRESADO and p.estado == ESTADO_POR_VALIDAR


def test_gerencia_aprobar(db):
    of, sku_id, m1, m2 = _mk(db)
    m1.destino = "GERENCIA"; db.commit()
    p = _generar(db, of, sku_id, 30)[0]
    svc.set_estado_paquete(p.id, ESTADO_POR_VALIDAR, db)
    svc.validar_paquete(p.id, [{"motivo_id": m1.id, "cantidad": 2, "destino": "GERENCIA"}], db)
    r = db.query(OFPaqueteRechazo).filter_by(paquete_id=p.id).one()
    assert [x.id for x in svc.listar_gerencia(db)] == [r.id]
    assert svc.listar_reprocesos(db) == []                 # no está en corte
    svc.aprobar_gerencia(r.id, db)
    db.refresh(r); db.refresh(p)
    assert r.estado == RECHAZO_REINGRESADO and p.estado == ESTADO_POR_VALIDAR


def test_gerencia_rehacer(db):
    of, sku_id, m1, m2 = _mk(db)
    m1.destino = "GERENCIA"; db.commit()
    p = _generar(db, of, sku_id, 30)[0]
    svc.set_estado_paquete(p.id, ESTADO_POR_VALIDAR, db)
    svc.validar_paquete(p.id, [{"motivo_id": m1.id, "cantidad": 2, "destino": "GERENCIA"}], db)
    r = db.query(OFPaqueteRechazo).filter_by(paquete_id=p.id).one()
    svc.rehacer_gerencia(r.id, db); db.refresh(r)
    assert r.destino == "CORTE" and r.rehacer is True and r.estado == RECHAZO_PENDIENTE
    assert [x.id for x in svc.listar_reprocesos(db)] == [r.id]   # ahora sí en Corte
    assert svc.punto_reinicio(r) == "TIZADO"                # rehacer desde cero


def test_resumen_calidad_derivado(db):
    of, sku_id, m1, m2 = _mk(db, cantidad=100)
    paqs = _generar(db, of, sku_id, 100)          # 3 paquetes (49+49+2)
    r = svc.resumen_calidad_por_talla(of.id, db)[sku_id]
    assert r["numeracion"] and r["calidad_pct"] == 0 and not r["calidad_done"]
    # entregar los dos primeros (98 de 100)
    for p in paqs[:2]:
        svc.set_estado_paquete(p.id, ESTADO_POR_VALIDAR, db)
        svc.validar_paquete(p.id, [], db)
    of_res = svc.resumen_calidad_of(of.id, db)
    assert of_res["hay_hoja"] and of_res["calidad_pct"] == 98 and not of_res["calidad_done"]
    # entregar el tercero → calidad completa
    svc.set_estado_paquete(paqs[2].id, ESTADO_POR_VALIDAR, db)
    svc.validar_paquete(paqs[2].id, [], db)
    assert svc.resumen_calidad_of(of.id, db)["calidad_done"] is True


# --------------------------------------------------------------------------- #
# HN — Candado de la hoja de numeración + reapertura + tiempos F4
# --------------------------------------------------------------------------- #

def test_generar_cierra_la_hoja(db):
    of, sku_id, m1, m2 = _mk(db, cantidad=30)
    assert of.hoja_numeracion_cerrada is False
    _generar(db, of, sku_id, 30)
    assert of.hoja_numeracion_cerrada is True
    assert of.hoja_numeracion_cerrada_at is not None
    # segundo intento de generar: bloqueado por el candado
    with pytest.raises(HTTPException):
        _generar(db, of, sku_id, 30)


def test_generar_marca_inicio_f4_si_no_estaba(db):
    of, sku_id, m1, m2 = _mk(db, cantidad=30)
    ft_antes = db.query(OFFaseTiempos).filter_by(of_id=of.id, fase_id="F4").first()
    assert ft_antes is None
    _generar(db, of, sku_id, 30)
    ft = db.query(OFFaseTiempos).filter_by(of_id=of.id, fase_id="F4").first()
    assert ft is not None and ft.inicio_real is not None and ft.fin_real is None


def test_iniciar_numeracion_es_idempotente(db):
    of, sku_id, m1, m2 = _mk(db, cantidad=30)
    ft1 = svc.iniciar_numeracion(of, db, usuario_id=None)
    primero = ft1.inicio_real
    ft2 = svc.iniciar_numeracion(of, db, usuario_id=None)
    assert ft2.inicio_real == primero        # no lo pisa


def test_reabrir_sin_estar_cerrada_falla(db):
    of, sku_id, m1, m2 = _mk(db, cantidad=30)
    with pytest.raises(HTTPException):
        svc.reabrir_hoja_numeracion(of, "motivo", db)


def test_reabrir_sin_motivo_falla(db):
    of, sku_id, m1, m2 = _mk(db, cantidad=30)
    _generar(db, of, sku_id, 30)
    with pytest.raises(HTTPException):
        svc.reabrir_hoja_numeracion(of, "   ", db)


def test_reabrir_permite_regenerar_y_queda_auditado(db):
    of, sku_id, m1, m2 = _mk(db, cantidad=30)
    _generar(db, of, sku_id, 30)
    assert of.hoja_numeracion_cerrada is True

    svc.reabrir_hoja_numeracion(of, "typo: eran 30 no 35", db, usuario_id=None)
    assert of.hoja_numeracion_cerrada is False
    assert of.hoja_numeracion_cerrada_por is None

    aud = svc.listar_reaperturas_numeracion(of.id, db)
    assert len(aud) == 1 and "typo" in aud[0].motivo

    # la fase F4 vuelve a cero (nuevo ciclo)
    ft = db.query(OFFaseTiempos).filter_by(of_id=of.id, fase_id="F4").first()
    assert ft.inicio_real is None and ft.fin_real is None

    # ahora sí se puede regenerar
    paqs = _generar(db, of, sku_id, 35)
    assert svc.corte_real(of.id, db) == 35
    assert of.hoja_numeracion_cerrada is True


def test_bultos_avanzados_bloquea_regenerar_incluso_reabierta(db):
    """El candado es independiente del seguro por bultos ya avanzados: aunque se
    reabra, si ya hay trabajo real hecho (bultos fuera de HABILITADO), no se borra."""
    of, sku_id, m1, m2 = _mk(db, cantidad=30)
    paqs = _generar(db, of, sku_id, 30)
    svc.set_estado_paquete(paqs[0].id, ESTADO_POR_VALIDAR, db)   # avanza uno

    svc.reabrir_hoja_numeracion(of, "quiero corregir", db)
    assert of.hoja_numeracion_cerrada is False

    with pytest.raises(HTTPException):
        _generar(db, of, sku_id, 30)


def test_fin_numeracion_automatico_al_vaciar_habilitado(db):
    of, sku_id, m1, m2 = _mk(db, cantidad=30)
    paqs = _generar(db, of, sku_id, 30)
    ft = db.query(OFFaseTiempos).filter_by(of_id=of.id, fase_id="F4").first()
    assert ft.fin_real is None

    # mueve todos los bultos fuera de HABILITADO (la pieza de _mk no fusiona)
    for p in paqs:
        svc.set_estado_paquete(p.id, ESTADO_POR_VALIDAR, db)

    db.refresh(ft)
    assert ft.fin_real is not None


def test_fin_numeracion_no_se_marca_si_queda_algo_habilitado(db):
    of, sku_id = _mk_multi(db, cantidad=40)   # 2 piezas: 1 fusible, 1 no
    paqs = svc.generar_paquetes(of, [{"sku_id": sku_id, "cantidad": 40}], db)
    delantero = next(p for p in paqs if p.pieza.nombre == "Delantero")
    svc.set_estado_paquete(delantero.id, ESTADO_POR_VALIDAR, db)   # solo uno de los dos

    ft = db.query(OFFaseTiempos).filter_by(of_id=of.id, fase_id="F4").first()
    assert ft.fin_real is None   # el Cuello (fusible) sigue HABILITADO
