from pydantic import BaseModel as PydanticBase
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database.connection import get_db
from app.models.of import OrdenFabricacion
from app.models.pieza import OFPieza
from app.models.fase import OFFaseEstado, OFFaseTiempos, AvanceRegistro, OFFaseParada
from app.models.usuario import Usuario
from app.schemas.fase import AvanceCreate, CompletarRequest
from app.services.corte_service import registrar_avance, completar_fase, iniciar_fase, get_fases_strip, registrar_avance_bulk, completar_fase_bulk, ORDEN_FASES
from app.services.semaforo_service import calcular_semaforo
from app.core.auth import get_current_user, get_rol
from app.core.templates import templates
from app.core.websocket_manager import ws_manager

router = APIRouter()

ROLES_CORTE = {"ADMIN", "PLANEADOR", "SUPERVISOR_CORTE"}
ROLES_DOCS = {
    "UDP", "COMERCIAL", "COMERCIAL_MARCA", "PLANEAMIENTO_MARCA",
    "INGENIERIA", "LOGISTICA", "CALIDAD",
}

# Fases visibles por rol en la grilla de seguimiento.
# Un rol AUSENTE de este mapa ve TODAS las fases (incl. SUPERVISOR_CORTE,
# ADMIN, PLANEADOR y gestión). Solo se restringe a quien tiene un foco claro,
# para bajar el ruido visual sin ocultarle nada a corte.
ROL_FASES_VISIBLES = {
    "CALIDAD": ["F6", "F9"],   # Calidad ve Calidad y Auditoría
}


def _check_corte(user: Usuario):
    if get_rol(user) not in ROLES_CORTE:
        raise HTTPException(403, f"Rol '{get_rol(user)}' no tiene permiso para registrar avance de corte")


@router.get("/{of_id}", response_class=HTMLResponse)
def seguimiento(of_id: int, request: Request, db: Session = Depends(get_db), current_user: Usuario = Depends(get_current_user)):
    of = db.query(OrdenFabricacion).filter_by(id=of_id).first()
    if not of:
        raise HTTPException(404, "OF no encontrada")
    semaforo = calcular_semaforo(of.fecha_apt, of.estado.value == "COMPLETADA")
    # OF completa tercerizada → bloqueo total; subproceso → template filtra por fase
    fase_tercerizada = getattr(of, 'fase_tercerizada', None)
    puede_registrar = get_rol(current_user) in ROLES_CORTE and not (of.tercerizado and not fase_tercerizada) and of.estado.value in ("ACTIVA", "EN_PROCESO")
    fases_visibles = ROL_FASES_VISIBLES.get(get_rol(current_user))   # None = ve todas
    metricas = _metricas_of(of, db)
    return templates.TemplateResponse("corte/seguimiento.html", {
        "request": request, "of": of, "semaforo": semaforo,
        "current_user": current_user, "puede_registrar": puede_registrar,
        "tercerizado": of.tercerizado, "fase_tercerizada": fase_tercerizada,
        "fases_visibles": fases_visibles, "metricas": metricas,
    })


