"""
Motor de fases del Proceso de Corte.
Centraliza toda la lógica de transición entre fases.
"""
import logging
from datetime import datetime
from sqlalchemy import func
from sqlalchemy.orm import Session
from fastapi import HTTPException

logger = logging.getLogger(__name__)

from app.models.fase import OFFaseEstado, OFFaseTiempos, AvanceRegistro, FaseCatalogo
from app.models.of import OrdenFabricacion, EstadoOF
from app.models.pieza import OFPieza
from app.constants import ORDEN_FASES, NOMBRES_FASE


def _orden_fases_activo(of: OrdenFabricacion) -> list[str]:
    """Retorna el orden de fases aplicables para esta OF (excluye opcionales inactivos)."""
    return [f for f in ORDEN_FASES if not (
        f in ("F8", "F9") and not of.estampado_activo
    )]


def _fase_anterior(fase_id: str, of: OrdenFabricacion) -> str | None:
    """Retorna el fase_id anterior en el orden activo de la OF, o None si es la primera."""
    orden = _orden_fases_activo(of)
    idx = orden.index(fase_id) if fase_id in orden else -1
    return orden[idx - 1] if idx > 0 else None


def _es_tela(fid: str) -> bool:
    """Fases de tela (van por pieza/trazo, no por talla)."""
    return fid in ("F1", "F2", "F3")


def _total_cantidad_fase(of_id: int, fase_id: str, db: Session) -> int:
    """Suma cantidad_actual de todos los registros de una fase para una OF."""
    result = db.query(func.sum(OFFaseEstado.cantidad_actual)).filter_by(
        of_id=of_id, fase_id=fase_id
    ).scalar()
    return result or 0


def _fase_anterior_pieza(fase_id: str, of: OrdenFabricacion, pieza: OFPieza, db: Session) -> str | None:
    """Retorna la fase anterior aplicable para esta pieza específica (respeta fusionado)."""
    orden = _orden_fases_activo(of)
    # Filtrar fases que aplican a esta pieza
    orden_pieza = [f for f in orden if not (f == "F5" and not pieza.fusionado)]
    idx = orden_pieza.index(fase_id) if fase_id in orden_pieza else -1
    return orden_pieza[idx - 1] if idx > 0 else None


def get_fase_actual_pieza(pieza: OFPieza, of: OrdenFabricacion, db: Session) -> str | None:
    """Devuelve el fase_id actual de una pieza (primera no completada aplicable)."""
    for fid in ORDEN_FASES:
        # Saltar opcionales si no están activos
        if fid in ("F8", "F9") and not of.estampado_activo:
            continue
        # Saltar F5 si la pieza no fusiona
        if fid == "F5" and not pieza.fusionado:
            continue
        estado = db.query(OFFaseEstado).filter_by(
            of_id=of.id, pieza_id=pieza.id, fase_id=fid
        ).first()
        if estado and not estado.completada:
            return fid
    return None  # pieza completada


