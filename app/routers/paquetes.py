"""
Router de paquetes de numeración + Calidad + Reprocesos.
Prefijo: /paquetes
"""
from typing import List, Optional
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.models.of import OrdenFabricacion, OFTallaDistribucion, EstadoOF
from app.models.catalogo import PrendaSku
from app.models.paquete import OFPaquete
from app.models.fase import OFFaseTiempos
from app.models.usuario import Usuario
from app.core.auth import get_current_user, get_rol
from app.core.templates import templates
from app.core.websocket_manager import ws_manager
from app.services import paquete_service

router = APIRouter()

# Quién puede numerar/habilitar y quién valida en calidad / reprocesa
ROLES_NUMERAR = {"ADMIN", "PLANEADOR", "SUPERVISOR_CORTE"}
ROLES_CALIDAD = {"ADMIN", "PLANEADOR", "SUPERVISOR_CORTE", "CALIDAD"}
ROLES_REPROCESO = {"ADMIN", "SUPERVISOR_CORTE", "CORTE", "FUSIONADO"}
ROLES_FUSIONADO = {"ADMIN", "SUPERVISOR_CORTE", "FUSIONADO"}
ROLES_PLANEAMIENTO = {"ADMIN", "PLANEADOR"}
ROLES_PLANTA_CORTE = ROLES_CALIDAD | ROLES_REPROCESO | ROLES_FUSIONADO
ROLES_GERENCIA = {"ADMIN", "GERENTE_PLANTA"}          # aprobación del gerente de planta
ROLES_DAR_OK = {"ADMIN", "SUPERVISOR_CORTE"}          # Modelista / Externo / Desmanchado dan OK
ROLES_REABRIR_NUMERACION = {"ADMIN", "GERENTE_PLANTA", "SUPERVISOR_CORTE", "JEFE_PLANTA"}


def _puede(user, roles):
    return get_rol(user) in roles


class GenerarReq(BaseModel):
    size: Optional[int] = None
    reales: List[dict] = []   # [{"sku_id": int, "cantidad": int}, ...] ORDENADO


class EstadoReq(BaseModel):
    estado: str
    motivo: Optional[str] = None


class RechazoItem(BaseModel):
    motivo_id: int
    cantidad: int
    destino: Optional[str] = None       # área destino (default = del defecto)
    rehacer: bool = False               # corta nueva (usa tela)


class ValidarReq(BaseModel):
    rechazos: List[RechazoItem] = []


class TopeReq(BaseModel):
    unidades_por_paquete: Optional[int] = None


class ReabrirReq(BaseModel):
    motivo: str


class AvanzarReq(BaseModel):
    grupo: str   # fusion | calidad | todo | fusionado_listo


def _rechazo_dict(r) -> dict:
    return {
        "id": r.id, "motivo_id": r.motivo_id,
        "codigo": (r.motivo.codigo if r.motivo else None),
        "descripcion": (r.motivo.descripcion if r.motivo else None),
        "cantidad": r.cantidad, "destino": r.destino, "rehacer": r.rehacer,
        "estado": r.estado,
    }


def _paquete_dict(p: OFPaquete, db: Session) -> dict:
    d = {
        "id": p.id, "numero": p.numero, "sku_id": p.sku_id,
        "pieza_id": p.pieza_id, "pieza": p.pieza_nombre, "fusiona": p.fusiona,
        "talla": p.talla, "color": p.color,
        "numero_desde": p.numero_desde, "numero_hasta": p.numero_hasta,
        "cantidad": p.cantidad, "estado": p.estado,
        "fus_en_proceso": p.fusionado_en_proceso,
        "fus_inicio": p.fusionado_inicio.strftime("%d/%m %H:%M") if p.fusionado_inicio else None,
        "fus_fin": p.fusionado_fin.strftime("%d/%m %H:%M") if p.fusionado_fin else None,
        "rechazos": [_rechazo_dict(r) for r in p.rechazos],
    }
    d.update(paquete_service.resumen_paquete(p, db))
    return d


