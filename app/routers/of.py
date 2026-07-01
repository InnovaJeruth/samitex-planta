from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File, Form
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from sqlalchemy.orm import Session, selectinload
from datetime import date, timedelta


def _safe_date(s: str) -> date:
    """Convierte string ISO a date; lanza HTTPException 400 si el formato es inválido."""
    try:
        return date.fromisoformat(s)
    except (ValueError, TypeError):
        raise HTTPException(400, f"Fecha inválida: '{s}'. Use formato YYYY-MM-DD")
from typing import Optional, List
from pydantic import BaseModel as PydanticBase
import os, shutil, uuid, json

from app.database.connection import get_db
from app.models.of import OrdenFabricacion, EstadoOF, TipoPrendaEnum, TipoDocumentoOF, DocumentoOF, TipoClienteEnum, EstadoDocsEnum, OFTallaDistribucion, AuditoriaDocumentoOF
from app.models.pieza import OFPieza, PlantillaPieza
from app.models.catalogo import PrendaCatalogo, PrendaSku, TIPOS_BASE_PRENDA
from app.models.fase import OFFaseEstado, FaseCatalogo, OFFaseTiempos
from app.models.planta import PlantaExterna, TercRecepcion, TercHistorialFecha, TercSubprocesoLog
from app.core.auth import get_current_user
from app.core.templates import templates
from app.models.usuario import Usuario
from app.config import settings
from app.services.gate_service import calcular_gates, puede_activar, gates_to_dict, puede_subir_gate, GATES, GATES_REQUERIDOS
from app.services import of_service
from app.services.of_service import actualizar_estado_docs, auto_derivar_programado
from app.services.semaforo_service import calcular_semaforo
from app.models.fase import AvanceRegistro
from app.models.parametro import ParametroSistema
from app.constants import ORDEN_FASES, NOMBRES_FASE, FASES_GANTT, FASES_GANTT_LBL
from sqlalchemy import func as sa_func, cast as sa_cast, Date as SA_Date

router = APIRouter()


# ── Listar OFs ────────────────────────────────────────────────
PAGE_SIZE = 20