def registrar_avance(
    of: OrdenFabricacion,
    pieza: OFPieza,
    fase_id: str,
    cantidad: int,
    usuario_id: int,
    observacion: str | None,
    db: Session,
    sku_id: int | None = None,
) -> OFFaseEstado:
    # sku_id != None → OF por talla en fase F4–F7 (opera sobre la fila de esa talla)
    q = db.query(OFFaseEstado).filter_by(of_id=of.id, pieza_id=pieza.id, fase_id=fase_id)
    if sku_id is not None:
        q = q.filter_by(sku_id=sku_id)
    estado = q.first()
    if not estado:
        raise HTTPException(404, "Estado de fase no encontrado")
    if estado.completada:
        raise HTTPException(400, "Esta fase ya está completada")

    # ── Gate Fusionado → Calidad ─────────────────────────────────────────────
    # F6 requiere que las piezas fusionables hayan completado F5 (misma talla si aplica).
    if fase_id == "F6":
        for pf in db.query(OFPieza).filter_by(of_id=of.id, fusionado=True).all():
            fq = db.query(OFFaseEstado).filter_by(of_id=of.id, pieza_id=pf.id, fase_id="F5")
            if sku_id is not None:
                fq = fq.filter_by(sku_id=sku_id)
            f5 = fq.first()
            if not f5 or not f5.completada:
                raise HTTPException(
                    400,
                    f"No se puede avanzar a Calidad: la pieza '{pf.nombre}' "
                    f"aún no completó Fusionado."
                )
    # ─────────────────────────────────────────────────────────────────────────

    # ── Cascada ────────────────────────────────────────────────────────────────
    fase_prev = _fase_anterior_pieza(fase_id, of, pieza, db)
    if fase_prev:
        if sku_id is not None and _es_tela(fase_prev):
            # Frontera tela→talla (F4): la fase de tela debe estar completa (gestionada por placas)
            est_prev = db.query(OFFaseEstado).filter_by(
                of_id=of.id, pieza_id=pieza.id, fase_id=fase_prev
            ).first()
            if not (est_prev and est_prev.completada):
                raise HTTPException(
                    400,
                    f"No se puede avanzar: la fase de tela anterior ({fase_prev}) "
                    f"aún no está completa (se gestiona en Placas)."
                )
        else:
            pq = db.query(OFFaseEstado).filter_by(
                of_id=of.id, pieza_id=pieza.id, fase_id=fase_prev
            )
            if sku_id is not None:
                pq = pq.filter_by(sku_id=sku_id)
            est_prev = pq.first()
            disponible_prev = est_prev.cantidad_actual if est_prev else 0
            if estado.cantidad_actual + cantidad > disponible_prev:
                disponible = max(disponible_prev - estado.cantidad_actual, 0)
                raise HTTPException(
                    400,
                    f"Solo puedes registrar {disponible} unidades en {fase_id}. "
                    f"La fase anterior ({fase_prev}) solo tiene {disponible_prev} unidades."
                )
    # ─────────────────────────────────────────────────────────────────────────

    restante = estado.max_cantidad - estado.cantidad_actual
    if cantidad > restante:
        raise HTTPException(400, f"Cantidad excede el máximo restante ({restante})")

    if estado.fecha_inicio is None:
        estado.fecha_inicio = datetime.now()

    estado.cantidad_actual += cantidad

    registro = AvanceRegistro(
        of_id=of.id, pieza_id=pieza.id, fase_id=fase_id,
        sku_id=sku_id, talla=estado.talla,
        cantidad=cantidad, usuario_id=usuario_id, observacion=observacion,
    )
    db.add(registro)

    if of.estado == EstadoOF.ACTIVA:
        of.estado = EstadoOF.EN_PROCESO

    db.commit()
    db.refresh(estado)
    return estado


