# Servicio de logica de negocio para Ordenes de Fabricacion.
from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.of import OrdenFabricacion, EstadoOF, EstadoDocsEnum, OFTallaDistribucion
from app.models.fase import OFFaseEstado, OFFaseTiempos, FaseCatalogo
from app.models.pieza import OFPieza, PlantillaPieza
from app.models.catalogo import PrendaSku
from app.models.planta import PlantaExterna, TercHistorialFecha, TercSubprocesoLog, TercRecepcion
from app.models.usuario import Usuario
from app.constants import ORDEN_FASES

# Fases de tela (van por pieza / trazo, no por talla)
TELA_FASES = {"F1", "F2", "F3"}
from app.services.gate_service import puede_activar


# ── Duraciones estándar por fase (horas) — fallback si no hay catálogo ───────
_DUR_STD = {
    'F1': 1.0, 'F2': 1.0, 'F3': 1.0, 'F4': 1.0,
    'F8': 1.0, 'F9': 1.0, 'F5': 1.0, 'F6': 1.0, 'F7': 1.0,
}


def auto_derivar_programado(of: OrdenFabricacion, db: Session) -> None:
    """
    Calcula y escribe OFFaseTiempos.inicio_programado / fin_programado
    para las fases que aún NO tienen inicio_real, usando duraciones estándar
    del catálogo de fases de forma secuencial desde fecha_inicio_plan 08:00.

    Las fases con inicio_real ya registrado no se tocan — solo avanzamos el
    puntero de tiempo a partir de su fin_real (o inicio_real + duración).
    """
    from datetime import timedelta

    fecha_base = of.fecha_inicio_plan
    if not fecha_base:
        return

    # Cargar catálogo de duraciones — defensivo: si la migración
    # bloque2_duracion_horas aún no fue aplicada, cae a _DUR_STD
    try:
        catalogo = {
            fc.fase_id: (fc.duracion_horas_std or _DUR_STD.get(fc.fase_id, 8.0))
            for fc in db.query(FaseCatalogo).all()
        }
    except Exception:
        catalogo = {}

    # Índice de tiempos existentes para esta OF
    tiempos_idx: dict[str, OFFaseTiempos] = {
        t.fase_id: t
        for t in db.query(OFFaseTiempos).filter_by(of_id=of.id).all()
    }

    # Puntero de tiempo — empieza a las 08:00 del día de inicio plan
    cursor = datetime(fecha_base.year, fecha_base.month, fecha_base.day, 8, 0)

    for fase_id in ORDEN_FASES:
        dur_h = catalogo.get(fase_id) or _DUR_STD.get(fase_id, 8.0)
        t = tiempos_idx.get(fase_id)

        if t and t.inicio_real is not None:
            # Fase ya iniciada — avanzar cursor desde su fin_real o estimado
            fin_real = t.fin_real or (t.inicio_real + timedelta(hours=dur_h))
            cursor = max(cursor, fin_real)
            continue  # No modificar fechas reales

        # Fase pendiente — calcular programado
        inicio_prog = cursor
        fin_prog    = cursor + timedelta(hours=dur_h)

        if t is None:
            t = OFFaseTiempos(of_id=of.id, fase_id=fase_id)
            db.add(t)
            tiempos_idx[fase_id] = t

        t.inicio_programado = inicio_prog
        t.fin_programado    = fin_prog

        cursor = fin_prog


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
        of.estado = EstadoOF.ACTIVA

    db.commit()


# ── Piezas / Fases ────────────────────────────────────────────

def crear_fases_pieza(pieza: OFPieza, of: OrdenFabricacion, db: Session) -> None:
    """Crea los registros OFFaseEstado para cada fase aplicable de esta pieza.

    - OF con corte_por_talla y curva cargada: F1–F3 por pieza (tela); F4–F7 por pieza×talla.
    - OF por pieza (viejas) o sin distribución: una fila por pieza×fase (sku_id NULL).
    """
    cxp = pieza.cantidad_x_prenda or 1
    por_talla = bool(getattr(of, "corte_por_talla", False))
    dist = []
    if por_talla:
        dist = (
            db.query(OFTallaDistribucion, PrendaSku)
            .join(PrendaSku, PrendaSku.id == OFTallaDistribucion.sku_id)
            .filter(OFTallaDistribucion.of_id == of.id)
            .all()
        )

    for fid in ORDEN_FASES:
        if fid in ("F8", "F9") and not of.estampado_activo:
            continue
        if fid == "F5" and not pieza.fusionado:
            continue

        if por_talla and dist and fid not in TELA_FASES:
            # F4–F7: una fila por talla
            for d, sku in dist:
                db.add(OFFaseEstado(
                    of_id=of.id, pieza_id=pieza.id, fase_id=fid,
                    sku_id=sku.id, talla=sku.talla,
                    max_cantidad=(d.cantidad or 0) * cxp,
                ))
        else:
            # F1–F3 (tela) o flujo por pieza: una fila por pieza
            db.add(OFFaseEstado(
                of_id=of.id, pieza_id=pieza.id, fase_id=fid,
                max_cantidad=of.total_juegos * cxp,
            ))


