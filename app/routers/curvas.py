"""
Módulo Curvas de Tallas — Samitex Planta
Acceso: UDP, ADMIN, GERENCIA, GERENTE_PLANTA (edición)
        SUPERVISOR_CORTE, PLANEADOR (solo lectura)
"""
from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File, Form
from fastapi.responses import HTMLResponse, FileResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel as PydanticBase
from typing import Optional, List
import os, uuid, pathlib

from app.database.connection import get_db
from app.models.curva_tallas import CurvaTallas, CurvaTallasDetalle, CurvaTallasOF
from app.models.catalogo import PrendaCatalogo, PrendaSku
from app.models.of import OrdenFabricacion, EstadoOF, DocumentoOF
from app.models.usuario import Usuario
from app.core.auth import get_current_user, get_rol
from app.core.templates import templates
from app.config import settings
from app.services import storage

router = APIRouter()

from app.roles import (ROLES_EDITOR_CURVAS as ROLES_EDITOR,
                       ROLES_LECTURA_CURVAS as ROLES_LECTURA,
                       ROLES_ACCESO_CURVAS as ROLES_ACCESO)

_EXTENSIONES_OK = {".pdf", ".xlsx", ".xls", ".docx", ".doc", ".png", ".jpg", ".jpeg"}


def _check(user: Usuario):
    if get_rol(user) not in ROLES_ACCESO:
        raise HTTPException(403, "Sin permiso para acceder a Curvas de tallas")


def _puede_editar(user: Usuario) -> bool:
    return get_rol(user) in ROLES_EDITOR


# ── Páginas ───────────────────────────────────────────────────────────────────

