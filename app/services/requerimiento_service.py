"""Servicio de Requerimientos comerciales (Fase 1).

Crea / edita / lista requerimientos con sus líneas y curva de tallas. NO genera
OFs (eso será Planeamiento en la Fase 2). Toda la validación de integridad vive
aquí: numero_req único, tallaje válido, y total = Σ curva por línea.
"""
from datetime import date
from typing import List, Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session, selectinload

from app.models.requerimiento import (
    Requerimiento, RequerimientoLinea, RequerimientoLineaTalla,
    TIPOS_REQUERIMIENTO, ESTADOS_REQUERIMIENTO, TALLAJES,
)

_CAMPOS_CAB = (
    "cliente", "proceso", "licitacion", "fecha_solicitud", "fecha_apt",
    "ejecutivo", "fecha_absolucion", "nota",
)
_CAMPOS_LINEA = (
    "grupo", "item_num", "sub_item", "articulo", "descripcion", "composicion",
    "proveedor_tela", "codigo_tela", "color", "prenda_catalogo_id",
)


# ── Validaciones ─────────────────────────────────────────────────────────────
def _validar_tipo(tipo: str) -> str:
    t = (tipo or "").upper().strip()
    if t not in TIPOS_REQUERIMIENTO:
        raise HTTPException(400, f"Tipo inválido: {tipo}. Use {', '.join(TIPOS_REQUERIMIENTO)}.")
    return t


def _validar_tallaje(tallaje: str) -> str:
    tj = (tallaje or "C").upper().strip()
    if tj not in TALLAJES:
        raise HTTPException(400, f"Tallaje inválido: {tallaje}. Use A, B o C.")
    return tj


def _normalizar_lineas(lineas: List[dict]) -> List[dict]:
    """Valida cada línea y calcula total = Σ curva. Devuelve líneas listas para persistir."""
    if not lineas:
        raise HTTPException(400, "El requerimiento debe tener al menos una línea.")
    out = []
    for i, ln in enumerate(lineas):
        desc = (ln.get("descripcion") or "").strip()
        if not desc:
            raise HTTPException(400, f"Línea {i + 1}: la descripción es obligatoria.")
        tallaje = _validar_tallaje(ln.get("tallaje"))
        validas = set(TALLAJES[tallaje])

        tallas = []
        suma = 0
        for t in (ln.get("tallas") or []):
            talla = str(t.get("talla") or "").strip()
            cant = int(t.get("cantidad") or 0)
            if not talla or cant <= 0:
                continue
            if talla not in validas:
                raise HTTPException(400, f"Línea {i + 1}: talla '{talla}' no pertenece al tallaje {tallaje}.")
            tallas.append({"talla": talla, "cantidad": cant})
            suma += cant
        if suma <= 0:
            raise HTTPException(400, f"Línea {i + 1}: la curva de tallas no puede estar vacía.")

        # total: si viene declarado debe coincidir con la curva; si no, se calcula
        declarado = ln.get("total")
        if declarado not in (None, "", 0) and int(declarado) != suma:
            raise HTTPException(
                400, f"Línea {i + 1}: el total ({declarado}) no coincide con la suma de la curva ({suma}).")

        datos = {c: ln.get(c) for c in _CAMPOS_LINEA}
        datos["descripcion"] = desc
        datos["tallaje"] = tallaje
        datos["total"] = suma
        datos["orden"] = ln.get("orden", i)
        datos["_tallas"] = tallas
        out.append(datos)
    return out


