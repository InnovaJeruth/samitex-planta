# Servicio de logica de negocio para Ordenes de Fabricacion.
from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.of import OrdenFabricacion, EstadoOF, EstadoDocsEnum
from app.models.fase import OFFaseEstado
from app.models.pieza import OFPieza, PlantillaPieza
from app.models.planta import PlantaExterna, TercHistorialFecha
from app.models.usuario import Usuario
from app.constants import ORDEN_FASES
from app.services.gate_service import puede_activar


def _rol(usuario: Usuario) -> str:
    return usuario.rol.value if hasattr(usuario.rol, "value") else str(usuario.rol)


def _parse_date(s: str) -> date:
    try:
        return date.fromisoformat(s)
    except (ValueError, TypeError):
        raise HTTPException(400, f"Fecha inválida: '{s}'. Use formato YYYY-MM-DD")


# ── Docs ──────────────────────────────────────────────────────

def actualizar_estado_docs(of: OrdenFabricacion, db: Session) -> None:
    ok, _ = puede_activar(of, db)

    if of.documentos:
        if of.estado_docs == EstadoDocsEnum.PENDIENTE:
            of.estado_docs = EstadoDocsEnum.EN_DOCUMENTACION

    if ok and of.estado == EstadoOF.BORRADOR:
        of.estado_docs = EstadoDocsEnum.COMPLETA
        piezas_sin_sap = [p for p in of.piezas if not p.codigo_sap]
        if not piezas_sin_sap:
            of.estado = EstadoOF.ACTIVA

    db.commit()


# ── Piezas / Fases ────────────────────────────────────────────

def crear_fases_pieza(pieza: OFPieza, of: OrdenFabricacion, db: Session) -> None:
    """Crea los registros OFFaseEstado para cada fase aplicable de esta pieza."""
    for fid in ORDEN_FASES:
        if fid in ("F8", "F9") and not of.estampado_activo:
            continue
        if fid == "F5" and not pieza.fusionado:
            continue
        estado = OFFaseEstado(
            of_id=of.id,
            pieza_id=pieza.id,
            fase_id=fid,
            max_cantidad=of.total_juegos * pieza.cantidad_x_prenda,
        )
        db.add(estado)


def auto_generar_piezas(of: OrdenFabricacion, db: Session) -> None:
    """Genera piezas desde plantilla y crea sus fases. Llámado al subir FICHA_TECNICA."""
    plantillas = (
        db.query(PlantillaPieza)
        .filter_by(tipo_prenda=of.tipo_prenda)
        .order_by(PlantillaPieza.orden)
        .all()
    )
    for p in plantillas:
        pieza = OFPieza(
            of_id=of.id,
            nombre=p.nombre,
            material=p.material_default,
            cantidad_x_prenda=p.cantidad_x_prenda,
            fusionado=p.fusionado_default,
            orden=p.orden,
        )
        db.add(pieza)
        db.flush()
        crear_fases_pieza(pieza, of, db)
    if plantillas:
        db.commit()


# ── Tercerización ─────────────────────────────────────────────

def tercerizar(
    of: OrdenFabricacion,
    planta_id: int,
    fecha_envio: Optional[str],
    fecha_recepcion_est: Optional[str],
    usuario: Usuario,
    db: Session,
) -> dict:
    rol = _rol(usuario)
    if rol not in ("ADMIN", "PLANEADOR"):
        raise HTTPException(403, "Solo ADMIN o PLANEADOR pueden tercerizar una OF")
    if of.estado != EstadoOF.ACTIVA:
        raise HTTPException(400, "Solo se puede tercerizar una OF en estado ACTIVA")
    if of.estado_docs != EstadoDocsEnum.COMPLETA:
        raise HTTPException(400, "Los gates documentales deben estar completos antes de tercerizar")
    tiene_avance = any(
        fe.cantidad_actual > 0 or fe.completada
        for p in of.piezas
        for fe in p.fases_estado
    )
    if tiene_avance:
        raise HTTPException(400, "No se puede tercerizar una OF que ya tiene avance de corte")

    planta = db.query(PlantaExterna).filter_by(id=planta_id, activo=True).first()
    if not planta:
        raise HTTPException(404, "Planta externa no encontrada o inactiva")

    of.tercerizado = True
    of.planta_id = planta.id
    of.planta_externa = planta.nombre
    of.estado_tercerizado = "PENDIENTE_ENVIO"
    of.juegos_recibidos = 0
    if fecha_envio:
        of.fecha_envio = _parse_date(fecha_envio)
    if fecha_recepcion_est:
        fecha_recep = _parse_date(fecha_recepcion_est)
        if of.fecha_apt and fecha_recep > of.fecha_apt:
            raise HTTPException(
                400,
                f"La fecha de recepción estimada ({fecha_recep}) no puede superar el APT de la OF ({of.fecha_apt})",
            )
        of.fecha_recepcion_est = fecha_recep
    db.commit()
    return {"ok": True, "mensaje": f"OF {of.numero_of} tercerizada a {planta.nombre}"}


