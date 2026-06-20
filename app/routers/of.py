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
from typing import Optional
from pydantic import BaseModel as PydanticBase
import os, shutil, uuid, json

from app.database.connection import get_db
from app.models.planta import PlantaExterna, TercHistorialFecha, TercRecepcion
from app.models.of import OrdenFabricacion, EstadoOF, TipoPrendaEnum, TipoDocumentoOF, DocumentoOF, TipoClienteEnum, EstadoDocsEnum
from app.models.pieza import OFPieza, PlantillaPieza
from app.models.fase import OFFaseEstado, FaseCatalogo
from app.core.auth import get_current_user
from app.core.templates import templates
from app.models.usuario import Usuario
from app.config import settings
from app.services.gate_service import calcular_gates, puede_activar, gates_to_dict, puede_subir_gate, GATES, GATES_REQUERIDOS
from app.services.of_service import actualizar_estado_docs
from app.services.semaforo_service import calcular_semaforo
from app.models.fase import AvanceRegistro
from app.constants import ORDEN_FASES, NOMBRES_FASE, FASES_GANTT, FASES_GANTT_LBL

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
    rol = current_user.rol.value if hasattr(current_user.rol, "value") else str(current_user.rol)
    if rol not in ROLES_PLAN_CORTE:
        raise HTTPException(403, "No tienes permiso para ver el Plan de Corte")
    ofs_raw = (
        db.query(OrdenFabricacion)
        .options(
            selectinload(OrdenFabricacion.piezas).selectinload(OFPieza.fases_estado),
            selectinload(OrdenFabricacion.recepciones_terc),
        )
        .filter(OrdenFabricacion.estado != EstadoOF.ANULADA)
        .all()
    )
    ofs_raw = sorted(ofs_raw, key=lambda x: (
        x.orden_plan if x.orden_plan is not None else 9999,
        x.fecha_apt or date(2099, 1, 1),
    ))

    today = date.today()
    ofs_data = []
    tasks_json = []

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

        ofs_data.append({
            "of": of,
            "semaforo": sem,
            "pct": pct,
            "fases_chips": fases_chips,
            "fecha_inicio_str": inicio.isoformat(),
            "fecha_apt_str": apt.isoformat(),
            "color_class": color_class,
            "apt_class": apt_class,
            "orden_num": orden_num,
        })

        tasks_json.append({
            "id":    str(of.id),
            "name":  of.numero_of,
            "start": inicio.isoformat(),
            "end":   apt.isoformat(),
            "progress": pct,
            "custom_class": color_class,
            "_cliente": of.cliente[:35],
            "_estado":  of.estado.value,
            "_apt":     of.fecha_apt.isoformat() if of.fecha_apt else "",
        })

    return templates.TemplateResponse("of/plan_corte.html", {
        "request":    request,
        "ofs":        ofs_data,
        "tasks_json": json.dumps(tasks_json),
        "current_user": current_user,
        "FASES_GANTT": FASES_GANTT,
    })


# ── Detalle unificado de OF ───────────────────────────────────
@router.get("/{of_id}/detalle", response_class=HTMLResponse)
def detalle_of(
    of_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    of = db.query(OrdenFabricacion).filter_by(id=of_id).first()
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
    })


