"""Router de Analítica / Process Mining (prefijo /analitica).

Solo lectura. Expone el flujo real (DFG), tiempos/cuellos y KPIs del ciclo de
bulto, derivados del event log. No escribe en el ERP ni lo bloquea.
"""
from datetime import datetime, date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.core.auth import get_current_user
from app.core.concurrency import limite_pesado
from app.core.templates import templates
from app.models.usuario import Usuario
from app.roles import ROLES_ANALITICA, rol_de
from app.services.process_mining import event_log as el
from app.services.process_mining import discovery, performance, simulation, critical_path, animation

router = APIRouter()


def _check(user: Usuario):
    if rol_de(user) not in ROLES_ANALITICA:
        raise HTTPException(403, "Sin permiso para la analítica de procesos")


def _rango(desde: Optional[date], hasta: Optional[date]):
    d = datetime.combine(desde, datetime.min.time()) if desde else None
    h = datetime.combine(hasta, datetime.max.time()) if hasta else None
    return d, h


def _ofids(of: Optional[str]) -> Optional[list]:
    """Convierte 'of' (una o varias ids separadas por coma) en lista de int."""
    if not of:
        return None
    ids = [int(x) for x in str(of).replace(" ", "").split(",") if x.strip().isdigit()]
    return ids or None


# ── Página ──────────────────────────────────────────────────────────────────
@router.get("/", response_class=HTMLResponse)
def pagina(request: Request, current_user: Usuario = Depends(get_current_user)):
    _check(current_user)
    return templates.TemplateResponse("analitica/process_mining.html", {
        "request": request, "current_user": current_user,
    })


# ── API (solo lectura) ──────────────────────────────────────────────────────
@router.get("/api/ofs")
def api_ofs(db: Session = Depends(get_db),
            current_user: Usuario = Depends(get_current_user)):
    """Lista de OFs para el selector (id + número)."""
    _check(current_user)
    from app.models.of import OrdenFabricacion
    ofs = (db.query(OrdenFabricacion.id, OrdenFabricacion.numero_of, OrdenFabricacion.cliente)
           .order_by(OrdenFabricacion.numero_of.desc()).limit(300).all())
    return [{"id": o.id, "numero_of": o.numero_of, "cliente": o.cliente} for o in ofs]


@router.get("/api/caso/{case_id}")
def api_caso(case_id: int, case_type: str = "OF", db: Session = Depends(get_db),
             current_user: Usuario = Depends(get_current_user)):
    """Traza de un caso (OF o bulto) ordenada en el tiempo."""
    _check(current_user)
    evs = el.build_event_log(db, case_type=case_type)
    traza = [e for e in evs if e["case_id"] == case_id]
    return {"case_id": case_id, "case_type": case_type, "eventos": traza}


@router.get("/api/dfg")
def api_dfg(case_type: str = "OF", of: Optional[str] = None,
            desde: Optional[date] = None, hasta: Optional[date] = None,
            db: Session = Depends(get_db),
            current_user: Usuario = Depends(get_current_user)):
    """Grafo directly-follows (nodos + aristas). `case_type` OF (desde Tizado) o BULTO.
    `of` = una o varias ids separadas por coma."""
    _check(current_user)
    d, h = _rango(desde, hasta)
    with limite_pesado("Calculando el flujo (DFG)"):
        evs = el.build_event_log(db, case_type=case_type, of_ids=_ofids(of), desde=d, hasta=h)
        return {"filtro": {"case_type": case_type, "of": of, "desde": desde, "hasta": hasta},
                **discovery.dfg(evs), "variantes": discovery.variantes(evs)}


@router.get("/api/tiempos")
def api_tiempos(case_type: str = "OF", of: Optional[str] = None,
                desde: Optional[date] = None, hasta: Optional[date] = None,
                db: Session = Depends(get_db),
                current_user: Usuario = Depends(get_current_user)):
    """Ranking de cuellos: transiciones por tiempo promedio (min)."""
    _check(current_user)
    d, h = _rango(desde, hasta)
    evs = el.build_event_log(db, case_type=case_type, of_ids=_ofids(of), desde=d, hasta=h)
    return {"cuellos": performance.cuellos(evs)}


@router.get("/api/kpis")
def api_kpis(case_type: str = "OF", of: Optional[str] = None,
             desde: Optional[date] = None, hasta: Optional[date] = None,
             db: Session = Depends(get_db),
             current_user: Usuario = Depends(get_current_user)):
    """Resumen: nº casos, lead time medio, % rework, top cuello."""
    _check(current_user)
    d, h = _rango(desde, hasta)
    evs = el.build_event_log(db, case_type=case_type, of_ids=_ofids(of), desde=d, hasta=h)
    return performance.kpis(evs)


@router.get("/api/simulacion/{of_id}")
def api_simulacion(of_id: int, db: Session = Depends(get_db),
                   current_user: Usuario = Depends(get_current_user)):
    """Secuencia de fases de UNA OF (tiempos reales + color) para reproducir."""
    _check(current_user)
    return simulation.simulacion_of(db, of_id)


@router.get("/api/ruta-critica/{of_id}")
def api_ruta_critica(of_id: int, db: Session = Depends(get_db),
                     current_user: Usuario = Depends(get_current_user)):
    """Ruta crítica de UNA OF (CPM): el bulto que determina el fin de la OF,
    su secuencia de actividades y la duración de cada paso."""
    _check(current_user)
    evs = el.build_event_log(db, of_ids=[of_id])
    return critical_path.ruta_critica_of(evs, of_id=of_id)


@router.get("/api/animacion")
def api_animacion(of: Optional[str] = None, db: Session = Depends(get_db),
                  current_user: Usuario = Depends(get_current_user)):
    """Grafo posicionado + tokens (placas/paquetes) con tiempos reales para la
    animación estilo Celonis. `of` = una o varias ids separadas por coma."""
    _check(current_user)
    with limite_pesado("Preparando la animación del flujo"):
        return animation.animacion(db, of_ids=_ofids(of))