# --- Cola de Calidad (transversal a todas las OFs) --------------------------
# OJO: estas rutas deben ir ANTES de "/{of_id}" y "/api/{of_id}/data".
@router.get("/calidad", response_class=HTMLResponse)
def cola_calidad_page(request: Request, of: Optional[int] = None,
                      db: Session = Depends(get_db),
                      current_user: Usuario = Depends(get_current_user)):
    if not _puede(current_user, ROLES_CALIDAD):
        raise HTTPException(403, "Sin permiso de calidad")
    of_ctx = None
    if of:
        o = db.query(OrdenFabricacion).filter_by(id=of).first()
        if o:
            of_ctx = {"id": o.id, "numero_of": o.numero_of, "cliente": o.cliente}
    return templates.TemplateResponse("of/calidad_cola.html", {
        "request": request, "current_user": current_user, "rol": get_rol(current_user),
        "puede_calidad": _puede(current_user, ROLES_CALIDAD),
        "puede_reproceso": _puede(current_user, ROLES_REPROCESO),
        "of_ctx": of_ctx,
    })


@router.get("/api/calidad/data")
def cola_calidad_data(filtro: str = "pendientes", of: Optional[int] = None,
                      db: Session = Depends(get_db),
                      current_user: Usuario = Depends(get_current_user)):
    if not _puede(current_user, ROLES_CALIDAD):
        raise HTTPException(403, "Sin permiso de calidad")
    paqs = paquete_service.listar_cola_calidad(db, filtro, of_id=of)
    items = []
    for p in paqs:
        d = _paquete_dict(p, db)
        d["of_id"] = p.of_id
        d["numero_of"] = p.of.numero_of if p.of else None
        d["prenda"] = (p.of.prenda_catalogo.codigo if (p.of and p.of.prenda_catalogo)
                       else (p.of.tipo_prenda if p.of else None))
        items.append(d)
    return {
        "filtro": filtro,
        "paquetes": items,
        "motivos": [{"id": m.id, "codigo": m.codigo, "descripcion": m.descripcion,
                     "destino": m.destino, "destinos_alt": m.destinos_alt,
                     "rehacer_default": m.rehacer_default}
                    for m in paquete_service.listar_motivos(db)],
    }


# --- Panel de Planeamiento (tela + órdenes) ---------------------------------
@router.get("/planeamiento", response_class=HTMLResponse)
def planeamiento_page(request: Request, db: Session = Depends(get_db),
                      current_user: Usuario = Depends(get_current_user)):
    if not _puede(current_user, ROLES_PLANEAMIENTO):
        raise HTTPException(403, "Sin permiso de planeamiento")
    return templates.TemplateResponse("of/planeamiento.html", {
        "request": request, "current_user": current_user, "rol": get_rol(current_user),
        "puede_planeamiento": _puede(current_user, ROLES_PLANEAMIENTO),
    })


@router.get("/api/planeamiento/data")
def planeamiento_data(db: Session = Depends(get_db), current_user: Usuario = Depends(get_current_user)):
    if not _puede(current_user, ROLES_PLANEAMIENTO):
        raise HTTPException(403, "Sin permiso de planeamiento")
    # 1) Requerimientos de tela (piezas esperando tela)
    tela = []
    for r in paquete_service.listar_espera_tela(db):
        p = r.paquete
        of = p.of if p else None
        tela.append({
            "rechazo_id": r.id, "cantidad": r.cantidad,
            "codigo": r.motivo.codigo if r.motivo else None,
            "descripcion": r.motivo.descripcion if r.motivo else None,
            "pieza": p.pieza_nombre if p else None,
            "talla": p.talla if p else None, "color": p.color if p else None,
            "of_id": of.id if of else None, "numero_of": of.numero_of if of else None,
            "desde": r.created_at.strftime("%d/%m %H:%M") if r.created_at else None,
            "solped": r.solped,
        })
    # 2) OFs activas con su resumen de tela
    ofs = []
    for of in (db.query(OrdenFabricacion).filter(OrdenFabricacion.estado == EstadoOF.ACTIVA)
               .order_by(OrdenFabricacion.numero_of).all()):
        d = paquete_service.resumen_desvio(of, db)
        ofs.append({
            "id": of.id, "numero_of": of.numero_of,
            "prenda": (of.prenda_catalogo.codigo if of.prenda_catalogo else of.tipo_prenda),
            "proyectado": d["proyectado"], "real": d["real"], "desvio": d["desvio"],
            "rehacer": d["rehacer"], "espera_tela": d["espera_tela"], "merma": d["merma"],
        })
    # 3) KPIs del tablero
    from app.models.planta import PlantaExterna
    plantas = db.query(PlantaExterna).filter_by(activo=True).count()
    kpis = {
        "ordenes_activas": len(ofs),
        "plantas": plantas,
        "espera_tela": sum(t["cantidad"] for t in tela),
        "solped_pendientes": sum(1 for t in tela if not (t["solped"] or "").strip()),
    }
    return {"tela": tela, "ofs": ofs, "kpis": kpis}


