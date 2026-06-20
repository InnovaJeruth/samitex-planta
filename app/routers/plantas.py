from fastapi import APIRouter, Depends, HTTPException, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from pydantic import BaseModel as PydanticBase
from typing import Optional
from datetime import date

from app.database.connection import get_db
from app.models.planta import PlantaExterna, TercRecepcion, TercHistorialFecha
from app.models.of import OrdenFabricacion, EstadoOF
from app.models.usuario import Usuario
from app.core.auth import get_current_user

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

ROLES_PLANTAS = {"ADMIN", "PLANEADOR", "GERENTE_PLANTA", "GERENCIA"}


def _rol(user: Usuario) -> str:
    return user.rol.value if hasattr(user.rol, "value") else str(user.rol)


def _check_rol(user: Usuario):
    if _rol(user) not in ROLES_PLANTAS:
        raise HTTPException(403, "Sin permiso para acceder a plantas externas")


# ── Página listado ─────────────────────────────────────────────
@router.get("/", response_class=HTMLResponse)
def lista_plantas(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    _check_rol(current_user)
    plantas = db.query(PlantaExterna).order_by(PlantaExterna.activo.desc(), PlantaExterna.nombre).all()

    plantas_data = []
    for p in plantas:
        ofs = p.ofs_tercerizadas or []
        total_ofs = len(ofs)

        recepciones = db.query(TercRecepcion).filter_by(planta_id=p.id).all()
        historial   = db.query(TercHistorialFecha).filter_by(planta_id=p.id).all()

        # Métricas de cumplimiento
        entregas_a_tiempo = 0
        entregas_tarde    = 0
        dias_retraso_total = 0
        for of in ofs:
            if of.fecha_recepcion_real and of.fecha_recepcion_est:
                delta = (of.fecha_recepcion_real - of.fecha_recepcion_est).days
                if delta <= 0:
                    entregas_a_tiempo += 1
                else:
                    entregas_tarde += 1
                    dias_retraso_total += delta

        pct_cumplimiento = round(entregas_a_tiempo / total_ofs * 100) if total_ofs else None
        avg_retraso = round(dias_retraso_total / entregas_tarde) if entregas_tarde else 0

        plantas_data.append({
            "planta": p,
            "total_ofs": total_ofs,
            "pct_cumplimiento": pct_cumplimiento,
            "avg_retraso": avg_retraso,
            "cambios_fecha": len(historial),
        })

    return templates.TemplateResponse("plantas/lista.html", {
        "request": request,
        "plantas_data": plantas_data,
        "current_user": current_user,
    })


# ── Página detalle de planta ───────────────────────────────────
@router.get("/{planta_id}/detalle", response_class=HTMLResponse)
def detalle_planta(
    planta_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    _check_rol(current_user)
    planta = db.query(PlantaExterna).filter_by(id=planta_id).first()
    if not planta:
        raise HTTPException(404, "Planta no encontrada")

    ofs = planta.ofs_tercerizadas or []
    recepciones = db.query(TercRecepcion).filter_by(planta_id=planta_id).order_by(TercRecepcion.fecha_recepcion.desc()).all()
    historial   = db.query(TercHistorialFecha).filter_by(planta_id=planta_id).order_by(TercHistorialFecha.registrado_at.desc()).all()

    entregas_a_tiempo = entregas_tarde = dias_retraso_total = 0
    for of in ofs:
        if of.fecha_recepcion_real and of.fecha_recepcion_est:
            delta = (of.fecha_recepcion_real - of.fecha_recepcion_est).days
            if delta <= 0:
                entregas_a_tiempo += 1
            else:
                entregas_tarde += 1
                dias_retraso_total += delta

    total_ofs = len(ofs)
    pct_cumplimiento = round(entregas_a_tiempo / total_ofs * 100) if total_ofs else None
    avg_retraso = round(dias_retraso_total / entregas_tarde) if entregas_tarde else 0

    return templates.TemplateResponse("plantas/detalle.html", {
        "request": request,
        "planta": planta,
        "ofs": ofs,
        "recepciones": recepciones,
        "historial": historial,
        "total_ofs": total_ofs,
        "pct_cumplimiento": pct_cumplimiento,
        "avg_retraso": avg_retraso,
        "current_user": current_user,
    })


# ── API: JSON para dropdown ────────────────────────────────────
@router.get("/api/")
def api_plantas(
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    plantas = db.query(PlantaExterna).filter_by(activo=True).order_by(PlantaExterna.nombre).all()
    return [{"id": p.id, "nombre": p.nombre, "ruc": p.ruc, "encargado": p.encargado} for p in plantas]


# ── API: crear planta ──────────────────────────────────────────
class PlantaBody(PydanticBase):
    nombre:    str
    ruc:       str
    encargado: str
    direccion: str


@router.post("/api/crear")
def crear_planta(
    body: PlantaBody,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    _check_rol(current_user)
    existe = db.query(PlantaExterna).filter_by(ruc=body.ruc.strip()).first()
    if existe:
        raise HTTPException(400, f"Ya existe una planta con RUC {body.ruc}")
    planta = PlantaExterna(
        nombre=body.nombre.strip(),
        ruc=body.ruc.strip(),
        encargado=body.encargado.strip(),
        direccion=body.direccion.strip(),
    )
    db.add(planta)
    db.commit()
    db.refresh(planta)
    return {"id": planta.id, "nombre": planta.nombre}


# ── API: editar planta ─────────────────────────────────────────
class PlantaEditBody(PydanticBase):
    nombre:    Optional[str] = None
    ruc:       Optional[str] = None
    encargado: Optional[str] = None
    direccion: Optional[str] = None
    activo:    Optional[bool] = None


@router.patch("/api/{planta_id}")
def editar_planta(
    planta_id: int,
    body: PlantaEditBody,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    _check_rol(current_user)
    planta = db.query(PlantaExterna).filter_by(id=planta_id).first()
    if not planta:
        raise HTTPException(404, "Planta no encontrada")
    if body.nombre    is not None: planta.nombre    = body.nombre.strip()
    if body.ruc       is not None: planta.ruc        = body.ruc.strip()
    if body.encargado is not None: planta.encargado  = body.encargado.strip()
    if body.direccion is not None: planta.direccion  = body.direccion.strip()
    if body.activo    is not None: planta.activo     = body.activo
    db.commit()
    return {"ok": True}