def completar_fase(
    of: OrdenFabricacion,
    pieza: OFPieza,
    fase_id: str,
    usuario_id: int,
    db: Session,
    sku_id: int | None = None,
) -> OFFaseEstado:
    q = db.query(OFFaseEstado).filter_by(of_id=of.id, pieza_id=pieza.id, fase_id=fase_id)
    if sku_id is not None:
        q = q.filter_by(sku_id=sku_id)
    estado = q.first()
    if not estado:
        raise HTTPException(404, "Estado de fase no encontrado")

    restante = estado.max_cantidad - estado.cantidad_actual
    if restante > 0:
        if sku_id is None:
            # Ruta por pieza (comportamiento original): cascada por totales de fase
            fase_prev = _fase_anterior(fase_id, of)
            if fase_prev:
                total_prev = _total_cantidad_fase(of.id, fase_prev, db)
                total_actual_fase = _total_cantidad_fase(of.id, fase_id, db)
                if total_actual_fase + restante > total_prev:
                    disponible = max(total_prev - total_actual_fase, 0)
                    raise HTTPException(
                        400,
                        f"No se puede completar: solo hay {disponible} unidades disponibles "
                        f"según la fase anterior ({fase_prev})."
                    )
        else:
            # Ruta por talla: cascada por (pieza, talla); frontera tela→talla requiere tela completa
            fase_prev = _fase_anterior_pieza(fase_id, of, pieza, db)
            if fase_prev and _es_tela(fase_prev):
                est_prev = db.query(OFFaseEstado).filter_by(
                    of_id=of.id, pieza_id=pieza.id, fase_id=fase_prev
                ).first()
                if not (est_prev and est_prev.completada):
                    raise HTTPException(
                        400,
                        f"No se puede completar: la fase de tela anterior ({fase_prev}) "
                        f"aún no está completa (se gestiona en Placas)."
                    )
            elif fase_prev:
                est_prev = db.query(OFFaseEstado).filter_by(
                    of_id=of.id, pieza_id=pieza.id, fase_id=fase_prev, sku_id=sku_id
                ).first()
                disponible_prev = est_prev.cantidad_actual if est_prev else 0
                if estado.cantidad_actual + restante > disponible_prev:
                    disponible = max(disponible_prev - estado.cantidad_actual, 0)
                    raise HTTPException(
                        400,
                        f"No se puede completar: solo hay {disponible} unidades disponibles "
                        f"según la fase anterior ({fase_prev})."
                    )
        registro = AvanceRegistro(
            of_id=of.id, pieza_id=pieza.id, fase_id=fase_id,
            sku_id=sku_id, talla=estado.talla,
            cantidad=restante, usuario_id=usuario_id, observacion="Completado",
        )
        db.add(registro)

    estado.cantidad_actual = estado.max_cantidad

    # Poblar fecha_inicio si aún es NULL (completado directamente sin avance previo)
    if estado.fecha_inicio is None:
        estado.fecha_inicio = datetime.now()

    estado.completada = True
    estado.fecha_completado = datetime.now()

    # Verificar si TODAS las piezas de esta fase están completas → registrar fin_real
    _verificar_fase_completa(of, fase_id, db)

    # Verificar si toda la OF está completa (F7 de todas las piezas)
    _verificar_of_completada(of, db)

    db.commit()
    db.refresh(estado)
    return estado


def _verificar_fase_completa(of: OrdenFabricacion, fase_id: str, db: Session):
    """Si TODAS las filas de la fase (pieza × talla) están completas, registra fin_real."""
    rows = db.query(OFFaseEstado).filter_by(of_id=of.id, fase_id=fase_id).all()
    if not rows:
        return
    if any(not fe.completada for fe in rows):
        return  # Aún hay filas pendientes
    # Todas completas → registrar fin_real
    tiempos = db.query(OFFaseTiempos).filter_by(of_id=of.id, fase_id=fase_id).first()
    if tiempos and tiempos.fin_real is None:
        tiempos.fin_real = datetime.now()
    elif not tiempos:
        # Crear fila si no existe (puede ocurrir si no se usó el botón Iniciar)
        tiempos = OFFaseTiempos(of_id=of.id, fase_id=fase_id, fin_real=datetime.now())
        db.add(tiempos)


def _verificar_of_completada(of: OrdenFabricacion, db: Session):
    """Marca la OF como COMPLETADA cuando termina el corte.

    Si la OF ya tiene hoja de numeración (paquetes), el cierre lo gobiernan los
    paquetes (todos ENTREGADOS), no la fase F7 del sistema viejo. Sin hoja,
    se mantiene el criterio original (todas las filas de F7 completas)."""
    from app.services import paquete_service
    res = paquete_service.resumen_calidad_of(of.id, db)
    if res["hay_hoja"]:
        if res["calidad_done"]:
            of.estado = EstadoOF.COMPLETADA
        return
    rows = db.query(OFFaseEstado).filter_by(of_id=of.id, fase_id="F7").all()
    if not rows:
        return
    if any(not f7.completada for f7 in rows):
        return
    of.estado = EstadoOF.COMPLETADA


