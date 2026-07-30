"""
Módulo de Programación del Supervisor.
Permite al supervisor programar tiempos por fase para cada OF.
Acceso: SUPERVISOR_CORTE, GERENTE_PLANTA, PLANEADOR, GERENCIA, ADMIN.
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel as PydanticBase
from datetime import date, datetime
from typing import Optional

from sqlalchemy import text, case
from app.database.connection import get_db
from app.models.of import OrdenFabricacion, EstadoOF
from app.models.fase import OFFaseTiempos
from app.models.usuario import Usuario
from app.core.auth import get_current_user, get_rol
from app.core.templates import templates
from app.services.corte_service import _orden_fases_activo
from app.constants import NOMBRES_FASE

router = APIRouter()

from app.roles import ROLES_SUPERVISOR, ROLES_PROGRAMAR
# Quién puede PROGRAMAR tiempos de máquina (UDP solo ve/edita Curvas de tallas)


def _check_acceso(user: Usuario):
    if get_rol(user) not in ROLES_SUPERVISOR:
        raise HTTPException(403, "Sin permiso para acceder a Programación")


def _color_of(of: OrdenFabricacion, hoy: date, tiene_tabla_tiempos: bool = True) -> str:
    """Determina el color de la OF según estado y proximidad de fecha."""
    if of.estado == EstadoOF.COMPLETADA:
        return "completada"
    # Tiene inicio_real en alguna fase → en proceso
    if tiene_tabla_tiempos:
        try:
            if any(t.inicio_real for t in (of.fase_tiempos or [])):
                return "en_proceso"
        except Exception:
            pass
    if not of.fecha_inicio_plan:
        return "sin_fecha"
    delta = (of.fecha_inicio_plan - hoy).days
    if delta < 0:
        return "vencida"
    if delta == 0:
        return "hoy"
    if delta == 1:
        return "manana"
    if delta == 2:
        return "pasado_manana"
    return "proxima"


# ── Vista principal ───────────────────────────────────────────
@router.get("/programacion", response_class=HTMLResponse)
def programacion(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    _check_acceso(current_user)
    # UDP solo trabaja Curvas de tallas: lo llevamos directo a su pestaña.
    if get_rol(current_user) not in ROLES_PROGRAMAR:
        return RedirectResponse(url="/curvas/", status_code=302)
    hoy = date.today()

    ofs = db.query(OrdenFabricacion).filter(
        OrdenFabricacion.estado.in_([EstadoOF.ACTIVA, EstadoOF.EN_PROCESO, EstadoOF.BORRADOR])
    ).order_by(
        case((OrdenFabricacion.fecha_inicio_plan == None, 1), else_=0),
        OrdenFabricacion.fecha_inicio_plan.asc()
    ).all()

    # Verificar si la tabla of_fase_tiempos existe antes del loop
    try:
        db.execute(text("SELECT 1 FROM of_fase_tiempos LIMIT 1"))
        tabla_tiempos_ok = True
    except Exception:
        db.rollback()
        tabla_tiempos_ok = False

    ofs_data = []
    for of in ofs:
        color = _color_of(of, hoy, tabla_tiempos_ok)
        tiempos_map = {}
        if tabla_tiempos_ok:
            try:
                tiempos_map = {t.fase_id: t for t in of.fase_tiempos}
            except Exception:
                db.rollback()
                tiempos_map = {}
        fases = []
        for fid in _orden_fases_activo(of):
            t = tiempos_map.get(fid)
            fases.append({
                "fase_id": fid,
                "nombre": NOMBRES_FASE.get(fid, fid),
                "inicio_programado": t.inicio_programado.strftime("%Y-%m-%dT%H:%M") if t and t.inicio_programado else "",
                "fin_programado":    t.fin_programado.strftime("%Y-%m-%dT%H:%M")    if t and t.fin_programado    else "",
                "inicio_real":       t.inicio_real.strftime("%d/%m %H:%M")          if t and t.inicio_real       else None,
                "fin_real":          t.fin_real.strftime("%d/%m %H:%M")             if t and t.fin_real          else None,
            })
        ofs_data.append({
            "of": of,
            "color": color,
            "fases": fases,
        })

    return templates.TemplateResponse("supervisor/programacion.html", {
        "request": request,
        "current_user": current_user,
        "ofs_data": ofs_data,
        "hoy": hoy,
        "puede_programar": get_rol(current_user) in ROLES_PROGRAMAR,
    })


# ── API: guardar tiempos programados ─────────────────────────
class TiempoFaseRequest(PydanticBase):
    fase_id: str
    inicio_programado: Optional[str] = None   # ISO datetime string "YYYY-MM-DDTHH:MM"
    fin_programado:    Optional[str] = None


@router.post("/api/{of_id}/programar-fase")
def programar_fase(
    of_id: int,
    body: TiempoFaseRequest,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """Guarda inicio_programado y fin_programado para una OF × fase."""
    if get_rol(current_user) not in ROLES_PROGRAMAR:
        raise HTTPException(403, "Tu rol puede ver Programación pero no programar tiempos de máquina")
    of = db.query(OrdenFabricacion).filter_by(id=of_id).first()
    if not of:
        raise HTTPException(404, "OF no encontrada")

    tiempos = db.query(OFFaseTiempos).filter_by(of_id=of_id, fase_id=body.fase_id).first()
    if not tiempos:
        tiempos = OFFaseTiempos(of_id=of_id, fase_id=body.fase_id)
        db.add(tiempos)

    def parse_dt(s: str | None) -> datetime | None:
        if not s:
            return None
        try:
            return datetime.fromisoformat(s)
        except Exception:
            return None

    tiempos.inicio_programado = parse_dt(body.inicio_programado)
    tiempos.fin_programado    = parse_dt(body.fin_programado)
    db.commit()

    return {
        "fase_id": body.fase_id,
        "inicio_programado": tiempos.inicio_programado.strftime("%d/%m/%Y %H:%M") if tiempos.inicio_programado else None,
        "fin_programado":    tiempos.fin_programado.strftime("%d/%m/%Y %H:%M")    if tiempos.fin_programado    else None,
    }