class SolpedReq(BaseModel):
    rechazo_ids: List[int] = []
    solped: str


@router.post("/api/planeamiento/solped")
def registrar_solped(body: SolpedReq, db: Session = Depends(get_db),
                     current_user: Usuario = Depends(get_current_user)):
    if not _puede(current_user, ROLES_PLANEAMIENTO):
        raise HTTPException(403, "Sin permiso de planeamiento")
    n = paquete_service.registrar_solped(body.rechazo_ids, body.solped, db, usuario_id=current_user.id)
    return {"actualizados": n}


# --- Bandeja de reprocesos (transversal, por operario de área) --------------
@router.get("/reprocesos", response_class=HTMLResponse)
def bandeja_reprocesos_page(request: Request, db: Session = Depends(get_db),
                            current_user: Usuario = Depends(get_current_user)):
    if not _puede(current_user, ROLES_REPROCESO):
        raise HTTPException(403, "Sin permiso de reproceso")
    return templates.TemplateResponse("of/reprocesos.html", {
        "request": request, "current_user": current_user, "rol": get_rol(current_user),
        "puede_reproceso": _puede(current_user, ROLES_REPROCESO),
    })


@router.get("/api/reprocesos/data")
def bandeja_reprocesos_data(of_id: Optional[int] = None, area: Optional[str] = None,
                            db: Session = Depends(get_db),
                            current_user: Usuario = Depends(get_current_user)):
    if not _puede(current_user, ROLES_REPROCESO):
        raise HTTPException(403, "Sin permiso de reproceso")
    rechazos = paquete_service.listar_reprocesos(db, of_id, area)
    items = []
    ofs = {}
    for r in rechazos:
        p = r.paquete
        of = p.of if p else None
        if of:
            ofs[of.id] = of.numero_of
        items.append({
            **_rechazo_dict(r),
            "grupo": paquete_service.grupo_reproceso(r),      # estación actual
            "reinicio": paquete_service.punto_reinicio(r),    # desde qué fase rehacer (hint)
            "paquete_id": p.id if p else None,
            "paquete_numero": p.numero if p else None,
            "pieza": p.pieza_nombre if p else None,
            "talla": p.talla if p else None,
            "color": p.color if p else None,
            "numeracion": (f"{p.numero_desde}–{p.numero_hasta}" if p else None),
            "of_id": of.id if of else None,
            "numero_of": of.numero_of if of else None,
        })
    return {"rechazos": items,
            "areas": paquete_service.areas_reproceso(db, of_id),
            "ofs": [{"id": k, "numero_of": v} for k, v in sorted(ofs.items())]}


# --- Hub Planta de corte (seguimiento + fusionado + calidad + reprocesos) ---
@router.get("/planta-corte", response_class=HTMLResponse)
def planta_corte_page(request: Request, db: Session = Depends(get_db),
                      current_user: Usuario = Depends(get_current_user)):
    if not _puede(current_user, ROLES_PLANTA_CORTE):
        raise HTTPException(403, "Sin permiso")
    ofs = (db.query(OrdenFabricacion)
           .filter(OrdenFabricacion.estado == EstadoOF.ACTIVA)
           .order_by(OrdenFabricacion.numero_of).all())
    ofs_ctx = [{
        "id": o.id, "numero_of": o.numero_of,
        "prenda": (o.prenda_catalogo.codigo if o.prenda_catalogo else o.tipo_prenda),
        "cliente": o.cliente, "prendas": o.total_juegos,
    } for o in ofs]
    return templates.TemplateResponse("of/planta_corte.html", {
        "request": request, "current_user": current_user, "rol": get_rol(current_user),
        "ofs": ofs_ctx,
    })


# --- Item de rechazo para las vistas de gerencia / dar OK -------------------
def _rechazo_vista(r) -> dict:
    p = r.paquete
    of = p.of if p else None
    return {
        **_rechazo_dict(r),
        "paquete_numero": p.numero if p else None,
        "pieza": p.pieza_nombre if p else None,
        "talla": p.talla if p else None,
        "color": p.color if p else None,
        "numeracion": (f"{p.numero_desde}–{p.numero_hasta}" if p else None),
        "of_id": of.id if of else None,
        "numero_of": of.numero_of if of else None,
    }