def iniciar_fase(
    of: OrdenFabricacion,
    fase_id: str,
    db: Session,
) -> OFFaseTiempos:
    """
    Registra inicio_real para una fase de la OF (acción del operario al presionar Iniciar).
    Valida que la fase anterior tenga progreso registrado.
    """
    orden = _orden_fases_activo(of)
    if fase_id not in orden:
        raise HTTPException(400, f"Fase {fase_id} no es aplicable para esta OF")

    # Restricción: fase anterior debe tener avance o inicio_real
    fase_prev = _fase_anterior(fase_id, of)
    if fase_prev:
        total_prev = _total_cantidad_fase(of.id, fase_prev, db)
        tiempos_prev = db.query(OFFaseTiempos).filter_by(
            of_id=of.id, fase_id=fase_prev
        ).first()
        prev_tiene_inicio = tiempos_prev and tiempos_prev.inicio_real is not None
        if total_prev == 0 and not prev_tiene_inicio:
            raise HTTPException(
                400,
                f"No se puede iniciar {fase_id}: la fase anterior ({fase_prev}) "
                f"no tiene avance registrado."
            )

    # Buscar o crear fila en of_fase_tiempos
    tiempos = db.query(OFFaseTiempos).filter_by(of_id=of.id, fase_id=fase_id).first()
    if not tiempos:
        tiempos = OFFaseTiempos(of_id=of.id, fase_id=fase_id)
        db.add(tiempos)

    if tiempos.inicio_real is not None:
        raise HTTPException(400, f"La fase {fase_id} ya fue iniciada")

    tiempos.inicio_real = datetime.now()

    # Transición OF a EN_PROCESO si estaba ACTIVA
    if of.estado == EstadoOF.ACTIVA:
        of.estado = EstadoOF.EN_PROCESO

    db.commit()
    db.refresh(tiempos)
    return tiempos


def get_fases_strip(of: OrdenFabricacion, db: Session) -> list[dict]:
    """
    Retorna datos para la franja de tarjetas de fase en seguimiento.html.
    Incluye tiempos programados, reales, estado y si el botón Iniciar está habilitado.

    Optimización: carga todos los OFFaseEstado y OFFaseTiempos en 2 queries
    y construye índices en memoria — evita N+1 (antes: hasta 9 queries por fase).
    """
    orden = _orden_fases_activo(of)

    # ── 1 query: todos los tiempos de esta OF ────────────────────
    try:
        tiempos_map = {
            t.fase_id: t
            for t in db.query(OFFaseTiempos).filter_by(of_id=of.id).all()
        }
    except Exception as e:
        logger.error("Error cargando of_fase_tiempos para OF %s: %s", of.id, e, exc_info=True)
        db.rollback()
        tiempos_map = {}

    # ── 1 query: todos los estados de todas las fases de esta OF ─
    # Agrupa por fase_id en Python — evita N queries dentro del loop
    todos_estados = db.query(OFFaseEstado).filter_by(of_id=of.id).all()
    estados_por_fase: dict[str, list[OFFaseEstado]] = {}
    for fe in todos_estados:
        estados_por_fase.setdefault(fe.fase_id, []).append(fe)

    # Precalcular cantidad_actual por fase para el check de cascada (puede_iniciar)
    cant_actual_por_fase: dict[str, int] = {
        fid: sum(fe.cantidad_actual for fe in fes)
        for fid, fes in estados_por_fase.items()
    }

    result = []
    for idx, fid in enumerate(orden):
        t = tiempos_map.get(fid)
        fases_estado = estados_por_fase.get(fid, [])

        total_piezas = len(fases_estado)
        completadas  = sum(1 for fe in fases_estado if fe.completada)
        cant_actual  = sum(fe.cantidad_actual for fe in fases_estado)
        cant_max     = sum(fe.max_cantidad    for fe in fases_estado)

        if (t and t.fin_real) or (completadas == total_piezas and total_piezas > 0):
            estado = "completada"
        elif cant_actual > 0 or (t and t.inicio_real):
            estado = "en_proceso"
        else:
            estado = "pendiente"

        # Botón Iniciar: habilitado si no tiene inicio_real
        # y la fase anterior tiene avance o inicio_real
        puede_iniciar = (t is None or t.inicio_real is None)
        if puede_iniciar and idx > 0:
            fase_prev = orden[idx - 1]
            t_prev    = tiempos_map.get(fase_prev)
            prev_ok   = (
                cant_actual_por_fase.get(fase_prev, 0) > 0
                or (t_prev and t_prev.inicio_real is not None)
            )
            puede_iniciar = prev_ok

        result.append({
            "fase_id": fid,
            "nombre": NOMBRES_FASE.get(fid, fid),
            "estado": estado,
            "puede_iniciar": puede_iniciar,
            "inicio_programado": t.inicio_programado.strftime("%d/%m %H:%M") if t and t.inicio_programado else None,
            "fin_programado":    t.fin_programado.strftime("%d/%m %H:%M")    if t and t.fin_programado    else None,
            "inicio_real":       t.inicio_real.strftime("%d/%m %H:%M")       if t and t.inicio_real       else None,
            "fin_real":          t.fin_real.strftime("%d/%m %H:%M")          if t and t.fin_real          else None,
            "pct": 100 if (t and t.fin_real) else (round(cant_actual / cant_max * 100) if cant_max else 0),
        })

    return result


