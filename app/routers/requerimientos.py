"""Router de Requerimientos comerciales (Muestra / Producción / Stock) — Fase 1.

Aditivo: rutas bajo /requerimientos. Solo CAPTURA el requerimiento; la
generación de OFs la hará Planeamiento en la Fase 2. No toca el flujo de muestra
actual del router comercial.
"""
from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.templates import templates
from app.database.connection import get_db
from app.models.catalogo import PrendaCatalogo
from app.models.usuario import Usuario
from app.roles import ROLES_REQ_EDITAR, ROLES_REQ_VER, rol_de
from app.models.requerimiento import TIPOS_REQUERIMIENTO, TALLAJES
from app.services import requerimiento_service as svc

router = APIRouter()


def _check(user: Usuario, roles: set):
    if rol_de(user) not in roles:
        raise HTTPException(403, f"Rol '{rol_de(user)}' sin permiso para requerimientos")


# ── Esquemas ─────────────────────────────────────────────────────────────────
class TallaIn(BaseModel):
    talla: str
    cantidad: int = 0


class LineaIn(BaseModel):
    grupo: Optional[str] = None
    item_num: Optional[str] = None
    sub_item: Optional[str] = None
    articulo: Optional[str] = None
    descripcion: str
    composicion: Optional[str] = None
    proveedor_tela: Optional[str] = None
    codigo_tela: Optional[str] = None
    color: Optional[str] = None
    tallaje: str = "C"
    total: Optional[int] = None
    prenda_catalogo_id: Optional[int] = None
    orden: Optional[int] = None
    tallas: List[TallaIn] = []


class RequerimientoIn(BaseModel):
    numero_req: str
    tipo: str = "PRODUCCION"
    cliente: str
    proceso: Optional[str] = None
    licitacion: Optional[str] = None
    fecha_solicitud: Optional[date] = None
    fecha_apt: Optional[date] = None
    ejecutivo: Optional[str] = None
    fecha_absolucion: Optional[date] = None
    nota: Optional[str] = None
    lineas: List[LineaIn] = []

    def cabecera(self) -> dict:
        d = self.model_dump(exclude={"lineas"})
        return d

    def lineas_dict(self) -> List[dict]:
        return [ln.model_dump() for ln in self.lineas]


# ── Serialización ────────────────────────────────────────────────────────────
def _req_dict(req) -> dict:
    return {
        "id": req.id, "numero_req": req.numero_req, "tipo": req.tipo,
        "cliente": req.cliente, "proceso": req.proceso, "licitacion": req.licitacion,
        "fecha_solicitud": req.fecha_solicitud.isoformat() if req.fecha_solicitud else None,
        "fecha_apt": req.fecha_apt.isoformat() if req.fecha_apt else None,
        "ejecutivo": req.ejecutivo,
        "fecha_absolucion": req.fecha_absolucion.isoformat() if req.fecha_absolucion else None,
        "nota": req.nota, "estado": req.estado, "total_general": req.total_general,
        "lineas": [{
            "id": ln.id, "grupo": ln.grupo, "item_num": ln.item_num, "sub_item": ln.sub_item,
            "articulo": ln.articulo, "descripcion": ln.descripcion, "composicion": ln.composicion,
            "proveedor_tela": ln.proveedor_tela, "codigo_tela": ln.codigo_tela, "color": ln.color,
            "tallaje": ln.tallaje, "total": ln.total, "orden": ln.orden,
            "prenda_catalogo_id": ln.prenda_catalogo_id,
            "tallas": [{"talla": t.talla, "cantidad": t.cantidad} for t in ln.tallas],
        } for ln in sorted(req.lineas, key=lambda x: x.orden)],
    }


# ── Páginas ──────────────────────────────────────────────────────────────────
@router.get("/", response_class=HTMLResponse)
def pagina_lista(request: Request, current_user: Usuario = Depends(get_current_user)):
    _check(current_user, ROLES_REQ_VER)
    return templates.TemplateResponse("comercial/requerimientos_lista.html", {
        "request": request, "current_user": current_user,
        "puede_editar": rol_de(current_user) in ROLES_REQ_EDITAR,
    })


@router.get("/nuevo", response_class=HTMLResponse)
def pagina_nuevo(request: Request, current_user: Usuario = Depends(get_current_user)):
    _check(current_user, ROLES_REQ_EDITAR)
    return templates.TemplateResponse("comercial/requerimiento_prod_form.html", {
        "request": request, "current_user": current_user,
        "tipos": TIPOS_REQUERIMIENTO, "tallajes": TALLAJES, "req_id": None,
    })