@router.get("/", response_class=HTMLResponse)
def curvas_lista(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    _check(current_user)
    curvas = (
        db.query(CurvaTallas)
          .filter_by(activo=True)
          .order_by(CurvaTallas.created_at.desc())
          .all()
    )
    return templates.TemplateResponse("supervisor/curvas_lista.html", {
        "request":      request,
        "current_user": current_user,
        "curvas":       curvas,
        "puede_editar": _puede_editar(current_user),
    })


@router.get("/nueva", response_class=HTMLResponse)
def curva_nueva_page(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    _check(current_user)
    if not _puede_editar(current_user):
        raise HTTPException(403, "Sin permiso para crear curvas")
    prendas_orm = (
        db.query(PrendaCatalogo)
          .filter(PrendaCatalogo.activo == True,
                  PrendaCatalogo.tipo_cliente != "BASE")
          .order_by(PrendaCatalogo.nombre)
          .all()
    )
    # Serializar a dicts planos — los objetos ORM no son JSON-serializables con tojson
    prendas = [
        {
            "id":           p.id,
            "codigo":       p.codigo or "",
            "nombre":       p.nombre,
            "tipo_base":    p.tipo_base or "",
            "tipo_cliente": p.tipo_cliente or "",
            "color":        p.color or "",
            "skus": [
                {"id": s.id, "talla": s.talla, "orden": s.orden}
                for s in sorted(p.skus, key=lambda x: x.orden)
                if s.activo
            ],
        }
        for p in prendas_orm
    ]
    return templates.TemplateResponse("supervisor/curva_nueva.html", {
        "request":      request,
        "current_user": current_user,
        "prendas":      prendas,
    })


@router.get("/{curva_id}", response_class=HTMLResponse)
def curva_detalle_page(
    curva_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    _check(current_user)
    curva = db.query(CurvaTallas).filter_by(id=curva_id, activo=True).first()
    if not curva:
        raise HTTPException(404, "Curva no encontrada")
    ofs_activas = (
        db.query(OrdenFabricacion)
          .filter(
              OrdenFabricacion.prenda_catalogo_id == curva.prenda_catalogo_id,
              OrdenFabricacion.estado.in_([EstadoOF.BORRADOR, EstadoOF.ACTIVA, EstadoOF.EN_PROCESO]),
          ).order_by(OrdenFabricacion.numero_of).all()
    )
    of_ids_vinculados = {v.of_id for v in curva.vinculos}
    return templates.TemplateResponse("supervisor/curva_detalle.html", {
        "request":           request,
        "current_user":      current_user,
        "curva":             curva,
        "ofs_activas":       ofs_activas,
        "of_ids_vinculados": of_ids_vinculados,
        "puede_editar":      _puede_editar(current_user),
    })


# ── API ───────────────────────────────────────────────────────────────────────

class DetalleIn(PydanticBase):
    sku_id:   int
    talla:    str
    cantidad: int
    orden:    int = 0


class CurvaIn(PydanticBase):
    prenda_catalogo_id: int
    nombre:  Optional[str] = None
    notas:   Optional[str] = None
    detalle: List[DetalleIn] = []


@router.post("/api/curvas")
def api_crear_curva(
    body: CurvaIn,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    _check(current_user)
    if not _puede_editar(current_user):
        raise HTTPException(403, "Sin permiso")
    prenda = db.query(PrendaCatalogo).filter_by(id=body.prenda_catalogo_id, activo=True).first()
    if not prenda:
        raise HTTPException(404, "Prenda no encontrada")
    if prenda.tipo_cliente == "BASE":
        raise HTTPException(400, "No aplica a prendas BASE")
    if not body.detalle:
        raise HTTPException(400, "Debes seleccionar al menos una talla")

    curva = CurvaTallas(
        prenda_catalogo_id=body.prenda_catalogo_id,
        nombre=body.nombre or None,
        notas=body.notas or None,
        creado_por_id=current_user.id,
    )
    db.add(curva)
    db.flush()

    sku_ids_validos = {s.id for s in prenda.skus}
    for d in body.detalle:
        if d.sku_id not in sku_ids_validos:
            raise HTTPException(400, f"SKU {d.sku_id} no pertenece a la prenda")
        db.add(CurvaTallasDetalle(
            curva_id=curva.id,
            sku_id=d.sku_id,
            talla=d.talla,
            cantidad=max(0, d.cantidad),
            orden=d.orden,
        ))

    db.commit()
    db.refresh(curva)
    return {"ok": True, "curva_id": curva.id}


@router.post("/api/curvas/{curva_id}/adjuntar")
def api_adjuntar_doc(   # sync → threadpool, no bloquea el loop
    curva_id: int,
    archivo: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    _check(current_user)
    if not _puede_editar(current_user):
        raise HTTPException(403, "Sin permiso")
    curva = db.query(CurvaTallas).filter_by(id=curva_id, activo=True).first()
    if not curva:
        raise HTTPException(404, "Curva no encontrada")

    ext = pathlib.Path(archivo.filename or "").suffix.lower()
    if ext not in _EXTENSIONES_OK:
        raise HTTPException(400, f"Extensión no permitida ({ext})")

    contenido = archivo.file.read()
    if len(contenido) > 10 * 1024 * 1024:
        raise HTTPException(400, "Archivo supera 10 MB")

    storage.delete(curva.ruta_archivo or "")

    filename = f"{uuid.uuid4().hex}_{pathlib.Path(archivo.filename).name}"
    filepath = storage.save_bytes(contenido, f"curvas/{curva_id}", filename)

    curva.nombre_archivo = archivo.filename
    curva.ruta_archivo   = filepath
    db.commit()
    return {"ok": True, "nombre_archivo": archivo.filename}


@router.get("/api/curvas/{curva_id}/descargar")
def api_descargar_doc(
    curva_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    _check(current_user)
    curva = db.query(CurvaTallas).filter_by(id=curva_id, activo=True).first()
    if not curva or not curva.ruta_archivo:
        raise HTTPException(404, "Documento no encontrado")
    if not storage.exists(curva.ruta_archivo):
        raise HTTPException(404, "Archivo no encontrado en el servidor")
    return storage.serve(curva.ruta_archivo, curva.nombre_archivo)


class CantidadItem(PydanticBase):
    sku_id:   int
    cantidad: int

class VincularOFsBody(PydanticBase):
    of_ids:    List[int]
    cantidades: List[CantidadItem] = []




@router.post("/api/curvas/{curva_id}/vincular-ofs")
def api_vincular_ofs(
    curva_id: int,
    body: VincularOFsBody,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    _check(current_user)
    if not _puede_editar(current_user):
        raise HTTPException(403, "Sin permiso")
    curva = db.query(CurvaTallas).filter_by(id=curva_id, activo=True).first()
    if not curva:
        raise HTTPException(404, "Curva no encontrada")
    if not body.of_ids:
        raise HTTPException(400, "Selecciona al menos una OF")

    from app.services.of_service import actualizar_estado_docs, regenerar_fases_talla
    from app.models.of import OFTallaDistribucion

    ya_vinculados = {v.of_id for v in curva.vinculos}
    enviadas = []

    for of_id in body.of_ids:
        of = db.query(OrdenFabricacion).filter_by(id=of_id).first()
        if not of:
            continue
        if of.prenda_catalogo_id != curva.prenda_catalogo_id:
            continue

        # Registrar vínculo (si no existe)
        if of_id not in ya_vinculados:
            db.add(CurvaTallasOF(
                curva_id=curva_id,
                of_id=of_id,
                enviado_por_id=current_user.id,
            ))

        # Upsert DocumentoOF tipo REPORTE_TALLAS (solo si hay archivo adjunto)
        # Se copia el archivo físico a la carpeta de la OF para que cada OF
        # tenga su propia copia independiente — evita puntero colgante si la
        # curva reemplaza su archivo en el futuro.
        if curva.ruta_archivo and storage.exists(curva.ruta_archivo):
            ext = pathlib.Path(curva.nombre_archivo or "").suffix
            copia_nombre = f"{uuid.uuid4().hex}_reporte_tallas{ext}"
            copia_ruta   = storage.copy_file(curva.ruta_archivo, str(of_id), copia_nombre)

            doc_ex = db.query(DocumentoOF).filter_by(of_id=of_id, tipo="REPORTE_TALLAS").first()
            if doc_ex:
                # Eliminar copia anterior si existe
                if doc_ex.ruta_archivo:
                    storage.delete(doc_ex.ruta_archivo)
                doc_ex.nombre_archivo = curva.nombre_archivo
                doc_ex.ruta_archivo   = copia_ruta
                doc_ex.usuario_id     = current_user.id
            else:
                db.add(DocumentoOF(
                    of_id=of_id, tipo="REPORTE_TALLAS",
                    nombre_archivo=curva.nombre_archivo,
                    ruta_archivo=copia_ruta,
                    area=get_rol(current_user),
                    usuario_id=current_user.id,
                ))

        # Actualizar detalle de la curva si vinieron cantidades modificadas
        if body.cantidades:
            cant_map = {item.sku_id: item.cantidad for item in body.cantidades}
            for det in curva.detalle:
                if det.sku_id in cant_map:
                    det.cantidad = cant_map[det.sku_id]

        # Escribir distribución de tallas (reemplaza siempre — curva es la fuente única)
        db.query(OFTallaDistribucion).filter_by(of_id=of_id).delete()
        if body.cantidades:
            for item in body.cantidades:
                if item.cantidad > 0:
                    db.add(OFTallaDistribucion(
                        of_id=of_id,
                        sku_id=item.sku_id,
                        cantidad=item.cantidad,
                    ))
        else:
            for det in curva.detalle:
                if det.cantidad > 0:
                    db.add(OFTallaDistribucion(
                        of_id=of_id,
                        sku_id=det.sku_id,
                        cantidad=det.cantidad,
                    ))

        db.flush()
        actualizar_estado_docs(of, db)
        # Regenerar F4–F7 por talla si la OF ya tiene piezas (curva vinculada después)
        regenerar_fases_talla(of, db)
        enviadas.append(of.numero_of)

    db.commit()
    n = len(enviadas)
    tiene_archivo = bool(curva.ruta_archivo)
    if enviadas:
        msg = f"Distribución de tallas enviada a {n} OF(s): {', '.join(enviadas)}"
        if tiene_archivo:
            msg += " (+ documento Reporte Tallas)"
    else:
        msg = "Sin cambios (OFs no válidas o ya procesadas)"
    return {"ok": True, "enviadas": enviadas, "msg": msg}


@router.get("/api/historial-prenda/{prenda_id}")
def api_historial_prenda(
    prenda_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """Historial de curvas de tallas para una prenda — usado en catálogo (solo lectura)."""
    _check(current_user)
    curvas = (
        db.query(CurvaTallas)
          .filter_by(prenda_catalogo_id=prenda_id, activo=True)
          .order_by(CurvaTallas.created_at.desc())
          .limit(20).all()
    )
    return [
        {
            "id":            c.id,
            "nombre":        c.nombre,
            "tallas":        [d.talla for d in c.detalle],
            "total_unidades": sum(d.cantidad for d in c.detalle),
            "of_numeros":    [v.of.numero_of for v in c.vinculos if v.of],
            "created_at":    c.created_at.strftime("%d/%m/%Y") if c.created_at else None,
        }
        for c in curvas
    ]


@router.get("/api/prendas-para-curva")
def api_prendas_para_curva(
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """Lista prendas variantes activas con sus SKUs para el combo de nueva curva."""
    _check(current_user)
    prendas = (
        db.query(PrendaCatalogo)
          .filter(PrendaCatalogo.activo == True,
                  PrendaCatalogo.tipo_cliente != "BASE")
          .order_by(PrendaCatalogo.nombre)
          .all()
    )
    return [
        {
            "id":       p.id,
            "codigo":   p.codigo,
            "nombre":   p.nombre,
            "tipo_base": p.tipo_base,
            "tipo_cliente": p.tipo_cliente,
            "color":    p.color,
            "skus": [
                {"id": s.id, "talla": s.talla, "orden": s.orden}
                for s in sorted(p.skus, key=lambda x: x.orden)
                if s.activo
            ],
        }
        for p in prendas
    ]