def registrar_avance_bulk(
    of: OrdenFabricacion,
    fase_id: str,
    cantidad: int,
    pieza_ids: list[int],
    usuario_id: int,
    db: Session,
) -> list[OFFaseEstado]:
    """
    Registra el mismo avance en múltiples piezas de una fase con timestamp uniforme.
    Todos los registros comparten el mismo datetime para medición de tiempo precisa.
    """
    from app.models.pieza import OFPieza

    # ── Gate Fusionado → Calidad (bulk) ──────────────────────────────────────
    if fase_id == "F6":
        piezas_fus = db.query(OFPieza).filter_by(of_id=of.id, fusionado=True).all()
        for pf in piezas_fus:
            f5 = db.query(OFFaseEstado).filter_by(
                of_id=of.id, pieza_id=pf.id, fase_id="F5"
            ).first()
            if not f5 or not f5.completada:
                raise HTTPException(
                    400,
                    f"No se puede avanzar a Calidad: la pieza '{pf.nombre}' "
                    f"aún no completó Fusionado."
                )
    # ─────────────────────────────────────────────────────────────────────────

    # Validar restricción cascada por pieza (respeta fusionado/no-fusionado)
    # En vez de comparar totales globales, cada pieza verifica contra su propia fase anterior.
    for pieza_id_check in pieza_ids:
        pieza_check = db.query(OFPieza).filter_by(id=pieza_id_check, of_id=of.id).first()
        if not pieza_check:
            continue
        fase_prev_pieza = _fase_anterior_pieza(fase_id, of, pieza_check, db)
        if fase_prev_pieza:
            est_prev = db.query(OFFaseEstado).filter_by(
                of_id=of.id, pieza_id=pieza_id_check, fase_id=fase_prev_pieza
            ).first()
            disponible_pieza = (est_prev.cantidad_actual if est_prev else 0)
            est_actual = db.query(OFFaseEstado).filter_by(
                of_id=of.id, pieza_id=pieza_id_check, fase_id=fase_id
            ).first()
            ya_registrado = est_actual.cantidad_actual if est_actual else 0
            if ya_registrado + cantidad > disponible_pieza:
                raise HTTPException(
                    400,
                    f"Pieza '{pieza_check.nombre}': solo hay {max(disponible_pieza - ya_registrado, 0)} "
                    f"unidades disponibles según {fase_prev_pieza}."
                )

    # Timestamp uniforme para todas las piezas
    ahora = datetime.now()
    estados = []

    for pieza_id in pieza_ids:
        pieza = db.query(OFPieza).filter_by(id=pieza_id, of_id=of.id).first()
        if not pieza:
            continue
        estado = db.query(OFFaseEstado).filter_by(
            of_id=of.id, pieza_id=pieza_id, fase_id=fase_id
        ).first()
        if not estado or estado.completada:
            continue

        restante = estado.max_cantidad - estado.cantidad_actual
        cant_real = min(cantidad, restante)
        if cant_real <= 0:
            continue

        # Poblar fecha_inicio si es el primer avance
        if estado.fecha_inicio is None:
            estado.fecha_inicio = ahora

        estado.cantidad_actual += cant_real

        registro = AvanceRegistro(
            of_id=of.id, pieza_id=pieza_id, fase_id=fase_id,
            cantidad=cant_real, usuario_id=usuario_id,
            observacion=f"Bulk {len(pieza_ids)} piezas",
        )
        db.add(registro)
        estados.append(estado)

    db.commit()
    for e in estados:
        db.refresh(e)
    return estados