# --- Aprobación de gerencia (gerente de planta) -----------------------------
@router.get("/gerencia", response_class=HTMLResponse)
def gerencia_page(request: Request, db: Session = Depends(get_db),
                  current_user: Usuario = Depends(get_current_user)):
    if not _puede(current_user, ROLES_GERENCIA):
        raise HTTPException(403, "Sin permiso de aprobación de gerencia")
    return templates.TemplateResponse("of/gerencia.html", {
        "request": request, "current_user": current_user, "rol": get_rol(current_user),
    })


@router.get("/api/gerencia/data")
def gerencia_data(of_id: Optional[int] = None, db: Session = Depends(get_db),
                  current_user: Usuario = Depends(get_current_user)):
    if not _puede(current_user, ROLES_GERENCIA):
        raise HTTPException(403, "Sin permiso de aprobación de gerencia")
    return {"rechazos": [_rechazo_vista(r) for r in paquete_service.listar_gerencia(db, of_id)]}


@router.post("/api/rechazo/{rechazo_id}/gerencia/aprobar")
def gerencia_aprobar(rechazo_id: int, db: Session = Depends(get_db),
                     current_user: Usuario = Depends(get_current_user)):
    if not _puede(current_user, ROLES_GERENCIA):
        raise HTTPException(403, "Sin permiso de aprobación de gerencia")
    r = paquete_service.aprobar_gerencia(rechazo_id, db, usuario_id=current_user.id)
    if r.paquete:
        ws_manager.notify_of(r.paquete.of_id, "paquetes", {"accion": "gerencia_aprobar", "por": current_user.nombre})
    return _rechazo_dict(r)


@router.post("/api/rechazo/{rechazo_id}/gerencia/rehacer")
def gerencia_rehacer(rechazo_id: int, db: Session = Depends(get_db),
                     current_user: Usuario = Depends(get_current_user)):
    if not _puede(current_user, ROLES_GERENCIA):
        raise HTTPException(403, "Sin permiso de aprobación de gerencia")
    r = paquete_service.rehacer_gerencia(rechazo_id, db, usuario_id=current_user.id)
    if r.paquete:
        ws_manager.notify_of(r.paquete.of_id, "paquetes", {"accion": "gerencia_rehacer", "por": current_user.nombre})
    return _rechazo_dict(r)


# --- Dar OK (Modelista / Externo / Desmanchado) -----------------------------
@router.get("/derivados", response_class=HTMLResponse)
def derivados_page(request: Request, db: Session = Depends(get_db),
                   current_user: Usuario = Depends(get_current_user)):
    if not _puede(current_user, ROLES_DAR_OK):
        raise HTTPException(403, "Sin permiso")
    return templates.TemplateResponse("of/derivados.html", {
        "request": request, "current_user": current_user, "rol": get_rol(current_user),
    })


@router.get("/api/derivados/data")
def derivados_data(of_id: Optional[int] = None, db: Session = Depends(get_db),
                   current_user: Usuario = Depends(get_current_user)):
    if not _puede(current_user, ROLES_DAR_OK):
        raise HTTPException(403, "Sin permiso")
    return {"rechazos": [_rechazo_vista(r) for r in paquete_service.listar_para_ok(db, of_id)]}


@router.post("/api/rechazo/{rechazo_id}/ok")
def dar_ok(rechazo_id: int, db: Session = Depends(get_db),
           current_user: Usuario = Depends(get_current_user)):
    if not _puede(current_user, ROLES_DAR_OK):
        raise HTTPException(403, "Sin permiso")
    r = paquete_service.dar_ok(rechazo_id, db, usuario_id=current_user.id)
    if r.paquete:
        ws_manager.notify_of(r.paquete.of_id, "paquetes", {"accion": "dar_ok", "por": current_user.nombre})
    return _rechazo_dict(r)


# --- Módulo de Fusionado (transversal, por operario de fusionado) -----------
@router.get("/fusionado", response_class=HTMLResponse)
def fusionado_page(request: Request, db: Session = Depends(get_db),
                   current_user: Usuario = Depends(get_current_user)):
    if not _puede(current_user, ROLES_FUSIONADO):
        raise HTTPException(403, "Sin permiso de fusionado")
    return templates.TemplateResponse("of/fusionado.html", {
        "request": request, "current_user": current_user, "rol": get_rol(current_user),
        "puede_fusionado": _puede(current_user, ROLES_FUSIONADO),
    })


