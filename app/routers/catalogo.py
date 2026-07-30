"""
Router: Catalogo de prendas
Prefijo: /catalogo
Roles permitidos para CRUD: ADMIN, UDP, COMERCIAL_MARCA
Roles solo lectura: todos los demas
"""
import os
import io
import uuid
import datetime
from typing import Optional, List

from PIL import Image

from fastapi import APIRouter, Depends, HTTPException, Request, Form, UploadFile, File
from fastapi import Form as _Form
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from pydantic import BaseModel as _PBase
from sqlalchemy.orm import Session

from app.config import settings
from app.database.connection import get_db
from app.core.auth import get_current_user
from app.core.templates import templates
from app.models.usuario import Usuario
from app.models.catalogo import (
    PrendaCatalogo, PrendaDocumento,
    CatalogoAvio, PrendaAvioConfig,
    CatalogoMp, PrendaMpConfig,
    PrendaSku, PrendaSkuMpConfig, PrendaSkuAvioConfig,
    TIPOS_BASE_PRENDA, FITS_PRENDA, TIPOS_DOC_PRENDA,
    SECCIONES_AVIO, UNIDADES_MEDIDA, MONEDAS_AVIO,
    TIPOS_MP, UNIDADES_MP,
)
from app.models.pieza import PlantillaPieza
from app.services import storage

router = APIRouter()

from app.roles import ROLES_EDITOR_CATALOGO as ROLES_EDITOR

UPLOAD_PRENDA = "static/uploads/prendas"
UPLOAD_PIEZA  = "static/uploads/piezas"
UPLOAD_DOCS   = "static/uploads/docs_prenda"

EXTS_IMAGEN = {".jpg", ".jpeg", ".png", ".webp"}
TIPOS_CLIENTE_PRENDA = ["INSTITUCION", "MARCA", "BASE"]


def _rol(usuario: Usuario) -> str:
    return usuario.rol.value if hasattr(usuario.rol, "value") else str(usuario.rol)


def _guardar_imagen(archivo: UploadFile, carpeta: str) -> str:
    ext = os.path.splitext(archivo.filename or "")[1].lower()
    if ext not in EXTS_IMAGEN:
        raise HTTPException(400, f"Formato no permitido. Use: {', '.join(EXTS_IMAGEN)}")
    try:
        data = archivo.file.read()
        img = Image.open(io.BytesIO(data)).convert("RGB")
        w, h = img.size
        lado = min(w, h)
        left = (w - lado) // 2
        top  = (h - lado) // 2
        img  = img.crop((left, top, left + lado, top + lado))
        img  = img.resize((600, 600), Image.LANCZOS)
        nombre = f"{uuid.uuid4().hex}.jpg"
        buf = io.BytesIO()
        img.save(buf, "JPEG", quality=85, optimize=True)
        return storage.save_bytes(buf.getvalue(), carpeta, nombre)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(400, "No se pudo procesar la imagen. Verifica que el archivo no esté dañado.")


def _borrar_imagen(ruta: Optional[str]):
    storage.delete(ruta or "")


def _prenda_base_de(prenda: PrendaCatalogo, db: Session) -> Optional[PrendaCatalogo]:
    if prenda.tipo_cliente == "BASE":
        return prenda
    return (
        db.query(PrendaCatalogo)
          .filter_by(tipo_base=prenda.tipo_base, tipo_cliente="BASE", activo=True)
          .first()
    )


# ── Vistas HTML ───────────────────────────────────────────────────────────────

@router.get("/", response_class=HTMLResponse)
def catalogo_lista(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
    tipo_base:    str = "",
    tipo_cliente: str = "",
    q:            str = "",
    solo_activos: str = "1",
):
    query = db.query(PrendaCatalogo)
    if tipo_base:
        query = query.filter(PrendaCatalogo.tipo_base == tipo_base)
    if tipo_cliente == "VARIANTE":
        query = query.filter(PrendaCatalogo.tipo_cliente != "BASE")
    elif tipo_cliente:
        query = query.filter(PrendaCatalogo.tipo_cliente == tipo_cliente)
    if q:
        like = f"%{q}%"
        query = query.filter(
            PrendaCatalogo.nombre.ilike(like) | PrendaCatalogo.codigo.ilike(like)
        )
    if solo_activos == "1":
        query = query.filter(PrendaCatalogo.activo == True)

    prendas = query.order_by(PrendaCatalogo.tipo_base, PrendaCatalogo.nombre).all()
    for p in prendas:
        p._num_piezas = len(p.plantilla_piezas)
        p._num_skus   = len(p.skus)

    # Stats calculados sobre el resultado filtrado
    total_bases       = sum(1 for p in prendas if p.tipo_cliente == "BASE")
    total_variantes   = sum(1 for p in prendas if p.tipo_cliente != "BASE")
    total_skus        = sum(p._num_skus for p in prendas)
    total_piezas_base = sum(p._num_piezas for p in prendas if p.tipo_cliente == "BASE")

    return templates.TemplateResponse("catalogo/lista.html", {
        "request":            request,
        "current_user":       current_user,
        "prendas":            prendas,
        "tipos_base":         TIPOS_BASE_PRENDA,
        "fits":               FITS_PRENDA,
        "tipo_base":          tipo_base,
        "tipo_cliente":       tipo_cliente,
        "q":                  q,
        "solo_activos":       solo_activos,
        "puede_editar":       _rol(current_user) in ROLES_EDITOR,
        "total_bases":        total_bases,
        "total_variantes":    total_variantes,
        "total_skus":         total_skus,
        "total_piezas_base":  total_piezas_base,
    })