# ── Formulario crear OF ───────────────────────────────────────
@router.get("/crear", response_class=HTMLResponse)
def crear_of_page(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    usuarios = db.query(Usuario).filter(Usuario.activo == True).all()
    return templates.TemplateResponse("of/crear.html", {
        "request": request, "usuarios": usuarios, "current_user": current_user,
    })


# ── API: crear OF ─────────────────────────────────────────────
@router.post("/api/crear")
def crear_of(
    numero_of: str = Form(...),
    cliente: str = Form(...),
    tipo_prenda: str = Form(...),
    total_juegos: int = Form(...),
    fecha_apt: str = Form(None),
    responsable_id: int = Form(None),
    tipo_cliente: str = Form("INSTITUCION"),
    solped_prenda: str = Form(None),
    orden_compra: str = Form(None),
    solped_mp: str = Form(None),
    estampado_activo: bool = Form(False),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    existe = db.query(OrdenFabricacion).filter_by(numero_of=numero_of).first()
    if existe:
        raise HTTPException(400, f"Ya existe una OF con número {numero_of}")
    if total_juegos < 1:
        raise HTTPException(400, "El total de juegos debe ser mayor a 0")

    of = OrdenFabricacion(
        numero_of=numero_of,
        cliente=cliente,
        tipo_prenda=tipo_prenda,
        total_juegos=total_juegos,
        fecha_creacion=date.today(),
        fecha_apt=_safe_date(fecha_apt) if fecha_apt else None,
        responsable_id=responsable_id,
        tipo_cliente=tipo_cliente,
        solped_prenda=solped_prenda,
        orden_compra=orden_compra,
        solped_mp=solped_mp,
        estampado_activo=estampado_activo,
        estado=EstadoOF.BORRADOR,
        estado_docs=EstadoDocsEnum.PENDIENTE,
    )
    db.add(of)
    db.commit()
    db.refresh(of)
    return {"id": of.id, "numero_of": of.numero_of, "estado": of.estado}


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
    _crear_fases_pieza(pieza, of, db)
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

    plantillas = db.query(PlantillaPieza).filter_by(
        tipo_prenda=of.tipo_prenda
    ).order_by(PlantillaPieza.orden).all()

    piezas_creadas = []
    for p in plantillas:
        pieza = OFPieza(
            of_id=of_id, nombre=p.nombre, material=p.material_default,
            cantidad_x_prenda=p.cantidad_x_prenda, fusionado=p.fusionado_default,
            orden=p.orden,
        )
        db.add(pieza)
        db.flush()
        _crear_fases_pieza(pieza, of, db)
        piezas_creadas.append(pieza.nombre)

    db.commit()
    return {"piezas_creadas": piezas_creadas}


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

    doc = DocumentoOF(
        of_id=of_id, tipo=tipo,
        nombre_archivo=archivo.filename, ruta_archivo=filepath,
        area=rol, usuario_id=current_user.id,
    )
    db.add(doc)
    db.commit()

    # Auto-generar piezas desde plantilla cuando se sube la Ficha Técnica
    if tipo == "FICHA_TECNICA" and not of.piezas:
        plantillas = db.query(PlantillaPieza).filter_by(
            tipo_prenda=of.tipo_prenda
        ).order_by(PlantillaPieza.orden).all()
        for p in plantillas:
            pieza = OFPieza(
                of_id=of_id, nombre=p.nombre, material=p.material_default,
                cantidad_x_prenda=p.cantidad_x_prenda,
                fusionado=p.fusionado_default, orden=p.orden,
            )
            db.add(pieza)
            db.flush()
            _crear_fases_pieza(pieza, of, db)
        if plantillas:
            db.commit()

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

    piezas_sin_sap = [p for p in of.piezas if not p.codigo_sap]
    if piezas_sin_sap:
        raise HTTPException(400, f"Piezas sin código SAP: {[p.nombre for p in piezas_sin_sap]}")

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
    if body.fecha_inicio_plan is not None:
        of.fecha_inicio_plan = _safe_date(body.fecha_inicio_plan) if body.fecha_inicio_plan else None
    if body.fecha_apt is not None:
        of.fecha_apt = _safe_date(body.fecha_apt) if body.fecha_apt else None
    if body.orden_plan is not None:
        of.orden_plan = body.orden_plan
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
        pieza.nombre            = item.nombre
        pieza.codigo_sap        = item.codigo_sap or None
        pieza.material          = item.material
        pieza.cantidad_x_prenda = item.cantidad_x_prenda
        pieza.fusionado         = item.fusionado

    db.commit()
    _actualizar_estado_docs(of, db)
    return {"ok": True, "actualizadas": len(body.piezas)}







# ── API: obtener piezas (para modal SAP) ──────────────────────
@router.get("/api/{of_id}/piezas")
def get_piezas(
    of_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    of = db.query(OrdenFabricacion).filter_by(id=of_id).first()
    if not of:
        raise HTTPException(404, "OF no encontrada")
    return [{"id": p.id, "nombre": p.nombre, "codigo_sap": p.codigo_sap or ""} for p in of.piezas]


# ── API: actualizar solo códigos SAP (UDP + ADMIN + PLANEADOR) ─
class SapCodigosBody(PydanticBase):
    piezas: list[dict]  # [{id, codigo_sap}]


ROLES_SAP = {"UDP", "COMERCIAL_MARCA", "ADMIN", "PLANEADOR"}

@router.patch("/api/{of_id}/piezas-sap")
def actualizar_sap(
    of_id: int,
    body: SapCodigosBody,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    of = db.query(OrdenFabricacion).filter_by(id=of_id).first()
    if not of:
        raise HTTPException(404, "OF no encontrada")
    rol = current_user.rol.value if hasattr(current_user.rol, "value") else str(current_user.rol)
    if rol not in ROLES_SAP:
        raise HTTPException(403, "Sin permiso para editar códigos SAP")
    piezas_map = {p.id: p for p in of.piezas}
    for item in body.piezas:
        pieza = piezas_map.get(item["id"])
        if pieza:
            pieza.codigo_sap = item.get("codigo_sap") or None
    db.commit()
    _actualizar_estado_docs(of, db)
    return {"ok": True}

# ── Tercerización ─────────────────────────────────────────────
class TercerizarBody(PydanticBase):
    planta_id: int
    fecha_envio: Optional[str] = None
    fecha_recepcion_est: Optional[str] = None


class ActualizarFechaBody(PydanticBase):
    fecha_recepcion_est: str
    motivo: Optional[str] = None


class RecepcionParcialBody(PydanticBase):
    juegos_recibidos: int
    fecha_recepcion: str
    observacion: Optional[str] = None


@router.post("/api/{of_id}/tercerizar")
def tercerizar_of(
    of_id: int,
    body: TercerizarBody,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    of = db.query(OrdenFabricacion).filter_by(id=of_id).first()
    if not of:
        raise HTTPException(404, "OF no encontrada")
    rol = current_user.rol.value if hasattr(current_user.rol, "value") else str(current_user.rol)
    if rol not in ("ADMIN", "PLANEADOR"):
        raise HTTPException(403, "Solo ADMIN o PLANEADOR pueden tercerizar una OF")
    if of.estado != EstadoOF.ACTIVA:
        raise HTTPException(400, "Solo se puede tercerizar una OF en estado ACTIVA")
    if of.estado_docs != EstadoDocsEnum.COMPLETA:
        raise HTTPException(400, "Los gates documentales deben estar completos antes de tercerizar")
    tiene_avance = any(
        fe.cantidad_actual > 0 or fe.completada
        for p in of.piezas for fe in p.fases_estado
    )
    if tiene_avance:
        raise HTTPException(400, "No se puede tercerizar una OF que ya tiene avance de corte")

    planta = db.query(PlantaExterna).filter_by(id=body.planta_id, activo=True).first()
    if not planta:
        raise HTTPException(404, "Planta externa no encontrada o inactiva")

    of.tercerizado = True
    of.planta_id = planta.id
    of.planta_externa = planta.nombre
    of.estado_tercerizado = "PENDIENTE_ENVIO"
    of.juegos_recibidos = 0
    if body.fecha_envio:
        of.fecha_envio = _safe_date(body.fecha_envio)
    if body.fecha_recepcion_est:
        fecha_recep = _safe_date(body.fecha_recepcion_est)
        if of.fecha_apt and fecha_recep > of.fecha_apt:
            raise HTTPException(400, f"La fecha de recepción estimada ({fecha_recep}) no puede superar el APT de la OF ({of.fecha_apt})")
        of.fecha_recepcion_est = fecha_recep
    db.commit()
    return {"ok": True, "mensaje": f"OF {of.numero_of} tercerizada a {planta.nombre}"}


@router.post("/api/{of_id}/tercerizar/enviar")
def marcar_enviada(
    of_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    of = db.query(OrdenFabricacion).filter_by(id=of_id).first()
    if not of or not of.tercerizado:
        raise HTTPException(404, "OF no encontrada o no esta tercerizada")
    rol = current_user.rol.value if hasattr(current_user.rol, "value") else str(current_user.rol)
    if rol not in ("ADMIN", "PLANEADOR"):
        raise HTTPException(403, "Sin permiso")
    of.estado_tercerizado = "ENVIADA"
    if not of.fecha_envio:
        from datetime import datetime
        of.fecha_envio = datetime.now().date()
    db.commit()
    return {"ok": True, "estado_tercerizado": "ENVIADA"}


@router.patch("/api/{of_id}/tercerizar/fecha")
def actualizar_fecha_recepcion(
    of_id: int,
    body: ActualizarFechaBody,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    of = db.query(OrdenFabricacion).filter_by(id=of_id).first()
    if not of or not of.tercerizado:
        raise HTTPException(404, "OF no encontrada o no esta tercerizada")
    rol = current_user.rol.value if hasattr(current_user.rol, "value") else str(current_user.rol)
    if rol not in ("ADMIN", "PLANEADOR"):
        raise HTTPException(403, "Sin permiso")

    nueva_fecha = _safe_date(body.fec