@router.get("/api/fusionado/data")
def fusionado_data(of_id: Optional[int] = None, db: Session = Depends(get_db),
                   current_user: Usuario = Depends(get_current_user)):
    if not _puede(current_user, ROLES_FUSIONADO):
        raise HTTPException(403, "Sin permiso de fusionado")
    bultos = paquete_service.listar_fusionado(db, of_id)
    items, ofs = [], {}
    for p in bultos:
        of = p.of
        if of:
            ofs[of.id] = of.numero_of
        d = _paquete_dict(p, db)
        d["of_id"] = p.of_id
        d["numero_of"] = of.numero_of if of else None
        items.append(d)
    # Re-fusionado: piezas rechazadas por Calidad que vuelven a fusionarse
    refus = []
    for r in paquete_service.listar_refusionado(db, of_id):
        p = r.paquete
        of = p.of if p else None
        if of:
            ofs[of.id] = of.numero_of
        desde = paquete_service.refusionado_desde(r)
        refus.append({
            **_rechazo_dict(r),
            "en_proceso": paquete_service._refusionado_iniciado(r),
            "desde": desde.strftime("%d/%m %H:%M") if desde else None,
            "paquete_numero": p.numero if p else None,
            "pieza": p.pieza_nombre if p else None,
            "talla": p.talla if p else None,
            "color": p.color if p else None,
            "numeracion": (f"{p.numero_desde}–{p.numero_hasta}" if p else None),
            "of_id": of.id if of else None,
            "numero_of": of.numero_of if of else None,
        })
    return {"bultos": items, "refusionado": refus,
            "ofs": [{"id": k, "numero_of": v} for k, v in sorted(ofs.items())]}


@router.post("/api/paquete/{paquete_id}/fusionado/iniciar")
def fus_iniciar(paquete_id: int, db: Session = Depends(get_db),
                current_user: Usuario = Depends(get_current_user)):
    if not _puede(current_user, ROLES_FUSIONADO):
        raise HTTPException(403, "Sin permiso de fusionado")
    p = paquete_service.iniciar_fusionado(paquete_id, db, usuario_id=current_user.id)
    return _paquete_dict(p, db)


@router.post("/api/paquete/{paquete_id}/fusionado/terminar")
def fus_terminar(paquete_id: int, db: Session = Depends(get_db),
                 current_user: Usuario = Depends(get_current_user)):
    if not _puede(current_user, ROLES_FUSIONADO):
        raise HTTPException(403, "Sin permiso de fusionado")
    p = paquete_service.terminar_fusionado(paquete_id, db, usuario_id=current_user.id)
    ws_manager.notify_of(p.of_id, "paquetes", {"accion": "fusionado_fin", "por": current_user.nombre})
    return _paquete_dict(p, db)


class FusLoteReq(BaseModel):
    accion: str   # iniciar | terminar


@router.post("/api/{of_id}/talla/{sku_id}/fusionado")
def fus_lote(of_id: int, sku_id: int, body: FusLoteReq, db: Session = Depends(get_db),
             current_user: Usuario = Depends(get_current_user)):
    if not _puede(current_user, ROLES_FUSIONADO):
        raise HTTPException(403, "Sin permiso de fusionado")
    n = paquete_service.avanzar_fusionado_talla(of_id, sku_id, body.accion, db, usuario_id=current_user.id)
    ws_manager.notify_of(of_id, "paquetes", {"accion": "fusionado_lote", "por": current_user.nombre})
    return {"movidos": n}


@router.post("/api/rechazo/{rechazo_id}/refusionado/iniciar")
def refus_iniciar(rechazo_id: int, db: Session = Depends(get_db),
                  current_user: Usuario = Depends(get_current_user)):
    """Fusionado: inicia el re-fusionado de una pieza rechazada (marca el inicio)."""
    if not _puede(current_user, ROLES_FUSIONADO):
        raise HTTPException(403, "Sin permiso de fusionado")
    r = paquete_service.iniciar_refusionado(rechazo_id, db, usuario_id=current_user.id)
    return _rechazo_dict(r)


@router.post("/api/rechazo/{rechazo_id}/refusionado/terminar")
def refus_terminar(rechazo_id: int, db: Session = Depends(get_db),
                   current_user: Usuario = Depends(get_current_user)):
    """Fusionado: termina el re-fusionado; la pieza reingresa a Calidad."""
    if not _puede(current_user, ROLES_FUSIONADO):
        raise HTTPException(403, "Sin permiso de fusionado")
    r = paquete_service.terminar_refusionado(rechazo_id, db, usuario_id=current_user.id)
    if r.paquete:
        ws_manager.notify_of(r.paquete.of_id, "paquetes", {"accion": "refusionado_fin", "por": current_user.nombre})
    return _rechazo_dict(r)