def _metricas_of(of: OrdenFabricacion, db: Session) -> dict:
    """Métricas resumen para la cabecera de seguimiento (estáticas al cargar).
    Avance global, consumo de tela y tiempo de corte (span + paradas)."""
    # Avance global — mismas fuentes que la franja: placas (F1–F3) + paquetes (F4–F7).
    # (El contador viejo OFFaseEstado ya no lo alimenta el flujo de placas/paquetes.)
    from app.models.of import EstadoOF
    from app.services import paquete_service
    res = paquete_service.resumen_calidad_of(of.id, db)
    if res["hay_hoja"]:
        strip = {c["fase_id"]: c for c in get_fases_strip(of, db)}
        _p = lambda fid: (strip[fid]["pct"] if fid in strip else 0)
        pcts = [_p("F1"), _p("F2"), _p("F3"),
                res["numeracion_pct"], res["fusionado_pct"], res["calidad_pct"], res["liberado_pct"]]
        avance = round(sum(pcts) / len(pcts))
    else:
        # OFs sin hoja de numeración (flujo viejo): se mantiene el contador de fases.
        tot = db.query(
            func.coalesce(func.sum(OFFaseEstado.cantidad_actual), 0),
            func.coalesce(func.sum(OFFaseEstado.max_cantidad), 0),
        ).filter(OFFaseEstado.of_id == of.id).first()
        avance = round((tot[0] / tot[1]) * 100) if tot and tot[1] else 0
    if of.estado == EstadoOF.COMPLETADA:
        avance = 100

    # Consumo de tela (proyectado vs real)
    try:
        from app.services import trazo_service
        consumo = trazo_service.resumen_consumo(of.id, db)
    except Exception:
        consumo = {}

    # Tiempo de corte de tela: span (último fin − primer inicio) y paradas
    TELA = ["F1", "F2", "F3"]
    tiempos = db.query(OFFaseTiempos).filter(
        OFFaseTiempos.of_id == of.id, OFFaseTiempos.fase_id.in_(TELA)
    ).all()
    inicios = [t.inicio_real for t in tiempos if t.inicio_real]
    fines = [t.fin_real for t in tiempos if t.fin_real]
    span = int((max(fines) - min(inicios)).total_seconds() // 60) if (inicios and fines) else None
    paradas_rows = db.query(OFFaseParada).filter(
        OFFaseParada.of_id == of.id, OFFaseParada.fase_id.in_(TELA)
    ).all()
    paradas = sum((p.duracion_minutos or 0) for p in paradas_rows)

    return {
        "total_prendas": of.total_juegos or 0,
        "avance_global": avance,
        "consumo_desvio_pct": consumo.get("desvio_pct"),
        "consumo_real": consumo.get("real"),
        "consumo_proy": consumo.get("proyectado"),
        "tiempo_corte_min": span,
        "tiempo_paradas_min": int(paradas or 0),
    }


@router.get("/api/{of_id}/estado")
def estado_of(of_id: int, db: Session = Depends(get_db), current_user: Usuario = Depends(get_current_user)):
    of = db.query(OrdenFabricacion).filter_by(id=of_id).first()
    if not of:
        raise HTTPException(404, "OF no encontrada")

    # Una sola query para todos los estados de esta OF (evita N+1: N piezas × 9 fases)
    todos_estados = db.query(OFFaseEstado).filter_by(of_id=of_id).all()
    estados_idx: dict[tuple, OFFaseEstado] = {
        (e.pieza_id, e.fase_id): e for e in todos_estados
    }

    piezas_data = []
    for pieza in of.piezas:
        fases_pieza = {}
        for fid in ORDEN_FASES:
            if fid in ("F8", "F9") and not of.estampado_activo:
                continue
            if fid == "F5" and not pieza.fusionado:
                continue
            estado = estados_idx.get((pieza.id, fid))
            if estado:
                fases_pieza[fid] = {
                    "cantidad_actual": estado.cantidad_actual,
                    "max_cantidad": estado.max_cantidad,
                    "completada": estado.completada,
                    "porcentaje": round(estado.cantidad_actual / estado.max_cantidad * 100) if estado.max_cantidad else 0,
                }
        piezas_data.append({
            "id": pieza.id, "nombre": pieza.nombre, "codigo_sap": pieza.codigo_sap,
            "material": pieza.material, "cantidad_x_prenda": pieza.cantidad_x_prenda,
            "fusionado": pieza.fusionado, "fases": fases_pieza,
        })
    return {
        "of_id": of_id, "numero_of": of.numero_of, "cliente": of.cliente, "estado": of.estado,
        "semaforo": calcular_semaforo(of.fecha_apt, of.estado.value == "COMPLETADA"),
        "piezas": piezas_data, "puede_registrar": get_rol(current_user) in ROLES_CORTE,
        "corte_por_talla": bool(getattr(of, "corte_por_talla", False)),
    }


# ── API: estado por talla (grilla talla-primaria, F4–F7) ──────────────────────
_TELA = {"F1", "F2", "F3"}


@router.get("/api/{of_id}/estado-talla")
def estado_talla(of_id: int, db: Session = Depends(get_db), current_user: Usuario = Depends(get_current_user)):
    from collections import defaultdict
    from app.models.of import OFTallaDistribucion
    of = db.query(OrdenFabricacion).filter_by(id=of_id).first()
    if not of:
        raise HTTPException(404, "OF no encontrada")

    fases = [f for f in ORDEN_FASES
             if f not in _TELA and not (f in ("F8", "F9") and not of.estampado_activo)]
    meta_prendas = {d.sku_id: d.cantidad for d in db.query(OFTallaDistribucion).filter_by(of_id=of_id).all()}
    piezas = {p.id: p for p in of.piezas}

    rows = (db.query(OFFaseEstado)
            .filter(OFFaseEstado.of_id == of_id, OFFaseEstado.sku_id.isnot(None))
            .all())
    by_sku = defaultdict(list)
    for r in rows:
        by_sku[r.sku_id].append(r)

    tallas = []
    for sku_id, rlist in by_sku.items():
        pz = defaultdict(dict)
        for r in rlist:
            pz[r.pieza_id][r.fase_id] = {
                "cantidad": r.cantidad_actual, "max": r.max_cantidad, "completada": r.completada,
            }
        fases_roll = {}
        for f in fases:
            fr = [r for r in rlist if r.fase_id == f]
            tot = sum(r.cantidad_actual for r in fr)
            mx = sum(r.max_cantidad for r in fr)
            fases_roll[f] = {"pct": round(tot / mx * 100) if mx else 0,
                             "done": bool(fr) and all(r.completada for r in fr)}
        piezas_list = [{
            "pieza_id": pid, "nombre": piezas[pid].nombre if pid in piezas else str(pid),
            "fusionado": piezas[pid].fusionado if pid in piezas else False, "fases": fdict,
        } for pid, fdict in pz.items()]
        tallas.append({
            "talla": rlist[0].talla, "sku_id": sku_id,
            "meta": meta_prendas.get(sku_id, 0),
            "fases": fases_roll, "piezas": piezas_list,
        })
    # Q5.1: F4 Numerado / F6 Calidad / F7 Habilitado se derivan de los paquetes
    # (fuente de verdad, por talla). El detalle por pieza de esas fases ya no
    # aplica — es por talla; en la grilla por pieza solo queda Fusionado (F5).
    from app.services import paquete_service
    cal = paquete_service.resumen_calidad_por_talla(of_id, db)
    for t in tallas:
        c = cal.get(t["sku_id"])
        if not c:
            continue
        fr = t["fases"]
        if "F4" in fr:
            fr["F4"] = {"pct": c["numeracion_pct"], "done": c["numeracion_done"]}
        if "F5" in fr:
            fr["F5"] = {"pct": c["fusionado_pct"], "done": c["fusionado_done"]}
        if "F6" in fr:
            fr["F6"] = {"pct": c["calidad_pct"], "done": c["calidad_done"]}
        if "F7" in fr:
            fr["F7"] = {"pct": c["liberado_pct"], "done": c["liberado_done"]}
        for pz in t["piezas"]:
            for f in ("F4", "F5", "F6", "F7"):
                pz["fases"].pop(f, None)
        t["calidad"] = {"en_reproceso": c["en_reproceso"], "merma": c["merma"],
                        "entregado": c["entregado"], "total": c["total"]}

    tallas.sort(key=lambda t: t["talla"])
    return {
        "corte_por_talla": True, "fases": fases, "tallas": tallas,
        "puede_registrar": get_rol(current_user) in ROLES_CORTE,
    }


@router.post("/api/{of_id}/avance")
def registrar(of_id: int, body: AvanceCreate, db: Session = Depends(get_db), current_user: Usuario = Depends(get_current_user)):
    _check_corte(current_user)
    of = db.query(OrdenFabricacion).filter_by(id=of_id).first()
    if not of:
        raise HTTPException(404, "OF no encontrada")
    if of.estado.value not in ("ACTIVA", "EN_PROCESO"):
        raise HTTPException(400, "Solo se pueden registrar avances en OFs ACTIVAS o EN PROCESO")
    pieza = db.query(OFPieza).filter_by(id=body.pieza_id, of_id=of_id).first()
    if not pieza:
        raise HTTPException(404, "Pieza no encontrada")
    estado = registrar_avance(of, pieza, body.fase_id, body.cantidad, current_user.id, body.observacion, db, sku_id=body.sku_id)
    ws_manager.notify_of(of_id, "avance", {"fase_id": body.fase_id, "por": current_user.nombre})
    return {"pieza_id": pieza.id, "fase_id": body.fase_id, "sku_id": body.sku_id, "cantidad_actual": estado.cantidad_actual, "max_cantidad": estado.max_cantidad, "completada": estado.completada}


@router.post("/api/{of_id}/completar")
def completar(of_id: int, body: CompletarRequest, db: Session = Depends(get_db), current_user: Usuario = Depends(get_current_user)):
    _check_corte(current_user)
    of = db.query(OrdenFabricacion).filter_by(id=of_id).first()
    if not of:
        raise HTTPException(404, "OF no encontrada")
    if of.estado.value not in ("ACTIVA", "EN_PROCESO"):
        raise HTTPException(400, "Solo se pueden completar fases en OFs ACTIVAS o EN PROCESO")
    pieza = db.query(OFPieza).filter_by(id=body.pieza_id, of_id=of_id).first()
    if not pieza:
        raise HTTPException(404, "Pieza no encontrada")
    estado = completar_fase(of, pieza, body.fase_id, current_user.id, db, sku_id=body.sku_id)
    ws_manager.notify_of(of_id, "completar", {"fase_id": body.fase_id, "por": current_user.nombre})
    return {"completada": estado.completada, "of_estado": of.estado}


class TallaBulkRequest(PydanticBase):
    sku_id: int
    fase_id: str
    cantidad: int | None = None   # prendas (se multiplica por cantidad_x_prenda). None/0 = completar
    completar: bool = False


@router.post("/api/{of_id}/talla-bulk")
def talla_bulk(of_id: int, body: TallaBulkRequest, db: Session = Depends(get_db),
               current_user: Usuario = Depends(get_current_user)):
    """Bulk: aplica avance/completar a TODAS las piezas de una talla en una fase.
    cantidad se interpreta en prendas (cada pieza avanza cantidad × cantidad_x_prenda, con tope)."""
    _check_corte(current_user)
    of = db.query(OrdenFabricacion).filter_by(id=of_id).first()
    if not of:
        raise HTTPException(404, "OF no encontrada")
    if of.estado.value not in ("ACTIVA", "EN_PROCESO"):
        raise HTTPException(400, "Solo se puede registrar en OFs ACTIVAS o EN PROCESO")
    filas = db.query(OFFaseEstado).filter_by(of_id=of_id, fase_id=body.fase_id, sku_id=body.sku_id).all()
    aplicadas, saltadas, errores = 0, 0, []
    for fe in filas:
        if fe.completada:
            continue
        pieza = db.query(OFPieza).filter_by(id=fe.pieza_id).first()
        try:
            if body.completar or not body.cantidad:
                completar_fase(of, pieza, body.fase_id, current_user.id, db, sku_id=body.sku_id)
            else:
                cxp = pieza.cantidad_x_prenda or 1
                reg = min(body.cantidad * cxp, fe.max_cantidad - fe.cantidad_actual)
                if reg <= 0:
                    saltadas += 1
                    continue
                registrar_avance(of, pieza, body.fase_id, reg, current_user.id, "bulk talla", db, sku_id=body.sku_id)
            aplicadas += 1
        except HTTPException as e:
            saltadas += 1
            errores.append(f"{pieza.nombre if pieza else fe.pieza_id}: {e.detail}")
    if aplicadas:
        ws_manager.notify_of(of_id, "avance", {"fase_id": body.fase_id, "por": current_user.nombre, "bulk": True})
    return {"aplicadas": aplicadas, "saltadas": saltadas, "errores": errores}


class FaseBulkRequest(PydanticBase):
    fase_id: str
    cantidad: int | None = None   # prendas por talla (× cantidad_x_prenda, con tope). None/0 = completar
    completar: bool = False


@router.post("/api/{of_id}/fase-bulk")
def fase_bulk(of_id: int, body: FaseBulkRequest, db: Session = Depends(get_db),
              current_user: Usuario = Depends(get_current_user)):
    """Bulk a nivel de FASE: aplica avance/completar a TODAS las tallas y piezas
    de una fase de la OF en una sola acción. Respeta topes y cascada por fila."""
    _check_corte(current_user)
    of = db.query(OrdenFabricacion).filter_by(id=of_id).first()
    if not of:
        raise HTTPException(404, "OF no encontrada")
    if of.estado.value not in ("ACTIVA", "EN_PROCESO"):
        raise HTTPException(400, "Solo se puede registrar en OFs ACTIVAS o EN PROCESO")
    filas = db.query(OFFaseEstado).filter_by(of_id=of_id, fase_id=body.fase_id).all()
    aplicadas, saltadas, errores = 0, 0, []
    for fe in filas:
        if fe.completada:
            continue
        pieza = db.query(OFPieza).filter_by(id=fe.pieza_id).first()
        try:
            if body.completar or not body.cantidad:
                completar_fase(of, pieza, body.fase_id, current_user.id, db, sku_id=fe.sku_id)
            else:
                cxp = pieza.cantidad_x_prenda or 1
                reg = min(body.cantidad * cxp, fe.max_cantidad - fe.cantidad_actual)
                if reg <= 0:
                    saltadas += 1
                    continue
                registrar_avance(of, pieza, body.fase_id, reg, current_user.id, "bulk fase", db, sku_id=fe.sku_id)
            aplicadas += 1
        except HTTPException as e:
            saltadas += 1
            tl = f" [{fe.talla}]" if fe.talla else ""
            errores.append(f"{(pieza.nombre if pieza else fe.pieza_id)}{tl}: {e.detail}")
    if aplicadas:
        ws_manager.notify_of(of_id, "avance", {"fase_id": body.fase_id, "por": current_user.nombre, "bulk": True})
    return {"aplicadas": aplicadas, "saltadas": saltadas, "errores": errores}


@router.get("/api/{of_id}/historial")
def historial(of_id: int, db: Session = Depends(get_db), current_user: Usuario = Depends(get_current_user)):
    registros = db.query(AvanceRegistro).filter_by(of_id=of_id, revertido=False).order_by(AvanceRegistro.created_at.desc()).limit(200).all()
    return [{"id": r.id, "pieza_id": r.pieza_id, "pieza_nombre": r.pieza.nombre if r.pieza else str(r.pieza_id), "fase_id": r.fase_id, "talla": r.talla, "cantidad": r.cantidad, "usuario_nombre": r.usuario.nombre if r.usuario else f"Usuario {r.usuario_id}", "observacion": r.observacion, "created_at": str(r.created_at)} for r in registros]


@router.post("/api/{of_id}/revertir/{registro_id}")
def revertir(of_id: int, registro_id: int, db: Session = Depends(get_db), current_user: Usuario = Depends(get_current_user)):
    _check_corte(current_user)
    registro = db.query(AvanceRegistro).filter_by(id=registro_id, of_id=of_id, revertido=False).first()
    if not registro:
        raise HTTPException(404, "Registro no encontrado o ya revertido")
    estado = db.query(OFFaseEstado).filter_by(of_id=of_id, pieza_id=registro.pieza_id, fase_id=registro.fase_id, sku_id=registro.sku_id).first()
    if estado:
        estado.cantidad_actual = max(0, estado.cantidad_actual - registro.cantidad)
        if estado.completada:
            estado.completada = False
            estado.fecha_completado = None
    registro.revertido = True
    db.commit()
    ws_manager.notify_of(of_id, "revertir", {"fase_id": registro.fase_id, "por": current_user.nombre})
    return {"revertido": True, "cantidad": registro.cantidad, "fase_id": registro.fase_id}


@router.get("/api/{of_id}/fases/strip")
def fases_strip(of_id: int, db: Session = Depends(get_db), current_user: Usuario = Depends(get_current_user)):
    of = db.query(OrdenFabricacion).filter_by(id=of_id).first()
    if not of:
        raise HTTPException(404, "OF no encontrada")
    strip = get_fases_strip(of, db)
    # F4 Numerado / F6 Calidad / F7 Habilitado se derivan de los paquetes
    # (fuente de verdad) cuando ya existe hoja de numeración.
    from app.services import paquete_service
    res = paquete_service.resumen_calidad_of(of_id, db)
    if res["hay_hoja"]:
        def _est(pct, done, algo):
            return "completada" if done else ("en_proceso" if algo else "pendiente")
        for card in strip:
            fid = card["fase_id"]
            if fid == "F4":                              # Numerado (bultos enviados a Fusionado/Calidad)
                # Hoja generada = inicio marcado → "en curso" aunque 0% enviado; 100% al enviar el último.
                card["pct"] = res["numeracion_pct"]
                card["estado"] = "completada" if res["numeracion_done"] else "en_proceso"
                card["puede_iniciar"] = False
            elif fid == "F5":                            # Fusionado (bultos terminados de fusionar)
                card["pct"] = res["fusionado_pct"]
                # "en curso" apenas arranca el primer bulto (aunque 0% terminado); completada al terminar todos.
                if res["fusionado_done"]:
                    card["estado"] = "completada"
                elif res["fusionado_iniciado"]:
                    card["estado"] = "en_proceso"
                else:
                    card["estado"] = "pendiente"
                card["puede_iniciar"] = False
                card["inicio_real"] = res["fusionado_inicio"].strftime("%d/%m %H:%M") if res["fusionado_inicio"] else None
                card["fin_real"] = res["fusionado_fin"].strftime("%d/%m %H:%M") if res["fusionado_fin"] else None
            elif fid == "F6":                            # Calidad
                card["pct"] = res["calidad_pct"]
                card["estado"] = _est(res["calidad_pct"], res["calidad_done"], res["entregado"] > 0)
                card["puede_iniciar"] = False
            elif fid == "F7":                            # Liberado (tras OK de Calidad)
                card["pct"] = res["liberado_pct"]
                card["estado"] = _est(res["liberado_pct"], res["liberado_done"], res["entregado"] > 0)
                card["puede_iniciar"] = False
    return strip


@router.post("/api/{of_id}/fases/{fase_id}/iniciar")
def iniciar(of_id: int, fase_id: str, db: Session = Depends(get_db), current_user: Usuario = Depends(get_current_user)):
    _check_corte(current_user)
    of = db.query(OrdenFabricacion).filter_by(id=of_id).first()
    if not of:
        raise HTTPException(404, "OF no encontrada")
    tiempos = iniciar_fase(of, fase_id, db)
    ws_manager.notify_of(of_id, "fase", {"fase_id": fase_id, "por": current_user.nombre})
    return {"fase_id": fase_id, "inicio_real": tiempos.inicio_real.strftime("%d/%m/%Y %H:%M") if tiempos.inicio_real else None, "mensaje": f"Fase {fase_id} iniciada correctamente"}


class AvanceBulkRequest(PydanticBase):
    fase_id: str
    cantidad: int
    pieza_ids: list[int]


class CompletarBulkRequest(PydanticBase):
    fase_id: str
    pieza_ids: list[int]


@router.post("/api/{of_id}/avance-bulk")
def avance_bulk(of_id: int, body: AvanceBulkRequest, db: Session = Depends(get_db), current_user: Usuario = Depends(get_current_user)):
    _check_corte(current_user)
    of = db.query(OrdenFabricacion).filter_by(id=of_id).first()
    if not of:
        raise HTTPException(404, "OF no encontrada")
    if of.estado.value not in ("ACTIVA", "EN_PROCESO"):
        raise HTTPException(400, "Solo se pueden registrar avances en OFs ACTIVAS o EN PROCESO")
    if getattr(of, "corte_por_talla", False):
        raise HTTPException(400, "Esta OF es por talla: usa el bulk por talla en la vista de piezas.")
    estados = registrar_avance_bulk(of, body.fase_id, body.cantidad, body.pieza_ids, current_user.id, db)
    ws_manager.notify_of(of_id, "avance", {"fase_id": body.fase_id, "por": current_user.nombre, "bulk": True})
    return {"registradas": len(estados), "fase_id": body.fase_id, "cantidad_por_pieza": body.cantidad}


@router.post("/api/{of_id}/completar-bulk")
def completar_bulk(of_id: int, body: CompletarBulkRequest, db: Session = Depends(get_db), current_user: Usuario = Depends(get_current_user)):
    _check_corte(current_user)
    of = db.query(OrdenFabricacion).filter_by(id=of_id).first()
    if not of:
        raise HTTPException(404, "OF no encontrada")
    if of.estado.value not in ("ACTIVA", "EN_PROCESO"):
        raise HTTPException(400, "Solo se pueden completar fases en OFs ACTIVAS o EN PROCESO")
    if getattr(of, "corte_por_talla", False):
        raise HTTPException(400, "Esta OF es por talla: usa el bulk por talla en la vista de piezas.")
    estados = completar_fase_bulk(of, body.fase_id, body.pieza_ids, current_user.id, db)
    ws_manager.notify_of(of_id, "completar", {"fase_id": body.fase_id, "por": current_user.nombre, "bulk": True})
    return {"completadas": len(estados), "fase_id": body.fase_id}


# ── Paradas ───────────────────────────────────────────────────

class PausarRequest(PydanticBase):
    fase_id: str
    motivo: str
    of_emergencia_id: int | None = None
    numero_requerimiento: str | None = None
    observacion: str | None = None


class ReanudarRequest(PydanticBase):
    parada_id: int


@router.post("/api/{of_id}/pausar")
def pausar(of_id: int, body: PausarRequest, db: Session = Depends(get_db), current_user: Usuario = Depends(get_current_user)):
    _check_corte(current_user)
    of = db.query(OrdenFabricacion).filter_by(id=of_id).first()
    if not of:
        raise HTTPException(404, "OF no encontrada")

    # Verificar que no haya ya una parada activa en esa fase
    activa = db.query(OFFaseParada).filter(
        OFFaseParada.of_id == of_id,
        OFFaseParada.fase_id == body.fase_id,
        OFFaseParada.fin_parada.is_(None),
    ).first()
    if activa:
        raise HTTPException(400, f"Ya existe una parada activa en {body.fase_id}")

    from datetime import datetime
    parada = OFFaseParada(
        of_id=of_id,
        fase_id=body.fase_id,
        motivo=body.motivo,
        of_emergencia_id=body.of_emergencia_id,
        numero_requerimiento=body.numero_requerimiento,
        observacion=body.observacion,
        inicio_parada=datetime.now(),
        usuario_id=current_user.id,
    )
    db.add(parada)
    db.commit()
    db.refresh(parada)
    ws_manager.notify_of(of_id, "pausar", {"fase_id": body.fase_id, "por": current_user.nombre})
    return {"ok": True, "parada_id": parada.id}


@router.post("/api/{of_id}/reanudar")
def reanudar(of_id: int, body: ReanudarRequest, db: Session = Depends(get_db), current_user: Usuario = Depends(get_current_user)):
    _check_corte(current_user)
    parada = db.query(OFFaseParada).filter_by(id=body.parada_id, of_id=of_id).first()
    if not parada:
        raise HTTPException(404, "Parada no encontrada")
    if parada.fin_parada is not None:
        raise HTTPException(400, "La parada ya fue cerrada")

    from datetime import datetime
    parada.fin_parada = datetime.now()
    db.commit()
    ws_manager.notify_of(of_id, "reanudar", {"por": current_user.nombre})
    return {"ok": True, "mensaje": "Parada cerrada", "duracion_minutos": parada.duracion_minutos}


@router.get("/api/{of_id}/paradas")
def listar_paradas(of_id: int, db: Session = Depends(get_db), current_user: Usuario = Depends(get_current_user)):
    paradas = db.query(OFFaseParada).filter_by(of_id=of_id).order_by(OFFaseParada.inicio_parada.desc()).all()

    # Resolver número de OF emergencia si aplica
    of_ids = {p.of_emergencia_id for p in paradas if p.of_emergencia_id}
    of_map = {}
    if of_ids:
        from app.models.of import OrdenFabricacion as OF2
        ofs = db.query(OF2).filter(OF2.id.in_(of_ids)).all()
        of_map = {o.id: o.numero_of for o in ofs}

    return [
        {
            "id": p.id,
            "fase_id": p.fase_id,
            "motivo": p.motivo,
            "of_emergencia_id": p.of_emergencia_id,
            "of_emergencia_numero": of_map.get(p.of_emergencia_id) if p.of_emergencia_id else None,
            "numero_requerimiento": p.numero_requerimiento,
            "observacion": p.observacion,
            "inicio_parada": p.inicio_parada.strftime("%d/%m %H:%M") if p.inicio_parada else None,
            "fin_parada": p.fin_parada.strftime("%d/%m %H:%M") if p.fin_parada else None,
            "duracion_minutos": p.duracion_minutos,
            "activa": p.fin_parada is None,
        }
        for p in paradas
    ]