@router.get("/", response_class=HTMLResponse)
def lista_ofs(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
    page: int = 1,
    q: str = "",
    estado: str = "",
    tipo_prenda: str = "",
):
    page = max(1, page)
    query = db.query(OrdenFabricacion)
    if q:
        like = f"%{q}%"
        query = query.filter(
            OrdenFabricacion.numero_of.ilike(like) |
            OrdenFabricacion.cliente.ilike(like)
        )
    if estado:
        try:
            query = query.filter(OrdenFabricacion.estado == EstadoOF(estado))
        except ValueError:
            pass
    if tipo_prenda:
        try:
            query = query.filter(OrdenFabricacion.tipo_prenda == TipoPrendaEnum(tipo_prenda))
        except ValueError:
            pass

    total = query.count()
    total_pages = max(1, -(-total // PAGE_SIZE))  # ceil division
    page = min(page, total_pages)
    offset = (page - 1) * PAGE_SIZE

    ofs = query.order_by(OrdenFabricacion.created_at.desc()).offset(offset).limit(PAGE_SIZE).all()

    return templates.TemplateResponse("of/lista.html", {
        "request": request,
        "ofs": ofs,
        "current_user": current_user,
        "page": page,
        "total_pages": total_pages,
        "total": total,
        "q": q,
        "estado": estado,
        "tipo_prenda": tipo_prenda,
        "estados_enum": [e.value for e in EstadoOF],
        "tipos_prenda_enum": [t.value for t in TipoPrendaEnum],
    })


# ── Plan Corte (Gantt) ────────────────────────────────────────
ROLES_PLAN_CORTE = {"ADMIN", "PLANEADOR", "GERENTE_PLANTA", "GERENCIA"}


@router.get("/plan-corte", response_class=HTMLResponse)
def plan_corte(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    import logging as _log
    _logger = _log.getLogger(__name__)
    rol = current_user.rol.value if hasattr(current_user.rol, "value") else str(current_user.rol)
    if rol not in ROLES_PLAN_CORTE:
        raise HTTPException(403, "No tienes permiso para ver el Plan de Corte")
    try:
        ofs_raw = (
            db.query(OrdenFabricacion)
            .options(
                selectinload(OrdenFabricacion.piezas).selectinload(OFPieza.fases_estado),
                selectinload(OrdenFabricacion.recepciones_terc),
                selectinload(OrdenFabricacion.fase_tiempos),
            )
            .filter(OrdenFabricacion.estado != EstadoOF.ANULADA)
            .all()
        )
    except Exception as _e:
        db.rollback()
        _logger.error("plan-corte DB query error: %s", _e, exc_info=True)
        import traceback as _tb
        return HTMLResponse(
            f"<pre style='color:red;padding:20px;font-size:13px'>ERROR EN QUERY plan-corte:\n{type(_e).__name__}: {_e}\n\n{_tb.format_exc()}</pre>",
            status_code=200,
        )
    except Exception as _e2:
        db.rollback()
        import traceback as _tb2
        return HTMLResponse(
            f"<pre style='color:red;padding:20px;font-size:13px'>ERROR procesando plan-corte:\n{type(_e2).__name__}: {_e2}\n\n{_tb2.format_exc()}</pre>",
            status_code=200,
        )

    ofs_raw = sorted(ofs_raw, key=lambda x: (
        x.orden_plan if x.orden_plan is not None else 9999,
        x.fecha_apt or date(2099, 1, 1),
    ))

    today = date.today()
    ofs_data = []
    tasks_json = []

    try:
        for i, of in enumerate(ofs_raw):
            sem = calcular_semaforo(of.fecha_apt, of.estado == EstadoOF.COMPLETADA)

            if getattr(of, 'tercerizado', False):
                if of.estado == EstadoOF.COMPLETADA:
                    pct = 100
                else:
                    recibidos = sum(r.juegos_recibidos for r in of.recepciones_terc) if of.recepciones_terc else 0
                    total_j   = of.total_juegos or 0
                    pct = min(round(recibidos / total_j * 100), 99) if total_j else 0
            else:
                cant_actual = sum(fe.cantidad_actual for p in of.piezas for fe in p.fases_estado)
                cant_max    = sum(fe.max_cantidad    for p in of.piezas for fe in p.fases_estado)
                pct = round(cant_actual / cant_max * 100) if cant_max else 0
                pct = min(pct, 99) if of.estado != EstadoOF.COMPLETADA else 100

            inicio = of.fecha_inicio_plan or of.fecha_creacion or today
            apt    = of.fecha_apt or (inicio + timedelta(days=14))
            if apt <= inicio:
                apt = inicio + timedelta(days=1)

            dias = sem.get("dias_restantes") if sem else None
            if getattr(of, "tercerizado", False):
                color_class, apt_class = "bar-morado", "apt-purple"
            elif dias is not None:
                if dias < 0:
                    color_class, apt_class = "bar-rojo", "apt-red"
                elif dias <= 7:
                    color_class, apt_class = "bar-naranja", "apt-orange"
                else:
                    color_class, apt_class = "bar-verde", "apt-green"
            else:
                color_class, apt_class = "bar-default", ""

            n_piezas = len(of.piezas)
            fases_chips = {}
            for fid in FASES_GANTT:
                ok_count = par_count = 0
                for pieza in of.piezas:
                    for fe in pieza.fases_estado:
                        if fe.fase_id == fid:
                            if fe.completada: ok_count += 1
                            elif fe.cantidad_actual > 0: par_count += 1
                if n_piezas == 0:              estado = "na"
                elif ok_count == n_piezas:     estado = "ok"
                elif ok_count > 0 or par_count > 0: estado = "par"
                else:                          estado = "pend"
                fases_chips[fid] = {"estado": estado, "label": FASES_GANTT_LBL[fid],
                                     "ok": ok_count, "total": n_piezas}

            orden_num = of.orden_plan if of.orden_plan is not None else (i + 1)

            fases_con_real = [
                {
                    "fase_id":    t.fase_id,
                    "nombre":     NOMBRES_FASE.get(t.fase_id, t.fase_id),
                    "inicio_real": t.inicio_real.strftime("%d/%m %H:%M"),
                }
                for t in of.fase_tiempos if t.inicio_real is not None
            ]

            ofs_data.append({
                "of": of,
                "semaforo": sem,
                "pct": pct,
                "fases_chips": fases_chips,
                "fecha_inicio_str": inicio.isoformat(),
                "fecha_apt_str": apt.isoformat(),
                "color_class": color_class,
                "apt_class": apt_class,
                "orden_num":     orden_num,
                "fases_con_real": fases_con_real,
            })

            # Bloque 3 — segmentos de fase para el Gantt
            from datetime import datetime as _dt
            _now = _dt.now()
            fases_prog = []
            for _t in of.fase_tiempos:
                if _t.inicio_real is not None:
                    if _t.fin_real is not None:
                        _tipo, _ini, _fin = "real_done",   _t.inicio_real, _t.fin_real
                    else:
                        _tipo, _ini, _fin = "real_active", _t.inicio_real, _now
                elif _t.inicio_programado is not None:
                    _ini = _t.inicio_programado
                    _fin = _t.fin_programado or (_t.inicio_programado + timedelta(hours=8))
                    _tipo = "prog_late" if _fin < _now else "prog"
                else:
                    continue
                fases_prog.append({
                    "fase_id": _t.fase_id,
                    "nombre":  NOMBRES_FASE.get(_t.fase_id, _t.fase_id),
                    "inicio":  _ini.strftime("%Y-%m-%dT%H:%M"),
                    "fin":     _fin.strftime("%Y-%m-%dT%H:%M"),
                    "tipo":    _tipo,
                })

            tasks_json.append({
                "id":    str(of.id),
                "name":  of.numero_of,
                "start": inicio.isoformat(),
                "end":   apt.isoformat(),
                "progress": pct,
                "custom_class": color_class,
                "_cliente":   of.cliente[:35],
                "_estado":    of.estado.value,
                "_apt":       of.fecha_apt.isoformat() if of.fecha_apt else "",
                "fases_prog": fases_prog,
            })

    except Exception as _e3:
        db.rollback()
        import traceback as _tb3
        return HTMLResponse(
            f"<pre style='color:red;padding:20px;font-size:13px'>ERROR en for-loop plan-corte:\n{type(_e3).__name__}: {_e3}\n\n{_tb3.format_exc()}</pre>",
            status_code=200,
        )

    # ── Capacidad diaria y carga planificada + real ───────────────
    try:
        capacidad = int(ParametroSistema.get(db, "corte_cap_diaria_juegos", "500"))

        # Carga planificada: sum(total_juegos) agrupado por fecha_inicio_plan
        plan_rows = (
            db.query(OrdenFabricacion.fecha_inicio_plan,
                     sa_func.sum(OrdenFabricacion.total_juegos).label("juegos"))
            .filter(OrdenFabricacion.fecha_inicio_plan.isnot(None),
                    OrdenFabricacion.estado != EstadoOF.ANULADA)
            .group_by(OrdenFabricacion.fecha_inicio_plan)
            .all()
        )
        planificado = {str(r.fecha_inicio_plan): int(r.juegos or 0) for r in plan_rows}

        # Carga real: sum(cantidad) de AvanceRegistro agrupado por fecha + fase
        from datetime import datetime as dt
        hace_14 = date.today() - timedelta(days=14)
        real_rows = (
            db.query(
                sa_cast(AvanceRegistro.created_at, SA_Date).label("dia"),
                AvanceRegistro.fase_id,
                sa_func.sum(AvanceRegistro.cantidad).label("juegos"),
            )
            .filter(AvanceRegistro.revertido == False,
                    AvanceRegistro.created_at >= dt.combine(hace_14, dt.min.time()))
            .group_by(sa_cast(AvanceRegistro.created_at, SA_Date), AvanceRegistro.fase_id)
            .all()
        )
        real_por_dia: dict = {}
        for r in real_rows:
            dia = str(r.dia)
            if dia not in real_por_dia:
                real_por_dia[dia] = {"total": 0, "por_fase": {}}
            real_por_dia[dia]["total"] += int(r.juegos or 0)
            real_por_dia[dia]["por_fase"][r.fase_id] = int(r.juegos or 0)

        carga_json = json.dumps({
            "capacidad": capacidad,
            "planificado": planificado,
            "real": real_por_dia,
        })
    except Exception:
        db.rollback()
        capacidad = 500
        carga_json = json.dumps({"capacidad": 500, "planificado": {}, "real": {}})

    return templates.TemplateResponse("of/plan_corte.html", {
        "request":      request,
        "ofs":          ofs_data,
        "tasks_json":   json.dumps(tasks_json),
        "current_user": current_user,
        "FASES_GANTT":  FASES_GANTT,
        "capacidad":    capacidad,
        "carga_json":   carga_json,
    })


# ── Detalle unificado de OF ───────────────────────────────────
@router.get("/{of_id}/detalle", response_class=HTMLResponse)
def detalle_of(
    of_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    of = db.query(OrdenFabricacion).options(
        selectinload(OrdenFabricacion.terc_logs)
    ).filter_by(id=of_id).first()
    if not of:
        raise HTTPException(404, "OF no encontrada")

    gates   = calcular_gates(of, db)
    ok, _   = puede_activar(of, db)
    sem_dict = calcular_semaforo(of.fecha_apt, of.estado == EstadoOF.COMPLETADA)
    semaforo = sem_dict["estado"]

    rol = current_user.rol.value if hasattr(current_user.rol, "value") else str(current_user.rol)
    tipo_cliente = of.tipo_cliente.value if of.tipo_cliente else "INSTITUCION"
    from app.services.gate_service import GATE_ROLES
    gates_permitidos = set()
    for gate_id, roles_por_tc in GATE_ROLES.items():
        allowed = roles_por_tc.get(tipo_cliente, [])
        if rol in allowed or rol == "ADMIN":
            gates_permitidos.add(gate_id)

    historial = db.query(AvanceRegistro).filter_by(
        of_id=of_id, revertido=False
    ).order_by(AvanceRegistro.created_at.desc()).limit(50).all()

    tiene_avance = any(
        fe.cantidad_actual > 0 or fe.completada
        for p in of.piezas
        for fe in p.fases_estado
    )

    return templates.TemplateResponse("of/detalle.html", {
        "request": request,
        "of": of,
        "gates": gates,
        "puede_activar": ok,
        "semaforo": semaforo,
        "historial": historial,
        "current_user": current_user,
        "ORDEN_FASES": ORDEN_FASES,
        "gates_permitidos": gates_permitidos,
        "tipo_cliente": tipo_cliente,
        "tiene_avance": tiene_avance,
        "fases_catalogo": db.query(FaseCatalogo).order_by(FaseCatalogo.orden).all(),
    })


# ── Formulario crear OF ───────────────────────────────────────
@router.get("/crear", response_class=HTMLResponse)
def crear_of_page(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    usuarios = db.query(Usuario).filter(Usuario.activo == True).all()
    prendas  = (db.query(PrendaCatalogo)
                  .filter_by(activo=True)
                  .filter(PrendaCatalogo.tipo_cliente != "BASE")
                  .order_by(PrendaCatalogo.tipo_base, PrendaCatalogo.nombre)
                  .all())
    return templates.TemplateResponse("of/crear.html", {
        "request":      request,
        "usuarios":     usuarios,
        "current_user": current_user,
        "prendas":      prendas,
        "tipos_base":   TIPOS_BASE_PRENDA,
    })


# ── API: crear OF ─────────────────────────────────────────────
@router.post("/api/crear")
def crear_of(
    numero_of:          str  = Form(...),
    cliente:            str  = Form(...),
    tipo_prenda:        str  = Form(...),
    prenda_catalogo_id: int  = Form(None),
    total_juegos:       int  = Form(...),
    fecha_apt:          str  = Form(None),
    responsable_id:     int  = Form(None),
    tipo_cliente:       str  = Form("INSTITUCION"),
    solped_prenda:      str  = Form(None),
    orden_compra:       str  = Form(None),
    solped_mp:          str  = Form(None),
    estampado_activo:   bool = Form(False),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    existe = db.query(OrdenFabricacion).filter_by(numero_of=numero_of).first()
    if existe:
        raise HTTPException(400, f"Ya existe una OF con número {numero_of}")
    if total_juegos < 1:
        raise HTTPException(400, "El total de juegos debe ser mayor a 0")

    # Si se envía prenda_catalogo_id, resolver el tipo_prenda desde el catálogo
    if prenda_catalogo_id:
        prenda = db.query(PrendaCatalogo).filter_by(id=prenda_catalogo_id, activo=True).first()
        if not prenda:
            raise HTTPException(404, "Prenda del catálogo no encontrada o inactiva")
        tipo_prenda = prenda.nombre  # guardar el nombre completo de la variante

    of = OrdenFabricacion(
        numero_of          = numero_of,
        cliente            = cliente,
        tipo_prenda        = tipo_prenda,
        prenda_catalogo_id = prenda_catalogo_id,
        total_juegos       = total_juegos,
        fecha_creacion     = date.today(),
        fecha_apt          = _safe_date(fecha_apt) if fecha_apt else None,
        responsable_id     = responsable_id,
        tipo_cliente       = tipo_cliente,
        solped_prenda      = solped_prenda,
        orden_compra       = orden_compra,
        solped_mp          = solped_mp,
        estampado_activo   = estampado_activo,
        estado             = EstadoOF.BORRADOR,
        estado_docs        = EstadoDocsEnum.PENDIENTE,
    )
    db.add(of)
    db.commit()
    db.refresh(of)
    return {"id": of.id, "numero_of": of.numero_of, "estado": of.estado}


# ── API: buscar OFs por número (usado por modal paradas) ─────
@router.get("/api/buscar")
def buscar_ofs(
    q: str = "",
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    if not q or len(q) < 2:
        return []
    resultados = (
        db.query(OrdenFabricacion)
        .filter(OrdenFabricacion.numero_of.ilike(f"%{q}%"))
        .limit(10)
        .all()
    )
    return [{"id": o.id, "numero_of": o.numero_of, "cliente": o.cliente} for o in resultados]


# ── API: obtener OF ───────────────────────────────────────────
@router.get("/api/{of_id}")
def get_of(
    of_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    of = db.query(OrdenFabricacion).filter_by(id=of_id).first()
    if not of:
        raise HTTPException(404, "OF no encontrada")
    return {
        "id": of.id,
        "numero_of": of.numero_of,
        "cliente": of.cliente,
        "tipo_prenda": of.tipo_prenda,
        "total_juegos": of.total_juegos,
        "estado": of.estado,
        "fecha_creacion": str(of.fecha_creacion),
        "fecha_apt": str(of.fecha_apt) if of.fecha_apt else None,
        "estampado_activo": of.estampado_activo,
        "solped_prenda": of.solped_prenda,
        "orden_compra": of.orden_compra,
        "solped_mp": of.solped_mp,
        "piezas": [
            {
                "id": p.id, "nombre": p.nombre, "codigo_sap": p.codigo_sap,
                "material": p.material, "cantidad_x_prenda": p.cantidad_x_prenda,
                "fusionado": p.fusionado,
            }
            for p in of.piezas
        ],
    }


# ── API: agregar pieza ────────────────────────────────────────
@router.post("/api/{of_id}/piezas")
def agregar_pieza(
    of_id: int,
    nombre: str = Form(...),
    codigo_sap: str = Form(None),
    material: str = Form("TELA"),
    cantidad_x_prenda: int = Form(1),
    fusionado: bool = Form(False),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    of = db.query(OrdenFabricacion).filter_by(id=of_id).first()
    if not of:
        raise HTTPException(404, "OF no encontrada")

    pieza = OFPieza(
        of_id=of_id, nombre=nombre, codigo_sap=codigo_sap,
        material=material, cantidad_x_prenda=cantidad_x_prenda, fusionado=fusionado,
    )
    db.add(pieza)
    db.flush()
    of_service.crear_fases_pieza(pieza, of, db)
    db.commit()
    return {"id": pieza.id, "nombre": pieza.nombre}


# ── API: cargar piezas desde plantilla ───────────────────────
@router.post("/api/{of_id}/piezas/plantilla")
def cargar_plantilla(
    of_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    of = db.query(OrdenFabricacion).filter_by(id=of_id).first()
    if not of:
        raise HTTPException(404, "OF no encontrada")
    if of.estado != EstadoOF.ACTIVA:
        raise HTTPException(400, "Solo se pueden generar piezas cuando la OF está ACTIVA")
    if of.piezas:
        raise HTTPException(400, "Esta OF ya tiene piezas definidas")

    # Prioridad: FK de catálogo; fallback: buscar por tipo_base
    if of.prenda_catalogo_id:
        plantillas = (db.query(PlantillaPieza)
                        .filter_by(prenda_catalogo_id=of.prenda_catalogo_id)
                        .order_by(PlantillaPieza.orden).all())
    else:
        prenda_cat = (db.query(PrendaCatalogo)
                        .filter_by(tipo_base=of.tipo_prenda, activo=True)
                        .order_by(PrendaCatalogo.id).first())
        plantillas = (db.query(PlantillaPieza)
                        .filter_by(prenda_catalogo_id=prenda_cat.id)
                        .order_by(PlantillaPieza.orden).all()) if prenda_cat else []

    piezas_creadas = []
    for p in plantillas:
        pieza = OFPieza(
            of_id=of_id, nombre=p.nombre, material=p.material_default,
            cantidad_x_prenda=p.cantidad_x_prenda, fusionado=p.fusionado_default,
            orden=p.orden,
            codigo_pieza=p.codigo,
            codigo_sap=p.codigo,
        )
        db.add(pieza)
        db.flush()
        of_service.crear_fases_pieza(pieza, of, db)
        piezas_creadas.append(pieza.nombre)

    db.commit()
    return {"piezas_creadas": piezas_creadas}


# ── API: diagnóstico piezas/catálogo para una OF ──────────────
@router.get("/api/{of_id}/diagnostico-piezas")
def diagnostico_piezas(
    of_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """Devuelve estado de piezas y catálogo sin tocar of_fases_estado."""
    of = db.query(OrdenFabricacion).filter_by(id=of_id).first()
    if not of:
        raise HTTPException(404, "OF no encontrada")

    n_piezas_of = db.query(OFPieza).filter_by(of_id=of_id).count()

    prenda_cat = None
    n_plantilla = 0
    plantilla_nombres = []
    if of.prenda_catalogo_id:
        prenda_cat = db.query(PrendaCatalogo).filter_by(id=of.prenda_catalogo_id).first()
        plantillas = (db.query(PlantillaPieza)
                        .filter_by(prenda_catalogo_id=of.prenda_catalogo_id)
                        .order_by(PlantillaPieza.orden).all())
        n_plantilla = len(plantillas)
        plantilla_nombres = [p.nombre for p in plantillas]
    else:
        # Fallback por tipo_base
        prenda_cat = (db.query(PrendaCatalogo)
                        .filter_by(tipo_base=of.tipo_prenda, activo=True)
                        .order_by(PrendaCatalogo.id).first())
        if prenda_cat:
            plantillas = (db.query(PlantillaPieza)
                            .filter_by(prenda_catalogo_id=prenda_cat.id)
                            .order_by(PlantillaPieza.orden).all())
            n_plantilla = len(plantillas)
            plantilla_nombres = [p.nombre for p in plantillas]

    return {
        "of_id":              of_id,
        "numero_of":          of.numero_of,
        "tipo_prenda":        of.tipo_prenda,
        "prenda_catalogo_id": of.prenda_catalogo_id,
        "prenda_catalogo":    prenda_cat.nombre if prenda_cat else None,
        "prenda_tipo_base":   prenda_cat.tipo_base if prenda_cat else None,
        "n_piezas_of":        n_piezas_of,
        "n_plantilla_piezas": n_plantilla,
        "plantilla_piezas":   plantilla_nombres,
        "diagnostico": (
            "OK: piezas ya generadas" if n_piezas_of > 0 else
            f"OK: plantilla tiene {n_plantilla} piezas, listo para generar" if n_plantilla > 0 else
            "PROBLEMA: plantilla vacía - agrega piezas al catálogo primero" if prenda_cat else
            f"PROBLEMA: no se encontró prenda en catálogo con tipo_base='{of.tipo_prenda}'"
        ),
    }


# ── Constantes de validación de uploads ───────────────────────
_EXTENSIONES_PERMITIDAS = {
    ".pdf", ".png", ".jpg", ".jpeg", ".webp",
    ".xlsx", ".xls", ".docx", ".doc",
    ".csv", ".txt",
}
_MAX_BYTES = 20 * 1024 * 1024   # 20 MB (coincide con MAX_UPLOAD_MB en .env)


# ── API: subir documento ──────────────────────────────────────
@router.post("/api/{of_id}/documentos")
async def subir_documento(
    of_id: int,
    tipo: str = Form(...),
    archivo: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    # Validar extensión
    import pathlib
    ext = pathlib.Path(archivo.filename or "").suffix.lower()
    if ext not in _EXTENSIONES_PERMITIDAS:
        raise HTTPException(
            400,
            f"Tipo de archivo no permitido ({ext or 'sin extensión'}). "
            f"Permitidos: {', '.join(sorted(_EXTENSIONES_PERMITIDAS))}"
        )

    # Validar tamaño (leer todo en memoria para contar bytes)
    contenido = await archivo.read()
    if len(contenido) > _MAX_BYTES:
        raise HTTPException(
            400,
            f"El archivo supera el límite de {_MAX_BYTES // 1024 // 1024} MB "
            f"(tamaño recibido: {len(contenido) // 1024 // 1024} MB)"
        )
    await archivo.seek(0)   # rebobinar para que shutil pueda leerlo

    of = db.query(OrdenFabricacion).filter_by(id=of_id).first()
    if not of:
        raise HTTPException(404, "OF no encontrada")

    rol = current_user.rol.value if hasattr(current_user.rol, "value") else str(current_user.rol)
    tipo_cliente = of.tipo_cliente.value if of.tipo_cliente else "INSTITUCION"
    gate_id = tipo
    if rol not in ("ADMIN", "PLANEADOR") and not puede_subir_gate(rol, gate_id, tipo_cliente):
        raise HTTPException(403, f"Tu rol ({rol}) no tiene permiso para subir '{gate_id}' en OFs de tipo {tipo_cliente}")

    upload_dir = os.path.join(settings.UPLOAD_DIR, str(of_id))
    os.makedirs(upload_dir, exist_ok=True)
    # Usar solo el stem del nombre original + extensión validada (sin path traversal)
    nombre_seguro = pathlib.Path(archivo.filename).name
    filename = f"{uuid.uuid4().hex}_{nombre_seguro}"
    filepath = os.path.join(upload_dir, filename)

    with open(filepath, "wb") as f:
        f.write(contenido)

    # Upsert: si ya existe un doc del mismo tipo para esta OF, actualizarlo
    doc_existente = db.query(DocumentoOF).filter_by(of_id=of_id, tipo=tipo).first()
    if doc_existente:
        # Eliminar archivo físico anterior si existe y es distinto
        if doc_existente.ruta_archivo and doc_existente.ruta_archivo != filepath:
            try:
                os.remove(doc_existente.ruta_archivo)
            except OSError:
                pass
        nombre_anterior = doc_existente.nombre_archivo
        doc_existente.nombre_archivo = archivo.filename
        doc_existente.ruta_archivo   = filepath
        doc_existente.area           = rol
        doc_existente.usuario_id     = current_user.id
        accion = "REEMPLAZADO"
    else:
        doc_existente = DocumentoOF(
            of_id=of_id, tipo=tipo,
            nombre_archivo=archivo.filename, ruta_archivo=filepath,
            area=rol, usuario_id=current_user.id,
        )
        db.add(doc_existente)
        accion = "SUBIDO"

    db.add(AuditoriaDocumentoOF(
        of_id=of_id, tipo=tipo, accion=accion,
        nombre_archivo=archivo.filename, usuario_id=current_user.id,
    ))
    db.commit()

    # Auto-generar piezas desde plantilla cuando se sube la Ficha Técnica
    if tipo == "FICHA_TECNICA" and not of.piezas:
        of_service.auto_generar_piezas(of, db)

    _actualizar_estado_docs(of, db)

    return {"mensaje": "Documento subido", "archivo": archivo.filename}


# ── API: descargar documento ──────────────────────────────────
@router.get("/api/documentos/{doc_id}/descargar")
def descargar_documento(
    doc_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    doc = db.query(DocumentoOF).filter_by(id=doc_id).first()
    if not doc:
        raise HTTPException(404, "Documento no encontrado")
    if not os.path.exists(doc.ruta_archivo):
        raise HTTPException(404, "Archivo no encontrado en el servidor")
    return FileResponse(
        path=doc.ruta_archivo,
        filename=doc.nombre_archivo,
        media_type="application/octet-stream",
    )


# ── API: ficha técnica disponible en catálogo para esta OF ────
@router.get("/api/{of_id}/ficha-catalogo")
def ficha_disponible_catalogo(
    of_id: int,
    db:    Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """Devuelve la ficha técnica del catálogo si la OF tiene prenda vinculada y está en BORRADOR."""
    from app.models.catalogo import PrendaDocumento
    of = db.query(OrdenFabricacion).filter_by(id=of_id).first()
    if not of:
        raise HTTPException(404, "OF no encontrada")
    if of.estado != EstadoOF.BORRADOR:
        return {"disponible": False, "motivo": "La OF no está en BORRADOR"}
    if not of.prenda_catalogo_id:
        return {"disponible": False, "motivo": "La OF no tiene prenda de catálogo vinculada"}

    ficha = (db.query(PrendaDocumento)
             .filter_by(prenda_catalogo_id=of.prenda_catalogo_id, tipo="FICHA_TECNICA")
             .order_by(PrendaDocumento.created_at.desc())
             .first())
    if not ficha:
        return {"disponible": False, "motivo": "La prenda no tiene ficha técnica en el catálogo"}

    return {
        "disponible":     True,
        "doc_id":         ficha.id,
        "nombre_archivo": ficha.nombre_archivo,
        "descripcion":    ficha.descripcion,
        "prenda_nombre":  of.prenda_catalogo.nombre if of.prenda_catalogo else "",
    }


# ── API: usar ficha técnica del catálogo en esta OF ────────────
@router.post("/api/{of_id}/usar-ficha-catalogo")
def usar_ficha_catalogo(
    of_id:  int,
    doc_id: int     = Form(...),
    db:     Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """Copia la ficha técnica del catálogo a la OF (solo BORRADOR)."""
    import shutil as _shutil
    from app.models.catalogo import PrendaDocumento

    of = db.query(OrdenFabricacion).filter_by(id=of_id).first()
    if not of:
        raise HTTPException(404, "OF no encontrada")
    if of.estado != EstadoOF.BORRADOR:
        raise HTTPException(400, "Solo se puede usar esta opción en OFs en BORRADOR")

    ficha = db.query(PrendaDocumento).filter_by(id=doc_id, tipo="FICHA_TECNICA").first()
    if not ficha:
        raise HTTPException(404, "Ficha técnica no encontrada en el catálogo")

    upload_dir = os.path.join(settings.UPLOAD_DIR, str(of_id))
    os.makedirs(upload_dir, exist_ok=True)
    ext          = os.path.splitext(ficha.ruta_archivo)[1]
    nuevo_nombre = f"{uuid.uuid4().hex}_{ficha.nombre_archivo}"
    nueva_ruta   = os.path.join(upload_dir, nuevo_nombre)
    _shutil.copy2(ficha.ruta_archivo, nueva_ruta)

    area = current_user.rol.value if hasattr(current_user.rol, "value") else str(current_user.rol)

    doc_existente = db.query(DocumentoOF).filter_by(of_id=of_id, tipo="FICHA_TECNICA").first()
    if doc_existente:
        if doc_existente.ruta_archivo and doc_existente.ruta_archivo != nueva_ruta:
            try:
                os.remove(doc_existente.ruta_archivo)
            except OSError:
                pass
        doc_existente.nombre_archivo = ficha.nombre_archivo
        doc_existente.ruta_archivo   = nueva_ruta
        doc_existente.area           = area
        doc_existente.usuario_id     = current_user.id
        accion = "REEMPLAZADO"
    else:
        doc_existente = DocumentoOF(
            of_id=of_id, tipo="FICHA_TECNICA",
            nombre_archivo=ficha.nombre_archivo, ruta_archivo=nueva_ruta,
            area=area, usuario_id=current_user.id,
        )
        db.add(doc_existente)
        accion = "SUBIDO"

    db.add(AuditoriaDocumentoOF(
        of_id=of_id, tipo="FICHA_TECNICA", accion=accion,
        nombre_archivo=ficha.nombre_archivo, usuario_id=current_user.id,
    ))
    db.commit()

    # Auto-generar piezas si aún no las tiene
    if not of.piezas:
        of_service.auto_generar_piezas(of, db)
    from app.services.of_service import actualizar_estado_docs
    actualizar_estado_docs(of, db)

    return {"ok": True, "mensaje": f"Ficha '{ficha.nombre_archivo}' copiada a la OF"}


# ── API: actualizar códigos (SOLPED_PRENDA, SOLPED_MP, ORDEN_COMPRA) ──
class CodigosBody(PydanticBase):
    solped_prenda: Optional[str] = None
    solped_mp:     Optional[str] = None
    orden_compra:  Optional[str] = None


@router.patch("/api/{of_id}/codigos")
def actualizar_codigos(
    of_id: int,
    body: CodigosBody,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    of = db.query(OrdenFabricacion).filter_by(id=of_id).first()
    if not of:
        raise HTTPException(404, "OF no encontrada")

    rol = current_user.rol.value if hasattr(current_user.rol, "value") else str(current_user.rol)
    tipo_cliente = of.tipo_cliente.value if of.tipo_cliente else "INSTITUCION"

    if body.solped_prenda is not None:
        if rol not in ("ADMIN", "PLANEADOR") and not puede_subir_gate(rol, "SOLPED_PRENDA", tipo_cliente):
            raise HTTPException(403, f"Tu rol ({rol}) no puede actualizar SOLPED Prenda")
        of.solped_prenda = body.solped_prenda or None

    if body.solped_mp is not None:
        if rol not in ("ADMIN", "PLANEADOR") and not puede_subir_gate(rol, "SOLPED_MP", tipo_cliente):
            raise HTTPException(403, f"Tu rol ({rol}) no puede actualizar SOLPED MP")
        of.solped_mp = body.solped_mp or None

    if body.orden_compra is not None:
        if rol not in ("ADMIN", "PLANEADOR") and not puede_subir_gate(rol, "ORDEN_COMPRA", tipo_cliente):
            raise HTTPException(403, f"Tu rol ({rol}) no puede actualizar Orden de Compra")
        of.orden_compra = body.orden_compra or None

    db.commit()
    _actualizar_estado_docs(of, db)
    return {"ok": True}


# ── Helper: auto-transición estado_docs y OF ──────────────────
def _actualizar_estado_docs(of: OrdenFabricacion, db: Session):
    """Delegado a of_service.actualizar_estado_docs (compatibilidad interna)."""
    actualizar_estado_docs(of, db)


# ── API: estado de gates de la OF ────────────────────────────
@router.get("/api/{of_id}/gates")
def get_gates(
    of_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    of = db.query(OrdenFabricacion).filter_by(id=of_id).first()
    if not of:
        raise HTTPException(404, "OF no encontrada")
    gates = calcular_gates(of, db)
    ok, faltantes = puede_activar(of, db)
    return {
        "puede_activar": ok,
        "faltantes": faltantes,
        "gates": gates_to_dict(gates),
    }


# ── API: activar OF ───────────────────────────────────────────
@router.post("/api/{of_id}/activar")
def activar_of(
    of_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    of = db.query(OrdenFabricacion).filter_by(id=of_id).first()
    if not of:
        raise HTTPException(404, "OF no encontrada")

    if len(of.piezas) == 0:
        raise HTTPException(400, "La OF no tiene piezas definidas")

    ok, faltantes = puede_activar(of, db)
    if not ok:
        raise HTTPException(400, f"Gates pendientes: {', '.join(faltantes)}")

    of.estado = EstadoOF.ACTIVA
    db.commit()
    return {"mensaje": "OF activada", "estado": of.estado}


# ── Cuerpo para planificar OF ─────────────────────────────────
class PlanificarBody(PydanticBase):
    fecha_inicio_plan: Optional[str] = None
    fecha_apt:         Optional[str] = None
    orden_plan:        Optional[int] = None
    force:             bool = False




# ── API: planificar (Gantt — fechas y prioridad) ──────────────
@router.patch("/api/{of_id}/planificar")
def planificar_of(
    of_id: int,
    body: PlanificarBody,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    of = db.query(OrdenFabricacion).filter_by(id=of_id).first()
    if not of:
        raise HTTPException(404, "OF no encontrada")

    # Guardrail fecha pasada
    if body.fecha_inicio_plan and body.fecha_inicio_plan != "":
        import datetime as _dt
        _fecha_dest = _safe_date(body.fecha_inicio_plan)
        if _fecha_dest and _fecha_dest < _dt.date.today():
            raise HTTPException(400, "No se puede asignar una fecha de inicio anterior a hoy")

    # Guardrail capacidad: verificar que el día destino no supere el techo diario
    if body.fecha_inicio_plan and body.fecha_inicio_plan != "" and not body.force:
        try:
            capacidad_max = int(ParametroSistema.get(db, "corte_cap_diaria_juegos", "500"))
            fecha_dest = _safe_date(body.fecha_inicio_plan)
            carga_dia = (
                db.query(sa_func.sum(OrdenFabricacion.total_juegos))
                .filter(
                    OrdenFabricacion.fecha_inicio_plan == fecha_dest,
                    OrdenFabricacion.estado != EstadoOF.ANULADA,
                    OrdenFabricacion.id != of_id,
                )
                .scalar() or 0
            )
            nueva_carga = carga_dia + (of.total_juegos or 0)
            if nueva_carga > capacidad_max:
                return JSONResponse(
                    status_code=409,
                    content={
                        "over_capacity": True,
                        "capacidad_max": capacidad_max,
                        "carga_actual":  int(carga_dia),
                        "of_juegos":     int(of.total_juegos or 0),
                        "nueva_carga":   int(nueva_carga),
                        "exceso":        int(nueva_carga - capacidad_max),
                        "fecha":         str(fecha_dest),
                    },
                )
        except Exception:
            pass  # si falla la validación, continúa sin bloquear

    # Guardrail: si se cambia fecha_inicio_plan y la OF ya tiene actividad real,
    # pedir confirmación explícita (force=True) para no silenciar el conflicto.
    if body.fecha_inicio_plan is not None and not body.force:
        fases_reales = (
            db.query(OFFaseTiempos)
            .filter(
                OFFaseTiempos.of_id == of_id,
                OFFaseTiempos.inicio_real.isnot(None),
            )
            .all()
        )
        if fases_reales:
            return JSONResponse(
                status_code=409,
                content={
                    "needs_confirm": True,
                    "fases_con_real": [
                        {
                            "fase_id":    t.fase_id,
                            "nombre":     NOMBRES_FASE.get(t.fase_id, t.fase_id),
                            "inicio_real": t.inicio_real.strftime("%d/%m %H:%M"),
                        }
                        for t in fases_reales
                    ],
                },
            )

    if body.fecha_inicio_plan is not None:
        of.fecha_inicio_plan = _safe_date(body.fecha_inicio_plan) if body.fecha_inicio_plan else None
    if body.fecha_apt is not None:
        of.fecha_apt = _safe_date(body.fecha_apt) if body.fecha_apt else None
    if body.orden_plan is not None:
        of.orden_plan = body.orden_plan

    # ── Bloque 2: auto-derivar inicio_programado para fases sin inicio_real ──
    if body.fecha_inicio_plan and of.fecha_inicio_plan:
        auto_derivar_programado(of, db)

    db.commit()
    return {"ok": True}


# ── Página: editar piezas ─────────────────────────────────────
@router.get("/{of_id}/editar-piezas", response_class=HTMLResponse)
def editar_piezas_page(
    of_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    of = db.query(OrdenFabricacion).filter_by(id=of_id).first()
    if not of:
        raise HTTPException(404, "OF no encontrada")
    if of.estado != EstadoOF.BORRADOR:
        raise HTTPException(400, "Solo se pueden editar piezas de OFs en BORRADOR")
    rol = current_user.rol.value if hasattr(current_user.rol, "value") else str(current_user.rol)
    if rol not in ("ADMIN", "PLANEADOR"):
        raise HTTPException(403, "Solo ADMIN o PLANEADOR pueden editar piezas")
    return templates.TemplateResponse("of/editar_piezas.html", {
        "request": request, "of": of, "current_user": current_user,
    })


# ── API: guardar edición de piezas ────────────────────────────
class PiezaEditItem(PydanticBase):
    id:              int
    nombre:          str
    codigo_sap:      Optional[str] = None
    material:        str = "TELA"
    cantidad_x_prenda: int = 1
    fusionado:       bool = False


class EditarPiezasBody(PydanticBase):
    piezas: list[PiezaEditItem]


@router.post("/api/{of_id}/editar-piezas")
def guardar_edicion_piezas(
    of_id: int,
    body: EditarPiezasBody,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    of = db.query(OrdenFabricacion).filter_by(id=of_id).first()
    if not of:
        raise HTTPException(404, "OF no encontrada")
    if of.estado != EstadoOF.BORRADOR:
        raise HTTPException(400, "Solo se pueden editar piezas de OFs en BORRADOR")
    rol = current_user.rol.value if hasattr(current_user.rol, "value") else str(current_user.rol)
    if rol not in ("ADMIN", "PLANEADOR"):
        raise HTTPException(403, "Sin permiso")

    piezas_map = {p.id: p for p in of.piezas}

    for item in body.piezas:
        pieza = piezas_map.get(item.id)
        if not pieza:
            continue
        pieza.nombre           = item.nombre
        pieza.codigo_sap       = item.codigo_sap or None
        pieza.material         = item.material
        pieza.cantidad_x_prenda = item.cantidad_x_prenda
        pieza.fusionado        = item.fusionado

    db.commit()
    return {"ok": True, "actualizadas": len(body.piezas)}


# ── API: Curva de tallas en OF ────────────────────────────────────────────────

class TallaDistEntry(PydanticBase):
    sku_id:   int
    cantidad: int


@router.get("/api/{of_id}/tallas-dist")
def api_get_tallas_dist(
    of_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """Retorna distribucion actual de tallas para la OF y los SKUs disponibles."""
    of = db.query(OrdenFabricacion).filter_by(id=of_id).first()
    if not of:
        raise HTTPException(404, "OF no encontrada")

    # SKUs disponibles de la variante vinculada
    skus_disponibles = []
    if of.prenda_catalogo_id:
        skus = (db.query(PrendaSku)
                  .filter_by(prenda_catalogo_id=of.prenda_catalogo_id, activo=True)
                  .order_by(PrendaSku.orden)
                  .all())
        skus_disponibles = [{"id": s.id, "talla": s.talla, "codigo_sku": s.codigo_sku} for s in skus]

    # Distribucion guardada
    dist = {d.sku_id: d.cantidad for d in of.talla_distribucion}
    total = sum(dist.values())

    return {
        "of_id":             of_id,
        "total_juegos":      of.total_juegos,
        "skus_disponibles":  skus_disponibles,
        "distribucion":      dist,
        "total_distribuido": total,
    }


class TallaDistBody(PydanticBase):
    entries: List[TallaDistEntry]


@router.post("/api/{of_id}/tallas-dist")
def api_guardar_tallas_dist(
    of_id: int,
    body: TallaDistBody,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """Guarda la distribución de tallas para la OF (reemplaza la anterior)."""
    of = db.query(OrdenFabricacion).filter_by(id=of_id).first()
    if not of:
        raise HTTPException(404, "OF no encontrada")

    # Validar SKUs si la OF tiene prenda asociada
    if of.prenda_catalogo_id:
        skus_validos = {
            s.id for s in db.query(PrendaSku)
            .filter_by(prenda_catalogo_id=of.prenda_catalogo_id, activo=True)
            .all()
        }
        for e in body.entries:
            if e.sku_id not in skus_validos:
                raise HTTPException(400, f"SKU {e.sku_id} no pertenece a la prenda")

    # Reemplazar distribución
    db.query(OFTallaDistribucion).filter_by(of_id=of_id).delete()
    for e in body.entries:
        if e.cantidad > 0:
            db.add(OFTallaDistribucion(of_id=of_id, sku_id=e.sku_id, cantidad=e.cantidad))

    db.commit()
    return {"ok": True, "msg": "Distribución de tallas guardada"}


# ── API: Tercerización ────────────────────────────────────────────────────────

class TercBody(PydanticBase):
    planta_id: int
    fecha_envio: Optional[str] = None
    fecha_recepcion_est: Optional[str] = None
    fase_id: Optional[str] = None

class RecepcionBody(PydanticBase):
    juegos_recibidos: int
    fecha_recepcion: str
    observacion: Optional[str] = None

class FechaBody(PydanticBase):
    fecha_recepcion_est: str
    motivo: Optional[str] = None


@router.post("/api/{of_id}/tercerizar")
def api_tercerizar(
    of_id: int,
    body: TercBody,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    of = db.query(OrdenFabricacion).options(
        selectinload(OrdenFabricacion.piezas).selectinload(OFPieza.fases_estado)
    ).filter_by(id=of_id).first()
    if not of:
        raise HTTPException(404, "OF no encontrada")
    return of_service.tercerizar(
        of, body.planta_id, body.fecha_envio, body.fecha_recepcion_est,
        current_user, db, fase_id=body.fase_id,
    )


@router.post("/api/{of_id}/tercerizar/enviar")
def api_marcar_enviada(
    of_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    of = db.query(OrdenFabricacion).filter_by(id=of_id).first()
    if not of:
        raise HTTPException(404, "OF no encontrada")
    return of_service.marcar_enviada(of, current_user, db)


@router.post("/api/{of_id}/tercerizar/recepcion")
def api_registrar_recepcion(
    of_id: int,
    body: RecepcionBody,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    of = db.query(OrdenFabricacion).options(
        selectinload(OrdenFabricacion.piezas).selectinload(OFPieza.fases_estado)
    ).filter_by(id=of_id).first()
    if not of:
        raise HTTPException(404, "OF no encontrada")
    if not of.tercerizado:
        raise HTTPException(400, "OF no está tercerizada")
    from app.core.auth import get_rol
    if get_rol(current_user) not in ("ADMIN", "PLANEADOR"):
        raise HTTPException(403, "Sin permiso")

    fecha_recep = _safe_date(body.fecha_recepcion)
    # Obtener fase_id del TercSubprocesoLog más reciente (fase_tercerizada no existe en el modelo)
    _log_fase = db.query(TercSubprocesoLog).filter_by(of_id=of_id).order_by(TercSubprocesoLog.id.desc()).first()
    fase_id_guardada = _log_fase.fase_id if _log_fase else None

    recep = TercRecepcion(
        of_id=of_id,
        planta_id=of.planta_id,
        fase_id=fase_id_guardada,
        juegos_recibidos=body.juegos_recibidos,
        fecha_recepcion=fecha_recep,
        observacion=body.observacion,
        usuario_id=current_user.id,
    )
    db.add(recep)
    of.juegos_recibidos = (of.juegos_recibidos or 0) + body.juegos_recibidos
    of.fecha_recepcion_real = fecha_recep

    recepcion_completa = of.juegos_recibidos >= (of.total_juegos or 0)
    of.estado_tercerizado = "RECIBIDA" if recepcion_completa else "ENVIADA"

    from datetime import datetime as dt
    log = db.query(TercSubprocesoLog).filter_by(
        of_id=of_id, fase_id=fase_id_guardada
    ).order_by(TercSubprocesoLog.id.desc()).first()
    if log:
        log.juegos_recibidos = (log.juegos_recibidos or 0) + body.juegos_recibidos
        log.fecha_recepcion_real = fecha_recep
        if recepcion_completa:
            log.estado = "COMPLETADO"
            log.fecha_completado = dt.now()
        log.usuario_recepcion_id = current_user.id
        if body.observacion:
            log.observacion = body.observacion

    if recepcion_completa:
        if fase_id_guardada:
            for p in of.piezas:
                for fe in p.fases_estado:
                    if fe.fase_id == fase_id_guardada:
                        fe.cantidad_actual = fe.max_cantidad
                        fe.completada = True
            # Escribir fin_real en OFFaseTiempos de la fase tercerizada
            t = db.query(OFFaseTiempos).filter_by(
                of_id=of_id, fase_id=fase_id_guardada
            ).first()
            if t is None:
                t = OFFaseTiempos(of_id=of_id, fase_id=fase_id_guardada)
                db.add(t)
            t.fin_real = dt.combine(fecha_recep, dt.min.time())
        of.tercerizado = False
        # of.fase_tercerizada no existe en el modelo; fase queda en TercSubprocesoLog

    db.commit()
    return {"ok": True, "msg": f"Recepción registrada: {body.juegos_recibidos} juegos", "completa": recepcion_completa}


@router.patch("/api/{of_id}/tercerizar/fecha")
def api_actualizar_fecha(
    of_id: int,
    body: FechaBody,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    of = db.query(OrdenFabricacion).filter_by(id=of_id).first()
    if not of:
        raise HTTPException(404, "OF no encontrada")
    return of_service.actualizar_fecha_recepcion(
        of, body.fecha_recepcion_est, body.motivo, current_user, db
    )


@router.get("/api/{of_id}/fases-pendientes")
def api_fases_pendientes(
    of_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """Fases con al menos una pieza sin completar en esta OF."""
    from app.constants import ORDEN_FASES, NOMBRES_FASE
    of = db.query(OrdenFabricacion).filter_by(id=of_id).first()
    if not of:
        raise HTTPException(404, "OF no encontrada")

    estados = db.query(OFFaseEstado).filter_by(of_id=of_id).all()

    # Fases que realmente tienen registros para esta OF
    fases_con_registro = {e.fase_id for e in estados}
    total_por_fase = {}
    completadas_por_fase = {}
    for e in estados:
        total_por_fase[e.fase_id] = total_por_fase.get(e.fase_id, 0) + 1
        if e.completada:
            completadas_por_fase[e.fase_id] = completadas_por_fase.get(e.fase_id, 0) + 1

    pendientes = []
    for fid in ORDEN_FASES:
        if fid not in fases_con_registro:
            continue  # fase no aplica a esta OF
        total = total_por_fase.get(fid, 0)
        completadas = completadas_por_fase.get(fid, 0)
        if completadas < total:
            pendientes.append({"fase_id": fid, "nombre": NOMBRES_FASE.get(fid, fid)})

    return pendientes
