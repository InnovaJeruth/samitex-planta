from pydantic import BaseModel as PydanticBase
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.models.of import OrdenFabricacion
from app.models.pieza import OFPieza
from app.models.fase import OFFaseEstado, OFFaseTiempos, AvanceRegistro
from app.models.usuario import Usuario
from app.schemas.fase import AvanceCreate, CompletarRequest
from app.services.corte_service import registrar_avance, completar_fase, iniciar_fase, get_fases_strip, registrar_avance_bulk, completar_fase_bulk, ORDEN_FASES
from app.services.semaforo_service import calcular_semaforo
from app.core.auth import get_current_user

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

ROLES_CORTE = {"ADMIN", "PLANEADOR", "SUPERVISOR_CORTE"}
ROLES_DOCS = {
    "UDP", "COMERCIAL", "COMERCIAL_MARCA", "PLANEAMIENTO_MARCA",
    "INGENIERIA", "LOGISTICA", "CALIDAD",
}


def _rol(user: Usuario) -> str:
    return user.rol.value if hasattr(user.rol, "value") else str(user.rol)


def _check_corte(user: Usuario):
    if _rol(user) not in ROLES_CORTE:
        raise HTTPException(403, f"Rol '{_rol(user)}' no tiene permiso para registrar avance de corte")


@router.get("/{of_id}", response_class=HTMLResponse)
def seguimiento(of_id: int, request: Request, db: Session = Depends(get_db), current_user: Usuario = Depends(get_current_user)):
    of = db.query(OrdenFabricacion).filter_by(id=of_id).first()
    if not of:
        raise HTTPException(404, "OF no encontrada")
    semaforo = calcular_semaforo(of.fecha_apt, of.estado.value == "COMPLETADA")
    puede_registrar = _rol(current_user) in ROLES_CORTE and not of.tercerizado
    return templates.TemplateResponse("corte/seguimiento.html", {
        "request": request, "of": of, "semaforo": semaforo,
        "current_user": current_user, "puede_registrar": puede_registrar, "tercerizado": of.tercerizado,
    })


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
        "piezas": piezas_data, "puede_registrar": _rol(current_user) in ROLES_CORTE,
    }


@router.post("/api/{of_id}/avance")
def registrar(of_id: int, body: AvanceCreate, db: Session = Depends(get_db), current_user: Usuario = Depends(get_current_user)):
    _check_corte(current_user)
    of = db.query(OrdenFabricacion).filter_by(id=of_id).first()
    if not of:
        raise HTTPException(404, "OF no encontrada")
    pieza = db.query(OFPieza).filter_by(id=body.pieza_id, of_id=of_id).first()
    if not pieza:
        raise HTTPException(404, "Pieza no encontrada")
    estado = registrar_avance(of, pieza, body.fase_id, body.cantidad, current_user.id, body.observacion, db)
    return {"pieza_id": pieza.id, "fase_id": body.fase_id, "cantidad_actual": estado.cantidad_actual, "max_cantidad": estado.max_cantidad, "completada": estado.completada}


@router.post("/api/{of_id}/completar")
def completar(of_id: int, body: CompletarRequest, db: Session = Depends(get_db), current_user: Usuario = Depends(get_current_user)):
    _check_corte(current_user)
    of = db.query(OrdenFabricacion).filter_by(id=of_id).first()
    if not of:
        raise HTTPException(404, "OF no encontrada")
    pieza = db.query(OFPieza).filter_by(id=body.pieza_id, of_id=of_id).first()
    if not pieza:
        raise HTTPException(404, "Pieza no encontrada")
    estado = completar_fase(of, pieza, body.fase_id, current_user.id, db)
    return {"completada": estado.completada, "of_estado": of.estado}


@router.get("/api/{of_id}/historial")
def historial(of_id: int, db: Session = Depends(get_db), current_user: Usuario = Depends(get_current_user)):
    registros = db.query(AvanceRegistro).filter_by(of_id=of_id, revertido=False).order_by(AvanceRegistro.created_at.desc()).limit(200).all()
    return [{"id": r.id, "pieza_id": r.pieza_id, "pieza_nombre": r.pieza.nombre if r.pieza else str(r.pieza_id), "fase_id": r.fase_id, "cantidad": r.cantidad, "usuario_nombre": r.usuario.nombre if r.usuario else f"Usuario {r.usuario_id}", "observacion": r.observacion, "created_at": str(r.created_at)} for r in registros]


@router.post("/api/{of_id}/revertir/{registro_id}")
def revertir(of_id: int, registro_id: int, db: Session = Depends(get_db), current_user: Usuario = Depends(get_current_user)):
    _check_corte(current_user)
    registro = db.query(AvanceRegistro).filter_by(id=registro_id, of_id=of_id, revertido=False).first()
    if not registro:
        raise HTTPException(404, "Registro no encontrado o ya revertido")
    estado = db.query(OFFaseEstado).filter_by(of_id=of_id, pieza_id=registro.pieza_id, fase_id=registro.fase_id).first()
    if estado:
        estado.cantidad_actual = max(0, estado.cantidad_actual - registro.cantidad)
        if estado.completada:
            estado.completada = False
            estado.fecha_completado = None
    registro.revertido = True
    db.commit()
    return {"revertido": True, "cantidad": registro.cantidad, "fase_id": registro.fase_id}


@router.get("/api/{of_id}/fases/strip")
def fases_strip(of_id: int, db: Session = Depends(get_db), current_user: Usuario = Depends(get_current_user)):
    of = db.query(OrdenFabricacion).filter_by(id=of_id).first()
    if not of:
        raise HTTPException(404, "OF no encontrada")
    return get_fases_strip(of, db)


@router.post("/api/{of_id}/fases/{fase_id}/iniciar")
def iniciar(of_id: int, fase_id: str, db: Session = Depends(get_db), current_user: Usuario = Depends(get_current_user)):
    _check_corte(current_user)
    of = db.query(OrdenFabricacion).filter_by(id=of_id).first()
    if not of:
        raise HTTPException(404, "OF no encontrada")
    tiempos = iniciar_fase(of, fase_id, db)
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
    estados = registrar_avance_bulk(of, body.fase_id, body.cantidad, body.pieza_ids, current_user.id, db)
    return {"registradas": len(estados), "fase_id": body.fase_id, "cantidad_por_pieza": body.cantidad}


@router.post("/api/{of_id}/completar-bulk")
def completar_bulk(of_id: int, body: CompletarBulkRequest, db: Session = Depends(get_db), current_user: Usuario = Depends(get_current_user)):
    _check_corte(current_user)
    of = db.query(OrdenFabricacion).filter_by(id=of_id).first()
    if not of:
        raise HTTPException(404, "OF no encontrada")
    estados = completar_fase_bulk(of, body.fase_id, body.pieza_ids, current_user.id, db)
    return {"completadas": len(estados), "fase_id": body.fase_id, "of_estado": of.estado}