@router.get("/{of_id}", response_class=HTMLResponse)
def pagina(of_id: int, request: Request, db: Session = Depends(get_db),
           current_user: Usuario = Depends(get_current_user)):
    of = db.query(OrdenFabricacion).filter_by(id=of_id).first()
    if not of:
        raise HTTPException(404, "OF no encontrada")
    return templates.TemplateResponse("of/paquetes.html", {
        "request": request, "of": of, "current_user": current_user,
        "rol": get_rol(current_user),
        "puede_numerar": _puede(current_user, ROLES_NUMERAR),
        "puede_calidad": _puede(current_user, ROLES_CALIDAD),
        "puede_reproceso": _puede(current_user, ROLES_REPROCESO),
        "puede_reabrir_numeracion": _puede(current_user, ROLES_REABRIR_NUMERACION),
    })


@router.get("/api/{of_id}/data")
def data(of_id: int, db: Session = Depends(get_db), current_user: Usuario = Depends(get_current_user)):
    of = db.query(OrdenFabricacion).filter_by(id=of_id).first()
    if not of:
        raise HTTPException(404, "OF no encontrada")

    paquetes = paquete_service.listar_paquetes(of_id, db)
    # prendas reales por talla: un bulto por pieza, así que se deduplica por pieza
    _tmp = {}
    for p in paquetes:
        _tmp[(p.sku_id, p.pieza_id)] = _tmp.get((p.sku_id, p.pieza_id), 0) + p.cantidad
    real_por_sku = {}
    for (sku, _pz), s in _tmp.items():
        real_por_sku[sku] = max(real_por_sku.get(sku, 0), s)

    dist = (db.query(OFTallaDistribucion, PrendaSku)
            .join(PrendaSku, PrendaSku.id == OFTallaDistribucion.sku_id)
            .filter(OFTallaDistribucion.of_id == of_id)
            .order_by(PrendaSku.orden).all())
    tallas = [{
        "sku_id": sku.id, "talla": sku.talla,
        "color": (sku.prenda.color if sku.prenda else None),
        "proyectado": d.cantidad,
        "real": real_por_sku.get(sku.id, d.cantidad),
    } for d, sku in dist]

    cerrada_por = None
    if of.hoja_numeracion_cerrada_por:
        u = db.query(Usuario).filter_by(id=of.hoja_numeracion_cerrada_por).first()
        cerrada_por = u.nombre if u else None

    ft = db.query(OFFaseTiempos).filter_by(of_id=of_id, fase_id="F4").first()

    return {
        "of": {"id": of.id, "numero_of": of.numero_of,
               "prenda": (of.prenda_catalogo.codigo if of.prenda_catalogo else of.tipo_prenda)},
        "requiere_fusionado": paquete_service.requiere_fusionado(of),
        "tope": paquete_service.tope_paquete(of),
        "tallas": tallas,
        "paquetes": [_paquete_dict(p, db) for p in paquetes],
        "motivos": [{"id": m.id, "codigo": m.codigo, "descripcion": m.descripcion,
                     "destino": m.destino, "destinos_alt": m.destinos_alt,
                     "rehacer_default": m.rehacer_default}
                    for m in paquete_service.listar_motivos(db)],
        "desvio": paquete_service.resumen_desvio(of, db),
        "reprocesos": paquete_service.listar_reprocesos_of(of_id, db),
        "hoja_cerrada": of.hoja_numeracion_cerrada,
        "hoja_cerrada_por": cerrada_por,
        "hoja_cerrada_at": (of.hoja_numeracion_cerrada_at.strftime("%d/%m %H:%M")
                            if of.hoja_numeracion_cerrada_at else None),
        "numeracion_inicio": (ft.inicio_real.strftime("%d/%m %H:%M")
                              if ft and ft.inicio_real else None),
        "numeracion_fin": (ft.fin_real.strftime("%d/%m %H:%M")
                           if ft and ft.fin_real else None),
    }


