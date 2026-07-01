from fastapi import APIRouter, Depends, HTTPException, Request, Form
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel as PydanticBase
from typing import Optional
from datetime import date

from app.database.connection import get_db
from app.models.planta import PlantaExterna, TercRecepcion, TercHistorialFecha
from app.models.of import OrdenFabricacion, EstadoOF
from app.models.usuario import Usuario
from app.core.auth import get_current_user, get_rol
from app.core.templates import templates

router = APIRouter()

ROLES_PLANTAS = {"ADMIN", "PLANEADOR", "GERENTE_PLANTA", "GERENCIA"}


def _check_rol(user: Usuario):
    if get_rol(user) not in ROLES_PLANTAS:
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
    historial   = db.query(TercHistorialFecha).filter_by(planta_id=planta_id).order_by(TercHistorialFecha.created_at.desc()).all()

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

    try:
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
    except Exception as e:
        import traceback, logging
        logging.getLogger(__name__).error("ERROR detalle_planta:\n%s", traceback.format_exc())
        raise


# ── API: JSON para dropdown ────────────────────────────────────
@router.get("/api/")
def api_plantas(
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    plantas = db.query(PlantaExterna).filter_by(activo=True).order_by(PlantaExterna.nombre).all()
    return [{"id": p.id, "nombre": p.nombre, "ruc": p.ruc, "encargado": p.encargado} for p in plantas]


class PlantaBody(PydanticBase):
    nombre:    str
    ruc:       str
    encargado: str
    direccion: str


# ── API: crear planta ──────────────────────────────────────────
@router.post("/api/crear")
def api_crear_planta(
    body: PlantaBody,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    _check_rol(current_user)
    if not body.nombre or not body.ruc or not body.encargado or not body.direccion:
        raise HTTPException(400, "Todos los campos son obligatorios")
    if len(body.ruc) != 11 or not body.ruc.isdigit():
        raise HTTPException(400, "RUC debe tener 11 dígitos numéricos")
    planta = PlantaExterna(
        nombre=body.nombre.strip(),
        ruc=body.ruc.strip(),
        encargado=body.encargado.strip(),
        direccion=body.direccion.strip(),
        activo=True,
    )
    db.add(planta)
    db.commit()
    db.refresh(planta)
    return {"ok": True, "id": planta.id, "nombre": planta.nombre}


# ── API: editar planta ─────────────────────────────────────────
@router.put("/api/{planta_id}")
def api_editar_planta(
    planta_id: int,
    body: PlantaBody,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    _check_rol(current_user)
    planta = db.query(PlantaExterna).filter_by(id=planta_id).first()
    if not planta:
        raise HTTPException(404, "Planta no encontrada")
    planta.nombre    = body.nombre.strip()
    planta.ruc       = body.ruc.strip()
    planta.encargado = body.encargado.strip()
    planta.direccion = body.direccion.strip()
    db.commit()
    return {"ok": True}


# ── API: desactivar planta ─────────────────────────────────────
@router.delete("/api/{planta_id}")
def api_desactivar_planta(
    planta_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    _check_rol(current_user)
    planta = db.query(PlantaExterna).filter_by(id=planta_id).first()
    if not planta:
        raise HTTPException(404, "Planta no encontrada")
    planta.activo = False
    db.commit()
    return {"ok": True}


# ── API: activar planta ────────────────────────────────────────
@router.patch("/api/{planta_id}/activar")
def api_activar_planta(
    planta_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    _check_rol(current_user)
    planta = db.query(PlantaExterna).filter_by(id=planta_id).first()
    if not planta:
        raise HTTPException(404, "Planta no encontrada")
    planta.activo = True
    db.commit()
    return {"ok": True}