@router.get("/{req_id}", response_class=HTMLResponse)
def pagina_detalle(req_id: int, request: Request, db: Session = Depends(get_db),
                   current_user: Usuario = Depends(get_current_user)):
    _check(current_user, ROLES_REQ_VER)
    svc.obtener_requerimiento(db, req_id)      # 404 si no existe
    return templates.TemplateResponse("comercial/requerimiento_prod_form.html", {
        "request": request, "current_user": current_user,
        "tipos": TIPOS_REQUERIMIENTO, "tallajes": TALLAJES, "req_id": req_id,
        "puede_editar": rol_de(current_user) in ROLES_REQ_EDITAR,
    })


# ── API ──────────────────────────────────────────────────────────────────────
@router.get("/api/tallajes")
def api_tallajes(current_user: Usuario = Depends(get_current_user)):
    _check(current_user, ROLES_REQ_VER)
    return {"tallajes": TALLAJES, "tipos": list(TIPOS_REQUERIMIENTO)}


@router.get("/api/prendas")
def api_prendas(q: Optional[str] = None, db: Session = Depends(get_db),
                current_user: Usuario = Depends(get_current_user)):
    """Autocomplete opcional de prendas del catálogo para enlazar una línea."""
    _check(current_user, ROLES_REQ_VER)
    query = db.query(PrendaCatalogo.id, PrendaCatalogo.codigo, PrendaCatalogo.nombre)
    if q:
        like = f"%{q.strip()}%"
        query = query.filter((PrendaCatalogo.codigo.ilike(like)) |
                             (PrendaCatalogo.nombre.ilike(like)))
    rows = query.order_by(PrendaCatalogo.codigo).limit(30).all()
    return [{"id": r.id, "codigo": r.codigo, "nombre": r.nombre} for r in rows]


@router.get("/api/lista")
def api_lista(tipo: Optional[str] = None, estado: Optional[str] = None,
              db: Session = Depends(get_db),
              current_user: Usuario = Depends(get_current_user)):
    _check(current_user, ROLES_REQ_VER)
    reqs = svc.listar_requerimientos(db, tipo=tipo, estado=estado)
    return [{
        "id": r.id, "numero_req": r.numero_req, "tipo": r.tipo, "cliente": r.cliente,
        "estado": r.estado, "lineas": len(r.lineas), "total_general": r.total_general,
        "fecha_solicitud": r.fecha_solicitud.isoformat() if r.fecha_solicitud else None,
    } for r in reqs]


@router.get("/api/{req_id}")
def api_detalle(req_id: int, db: Session = Depends(get_db),
                current_user: Usuario = Depends(get_current_user)):
    _check(current_user, ROLES_REQ_VER)
    return _req_dict(svc.obtener_requerimiento(db, req_id))


@router.post("/api/crear")
def api_crear(body: RequerimientoIn, db: Session = Depends(get_db),
              current_user: Usuario = Depends(get_current_user)):
    _check(current_user, ROLES_REQ_EDITAR)
    req = svc.crear_requerimiento(db, body.cabecera(), body.lineas_dict(),
                                  usuario_id=current_user.id)
    return _req_dict(req)


@router.post("/api/{req_id}/editar")
def api_editar(req_id: int, body: RequerimientoIn, db: Session = Depends(get_db),
               current_user: Usuario = Depends(get_current_user)):
    _check(current_user, ROLES_REQ_EDITAR)
    req = svc.actualizar_requerimiento(db, req_id, body.cabecera(), body.lineas_dict(),
                                       usuario_id=current_user.id)
    return _req_dict(req)


@router.post("/api/{req_id}/registrar")
def api_registrar(req_id: int, db: Session = Depends(get_db),
                  current_user: Usuario = Depends(get_current_user)):
    _check(current_user, ROLES_REQ_EDITAR)
    return _req_dict(svc.registrar_requerimiento(db, req_id))


@router.delete("/api/{req_id}")
def api_eliminar(req_id: int, db: Session = Depends(get_db),
                 current_user: Usuario = Depends(get_current_user)):
    _check(current_user, ROLES_REQ_EDITAR)
    svc.eliminar_requerimiento(db, req_id)
    return {"ok": True}