@router.post("/api/{of_id}/numeracion/iniciar")
def numeracion_iniciar(of_id: int, db: Session = Depends(get_db),
                       current_user: Usuario = Depends(get_current_user)):
    if not _puede(current_user, ROLES_NUMERAR):
        raise HTTPException(403, "Sin permiso")
    of = db.query(OrdenFabricacion).filter_by(id=of_id).first()
    if not of:
        raise HTTPException(404, "OF no encontrada")
    ft = paquete_service.iniciar_numeracion(of, db, usuario_id=current_user.id)
    return {"inicio_real": ft.inicio_real.strftime("%d/%m %H:%M") if ft.inicio_real else None}


@router.post("/api/{of_id}/numeracion/reabrir")
def numeracion_reabrir(of_id: int, body: ReabrirReq, db: Session = Depends(get_db),
                       current_user: Usuario = Depends(get_current_user)):
    if not _puede(current_user, ROLES_REABRIR_NUMERACION):
        raise HTTPException(403, "Sin permiso para reabrir la hoja de numeración")
    of = db.query(OrdenFabricacion).filter_by(id=of_id).first()
    if not of:
        raise HTTPException(404, "OF no encontrada")
    paquete_service.reabrir_hoja_numeracion(of, body.motivo, db, usuario_id=current_user.id)
    ws_manager.notify_of(of_id, "paquetes", {"accion": "reabrir_numeracion", "por": current_user.nombre})
    return {"reabierta": True}


@router.post("/api/{of_id}/tope")
def set_tope(of_id: int, body: TopeReq, db: Session = Depends(get_db),
             current_user: Usuario = Depends(get_current_user)):
    if not _puede(current_user, ROLES_NUMERAR):
        raise HTTPException(403, "Sin permiso")
    of = db.query(OrdenFabricacion).filter_by(id=of_id).first()
    if not of:
        raise HTTPException(404, "OF no encontrada")
    if body.unidades_por_paquete is not None and body.unidades_por_paquete <= 0:
        raise HTTPException(400, "Las unidades por paquete deben ser mayor a 0")
    of.unidades_por_paquete = body.unidades_por_paquete
    db.commit()
    return {"tope": paquete_service.tope_paquete(of)}


@router.post("/api/{of_id}/generar")
def generar(of_id: int, body: GenerarReq, db: Session = Depends(get_db),
            current_user: Usuario = Depends(get_current_user)):
    if not _puede(current_user, ROLES_NUMERAR):
        raise HTTPException(403, "Sin permiso para numerar")
    of = db.query(OrdenFabricacion).filter_by(id=of_id).first()
    if not of:
        raise HTTPException(404, "OF no encontrada")
    paqs = paquete_service.generar_paquetes(of, body.reales, db, usuario_id=current_user.id, size=body.size)
    ws_manager.notify_of(of_id, "paquetes", {"accion": "generar", "por": current_user.nombre})
    return {"generados": len(paqs), "desvio": paquete_service.resumen_desvio(of, db)}


@router.post("/api/paquete/{paquete_id}/estado")
def cambiar_estado(paquete_id: int, body: EstadoReq, db: Session = Depends(get_db),
                   current_user: Usuario = Depends(get_current_user)):
    """Transición de flujo (enviar a Fusionado / a Calidad, fusionado listo, entregar)."""
    if not _puede(current_user, ROLES_NUMERAR | ROLES_CALIDAD | ROLES_REPROCESO):
        raise HTTPException(403, "Sin permiso")
    p = paquete_service.set_estado_paquete(paquete_id, body.estado, db,
                                           usuario_id=current_user.id, motivo=body.motivo)
    ws_manager.notify_of(p.of_id, "paquetes", {"accion": "estado", "por": current_user.nombre})
    return _paquete_dict(p, db)


@router.post("/api/{of_id}/talla/{sku_id}/enviar")
def avanzar_talla(of_id: int, sku_id: int, body: AvanzarReq, db: Session = Depends(get_db),
                  current_user: Usuario = Depends(get_current_user)):
    """Avance en lote de los bultos de una talla (a Fusionado / Calidad / fusionado listo)."""
    if not _puede(current_user, ROLES_NUMERAR | ROLES_CALIDAD | ROLES_REPROCESO):
        raise HTTPException(403, "Sin permiso")
    n = paquete_service.avanzar_talla(of_id, sku_id, body.grupo, db, usuario_id=current_user.id)
    ws_manager.notify_of(of_id, "paquetes", {"accion": "avanzar", "por": current_user.nombre})
    return {"movidos": n}