def marcar_enviada(of: OrdenFabricacion, usuario: Usuario, db: Session) -> dict:
    rol = _rol(usuario)
    if rol not in ("ADMIN", "PLANEADOR"):
        raise HTTPException(403, "Sin permiso")
    of.estado_tercerizado = "ENVIADA"
    if not of.fecha_envio:
        of.fecha_envio = datetime.now().date()
    db.commit()
    return {"ok": True, "estado_tercerizado": "ENVIADA"}


def actualizar_fecha_recepcion(
    of: OrdenFabricacion,
    fecha_recepcion_est: str,
    motivo: Optional[str],
    usuario: Usuario,
    db: Session,
) -> dict:
    rol = _rol(usuario)
    if rol not in ("ADMIN", "PLANEADOR"):
        raise HTTPException(403, "Sin permiso")

    nueva_fecha = _parse_date(fecha_recepcion_est)
    if of.fecha_apt and nueva_fecha > of.fecha_apt:
        raise HTTPException(
            400,
            f"La fecha de recepción ({nueva_fecha}) no puede superar el APT ({of.fecha_apt})",
        )

    historial = TercHistorialFecha(
        of_id=of.id,
        planta_id=of.planta_id,       # fix: era of.planta_externa_id (campo inexistente)
        fecha_anterior=of.fecha_recepcion_est,
        fecha_nueva=nueva_fecha,
        motivo=motivo,
        usuario_id=usuario.id,
    )
    db.add(historial)
    of.fecha_recepcion_est = nueva_fecha
    db.commit()
    return {"ok": True, "fecha_recepcion_est": str(nueva_fecha)}


def _completar_fases_tercerizada(of: OrdenFabricacion, db: Session) -> None:
    """Marca todas las OFFaseEstado como completadas al 100% y la OF como COMPLETADA."""
    ahora = datetime.now()
    estados = db.query(OFFaseEstado).filter_by(of_id=of.id).all()
    for e in estados:
        e.cantidad_actual = e.max_cantidad
        e.completada = True
        if e.fecha_inicio is None:
            e.fecha_inicio = ahora
        if e.fecha_completado is None:
            e.fecha_completado = ahora
    of.estado = EstadoOF.COMPLETADA


def registrar_recepcion(
    of: OrdenFabricacion,
    juegos_recibidos: int,
    fecha_recepcion: str,
    observacion: Optional[str],
    usuario: Usuario,
    db: Session,
) -> dict:
    from app.models.planta import TercRecepcion

    rol = _rol(usuario)
    if rol not in ("ADMIN", "PLANEADOR", "LOGISTICA"):
        raise HTTPException(403, "Sin permiso para registrar recepción")
    if of.estado_tercerizado not in ("PENDIENTE_ENVIO", "ENVIADA"):
        raise HTTPException(400, f"No se puede registrar recepción en estado '{of.estado_tercerizado}'")
    if juegos_recibidos < 1:
        raise HTTPException(400, "juegos_recibidos debe ser >= 1")

    ya_recibidos = of.juegos_recibidos or 0
    pendientes = of.total_juegos - ya_recibidos
    if juegos_recibidos > pendientes:
        raise HTTPException(
            400,
            f"Solo quedan {pendientes} juegos pendientes de recibir (total OF: {of.total_juegos})",
        )

    fecha = _parse_date(fecha_recepcion)
    recepcion = TercRecepcion(
        of_id=of.id,
        planta_id=of.planta_id,
        juegos_recibidos=juegos_recibidos,
        fecha_recepcion=fecha,
        observacion=observacion,
        usuario_id=usuario.id,
    )
    db.add(recepcion)

    of.juegos_recibidos = ya_recibidos + juegos_recibidos
    recepcion_completa = of.juegos_recibidos >= of.total_juegos
    if recepcion_completa:
        of.estado_tercerizado = "RECIBIDA"
        _completar_fases_tercerizada(of, db)

    db.commit()
    return {
        "ok": True,
        "juegos_recibidos_total": of.juegos_recibidos,
        "estado_tercerizado": of.estado_tercerizado,
        "completa": recepcion_completa,
    }