def completar_fase_bulk(
    of: OrdenFabricacion,
    fase_id: str,
    pieza_ids: list[int],
    usuario_id: int,
    db: Session,
) -> list[OFFaseEstado]:
    """
    Completa la fase para múltiples piezas a la vez (llena hasta max_cantidad).
    """
    from app.models.pieza import OFPieza

    # ── Gate Fusionado → Calidad ──────────────────────────────────────────────
    if fase_id == "F6":
        piezas_fus = db.query(OFPieza).filter_by(of_id=of.id, fusionado=True).all()
        for pf in piezas_fus:
            f5 = db.query(OFFaseEstado).filter_by(
                of_id=of.id, pieza_id=pf.id, fase_id="F5"
            ).first()
            if not f5 or not f5.completada:
                raise HTTPException(
                    400,
                    f"No se puede completar a Calidad: la pieza '{pf.nombre}' "
                    f"aún no completó Fusionado."
                )
    # ─────────────────────────────────────────────────────────────────────────

    ahora = datetime.now()
    estados = []

    for pieza_id in pieza_ids:
        pieza = db.query(OFPieza).filter_by(id=pieza_id, of_id=of.id).first()
        if not pieza:
            continue
        estado = db.query(OFFaseEstado).filter_by(
            of_id=of.id, pieza_id=pieza_id, fase_id=fase_id
        ).first()
        if not estado or estado.completada:
            continue

        restante = estado.max_cantidad - estado.cantidad_actual
        if restante > 0:
            # Cascada por pieza
            fase_prev = _fase_anterior_pieza(fase_id, of, pieza, db)
            if fase_prev:
                est_prev = db.query(OFFaseEstado).filter_by(
                    of_id=of.id, pieza_id=pieza_id, fase_id=fase_prev
                ).first()
                disponible_pieza = est_prev.cantidad_actual if est_prev else 0
                if estado.cantidad_actual + restante > disponible_pieza:
                    restante = max(0, disponible_pieza - estado.cantidad_actual)

            if restante <= 0:
                continue

            if estado.fecha_inicio is None:
                estado.fecha_inicio = ahora

            estado.cantidad_actual += restante
            estado.completada = True
            estado.fecha_completado = ahora

            registro = AvanceRegistro(
                of_id=of.id, pieza_id=pieza_id, fase_id=fase_id,
                cantidad=restante, usuario_id=usuario_id,
                observacion=f"Completar bulk {len(pieza_ids)} piezas",
            )
            db.add(registro)
            estados.append(estado)

    db.commit()
    for e in estados:
        db.refresh(e)

    _verificar_fase_completa(of, fase_id, db)
    _verificar_of_completada(of, db)
    db.commit()
    return estados