@router.post("/api/{of_id}/talla/{sku_id}/aprobar-calidad")
def aprobar_talla_calidad(of_id: int, sku_id: int, db: Session = Depends(get_db),
                          current_user: Usuario = Depends(get_current_user)):
    """Calidad: aprueba (sin rechazos) todos los bultos por-validar de una talla."""
    if not _puede(current_user, ROLES_CALIDAD):
        raise HTTPException(403, "Sin permiso de calidad")
    n = paquete_service.aprobar_talla_calidad(of_id, sku_id, db, usuario_id=current_user.id)
    ws_manager.notify_of(of_id, "paquetes", {"accion": "aprobar_talla", "por": current_user.nombre})
    return {"aprobados": n}


@router.post("/api/paquete/{paquete_id}/validar")
def validar(paquete_id: int, body: ValidarReq, db: Session = Depends(get_db),
            current_user: Usuario = Depends(get_current_user)):
    """Calidad valida el paquete: registra rechazos y deja ENTREGADO o STAND_BY."""
    if not _puede(current_user, ROLES_CALIDAD):
        raise HTTPException(403, "Sin permiso de calidad")
    rechazos = [r.model_dump() for r in body.rechazos]
    p = paquete_service.validar_paquete(paquete_id, rechazos, db, usuario_id=current_user.id)
    ws_manager.notify_of(p.of_id, "paquetes", {"accion": "validar", "por": current_user.nombre})
    return _paquete_dict(p, db)


@router.post("/api/rechazo/{rechazo_id}/tomar")
def tomar(rechazo_id: int, db: Session = Depends(get_db),
          current_user: Usuario = Depends(get_current_user)):
    if not _puede(current_user, ROLES_REPROCESO):
        raise HTTPException(403, "Sin permiso de reproceso")
    r = paquete_service.tomar_reproceso(rechazo_id, db, usuario_id=current_user.id)
    return _rechazo_dict(r)


@router.post("/api/rechazo/{rechazo_id}/reingresar")
def reingresar(rechazo_id: int, db: Session = Depends(get_db),
               current_user: Usuario = Depends(get_current_user)):
    if not _puede(current_user, ROLES_REPROCESO):
        raise HTTPException(403, "Sin permiso de reproceso")
    r = paquete_service.reingresar_rechazo(rechazo_id, db, usuario_id=current_user.id)
    ws_manager.notify_of(r.paquete.of_id, "paquetes", {"accion": "reingreso", "por": current_user.nombre})
    return _rechazo_dict(r)


@router.post("/api/rechazo/{rechazo_id}/terminar")
def terminar_reproceso(rechazo_id: int, db: Session = Depends(get_db),
                       current_user: Usuario = Depends(get_current_user)):
    """La estación termina su parte: handoff a Fusionado (si fusible) o reingreso a Calidad."""
    if not _puede(current_user, ROLES_REPROCESO):
        raise HTTPException(403, "Sin permiso de reproceso")
    r = paquete_service.terminar_reproceso(rechazo_id, db, usuario_id=current_user.id)
    ws_manager.notify_of(r.paquete.of_id, "paquetes", {"accion": "reproceso_fin", "por": current_user.nombre})
    return _rechazo_dict(r)


@router.post("/api/rechazo/{rechazo_id}/falta-tela")
def falta_tela(rechazo_id: int, db: Session = Depends(get_db),
               current_user: Usuario = Depends(get_current_user)):
    """Corte: no hay tela para rehacer → esperando tela (aviso a Planeamiento)."""
    if not _puede(current_user, ROLES_REPROCESO):
        raise HTTPException(403, "Sin permiso de reproceso")
    r = paquete_service.marcar_falta_tela(rechazo_id, db, usuario_id=current_user.id)
    ws_manager.notify_of(r.paquete.of_id, "paquetes", {"accion": "falta_tela", "por": current_user.nombre})
    return _rechazo_dict(r)


@router.post("/api/rechazo/{rechazo_id}/tela-recibida")
def tela_recibida(rechazo_id: int, db: Session = Depends(get_db),
                  current_user: Usuario = Depends(get_current_user)):
    """Planeamiento: llegó la tela (Almacén entregó) → vuelve a Corte a rehacer."""
    if not _puede(current_user, ROLES_PLANEAMIENTO):
        raise HTTPException(403, "Sin permiso")
    r = paquete_service.marcar_tela_recibida(rechazo_id, db, usuario_id=current_user.id)
    ws_manager.notify_of(r.paquete.of_id, "paquetes", {"accion": "tela_recibida", "por": current_user.nombre})
    return _rechazo_dict(r)