def regenerar_fases_talla(of: OrdenFabricacion, db: Session) -> None:
    """Asegura las filas F4–F7 por (pieza, talla) para OFs corte_por_talla.

    Idempotente: si una fase ya tiene filas por talla, no la toca. Si tiene una
    fila por pieza (sku NULL, sin avance) — creada antes de vincular la curva —,
    la reemplaza por filas por talla desde la distribución. No toca F1–F3 (tela).
    Se usa al vincular la curva a una OF que ya tiene piezas.
    """
    if not getattr(of, "corte_por_talla", False):
        return
    dist = (
        db.query(OFTallaDistribucion, PrendaSku)
        .join(PrendaSku, PrendaSku.id == OFTallaDistribucion.sku_id)
        .filter(OFTallaDistribucion.of_id == of.id)
        .all()
    )
    piezas = db.query(OFPieza).filter_by(of_id=of.id).all()
    if not dist or not piezas:
        return

    cambiado = False
    for pieza in piezas:
        cxp = pieza.cantidad_x_prenda or 1
        for fid in ORDEN_FASES:
            if fid in TELA_FASES:
                continue
            if fid in ("F8", "F9") and not of.estampado_activo:
                continue
            if fid == "F5" and not pieza.fusionado:
                continue
            filas = db.query(OFFaseEstado).filter_by(
                of_id=of.id, pieza_id=pieza.id, fase_id=fid
            ).all()
            if any(f.sku_id is not None for f in filas):
                continue  # ya está por talla
            null_rows = [f for f in filas if f.sku_id is None]
            if any((f.cantidad_actual or 0) > 0 for f in null_rows):
                continue  # tiene avance → no tocar
            for f in null_rows:
                db.delete(f)
            for d, sku in dist:
                db.add(OFFaseEstado(
                    of_id=of.id, pieza_id=pieza.id, fase_id=fid,
                    sku_id=sku.id, talla=sku.talla,
                    max_cantidad=(d.cantidad or 0) * cxp,
                ))
            cambiado = True
    if cambiado:
        db.commit()


def auto_generar_piezas(of: OrdenFabricacion, db: Session) -> None:
    """Genera piezas desde plantilla y crea sus fases. Llamado al subir FICHA_TECNICA.

    Prioridad:
      1. Si la OF tiene prenda_catalogo_id → filtra PlantillaPieza por ese FK.
      2. Fallback: filtra por tipo_prenda (string) para compatibilidad con prendas base.
    Guard: si la OF ya tiene piezas, no vuelve a generarlas.
    """
    if of.piezas:
        return  # Guard: evita duplicar piezas

    if of.prenda_catalogo_id and of.prenda_catalogo is not None:
        # Ficha efectiva: si la prenda es una variante que hereda, toma las piezas de su base.
        plantillas = sorted(of.prenda_catalogo.piezas_efectivas, key=lambda p: p.orden)
    elif of.prenda_catalogo_id:
        plantillas = (
            db.query(PlantillaPieza)
            .filter_by(prenda_catalogo_id=of.prenda_catalogo_id)
            .order_by(PlantillaPieza.orden)
            .all()
        )
    else:
        # Fallback: buscar por tipo_base en el catálogo activo
        from app.models.catalogo import PrendaCatalogo
        prenda_cat = (
            db.query(PrendaCatalogo)
            .filter_by(tipo_base=of.tipo_prenda, activo=True)
            .order_by(PrendaCatalogo.id)
            .first()
        )
        if prenda_cat:
            plantillas = (
                db.query(PlantillaPieza)
                .filter_by(prenda_catalogo_id=prenda_cat.id)
                .order_by(PlantillaPieza.orden)
                .all()
            )
            # Vincular la OF al catálogo encontrado
            of.prenda_catalogo_id = prenda_cat.id
        else:
            plantillas = []

    for p in plantillas:
        pieza = OFPieza(
            of_id=of.id,
            codigo_pieza=p.codigo,       # trazabilidad hacia el catálogo
            codigo_sap=p.codigo,         # heredar código del catálogo como SAP inicial
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
    fase_id: Optional[str] = None,
) -> dict:
    rol = _rol(usuario)
    if rol not in ("ADMIN", "PLANEADOR"):
        raise HTTPException(403, "Solo ADMIN o PLANEADOR pueden tercerizar una OF")
    estados_permitidos = [EstadoOF.ACTIVA, EstadoOF.EN_PROCESO] if fase_id else [EstadoOF.ACTIVA]
    if of.estado not in estados_permitidos:
        raise HTTPException(400, "Solo se puede tercerizar una OF en estado ACTIVA" if not fase_id else "Solo se puede tercerizar un subproceso en OF ACTIVA o EN PROCESO")
    if of.estado_docs != EstadoDocsEnum.COMPLETA:
        raise HTTPException(400, "Los gates documentales deben estar completos antes de tercerizar")
    if fase_id:
        tiene_avance_fase = any(
            fe.cantidad_actual > 0 or fe.completada
            for p in of.piezas
            for fe in p.fases_estado
            if fe.fase_id == fase_id
        )
        if tiene_avance_fase:
            raise HTTPException(400, f"La fase {fase_id} ya tiene avance registrado")
    else:
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
    log = TercSubprocesoLog(
        of_id=of.id,
        planta_id=planta.id,
        fase_id=fase_id,
        estado="PROGRAMADO",
        juegos_enviados=of.total_juegos,
        fecha_envio=of.fecha_envio,
        fecha_recepcion_est=of.fecha_recepcion_est,
        usuario_creo_id=usuario.id,
    )
    db.add(log)
    db.commit()
    scope = f"fase {fase_id}" if fase_id else "proceso completo"
    return {"ok": True, "mensaje": f"OF {of.numero_of} tercerizada a {planta.nombre} ({scope})"}


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
        raise HTTPException(400, "Las prendas recibidas deben ser >= 1")

    ya_recibidos = of.juegos_recibidos or 0
    pendientes = of.total_juegos - ya_recibidos
    if juegos_recibidos > pendientes:
        raise HTTPException(
            400,
            f"Solo quedan {pendientes} prendas pendientes de recibir (total OF: {of.total_juegos})",
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
    of.fecha_recepcion_real = fecha   # última fecha de recepción registrada
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