@router.get("/nueva", response_class=HTMLResponse)
def catalogo_nueva_page(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    if _rol(current_user) not in ROLES_EDITOR:
        raise HTTPException(403, "Sin permiso para crear prendas")
    return templates.TemplateResponse("catalogo/form_prenda.html", {
        "request":       request,
        "current_user":  current_user,
        "prenda":        None,
        "tipos_base":    TIPOS_BASE_PRENDA,
        "tipos_cliente": TIPOS_CLIENTE_PRENDA,
        "fits":          FITS_PRENDA,
        "accion":        "crear",
    })


@router.get("/tipo-cambio", response_class=HTMLResponse)
def catalogo_tipo_cambio_page(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """Apartado de Logística: ver/editar el tipo de cambio USD→S/ del día.
    Debe declararse ANTES de /{prenda_id} para no chocar con esa ruta."""
    from app.roles import ROLES_TC
    return templates.TemplateResponse("catalogo/tipo_cambio.html", {
        "request":      request,
        "current_user": current_user,
        "puede_editar": _rol(current_user) in ROLES_TC,
    })


@router.get("/{prenda_id}", response_class=HTMLResponse)
def catalogo_detalle(
    prenda_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    prenda = db.query(PrendaCatalogo).filter_by(id=prenda_id).first()
    if not prenda:
        raise HTTPException(404, "Prenda no encontrada")

    # Piezas efectivas: propias (base o variante con ficha propia) o heredadas de la base.
    piezas     = sorted(prenda.piezas_efectivas, key=lambda p: p.orden)
    documentos = sorted(prenda.documentos, key=lambda d: d.created_at or datetime.datetime.min, reverse=True)

    # Resolver prenda BASE (prioriza el FK base_id; fallback al viejo match por tipo_base)
    if prenda.tipo_cliente == "BASE":
        prenda_base        = prenda
        prenda_base_nombre = None
    else:
        prenda_base = prenda.base or (
            db.query(PrendaCatalogo)
            .filter_by(tipo_base=prenda.tipo_base, tipo_cliente="BASE", activo=True)
            .first()
        )
        prenda_base_nombre = prenda_base.nombre if prenda_base else None

    # Tab Avíos
    if prenda.tipo_cliente == "BASE":
        avios_mostrar    = sorted(prenda.avios, key=lambda a: (a.seccion, a.orden))
        avio_configs_map = {}
        avios_propios    = []
    else:
        avios_mostrar    = sorted(prenda_base.avios, key=lambda a: (a.seccion, a.orden)) if prenda_base else []
        avio_configs_map = {c.avio_id: c for c in prenda.avio_configs}
        avios_propios    = sorted(prenda.avios, key=lambda a: (a.seccion, a.orden))

    # Tab Materia Prima
    if prenda.tipo_cliente == "BASE":
        materiales      = sorted(prenda.materiales, key=lambda m: (m.tipo, m.orden))
        mp_configs_map  = {}
        materiales_propios = []
    else:
        materiales      = sorted(prenda_base.materiales, key=lambda m: (m.tipo, m.orden)) if prenda_base else []
        mp_configs_map  = {c.mp_id: c for c in prenda.mp_configs}
        materiales_propios = sorted(prenda.materiales, key=lambda m: (m.tipo, m.orden))

    # Tab SKUs
    tallas = sorted(prenda.skus, key=lambda t: t.orden)

    # Tabs Servicios + MOD (heredados de la base o propios)
    servicios = sorted(prenda.servicios_efectivos, key=lambda s: s.orden)
    mod_ops   = sorted(prenda.mod_efectivos, key=lambda m: m.orden)
    mod_total = round(sum((m.subtotal or 0) for m in mod_ops), 4)
    servicios_total = round(sum((s.costo or 0) for s in servicios), 4)

    return templates.TemplateResponse("catalogo/detalle.html", {
        "request":             request,
        "current_user":        current_user,
        "prenda":              prenda,
        "piezas":              piezas,
        "documentos":          documentos,
        "tipos_doc":           TIPOS_DOC_PRENDA,
        "fits":                dict(FITS_PRENDA),
        "puede_editar":        _rol(current_user) in ROLES_EDITOR,
        "avios":               avios_mostrar,
        "avios_propios":       avios_propios,
        "avio_configs_map":    avio_configs_map,
        "prenda_base_nombre":  prenda_base_nombre,
        "secciones_avio":      SECCIONES_AVIO,
        "unidades_medida":     UNIDADES_MEDIDA,
        "monedas_avio":        MONEDAS_AVIO,
        "materiales":          materiales,
        "materiales_propios":  materiales_propios,
        "mp_configs_map":      mp_configs_map,
        "tipos_mp":            TIPOS_MP,
        "unidades_mp":         UNIDADES_MP,
        "tallas":              tallas,
        "servicios":           servicios,
        "mod_ops":             mod_ops,
        "mod_total":           mod_total,
        "servicios_total":     servicios_total,
    })


@router.get("/{prenda_id}/editar", response_class=HTMLResponse)
def catalogo_editar_page(
    prenda_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    if _rol(current_user) not in ROLES_EDITOR:
        raise HTTPException(403, "Sin permiso")
    prenda = db.query(PrendaCatalogo).filter_by(id=prenda_id).first()
    if not prenda:
        raise HTTPException(404, "Prenda no encontrada")
    return templates.TemplateResponse("catalogo/form_prenda.html", {
        "request":       request,
        "current_user":  current_user,
        "prenda":        prenda,
        "tipos_base":    TIPOS_BASE_PRENDA,
        "tipos_cliente": TIPOS_CLIENTE_PRENDA,
        "fits":          FITS_PRENDA,
        "accion":        "editar",
    })


# ── API: CRUD Prendas ─────────────────────────────────────────────────────────

@router.post("/api/crear")
def api_crear_prenda(
    codigo:        str  = Form(...),
    nombre:        str  = Form(...),
    tipo_base:     str  = Form(...),
    tipo_cliente:  str  = Form(...),
    fit:           str  = Form(""),
    descripcion:   str  = Form(""),
    composicion:   str  = Form(""),
    base_id:       Optional[int] = Form(None),
    imagen:        Optional[UploadFile] = File(None),
    db:            Session = Depends(get_db),
    current_user:  Usuario = Depends(get_current_user),
):
    rol = _rol(current_user)
    if rol not in ROLES_EDITOR:
        raise HTTPException(403, "Sin permiso para crear prendas")
    if tipo_base not in TIPOS_BASE_PRENDA:
        raise HTTPException(400, f"tipo_base invalido. Opciones: {TIPOS_BASE_PRENDA}")
    if tipo_cliente not in TIPOS_CLIENTE_PRENDA:
        raise HTTPException(400, f"tipo_cliente invalido. Opciones: {TIPOS_CLIENTE_PRENDA}")
    fits_validos = [f[0] for f in FITS_PRENDA]
    if fit and fit not in fits_validos:
        raise HTTPException(400, f"fit invalido. Opciones: {fits_validos}")
    if db.query(PrendaCatalogo).filter_by(codigo=codigo.upper().strip()).first():
        raise HTTPException(409, f"Ya existe una prenda con el codigo '{codigo}'")

    # Integridad de subtipo: una BASE no cuelga de otra; una variante debe apuntar a una BASE real.
    if tipo_cliente == "BASE":
        base_id = None
    elif base_id:
        base = db.query(PrendaCatalogo).filter_by(id=base_id).first()
        if not base or base.tipo_cliente != "BASE":
            raise HTTPException(400, "base_id debe apuntar a una prenda BASE existente")

    imagen_ruta = None
    if imagen and imagen.filename:
        imagen_ruta = _guardar_imagen(imagen, UPLOAD_PRENDA)

    prenda = PrendaCatalogo(
        codigo         = codigo.upper().strip(),
        nombre         = nombre.strip(),
        tipo_base      = tipo_base,
        tipo_cliente   = tipo_cliente,
        base_id        = base_id,
        fit            = fit or None,
        descripcion    = descripcion.strip() or None,
        composicion    = composicion.strip() or None,
        imagen_ruta    = imagen_ruta,
        activo         = True,
        creado_por_rol = rol,
    )
    db.add(prenda)
    db.commit()
    db.refresh(prenda)
    return {"ok": True, "id": prenda.id, "codigo": prenda.codigo}


@router.post("/api/{prenda_id}/hereda-ficha")
def api_toggle_hereda_ficha(
    prenda_id: int,
    hereda: bool = Form(...),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """Alterna si una variante usa la ficha de su base (herencia viva) o ficha propia."""
    if _rol(current_user) not in ROLES_EDITOR:
        raise HTTPException(403, "Sin permiso")
    prenda = db.query(PrendaCatalogo).filter_by(id=prenda_id).first()
    if not prenda:
        raise HTTPException(404, "Prenda no encontrada")
    if prenda.tipo_cliente == "BASE":
        raise HTTPException(400, "Una prenda base no hereda ficha")
    if not prenda.base_id:
        raise HTTPException(400, "Esta variante no tiene base asignada")
    prenda.hereda_ficha = bool(hereda)
    db.commit()
    return {"ok": True, "hereda_ficha": prenda.hereda_ficha}


@router.post("/api/{prenda_id}/editar")
def api_editar_prenda(
    prenda_id:    int,
    nombre:       str  = Form(...),
    tipo_base:    str  = Form(...),
    tipo_cliente: str  = Form(...),
    fit:          str  = Form(""),
    descripcion:  str  = Form(""),
    composicion:  str  = Form(""),
    imagen:       Optional[UploadFile] = File(None),
    db:           Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    if _rol(current_user) not in ROLES_EDITOR:
        raise HTTPException(403, "Sin permiso")
    prenda = db.query(PrendaCatalogo).filter_by(id=prenda_id).first()
    if not prenda:
        raise HTTPException(404, "Prenda no encontrada")
    if tipo_base not in TIPOS_BASE_PRENDA:
        raise HTTPException(400, "tipo_base invalido")
    if tipo_cliente not in TIPOS_CLIENTE_PRENDA:
        raise HTTPException(400, "tipo_cliente invalido")

    prenda.nombre       = nombre.strip()
    prenda.tipo_base    = tipo_base
    prenda.tipo_cliente = tipo_cliente
    prenda.fit          = fit or None
    prenda.descripcion  = descripcion.strip() or None
    prenda.composicion  = composicion.strip() or None

    if imagen and imagen.filename:
        _borrar_imagen(prenda.imagen_ruta)
        prenda.imagen_ruta = _guardar_imagen(imagen, UPLOAD_PRENDA)

    db.commit()
    return {"ok": True}


@router.post("/api/{prenda_id}/archivar")
def api_archivar_prenda(
    prenda_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    if _rol(current_user) not in ROLES_EDITOR:
        raise HTTPException(403, "Sin permiso")
    prenda = db.query(PrendaCatalogo).filter_by(id=prenda_id).first()
    if not prenda:
        raise HTTPException(404, "Prenda no encontrada")
    ofs_activas = [of for of in prenda.ofs if of.estado.value not in ("COMPLETADA", "ANULADA")]
    if ofs_activas:
        raise HTTPException(400, f"No se puede archivar: hay {len(ofs_activas)} OF(s) activa(s)")
    prenda.activo = False
    db.commit()
    return {"ok": True}


@router.post("/api/{prenda_id}/activar")
def api_activar_prenda(
    prenda_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    if _rol(current_user) not in ROLES_EDITOR:
        raise HTTPException(403, "Sin permiso")
    prenda = db.query(PrendaCatalogo).filter_by(id=prenda_id).first()
    if not prenda:
        raise HTTPException(404, "Prenda no encontrada")
    prenda.activo = True
    db.commit()
    return {"ok": True}


# ── API: CRUD Piezas ──────────────────────────────────────────────────────────

def _auto_codigo_pieza(prenda: PrendaCatalogo, orden: int, db: Session) -> str:
    base = f"{prenda.codigo}-P{(orden + 1):02d}"
    sufijo = 0
    candidato = base
    while db.query(PlantillaPieza).filter_by(codigo=candidato).first():
        sufijo += 1
        candidato = f"{base}-{sufijo}"
    return candidato


@router.post("/api/{prenda_id}/piezas/agregar")
def api_agregar_pieza(
    prenda_id:         int,
    nombre:            str  = Form(...),
    codigo:            str  = Form(""),
    material_default:  str  = Form("TELA"),
    cantidad_x_prenda: int  = Form(1),
    fusionado_default: str  = Form("false"),
    orden:             int  = Form(0),
    imagen:            Optional[UploadFile] = File(None),
    db:                Session = Depends(get_db),
    current_user:      Usuario = Depends(get_current_user),
):
    if _rol(current_user) not in ROLES_EDITOR:
        raise HTTPException(403, "Sin permiso para agregar piezas")
    prenda = db.query(PrendaCatalogo).filter_by(id=prenda_id).first()
    if not prenda:
        raise HTTPException(404, "Prenda no encontrada")

    if prenda.tipo_cliente == "BASE":
        codigo_final = _auto_codigo_pieza(prenda, orden, db)
    else:
        if not codigo or not codigo.strip():
            raise HTTPException(400, "El codigo de pieza es obligatorio para prendas de INSTITUCION o MARCA")
        codigo_final = codigo.strip().upper()
        if db.query(PlantillaPieza).filter_by(codigo=codigo_final).first():
            raise HTTPException(409, f"Ya existe una pieza con el codigo '{codigo_final}'")

    imagen_ruta = None
    if imagen and imagen.filename:
        imagen_ruta = _guardar_imagen(imagen, UPLOAD_PIEZA)

    fusionado = fusionado_default.lower() in ("true", "1", "on")
    pieza = PlantillaPieza(
        prenda_catalogo_id = prenda_id,
        codigo             = codigo_final,
        nombre             = nombre.strip(),
        material_default   = material_default.strip() or "TELA",
        cantidad_x_prenda  = max(1, cantidad_x_prenda),
        fusionado_default  = fusionado,
        orden              = orden,
        imagen_ruta        = imagen_ruta,
    )
    db.add(pieza)
    db.commit()
    db.refresh(pieza)
    return {"ok": True, "id": pieza.id, "codigo": pieza.codigo}


@router.post("/api/piezas/{pieza_id}/editar")
def api_editar_pieza(
    pieza_id:          int,
    nombre:            str  = Form(...),
    codigo:            str  = Form(""),
    material_default:  str  = Form("TELA"),
    cantidad_x_prenda: int  = Form(1),
    fusionado_default: str  = Form("false"),
    orden:             int  = Form(0),
    imagen:            Optional[UploadFile] = File(None),
    db:                Session = Depends(get_db),
    current_user:      Usuario = Depends(get_current_user),
):
    if _rol(current_user) not in ROLES_EDITOR:
        raise HTTPException(403, "Sin permiso")
    pieza = db.query(PlantillaPieza).filter_by(id=pieza_id).first()
    if not pieza:
        raise HTTPException(404, "Pieza no encontrada")

    if pieza.prenda_catalogo.tipo_cliente != "BASE" and codigo and codigo.strip():
        nuevo_codigo = codigo.strip().upper()
        if nuevo_codigo != pieza.codigo:
            if db.query(PlantillaPieza).filter(
                PlantillaPieza.codigo == nuevo_codigo,
                PlantillaPieza.id != pieza_id
            ).first():
                raise HTTPException(409, f"Ya existe una pieza con el codigo '{nuevo_codigo}'")
            pieza.codigo = nuevo_codigo

    pieza.nombre            = nombre.strip()
    pieza.material_default  = material_default.strip() or "TELA"
    pieza.cantidad_x_prenda = max(1, cantidad_x_prenda)
    pieza.fusionado_default = fusionado_default.lower() in ("true", "1", "on")
    pieza.orden             = orden

    if imagen and imagen.filename:
        _borrar_imagen(pieza.imagen_ruta)
        pieza.imagen_ruta = _guardar_imagen(imagen, UPLOAD_PIEZA)

    db.commit()
    return {"ok": True}


@router.post("/api/piezas/{pieza_id}/eliminar")
def api_eliminar_pieza(
    pieza_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    if _rol(current_user) not in ROLES_EDITOR:
        raise HTTPException(403, "Sin permiso")
    pieza = db.query(PlantillaPieza).filter_by(id=pieza_id).first()
    if not pieza:
        raise HTTPException(404, "Pieza no encontrada")
    _borrar_imagen(pieza.imagen_ruta)
    db.delete(pieza)
    db.commit()
    return {"ok": True}


@router.get("/api/{prenda_id}/bases-disponibles")
def api_bases_disponibles(
    prenda_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """Retorna todas las prendas BASE activas del mismo tipo_base."""
    prenda = db.query(PrendaCatalogo).filter_by(id=prenda_id).first()
    if not prenda:
        raise HTTPException(404, "Prenda no encontrada")
    if prenda.tipo_cliente == "BASE":
        raise HTTPException(400, "Esta prenda ya es BASE")

    bases = (db.query(PrendaCatalogo)
               .filter_by(tipo_base=prenda.tipo_base, tipo_cliente="BASE", activo=True)
               .order_by(PrendaCatalogo.id)
               .all())
    if not bases:
        raise HTTPException(404, f"No hay prenda BASE activa para el tipo '{prenda.tipo_base}'")

    return [
        {
            "id":         b.id,
            "codigo":     b.codigo,
            "nombre":     b.nombre,
            "num_piezas": len(b.plantilla_piezas),
        }
        for b in bases
    ]


@router.get("/api/{prenda_id}/piezas/base")
def api_piezas_base_para_heredar(
    prenda_id: int,
    base_id: int = None,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    prenda = db.query(PrendaCatalogo).filter_by(id=prenda_id).first()
    if not prenda:
        raise HTTPException(404, "Prenda no encontrada")
    if prenda.tipo_cliente == "BASE":
        raise HTTPException(400, "Esta prenda ya es BASE")

    if base_id:
        prenda_base = db.query(PrendaCatalogo).filter_by(id=base_id, tipo_cliente="BASE", activo=True).first()
        if not prenda_base:
            raise HTTPException(404, "BASE seleccionada no encontrada")
    else:
        prenda_base = (db.query(PrendaCatalogo)
                       .filter_by(tipo_base=prenda.tipo_base, tipo_cliente="BASE", activo=True)
                       .order_by(PrendaCatalogo.id)
                       .first())
    if not prenda_base:
        raise HTTPException(404, f"No hay prenda BASE activa para el tipo '{prenda.tipo_base}'")

    piezas = sorted(prenda_base.plantilla_piezas, key=lambda p: p.orden)
    if not piezas:
        raise HTTPException(404, "La prenda BASE no tiene piezas definidas")

    return {
        "prenda_base": prenda_base.nombre,
        "piezas": [
            {
                "nombre":            p.nombre,
                "material_default":  p.material_default,
                "cantidad_x_prenda": p.cantidad_x_prenda,
                "fusionado_default": p.fusionado_default,
                "orden":             p.orden,
            }
            for p in piezas
        ],
    }


@router.post("/api/{prenda_id}/imagen")
def api_subir_imagen_prenda(
    prenda_id: int,
    imagen:    UploadFile = File(...),
    db:        Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    if _rol(current_user) not in ROLES_EDITOR:
        raise HTTPException(403, "Sin permiso")
    prenda = db.query(PrendaCatalogo).filter_by(id=prenda_id).first()
    if not prenda:
        raise HTTPException(404, "Prenda no encontrada")
    _borrar_imagen(prenda.imagen_ruta)
    prenda.imagen_ruta = _guardar_imagen(imagen, UPLOAD_PRENDA)
    db.commit()
    return {"ok": True, "imagen_ruta": prenda.imagen_ruta}


@router.post("/api/piezas/{pieza_id}/imagen")
def api_subir_imagen_pieza(
    pieza_id: int,
    imagen:   UploadFile = File(...),
    db:       Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    if _rol(current_user) not in ROLES_EDITOR:
        raise HTTPException(403, "Sin permiso")
    pieza = db.query(PlantillaPieza).filter_by(id=pieza_id).first()
    if not pieza:
        raise HTTPException(404, "Pieza no encontrada")
    _borrar_imagen(pieza.imagen_ruta)
    pieza.imagen_ruta = _guardar_imagen(imagen, UPLOAD_PIEZA)
    db.commit()
    return {"ok": True, "imagen_ruta": pieza.imagen_ruta}


# ── API: JSON para select en crear OF ────────────────────────────────────────

@router.get("/api/lista")
def api_lista_prendas(
    tipo_base:    str = "",
    tipo_cliente: str = "",
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    query = db.query(PrendaCatalogo).filter_by(activo=True)
    if tipo_base:
        query = query.filter(PrendaCatalogo.tipo_base == tipo_base)
    if tipo_cliente == "VARIANTE":
        query = query.filter(PrendaCatalogo.tipo_cliente != "BASE")
    elif tipo_cliente:
        query = query.filter(PrendaCatalogo.tipo_cliente == tipo_cliente)
    prendas = query.order_by(PrendaCatalogo.tipo_cliente, PrendaCatalogo.tipo_base, PrendaCatalogo.nombre).all()
    return [
        {"id": p.id, "codigo": p.codigo, "nombre": p.nombre,
         "tipo_base": p.tipo_base, "tipo_cliente": p.tipo_cliente, "imagen_ruta": p.imagen_ruta}
        for p in prendas
    ]


@router.get("/api/{prenda_id}/piezas")
def api_piezas_de_prenda(
    prenda_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    prenda = db.query(PrendaCatalogo).filter_by(id=prenda_id).first()
    if not prenda:
        raise HTTPException(404, "Prenda no encontrada")
    piezas = sorted(prenda.plantilla_piezas, key=lambda p: p.orden)
    return [
        {"id": p.id, "codigo": p.codigo, "nombre": p.nombre, "material_default": p.material_default,
         "cantidad_x_prenda": p.cantidad_x_prenda, "fusionado_default": p.fusionado_default,
         "orden": p.orden, "imagen_ruta": p.imagen_ruta}
        for p in piezas
    ]


# ── API: Documentos de prenda ─────────────────────────────────────────────────

EXTS_DOC = {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".png", ".jpg", ".jpeg", ".dxf"}

# Firmas (magic bytes) por extensión. .dxf es texto (ASCII/UTF) → sin firma estricta.
_MAGIC_DOC = {
    ".pdf":  [b"%PDF"],
    ".png":  [b"\x89PNG\r\n\x1a\n"],
    ".jpg":  [b"\xff\xd8\xff"],
    ".jpeg": [b"\xff\xd8\xff"],
    ".docx": [b"PK\x03\x04"],
    ".xlsx": [b"PK\x03\x04"],
    ".doc":  [b"\xd0\xcf\x11\xe0"],   # OLE compound
    ".xls":  [b"\xd0\xcf\x11\xe0"],
}


def _magic_doc_ok(contenido: bytes, ext: str) -> bool:
    """True si los primeros bytes coinciden con la extensión. .dxf (texto) no se verifica."""
    firmas = _MAGIC_DOC.get(ext)
    if not firmas:
        return True
    head = contenido[:16]
    return any(head.startswith(f) for f in firmas)


@router.post("/api/{prenda_id}/documentos/subir")
def api_subir_documento(
    prenda_id:   int,
    tipo:        str          = Form(...),
    descripcion: str          = Form(""),
    archivo:     UploadFile   = File(...),
    db:          Session      = Depends(get_db),
    current_user: Usuario     = Depends(get_current_user),
):
    if _rol(current_user) not in ROLES_EDITOR:
        raise HTTPException(403, "Sin permiso para subir documentos")
    if tipo not in TIPOS_DOC_PRENDA:
        raise HTTPException(400, f"Tipo invalido. Opciones: {TIPOS_DOC_PRENDA}")
    prenda = db.query(PrendaCatalogo).filter_by(id=prenda_id).first()
    if not prenda:
        raise HTTPException(404, "Prenda no encontrada")

    ext = os.path.splitext(archivo.filename or "")[1].lower()
    if ext not in EXTS_DOC:
        raise HTTPException(400, f"Formato no permitido. Use: {', '.join(EXTS_DOC)}")

    contenido = archivo.file.read()
    max_bytes = settings.MAX_UPLOAD_MB * 1024 * 1024
    if len(contenido) > max_bytes:
        raise HTTPException(413, f"Archivo demasiado grande (máx. {settings.MAX_UPLOAD_MB} MB).")
    if not _magic_doc_ok(contenido, ext):
        raise HTTPException(400, "El contenido del archivo no coincide con su extensión.")

    nombre_guardado = f"{uuid.uuid4().hex}{ext}"
    ruta = storage.save_bytes(contenido, UPLOAD_DOCS, nombre_guardado)

    doc = PrendaDocumento(
        prenda_catalogo_id = prenda_id,
        tipo               = tipo,
        nombre_archivo     = archivo.filename,
        ruta_archivo       = ruta,
        descripcion        = descripcion.strip() or None,
        subido_por_id      = current_user.id,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    ofs_borrador = []
    if tipo == "FICHA_TECNICA":
        from app.models.of import OrdenFabricacion, EstadoOF
        ofs = (db.query(OrdenFabricacion)
               .filter_by(prenda_catalogo_id=prenda_id, estado=EstadoOF.BORRADOR)
               .all())
        ofs_borrador = [{"id": of.id, "numero_of": of.numero_of, "cliente": of.cliente}
                        for of in ofs]

    return {
        "ok": True,
        "id": doc.id,
        "nombre_archivo": doc.nombre_archivo,
        "ruta_archivo": ruta,
        "ofs_borrador": ofs_borrador,
    }


@router.post("/api/{prenda_id}/documentos/copiar-a-ofs")
def api_copiar_ficha_a_ofs(
    prenda_id:  int,
    doc_id:     int  = Form(...),
    of_ids:     str  = Form(...),
    db:         Session  = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    import json as _json
    from app.models.of import OrdenFabricacion, EstadoOF, DocumentoOF
    if _rol(current_user) not in ROLES_EDITOR:
        raise HTTPException(403, "Sin permiso")

    doc = db.query(PrendaDocumento).filter_by(id=doc_id, prenda_catalogo_id=prenda_id).first()
    if not doc:
        raise HTTPException(404, "Documento no encontrado")

    try:
        ids = _json.loads(of_ids)
    except Exception:
        raise HTTPException(400, "of_ids debe ser un JSON array")

    copiados = []
    for of_id in ids:
        of = db.query(OrdenFabricacion).filter_by(id=of_id, estado=EstadoOF.BORRADOR).first()
        if not of:
            continue
        nuevo_nombre = f"{uuid.uuid4().hex}_{doc.nombre_archivo}"
        nueva_ruta   = storage.copy_file(doc.ruta_archivo, str(of_id), nuevo_nombre)

        doc_of = DocumentoOF(
            of_id=of_id,
            tipo="FICHA_TECNICA",
            nombre_archivo=doc.nombre_archivo,
            ruta_archivo=nueva_ruta,
            area=_rol(current_user),
            usuario_id=current_user.id,
        )
        db.add(doc_of)
        copiados.append(of.numero_of)

    db.commit()
    return {"ok": True, "copiados": copiados}


@router.post("/api/documentos/{doc_id}/eliminar")
def api_eliminar_documento(
    doc_id: int,
    db:     Session  = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    if _rol(current_user) not in ROLES_EDITOR:
        raise HTTPException(403, "Sin permiso")
    doc = db.query(PrendaDocumento).filter_by(id=doc_id).first()
    if not doc:
        raise HTTPException(404, "Documento no encontrado")
    _borrar_imagen(doc.ruta_archivo)
    db.delete(doc)
    db.commit()
    return {"ok": True}


@router.get("/api/{prenda_id}/documentos")
def api_documentos_prenda(
    prenda_id: int,
    db:        Session  = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    prenda = db.query(PrendaCatalogo).filter_by(id=prenda_id).first()
    if not prenda:
        raise HTTPException(404, "Prenda no encontrada")
    return [
        {"id": d.id, "tipo": d.tipo, "nombre_archivo": d.nombre_archivo,
         "ruta_archivo": d.ruta_archivo, "descripcion": d.descripcion,
         "subido_por": d.subido_por.nombre if d.subido_por else "—",
         "created_at": d.created_at.strftime("%d/%m/%Y") if d.created_at else ""}
        for d in prenda.documentos
    ]


# ── API: Avios ────────────────────────────────────────────────────────────────

class AvioIn(_PBase):
    seccion:          str
    nombre:           str
    codigo_base:      Optional[str]   = None   # trazabilidad BASE→VARIANTE
    codigo_interno:   Optional[str]   = None
    proveedor:        Optional[str]   = None
    procedencia:      Optional[str]   = None
    unidad_medida:    str             = "Unid"
    consumo_unitario: float           = 1.0
    pct_adicional:    float           = 0.01
    unidad_compra:    Optional[str]   = None
    factor_conversion: float          = 1.0
    moneda:           Optional[str]   = None
    precio:           Optional[float] = None
    orden:            int             = 0


class AvioConfigIn(_PBase):
    codigo_cliente:   Optional[str]   = None
    excluido:         bool            = False
    consumo_override: Optional[float] = None
    notas:            Optional[str]   = None


def _avio_dict(a: CatalogoAvio) -> dict:
    return {
        "id":               a.id,
        "seccion":          a.seccion,
        "nombre":           a.nombre,
        "codigo_interno":   a.codigo_interno,
        "codigo_base":      a.codigo_base,
        "proveedor":        a.proveedor,
        "procedencia":      a.procedencia,
        "unidad_medida":    a.unidad_medida,
        "consumo_unitario": a.consumo_unitario,
        "pct_adicional":    a.pct_adicional,
        "unidad_compra":    a.unidad_compra,
        "factor_conversion": a.factor_conversion,
        "moneda":           a.moneda,
        "precio":           a.precio,
        "orden":            a.orden,
        "activo":           a.activo,
    }


@router.get("/api/{prenda_id}/avios")
def api_get_avios(
    prenda_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    prenda = db.query(PrendaCatalogo).filter_by(id=prenda_id).first()
    if not prenda:
        raise HTTPException(404, "Prenda no encontrada")

    if prenda.tipo_cliente == "BASE":
        avios = sorted(prenda.avios, key=lambda a: (a.seccion, a.orden))
        return {"es_base": True, "prenda_base_nombre": None,
                "avios": [_avio_dict(a) for a in avios], "avios_propios": []}

    prenda_base = (
        db.query(PrendaCatalogo)
        .filter_by(tipo_base=prenda.tipo_base, tipo_cliente="BASE", activo=True)
        .first()
    )
    if not prenda_base:
        return {"es_base": False, "prenda_base_nombre": None, "avios": [], "avios_propios": []}

    avios   = sorted(prenda_base.avios, key=lambda a: (a.seccion, a.orden))
    cfg_map = {c.avio_id: c for c in prenda.avio_configs}
    avios_propios = sorted(prenda.avios, key=lambda a: (a.seccion, a.orden))

    result = []
    for a in avios:
        d = _avio_dict(a)
        cfg = cfg_map.get(a.id)
        d["config"] = {
            "codigo_cliente":   cfg.codigo_cliente   if cfg else None,
            "excluido":         cfg.excluido         if cfg else False,
            "consumo_override": cfg.consumo_override if cfg else None,
            "notas":            cfg.notas            if cfg else None,
        }
        result.append(d)

    return {
        "es_base":            False,
        "prenda_base_nombre": prenda_base.nombre,
        "avios":              result,
        "avios_propios":      [_avio_dict(a) for a in avios_propios],
    }


@router.post("/api/{prenda_id}/avios/agregar")
def api_agregar_avio(
    prenda_id: int,
    body: AvioIn,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """Agrega un avío a la prenda. Para BASE: define avío heredable.
    Para VARIANTE: agrega avío específico de esta variante (es_adicion_variante)."""
    if _rol(current_user) not in ROLES_EDITOR:
        raise HTTPException(403, "Sin permiso")
    prenda = db.query(PrendaCatalogo).filter_by(id=prenda_id).first()
    if not prenda:
        raise HTTPException(404, "Prenda no encontrada")
    if body.seccion not in SECCIONES_AVIO:
        raise HTTPException(400, f"Seccion invalida. Opciones: {SECCIONES_AVIO}")

    avio = CatalogoAvio(
        prenda_catalogo_id = prenda_id,
        seccion            = body.seccion,
        nombre             = body.nombre.strip(),
        codigo_base        = body.codigo_base,
        codigo_interno     = body.codigo_interno,
        proveedor          = body.proveedor,
        procedencia        = body.procedencia,
        unidad_medida      = body.unidad_medida,
        consumo_unitario   = body.consumo_unitario,
        pct_adicional      = body.pct_adicional,
        unidad_compra      = body.unidad_compra,
        moneda             = body.moneda,
        precio             = body.precio,
        orden              = body.orden,
    )
    db.add(avio)
    db.commit()
    db.refresh(avio)
    return {"ok": True, "id": avio.id}


@router.patch("/api/avios/{avio_id}")
def api_editar_avio(
    avio_id: int,
    body: AvioIn,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    if _rol(current_user) not in ROLES_EDITOR:
        raise HTTPException(403, "Sin permiso")
    avio = db.query(CatalogoAvio).filter_by(id=avio_id).first()
    if not avio:
        raise HTTPException(404, "Avio no encontrado")
    if body.seccion not in SECCIONES_AVIO:
        raise HTTPException(400, f"Seccion invalida. Opciones: {SECCIONES_AVIO}")

    avio.seccion          = body.seccion
    avio.nombre           = body.nombre.strip()
    avio.codigo_base      = body.codigo_base
    avio.codigo_interno   = body.codigo_interno
    avio.proveedor        = body.proveedor
    avio.procedencia      = body.procedencia
    avio.unidad_medida    = body.unidad_medida
    avio.consumo_unitario = body.consumo_unitario
    avio.pct_adicional    = body.pct_adicional
    avio.unidad_compra    = body.unidad_compra
    avio.factor_conversion = body.factor_conversion
    avio.moneda           = body.moneda
    avio.precio           = body.precio
    avio.orden            = body.orden
    db.commit()
    return {"ok": True}


@router.post("/api/avios/{avio_id}/eliminar")
def api_eliminar_avio(
    avio_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """Elimina un avío. Solo para BASE o avíos propios de variante."""
    if _rol(current_user) not in ROLES_EDITOR:
        raise HTTPException(403, "Sin permiso")
    avio = db.query(CatalogoAvio).filter_by(id=avio_id).first()
    if not avio:
        raise HTTPException(404, "Avio no encontrado")
    db.delete(avio)
    db.commit()
    return {"ok": True}


@router.post("/api/{prenda_id}/avios/{avio_id}/eliminar-variante")
def api_eliminar_avio_variante(
    prenda_id: int,
    avio_id:   int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """Elimina un avío propio de variante (solo si pertenece a esta variante, no a BASE)."""
    if _rol(current_user) not in ROLES_EDITOR:
        raise HTTPException(403, "Sin permiso")
    prenda = db.query(PrendaCatalogo).filter_by(id=prenda_id).first()
    if not prenda:
        raise HTTPException(404, "Prenda no encontrada")
    if prenda.tipo_cliente == "BASE":
        raise HTTPException(400, "Use /avios/{id}/eliminar para prendas BASE")
    avio = db.query(CatalogoAvio).filter_by(id=avio_id, prenda_catalogo_id=prenda_id).first()
    if not avio:
        raise HTTPException(404, "Avío no encontrado en esta variante")
    db.delete(avio)
    db.commit()
    return {"ok": True}


@router.post("/api/{prenda_id}/avio-config/{avio_id}")
def api_guardar_config_avio(
    prenda_id: int,
    avio_id:   int,
    body: AvioConfigIn,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    if _rol(current_user) not in ROLES_EDITOR:
        raise HTTPException(403, "Sin permiso")
    prenda = db.query(PrendaCatalogo).filter_by(id=prenda_id).first()
    if not prenda:
        raise HTTPException(404, "Prenda no encontrada")
    if prenda.tipo_cliente == "BASE":
        raise HTTPException(400, "Las prendas BASE no usan avio-config")
    avio = db.query(CatalogoAvio).filter_by(id=avio_id).first()
    if not avio:
        raise HTTPException(404, "Avio no encontrado")

    cfg = db.query(PrendaAvioConfig).filter_by(
        prenda_catalogo_id=prenda_id, avio_id=avio_id
    ).first()
    if cfg is None:
        cfg = PrendaAvioConfig(prenda_catalogo_id=prenda_id, avio_id=avio_id)
        db.add(cfg)

    cfg.codigo_cliente   = body.codigo_cliente
    cfg.excluido         = body.excluido
    cfg.consumo_override = body.consumo_override
    cfg.notas            = body.notas
    db.commit()
    return {"ok": True}


# ── API: Materia Prima ────────────────────────────────────────────────────────

class MpIn(_PBase):
    nombre:            str
    tipo:              str
    codigo_base:       Optional[str]   = None   # trazabilidad BASE→VARIANTE
    ancho_referencia:  Optional[float] = None
    consumo_unitario:  float           = 1.0
    pct_adicional:     float           = 0.02
    unidad_medida:     str             = "mt."
    unidad_compra:     Optional[str]   = None
    factor_conversion: float           = 1.0
    codigo_interno:    Optional[str]   = None
    proveedor:         Optional[str]   = None
    procedencia:       Optional[str]   = None
    moneda:            Optional[str]   = None
    precio_referencia: Optional[float] = None
    orden:             int             = 0


class MpConfigIn(_PBase):
    codigo_cliente:   Optional[str]   = None
    excluido:         bool            = False
    consumo_override: Optional[float] = None
    notas:            Optional[str]   = None


def _mp_dict(m: CatalogoMp) -> dict:
    return {
        "id":                m.id,
        "nombre":            m.nombre,
        "tipo":              m.tipo,
        "ancho_referencia":  m.ancho_referencia,
        "consumo_unitario":  m.consumo_unitario,
        "pct_adicional":     m.pct_adicional,
        "unidad_medida":     m.unidad_medida,
        "unidad_compra":     m.unidad_compra,
        "factor_conversion": m.factor_conversion,
        "codigo_interno":    m.codigo_interno,
        "codigo_base":       m.codigo_base,
        "proveedor":         m.proveedor,
        "moneda":            m.moneda,
        "precio_referencia": m.precio_referencia,
        "orden":             m.orden,
        "activo":            m.activo,
    }


@router.get("/api/{prenda_id}/mp")
def api_get_mp(
    prenda_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    prenda = db.query(PrendaCatalogo).filter_by(id=prenda_id).first()
    if not prenda:
        raise HTTPException(404, "Prenda no encontrada")

    if prenda.tipo_cliente == "BASE":
        mats = sorted(prenda.materiales, key=lambda m: m.orden)
        return {"es_base": True, "prenda_base_nombre": None,
                "materiales": [_mp_dict(m) for m in mats], "materiales_propios": []}

    prenda_base = (
        db.query(PrendaCatalogo)
        .filter_by(tipo_base=prenda.tipo_base, tipo_cliente="BASE", activo=True)
        .first()
    )
    if not prenda_base:
        return {"es_base": False, "prenda_base_nombre": None, "materiales": [], "materiales_propios": []}

    mats    = sorted(prenda_base.materiales, key=lambda m: m.orden)
    cfg_map = {c.mp_id: c for c in prenda.mp_configs}
    mats_propios = sorted(prenda.materiales, key=lambda m: m.orden)

    result = []
    for m in mats:
        d = _mp_dict(m)
        cfg = cfg_map.get(m.id)
        d["config"] = {
            "codigo_cliente":   cfg.codigo_cliente   if cfg else None,
            "excluido":         cfg.excluido         if cfg else False,
            "consumo_override": cfg.consumo_override if cfg else None,
            "notas":            cfg.notas            if cfg else None,
        }
        result.append(d)

    return {
        "es_base":            False,
        "prenda_base_nombre": prenda_base.nombre,
        "materiales":         result,
        "materiales_propios": [_mp_dict(m) for m in mats_propios],
    }


@router.post("/api/{prenda_id}/mp/agregar")
def api_agregar_mp(
    prenda_id: int,
    body: MpIn,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """Agrega materia prima a la prenda. Para BASE: define MP heredable.
    Para VARIANTE: agrega MP específico de esta variante."""
    if _rol(current_user) not in ROLES_EDITOR:
        raise HTTPException(403, "Sin permiso")
    prenda = db.query(PrendaCatalogo).filter_by(id=prenda_id).first()
    if not prenda:
        raise HTTPException(404, "Prenda no encontrada")
    if body.tipo not in TIPOS_MP:
        raise HTTPException(400, f"Tipo invalido. Opciones: {TIPOS_MP}")

    mp = CatalogoMp(
        prenda_catalogo_id = prenda_id,
        nombre             = body.nombre.strip(),
        tipo               = body.tipo,
        codigo_base        = body.codigo_base,
        ancho_referencia   = body.ancho_referencia,
        consumo_unitario   = body.consumo_unitario,
        pct_adicional      = body.pct_adicional,
        unidad_medida      = body.unidad_medida,
        codigo_interno     = body.codigo_interno,
        proveedor          = body.proveedor,
        procedencia        = body.procedencia,
        moneda             = body.moneda,
        precio_referencia  = body.precio_referencia,
        orden              = body.orden,
    )
    db.add(mp)
    db.commit()
    db.refresh(mp)
    return {"ok": True, "id": mp.id}


@router.patch("/api/mp/{mp_id}")
def api_editar_mp(
    mp_id: int,
    body: MpIn,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    if _rol(current_user) not in ROLES_EDITOR:
        raise HTTPException(403, "Sin permiso")
    mp = db.query(CatalogoMp).filter_by(id=mp_id).first()
    if not mp:
        raise HTTPException(404, "Material no encontrado")
    if body.tipo not in TIPOS_MP:
        raise HTTPException(400, f"Tipo invalido. Opciones: {TIPOS_MP}")

    mp.nombre            = body.nombre.strip()
    mp.tipo              = body.tipo
    mp.codigo_base       = body.codigo_base
    mp.ancho_referencia  = body.ancho_referencia
    mp.consumo_unitario  = body.consumo_unitario
    mp.pct_adicional     = body.pct_adicional
    mp.unidad_medida     = body.unidad_medida
    mp.unidad_compra     = body.unidad_compra
    mp.factor_conversion = body.factor_conversion
    mp.codigo_interno    = body.codigo_interno
    mp.proveedor         = body.proveedor
    mp.procedencia       = body.procedencia
    mp.moneda            = body.moneda
    mp.precio_referencia = body.precio_referencia
    mp.orden             = body.orden
    db.commit()
    return {"ok": True}


@router.post("/api/mp/{mp_id}/eliminar")
def api_eliminar_mp(
    mp_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """Elimina un material. Solo para BASE o materiales propios de variante."""
    if _rol(current_user) not in ROLES_EDITOR:
        raise HTTPException(403, "Sin permiso")
    mp = db.query(CatalogoMp).filter_by(id=mp_id).first()
    if not mp:
        raise HTTPException(404, "Material no encontrado")
    db.delete(mp)
    db.commit()
    return {"ok": True}


@router.post("/api/{prenda_id}/mp/{mp_id}/eliminar-variante")
def api_eliminar_mp_variante(
    prenda_id: int,
    mp_id:     int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """Elimina un material propio de variante (solo si pertenece a esta variante, no a BASE)."""
    if _rol(current_user) not in ROLES_EDITOR:
        raise HTTPException(403, "Sin permiso")
    prenda = db.query(PrendaCatalogo).filter_by(id=prenda_id).first()
    if not prenda:
        raise HTTPException(404, "Prenda no encontrada")
    if prenda.tipo_cliente == "BASE":
        raise HTTPException(400, "Use /mp/{id}/eliminar para prendas BASE")
    mp = db.query(CatalogoMp).filter_by(id=mp_id, prenda_catalogo_id=prenda_id).first()
    if not mp:
        raise HTTPException(404, "Material no encontrado en esta variante")
    db.delete(mp)
    db.commit()
    return {"ok": True}


@router.post("/api/{prenda_id}/mp-config/{mp_id}")
def api_guardar_config_mp(
    prenda_id: int,
    mp_id:     int,
    body: MpConfigIn,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    if _rol(current_user) not in ROLES_EDITOR:
        raise HTTPException(403, "Sin permiso")
    prenda = db.query(PrendaCatalogo).filter_by(id=prenda_id).first()
    if not prenda:
        raise HTTPException(404, "Prenda no encontrada")
    if prenda.tipo_cliente == "BASE":
        raise HTTPException(400, "Las prendas BASE no usan mp-config")
    mp = db.query(CatalogoMp).filter_by(id=mp_id).first()
    if not mp:
        raise HTTPException(404, "Material no encontrado")

    cfg = db.query(PrendaMpConfig).filter_by(
        prenda_catalogo_id=prenda_id, mp_id=mp_id
    ).first()
    if cfg is None:
        cfg = PrendaMpConfig(prenda_catalogo_id=prenda_id, mp_id=mp_id)
        db.add(cfg)

    cfg.codigo_cliente   = body.codigo_cliente
    cfg.excluido         = body.excluido
    cfg.consumo_override = body.consumo_override
    cfg.notas            = body.notas
    db.commit()
    return {"ok": True}


# ── API: SKUs ─────────────────────────────────────────────────────────────────

class SkuMpConfigIn(_PBase):
    consumo_override: float
    notas: Optional[str] = None

class SkuAvioConfigIn(_PBase):
    codigo_override: Optional[str] = None
    notas: Optional[str] = None


def _sku_dict(s: PrendaSku) -> dict:
    return {
        "id":         s.id,
        "talla":      s.talla,
        "codigo_sku": s.codigo_sku,
        "orden":      s.orden,
        "activo":     s.activo,
        "mp_configs": [
            {"mp_id": c.mp_id, "consumo_override": c.consumo_override, "notas": c.notas}
            for c in s.mp_configs
        ],
        "avio_configs": [
            {"avio_id": c.avio_id, "codigo_override": c.codigo_override, "notas": c.notas}
            for c in s.avio_configs
        ],
    }


@router.get("/api/{prenda_id}/skus")
def api_get_skus(
    prenda_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    prenda = db.query(PrendaCatalogo).filter_by(id=prenda_id).first()
    if not prenda:
        raise HTTPException(404, "Prenda no encontrada")
    skus = sorted(prenda.skus, key=lambda s: s.orden)
    return [_sku_dict(s) for s in skus]


@router.post("/api/{prenda_id}/skus/agregar")
def api_agregar_sku(
    prenda_id:  int,
    talla:      str = _Form(...),
    codigo_sku: str = _Form(default=""),
    orden:      int = _Form(default=0),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    if _rol(current_user) not in ROLES_EDITOR:
        raise HTTPException(403, "Sin permiso")
    prenda = db.query(PrendaCatalogo).filter_by(id=prenda_id).first()
    if not prenda:
        raise HTTPException(404, "Prenda no encontrada")
    talla_str = talla.strip()
    if not talla_str:
        raise HTTPException(400, "La talla no puede estar vacia")
    existe = db.query(PrendaSku).filter_by(
        prenda_catalogo_id=prenda_id, talla=talla_str
    ).first()
    if existe:
        raise HTTPException(409, f"La talla '{talla_str}' ya existe en esta prenda")
    sku = PrendaSku(
        prenda_catalogo_id=prenda_id,
        talla=talla_str,
        codigo_sku=codigo_sku.strip() or None,
        orden=orden,
    )
    db.add(sku)
    db.commit()
    db.refresh(sku)
    return _sku_dict(sku)


@router.patch("/api/skus/{sku_id}")
def api_editar_sku(
    sku_id: int,
    talla:      str = _Form(default=""),
    codigo_sku: str = _Form(default=""),
    orden:      int = _Form(default=0),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    if _rol(current_user) not in ROLES_EDITOR:
        raise HTTPException(403, "Sin permiso")
    sku = db.query(PrendaSku).filter_by(id=sku_id).first()
    if not sku:
        raise HTTPException(404, "SKU no encontrado")
    if talla.strip():
        sku.talla = talla.strip()
    sku.codigo_sku = codigo_sku.strip() or None
    sku.orden = orden
    db.commit()
    db.refresh(sku)
    return _sku_dict(sku)


@router.post("/api/skus/{sku_id}/eliminar")
def api_eliminar_sku(
    sku_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    if _rol(current_user) not in ROLES_EDITOR:
        raise HTTPException(403, "Sin permiso")
    sku = db.query(PrendaSku).filter_by(id=sku_id).first()
    if not sku:
        raise HTTPException(404, "SKU no encontrado")
    db.delete(sku)
    db.commit()
    return {"ok": True}


@router.post("/api/skus/{sku_id}/mp-config")
def api_sku_mp_config(
    sku_id: int,
    mp_id:  int,
    body:   SkuMpConfigIn,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    if _rol(current_user) not in ROLES_EDITOR:
        raise HTTPException(403, "Sin permiso")
    sku = db.query(PrendaSku).filter_by(id=sku_id).first()
    if not sku:
        raise HTTPException(404, "SKU no encontrado")
    cfg = db.query(PrendaSkuMpConfig).filter_by(sku_id=sku_id, mp_id=mp_id).first()
    if cfg:
        cfg.consumo_override = body.consumo_override
        cfg.notas = body.notas
    else:
        cfg = PrendaSkuMpConfig(
            sku_id=sku_id, mp_id=mp_id,
            consumo_override=body.consumo_override,
            notas=body.notas,
        )
        db.add(cfg)
    db.commit()
    return {"ok": True, "sku_id": sku_id, "mp_id": mp_id, "consumo_override": cfg.consumo_override}


@router.post("/api/skus/{sku_id}/avio-config")
def api_sku_avio_config(
    sku_id:  int,
    avio_id: int,
    body:    SkuAvioConfigIn,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    if _rol(current_user) not in ROLES_EDITOR:
        raise HTTPException(403, "Sin permiso")
    sku = db.query(PrendaSku).filter_by(id=sku_id).first()
    if not sku:
        raise HTTPException(404, "SKU no encontrado")
    cfg = db.query(PrendaSkuAvioConfig).filter_by(sku_id=sku_id, avio_id=avio_id).first()
    if cfg:
        cfg.codigo_override = body.codigo_override
        cfg.notas = body.notas
    else:
        cfg = PrendaSkuAvioConfig(
            sku_id=sku_id, avio_id=avio_id,
            codigo_override=body.codigo_override,
            notas=body.notas,
        )
        db.add(cfg)
    db.commit()
    return {"ok": True, "sku_id": sku_id, "avio_id": avio_id}


# Alias compat: /tallas/ → /skus/ para JS legacy del template anterior
@router.post("/api/{prenda_id}/tallas/agregar")
def api_agregar_talla_compat(
    prenda_id:  int,
    talla:      str = _Form(...),
    orden:      int = _Form(default=0),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    return api_agregar_sku(prenda_id, talla, "", orden, db, current_user)


@router.post("/api/tallas/{talla_id}/eliminar")
def api_eliminar_talla_compat(
    talla_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    return api_eliminar_sku(talla_id, db, current_user)


# ── API: Gates linkeados desde catálogo ──────────────────────────────────────

@router.get("/api/{prenda_id}/ofs-activas")
def api_ofs_activas(
    prenda_id: int,
    tipo: str = "MUESTRA_APROBADA",
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """Lista OFs en BORRADOR de esta variante. tipo= indica qué doc revisar para ya_tiene."""
    from app.models.of import OrdenFabricacion, EstadoOF
    ofs = (
        db.query(OrdenFabricacion)
          .filter(
              OrdenFabricacion.prenda_catalogo_id == prenda_id,
              OrdenFabricacion.estado.in_([EstadoOF.BORRADOR, EstadoOF.ACTIVA, EstadoOF.EN_PROCESO]),
          ).order_by(OrdenFabricacion.numero_of).all()
    )
    return [
        {
            "id":           of.id,
            "numero_of":    of.numero_of,
            "cliente":      of.cliente,
            "estado":       str(getattr(of.estado, "value", of.estado)),
            "total_juegos": of.total_juegos or 0,
            "ya_tiene":     any(str(getattr(d.tipo, "value", d.tipo)) == tipo for d in of.documentos),
        }
        for of in ofs
    ]


class VincularMuestraBody(_PBase):
    of_ids: Optional[List[int]] = None   # None = todas; lista = solo esas


@router.post("/api/{prenda_id}/vincular-muestra")
def api_vincular_muestra(
    prenda_id: int,
    body: VincularMuestraBody = VincularMuestraBody(),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """Copia MUESTRA_APROBADA del catálogo a las OFs seleccionadas (o todas si of_ids es None)."""
    if _rol(current_user) not in ROLES_EDITOR | {"COMERCIAL", "COMERCIAL_MARCA"}:
        raise HTTPException(403, "Sin permiso")
    from app.models.of import OrdenFabricacion, DocumentoOF, EstadoOF
    from app.services.of_service import actualizar_estado_docs

    prenda = db.query(PrendaCatalogo).filter_by(id=prenda_id).first()
    if not prenda:
        raise HTTPException(404, "Prenda no encontrada")
    if prenda.tipo_cliente == "BASE":
        raise HTTPException(400, "No aplica a prendas BASE")

    doc_muestra = (
        db.query(PrendaDocumento)
          .filter_by(prenda_catalogo_id=prenda_id, tipo="MUESTRA_APROBADA")
          .order_by(PrendaDocumento.created_at.desc())
          .first()
    )
    if not doc_muestra:
        raise HTTPException(404, "Sin documento MUESTRA_APROBADA en catálogo")

    q = db.query(OrdenFabricacion).filter(
        OrdenFabricacion.prenda_catalogo_id == prenda_id,
        OrdenFabricacion.estado == EstadoOF.BORRADOR,
    )
    if body.of_ids:
        q = q.filter(OrdenFabricacion.id.in_(body.of_ids))
    ofs = q.all()

    if not ofs:
        return {"ok": True, "vinculadas": [], "msg": "No hay OFs en BORRADOR para vincular"}

    vinculadas = []
    for of in ofs:
        ya = any(str(getattr(d.tipo, "value", d.tipo)) == "MUESTRA_APROBADA" for d in of.documentos)
        if ya:
            continue
        db.add(DocumentoOF(
            of_id=of.id, tipo="MUESTRA_APROBADA",
            nombre_archivo=doc_muestra.nombre_archivo,
            ruta_archivo=doc_muestra.ruta_archivo,
            area=_rol(current_user), usuario_id=current_user.id,
        ))
        db.flush()
        actualizar_estado_docs(of, db)
        vinculadas.append(of.numero_of)

    db.commit()
    n   = len(vinculadas)
    msg = (f"MUESTRA_APROBADA vinculada a {n} OF(s): {', '.join(vinculadas)}"
           if vinculadas else "Todas las OFs seleccionadas ya tenían MUESTRA_APROBADA")
    return {"ok": True, "vinculadas": vinculadas, "msg": msg}


# ── Endpoint genérico: vincular cualquier tipo de documento del catálogo a OFs ─

_TIPOS_VINCULABLES = {"MUESTRA_APROBADA", "FICHA_TECNICA", "MOLDE"}
_TIPO_CATALOGO_A_OF = {"MOLDE": "MOLDES_LECTRA"}  # catalogo usa MOLDE, documentos_of usa MOLDES_LECTRA

class VincularDocBody(_PBase):
    tipo:   str
    of_ids: Optional[List[int]] = None

@router.post("/api/{prenda_id}/vincular-documento")
def api_vincular_documento(
    prenda_id: int,
    body: VincularDocBody,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """Copia un documento del catálogo (tipo= FICHA_TECNICA | MUESTRA_APROBADA | MOLDE) a OFs seleccionadas."""
    if body.tipo not in _TIPOS_VINCULABLES:
        raise HTTPException(400, f"Tipo no válido. Use: {', '.join(_TIPOS_VINCULABLES)}")
    if _rol(current_user) not in ROLES_EDITOR | {"COMERCIAL", "COMERCIAL_MARCA"}:
        raise HTTPException(403, "Sin permiso")
    from app.models.of import OrdenFabricacion, DocumentoOF, EstadoOF
    from app.services.of_service import actualizar_estado_docs

    prenda = db.query(PrendaCatalogo).filter_by(id=prenda_id).first()
    if not prenda:
        raise HTTPException(404, "Prenda no encontrada")
    if prenda.tipo_cliente == "BASE":
        raise HTTPException(400, "No aplica a prendas BASE")

    doc_cat = (
        db.query(PrendaDocumento)
          .filter_by(prenda_catalogo_id=prenda_id, tipo=body.tipo)
          .order_by(PrendaDocumento.created_at.desc())
          .first()
    )
    if not doc_cat:
        raise HTTPException(404, f"Sin documento {body.tipo} en catálogo")

    q = db.query(OrdenFabricacion).filter(
        OrdenFabricacion.prenda_catalogo_id == prenda_id,
        OrdenFabricacion.estado.in_([EstadoOF.BORRADOR, EstadoOF.ACTIVA, EstadoOF.EN_PROCESO]),
    )
    if body.of_ids:
        q = q.filter(OrdenFabricacion.id.in_(body.of_ids))
    ofs = q.all()

    if not ofs:
        raise HTTPException(400, "No hay OFs activas para esta prenda")

    tipo_doc = _TIPO_CATALOGO_A_OF.get(body.tipo, body.tipo)
    enviadas = []
    for of in ofs:
        doc_ex = db.query(DocumentoOF).filter_by(of_id=of.id, tipo=tipo_doc).first()
        if doc_ex:
            doc_ex.nombre_archivo = doc_cat.nombre_archivo
            doc_ex.ruta_archivo   = doc_cat.ruta_archivo
            doc_ex.usuario_id     = current_user.id
        else:
            db.add(DocumentoOF(
                of_id=of.id, tipo=tipo_doc,
                nombre_archivo=doc_cat.nombre_archivo,
                ruta_archivo=doc_cat.ruta_archivo,
                area=_rol(current_user),
                usuario_id=current_user.id,
            ))
        db.flush()
        actualizar_estado_docs(of, db)
        enviadas.append(of.numero_of)

    db.commit()
    n = len(enviadas)
    return {
        "ok":      True,
        "enviadas": enviadas,
        "msg": f"Documento enviado a {n} OF(s): {', '.join(enviadas)}" if enviadas else "Sin OFs activas para esta prenda"
    }
