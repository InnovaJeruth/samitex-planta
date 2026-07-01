from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.templates import templates
from app.database.connection import get_db
from app.models.catalogo import PrendaCatalogo
from app.models.of import EstadoDocsEnum, EstadoOF, OrdenFabricacion
from app.models.usuario import Usuario
from app.services.of_service import auto_generar_piezas

router = APIRouter()

ROLES_COMERCIAL = {
    "ADMIN", "PLANEADOR", "COMERCIAL", "COMERCIAL_MARCA",
    "PLANEAMIENTO_MARCA", "GERENTE_PLANTA", "GERENCIA",
}
ROLES_CREAR = {"ADMIN", "PLANEADOR", "COMERCIAL", "COMERCIAL_MARCA"}


def _rol(user: Usuario) -> str:
    return user.rol.value if hasattr(user.rol, "value") else str(user.rol)


def _check(user: Usuario, roles: set = ROLES_COMERCIAL):
    if _rol(user) not in roles:
        raise HTTPException(403, "Sin acceso al módulo comercial")


# ── Páginas ───────────────────────────────────────────────────────────────────

@router.get("/", response_class=HTMLResponse)
def lista_requerimientos(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    _check(current_user)
    muestras = (
        db.query(OrdenFabricacion)
        .filter(OrdenFabricacion.es_muestra == True)
        .order_by(OrdenFabricacion.fecha_creacion.desc())
        .all()
    )
    return templates.TemplateResponse("comercial/lista.html", {
        "request": request,
        "current_user": current_user,
        "muestras": muestras,
    })


@router.get("/nuevo", response_class=HTMLResponse)
def nuevo_requerimiento(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    _check(current_user, ROLES_CREAR)
    prendas = (
        db.query(PrendaCatalogo)
        .filter(PrendaCatalogo.activo == True, PrendaCatalogo.tipo_cliente == "INSTITUCION")
        .order_by(PrendaCatalogo.nombre)
        .all()
    )
    return templates.TemplateResponse("comercial/requerimiento_form.html", {
        "request": request,
        "current_user": current_user,
        "prendas": prendas,
    })


# ── API ───────────────────────────────────────────────────────────────────────

@router.post("/api/muestras")
def api_crear_muestra(
    request: Request,
    numero_rm:          str  = Form(...),
    cliente:            str  = Form(...),
    prenda_catalogo_id: int  = Form(...),
    fecha_apt:          Optional[str] = Form(None),
    descripcion:        Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    _check(current_user, ROLES_CREAR)

    # Validar número único
    existe = db.query(OrdenFabricacion).filter_by(numero_of=numero_rm).first()
    if existe:
        raise HTTPException(400, f"El número '{numero_rm}' ya está en uso")

    prenda = db.query(PrendaCatalogo).filter_by(id=prenda_catalogo_id, activo=True).first()
    if not prenda:
        raise HTTPException(404, "Prenda no encontrada o inactiva")

    of = OrdenFabricacion(
        numero_of          = numero_rm,
        cliente            = cliente,
        tipo_prenda        = prenda.nombre,
        prenda_catalogo_id = prenda_catalogo_id,
        total_juegos       = 1,
        es_muestra         = True,
        estado             = EstadoOF.ACTIVA,
        estado_docs        = EstadoDocsEnum.COMPLETA,  # sin gates
        fecha_creacion     = date.today(),
        fecha_apt          = date.fromisoformat(fecha_apt) if fecha_apt else None,
        responsable_id     = current_user.id,
    )
    db.add(of)
    db.flush()

    # Generar piezas y fases desde el catálogo
    auto_generar_piezas(of, db)
    db.commit()

    return {"ok": True, "of_id": of.id, "numero_of": of.numero_of}