# ── Escritura ────────────────────────────────────────────────────────────────
def crear_requerimiento(db: Session, cabecera: dict, lineas: List[dict],
                        usuario_id: Optional[int] = None) -> Requerimiento:
    numero = (cabecera.get("numero_req") or "").strip()
    if not numero:
        raise HTTPException(400, "El número de requerimiento es obligatorio.")
    if db.query(Requerimiento).filter(Requerimiento.numero_req == numero).first():
        raise HTTPException(409, f"Ya existe un requerimiento con el número {numero}.")
    cliente = (cabecera.get("cliente") or "").strip()
    if not cliente:
        raise HTTPException(400, "El cliente es obligatorio.")

    tipo = _validar_tipo(cabecera.get("tipo"))
    lineas_ok = _normalizar_lineas(lineas)

    req = Requerimiento(numero_req=numero, tipo=tipo, cliente=cliente,
                        estado="BORRADOR", creado_por_id=usuario_id)
    for c in _CAMPOS_CAB:
        setattr(req, c, cabecera.get(c))
    db.add(req)
    db.flush()

    _persistir_lineas(db, req, lineas_ok)
    db.commit()
    db.refresh(req)
    return req


def actualizar_requerimiento(db: Session, req_id: int, cabecera: dict,
                             lineas: List[dict], usuario_id: Optional[int] = None) -> Requerimiento:
    req = obtener_requerimiento(db, req_id)
    if req.estado == "REGISTRADO":
        raise HTTPException(409, "El requerimiento ya está REGISTRADO; no se puede editar.")

    numero = (cabecera.get("numero_req") or req.numero_req).strip()
    if numero != req.numero_req:
        if db.query(Requerimiento).filter(Requerimiento.numero_req == numero,
                                          Requerimiento.id != req.id).first():
            raise HTTPException(409, f"Ya existe un requerimiento con el número {numero}.")
        req.numero_req = numero
    if cabecera.get("cliente"):
        req.cliente = cabecera["cliente"].strip()
    if cabecera.get("tipo"):
        req.tipo = _validar_tipo(cabecera.get("tipo"))
    for c in _CAMPOS_CAB:
        if c in cabecera:
            setattr(req, c, cabecera.get(c))

    lineas_ok = _normalizar_lineas(lineas)
    # reemplazo completo de líneas (cascade borra hijos)
    for ln in list(req.lineas):
        db.delete(ln)
    db.flush()
    _persistir_lineas(db, req, lineas_ok)
    db.commit()
    db.refresh(req)
    return req


def registrar_requerimiento(db: Session, req_id: int) -> Requerimiento:
    """BORRADOR → REGISTRADO (queda listo para que Planeamiento lo tome en Fase 2)."""
    req = obtener_requerimiento(db, req_id)
    if not req.lineas:
        raise HTTPException(400, "No se puede registrar un requerimiento sin líneas.")
    req.estado = "REGISTRADO"
    db.commit()
    db.refresh(req)
    return req


def eliminar_requerimiento(db: Session, req_id: int) -> None:
    req = obtener_requerimiento(db, req_id)
    if req.estado == "REGISTRADO":
        raise HTTPException(409, "No se puede eliminar un requerimiento REGISTRADO.")
    db.delete(req)
    db.commit()


def _persistir_lineas(db: Session, req: Requerimiento, lineas_ok: List[dict]) -> None:
    for datos in lineas_ok:
        tallas = datos.pop("_tallas")
        linea = RequerimientoLinea(requerimiento_id=req.id, **datos)
        db.add(linea)
        db.flush()
        for t in tallas:
            db.add(RequerimientoLineaTalla(linea_id=linea.id, **t))


# ── Lectura ──────────────────────────────────────────────────────────────────
def listar_requerimientos(db: Session, tipo: Optional[str] = None,
                          estado: Optional[str] = None) -> List[Requerimiento]:
    q = db.query(Requerimiento).options(selectinload(Requerimiento.lineas))
    if tipo:
        q = q.filter(Requerimiento.tipo == tipo.upper())
    if estado:
        q = q.filter(Requerimiento.estado == estado.upper())
    return q.order_by(Requerimiento.created_at.desc(), Requerimiento.id.desc()).all()


def obtener_requerimiento(db: Session, req_id: int) -> Requerimiento:
    req = (db.query(Requerimiento)
           .options(selectinload(Requerimiento.lineas).selectinload(RequerimientoLinea.tallas))
           .filter(Requerimiento.id == req_id).first())
    if not req:
        raise HTTPException(404, "Requerimiento no encontrado.")
    return req
