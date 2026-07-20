"""
Servicio de paquetes de numeración + Calidad + Reprocesos.

Flujo del paquete:
  HABILITADO  (numerado + agrupado + sticker; nace aquí)
    → POR_VALIDAR (listo para Calidad, tras fusionado si aplica)
      → ENTREGADO (Calidad valida sin rechazos → a costura)
      → STAND_BY  (Calidad valida con piezas rechazadas)
        → (reproceso por el área que Calidad asigna → reingreso)
        → POR_VALIDAR (todas las piezas volvieron) → re-validación

Normalizado: talla/color/numero_hasta/corte_real/aprobadas/entregable/merma son
derivados (no se guardan). `estado` es caché del último evento.
"""
from datetime import datetime
from typing import List, Optional
from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload

from app.constants import UNIDADES_POR_PAQUETE_DEFAULT
from app.models.catalogo import PrendaSku
from app.models.of import OrdenFabricacion, OFTallaDistribucion, EstadoOF
from app.models.fase import OFFaseTiempos
from app.models.paquete import (
    OFPaquete, OFPaqueteEvento, OFPaqueteRechazo, MotivoRechazo, OFNumeracionReapertura,
    ESTADO_HABILITADO, ESTADO_FUSIONADO, ESTADO_POR_VALIDAR, ESTADO_STANDBY, ESTADO_ENTREGADO,
    TIPO_REPROCESO, TIPO_REHACER, TIPO_MERMA, TIPOS_RECHAZO,
    RECHAZO_PENDIENTE, RECHAZO_EN_REPROCESO, RECHAZO_ESPERA_TELA, RECHAZO_REINGRESADO, RECHAZO_MERMA,
    ETAPA_TIZADO, ETAPA_NUMERADO, ETAPA_FUSIONADO, OFReprocesoHito,
    DEST_CORTE, DEST_FUSIONADO, DEST_DESMANCHADO, DEST_HABILITADO, DEST_TENDIDO,
    DEST_TIZADO, DEST_MODELISTA, DEST_GERENCIA, DEST_EXTERNO, DEST_MERMA,
    DESTINOS_CON_BANDEJA, DESTINOS_OK,
)

# Fase del catálogo de fases (F1-F7) que corresponde a la Numeración/Habilitado.
FASE_NUMERACION = "F4"

# Transiciones manuales permitidas del estado del paquete.
# Desde HABILITADO se va a FUSIONADO (si la prenda fusiona) o directo a POR_VALIDAR;
# esa condición la valida set_estado_paquete con requiere_fusionado().
TRANSICIONES = {
    ESTADO_HABILITADO:  {ESTADO_FUSIONADO, ESTADO_POR_VALIDAR},
    ESTADO_FUSIONADO:   {ESTADO_POR_VALIDAR},
    ESTADO_POR_VALIDAR: {ESTADO_ENTREGADO, ESTADO_STANDBY},
    ESTADO_STANDBY:     {ESTADO_POR_VALIDAR},
    ESTADO_ENTREGADO:   set(),
}

# Estados en los que el paquete ya pasó fusionado (o no lo requería)
ESTADOS_POST_FUSIONADO = (ESTADO_POR_VALIDAR, ESTADO_STANDBY, ESTADO_ENTREGADO)

# Un rechazo está "abierto" (la pieza no ha vuelto) mientras se procesa o espera tela
RECHAZOS_ABIERTOS = (RECHAZO_PENDIENTE, RECHAZO_EN_REPROCESO, RECHAZO_ESPERA_TELA)
# En los que el operario puede reingresar (ya corregida)
RECHAZOS_EN_PROCESO = (RECHAZO_PENDIENTE, RECHAZO_EN_REPROCESO)


def requiere_fusionado(of) -> bool:
    """La OF tiene fusionado si alguna de sus piezas fusiona (ficha)."""
    return any(getattr(p, "fusionado", False) for p in (of.piezas or []))


def destinos_permitidos(motivo) -> list:
    """Destinos válidos para un defecto: el fijo + sus alternativas (si Calidad elige)."""
    base = [motivo.destino] if motivo.destino else [DEST_CORTE]
    if motivo.destinos_alt:
        base += [d.strip() for d in motivo.destinos_alt.split(",") if d.strip()]
    return base


# --------------------------------------------------------------------------- #
# Numeración / generación
# --------------------------------------------------------------------------- #
def tope_paquete(of: OrdenFabricacion) -> int:
    v = getattr(of, "unidades_por_paquete", None)
    return v if v else UNIDADES_POR_PAQUETE_DEFAULT


def _bultos_ya_avanzados(of_id: int, db: Session) -> int:
    """Bultos de la OF que ya salieron de HABILITADO (Fusionado/Calidad/Entregado/etc.).
    Si hay alguno, regenerar la hoja los borraría junto con su trabajo — se bloquea
    siempre, sin excepción de rol ni de candado."""
    return (db.query(OFPaquete)
            .filter(OFPaquete.of_id == of_id, OFPaquete.estado != ESTADO_HABILITADO)
            .count())


def _get_o_crear_fase_tiempos(of_id: int, db: Session) -> OFFaseTiempos:
    ft = db.query(OFFaseTiempos).filter_by(of_id=of_id, fase_id=FASE_NUMERACION).first()
    if not ft:
        ft = OFFaseTiempos(of_id=of_id, fase_id=FASE_NUMERACION)
        db.add(ft)
        db.flush()
    return ft


def iniciar_numeracion(of: OrdenFabricacion, db: Session, usuario_id: int = None) -> OFFaseTiempos:
    """Marca el inicio (a nivel OF) del trabajo de numeración. Idempotente:
    si ya tiene inicio_real, no lo pisa."""
    ft = _get_o_crear_fase_tiempos(of.id, db)
    if not ft.inicio_real:
        ft.inicio_real = datetime.now()
        db.commit()
        db.refresh(ft)
    return ft


def _marcar_fin_numeracion_si_corresponde(of_id: int, db: Session) -> None:
    """Cuando el último bulto de la OF sale de HABILITADO (a Fusionado o Calidad),
    cierra automáticamente el fin_real de la fase F4. No requiere acción manual."""
    quedan = db.query(OFPaquete).filter_by(of_id=of_id, estado=ESTADO_HABILITADO).count()
    if quedan > 0:
        return
    ft = db.query(OFFaseTiempos).filter_by(of_id=of_id, fase_id=FASE_NUMERACION).first()
    if ft and not ft.fin_real:
        ft.fin_real = datetime.now()
        db.commit()


def generar_paquetes(of: OrdenFabricacion, reales: List[dict], db: Session,
                     usuario_id: int = None, size: int = None) -> List[OFPaquete]:
    """Regenera los bultos de la OF a partir de las prendas reales por talla, y
    CIERRA la hoja de numeración en el mismo paso (candado: no se puede volver a
    generar hasta que alguien la reabra con motivo).

    `reales` = [{"sku_id": int, "cantidad": int}, ...] ORDENADO (prendas por
    talla; define la numeración correlativa de prenda). Por cada talla se crea
    **un bulto por cada pieza de la OF**, partido por tope (en prendas), con el
    mismo rango de numeración de prenda. Cada bulto nace en HABILITADO.
    """
    if _bultos_ya_avanzados(of.id, db) > 0:
        raise HTTPException(
            400, "No se puede regenerar: hay bultos que ya avanzaron de estado "
                 "(Fusionado, Calidad o Entregado). Esa numeración ya no se puede tocar.")
    if of.hoja_numeracion_cerrada:
        raise HTTPException(
            400, "La hoja de numeración de esta OF ya está cerrada. Debe reabrirse "
                 "(con motivo) antes de volver a generar.")

    tope = size if (size and size > 0) else tope_paquete(of)
    piezas = list(of.piezas or [])

    db.query(OFPaquete).filter(OFPaquete.of_id == of.id).delete(synchronize_session=False)

    paquetes = []
    prenda = 1                                  # nº de prenda correlativo en toda la OF
    numero_por_pieza = {pz.id: 0 for pz in piezas}   # correlativo de bulto por pieza (continuo entre tallas)
    for fila in reales:
        sku_id = fila.get("sku_id")
        cant = int(fila.get("cantidad") or 0)
        if not sku_id or cant <= 0:
            continue
        # Trozos de prendas de esta talla (compartidos por todas las piezas)
        chunks = []
        g, restante = prenda, cant
        while restante > 0:
            c = min(tope, restante)
            chunks.append((g, c))
            g += c
            restante -= c
        for pieza in piezas:
            for (desde, c) in chunks:
                numero_por_pieza[pieza.id] += 1
                p = OFPaquete(of_id=of.id, sku_id=sku_id, pieza_id=pieza.id,
                              numero=numero_por_pieza[pieza.id],
                              numero_desde=desde, cantidad=c, estado=ESTADO_HABILITADO)
                db.add(p)
                db.flush()
                db.add(OFPaqueteEvento(paquete_id=p.id, estado=ESTADO_HABILITADO, usuario_id=usuario_id))
                paquetes.append(p)
        prenda += cant

    # Cierre + fase F4: nuevo ciclo (fin_real se limpia, inicio_real se asegura).
    of.hoja_numeracion_cerrada = True
    of.hoja_numeracion_cerrada_por = usuario_id
    of.hoja_numeracion_cerrada_at = datetime.now()
    ft = _get_o_crear_fase_tiempos(of.id, db)
    if not ft.inicio_real:
        ft.inicio_real = datetime.now()
    ft.fin_real = None

    db.commit()
    return paquetes


def reabrir_hoja_numeracion(of: OrdenFabricacion, motivo: str, db: Session,
                            usuario_id: int = None) -> OrdenFabricacion:
    """Reabre una hoja de numeración cerrada (excepción, con motivo obligatorio).
    Deja auditoría en OFNumeracionReapertura y reinicia el ciclo de la fase F4."""
    if not of.hoja_numeracion_cerrada:
        raise HTTPException(400, "Esta hoja de numeración no está cerrada.")
    if not motivo or not motivo.strip():
        raise HTTPException(400, "El motivo de la reapertura es obligatorio.")

    db.add(OFNumeracionReapertura(of_id=of.id, usuario_id=usuario_id, motivo=motivo.strip()))

    of.hoja_numeracion_cerrada = False
    of.hoja_numeracion_cerrada_por = None
    of.hoja_numeracion_cerrada_at = None

    ft = db.query(OFFaseTiempos).filter_by(of_id=of.id, fase_id=FASE_NUMERACION).first()
    if ft:
        ft.inicio_real = None
        ft.fin_real = None

    db.commit()
    db.refresh(of)
    return of


def listar_reaperturas_numeracion(of_id: int, db: Session) -> List[OFNumeracionReapertura]:
    return (db.query(OFNumeracionReapertura)
            .filter_by(of_id=of_id)
            .order_by(OFNumeracionReapertura.created_at.desc())
            .all())


# --------------------------------------------------------------------------- #
# Transiciones simples de estado
# --------------------------------------------------------------------------- #
def set_estado_paquete(paquete_id: int, nuevo_estado: str, db: Session,
                       usuario_id: int = None, motivo: str = None) -> OFPaquete:
    """Transición manual del paquete (ej. HABILITADO → POR_VALIDAR: 'enviar a Calidad').

    Para pasar a ENTREGADO desde POR_VALIDAR no debe haber rechazos abiertos.
    """
    p = _get_paquete(paquete_id, db)
    permitidos = TRANSICIONES.get(p.estado, set())
    if nuevo_estado not in permitidos:
        raise HTTPException(400, f"Transición no permitida: {p.estado} → {nuevo_estado}")
    # Frontera de fusionado: si ESTA pieza fusiona, HABILITADO debe pasar por FUSIONADO
    if p.estado == ESTADO_HABILITADO:
        fusiona = p.fusiona
        if nuevo_estado == ESTADO_POR_VALIDAR and fusiona:
            raise HTTPException(400, "Esta pieza requiere fusionado antes de Calidad")
        if nuevo_estado == ESTADO_FUSIONADO and not fusiona:
            raise HTTPException(400, "Esta pieza no requiere fusionado")
    if nuevo_estado == ESTADO_ENTREGADO and _rechazos_abiertos(p.id, db) > 0:
        raise HTTPException(400, "No se puede entregar: hay piezas en reproceso (stand-by)")

    estado_anterior = p.estado
    p.estado = nuevo_estado
    db.add(OFPaqueteEvento(paquete_id=p.id, estado=nuevo_estado, motivo=motivo, usuario_id=usuario_id))
    db.commit()
    db.refresh(p)
    if estado_anterior == ESTADO_HABILITADO:
        _marcar_fin_numeracion_si_corresponde(p.of_id, db)
    return p


# --------------------------------------------------------------------------- #
# Calidad
# --------------------------------------------------------------------------- #
def iniciar_fusionado(paquete_id: int, db: Session, usuario_id: int = None) -> OFPaquete:
    """Marca el inicio del fusionado de un bulto (sigue en estado FUSIONADO)."""
    from datetime import datetime
    p = _get_paquete(paquete_id, db)
    if p.estado != ESTADO_FUSIONADO:
        raise HTTPException(400, "El bulto no está en fusionado")
    if not p.fusionado_inicio:
        p.fusionado_inicio = datetime.now()
    db.commit()
    db.refresh(p)
    return p


def terminar_fusionado(paquete_id: int, db: Session, usuario_id: int = None) -> OFPaquete:
    """Termina el fusionado de un bulto: registra fin y lo manda a Calidad."""
    from datetime import datetime
    p = _get_paquete(paquete_id, db)
    if p.estado != ESTADO_FUSIONADO:
        raise HTTPException(400, "El bulto no está en fusionado")
    if not p.fusionado_inicio:
        p.fusionado_inicio = datetime.now()
    p.fusionado_fin = datetime.now()
    p.estado = ESTADO_POR_VALIDAR
    db.add(OFPaqueteEvento(paquete_id=p.id, estado=ESTADO_POR_VALIDAR, usuario_id=usuario_id))
    db.commit()
    db.refresh(p)
    return p


def listar_fusionado(db: Session, of_id: int = None) -> List[OFPaquete]:
    """Bultos en FUSIONADO de todas las OFs activas (bandeja del operario de fusionado)."""
    q = (db.query(OFPaquete)
         .join(OrdenFabricacion, OrdenFabricacion.id == OFPaquete.of_id)
         .filter(OrdenFabricacion.estado == EstadoOF.ACTIVA,
                 OFPaquete.estado == ESTADO_FUSIONADO))
    if of_id:
        q = q.filter(OFPaquete.of_id == of_id)
    return q.order_by(OrdenFabricacion.numero_of, OFPaquete.numero).all()


def avanzar_fusionado_talla(of_id: int, sku_id: int, accion: str, db: Session, usuario_id: int = None) -> int:
    """Lote en el módulo de fusionado: 'iniciar' o 'terminar' los bultos FUSIONADO de una talla."""
    bultos = db.query(OFPaquete).filter_by(of_id=of_id, sku_id=sku_id, estado=ESTADO_FUSIONADO).all()
    n = 0
    for p in bultos:
        if accion == "iniciar":
            iniciar_fusionado(p.id, db, usuario_id)
        elif accion == "terminar":
            terminar_fusionado(p.id, db, usuario_id)
        n += 1
    return n


def validar_paquete(paquete_id: int, rechazos: List[dict], db: Session,
                    usuario_id: int = None) -> OFPaquete:
    """Calidad valida un paquete: registra las piezas rechazadas (con su defecto
    y el destino que asigna Calidad) y deja el paquete ENTREGADO (sin rechazos) o
    STAND_BY (con rechazos).

    `rechazos` = [{"motivo_id": int, "cantidad": int,
                   "destino": "CORTE|FUSIONADO|...|GERENCIA|MERMA" (opcional; default = del defecto),
                   "rehacer": bool}, ...]
    """
    p = _get_paquete(paquete_id, db)
    if p.estado not in (ESTADO_POR_VALIDAR, ESTADO_STANDBY):
        raise HTTPException(400, f"El paquete no está en validación (estado {p.estado})")

    rechazos = rechazos or []
    total = sum(int(r.get("cantidad") or 0) for r in rechazos)
    if total > p.cantidad:
        raise HTTPException(400, "Las piezas rechazadas superan la cantidad del paquete")

    for r in rechazos:
        cant = int(r.get("cantidad") or 0)
        motivo_id = r.get("motivo_id")
        if cant <= 0 or not motivo_id:
            continue
        motivo = db.query(MotivoRechazo).filter_by(id=motivo_id).first()
        if not motivo:
            raise HTTPException(400, f"Motivo de rechazo inexistente: {motivo_id}")
        # el destino debe estar dentro de lo permitido del defecto; si no, se usa el del catálogo
        permitidos = destinos_permitidos(motivo)
        destino = r.get("destino")
        if destino not in permitidos:
            destino = motivo.destino or DEST_CORTE
        rehacer = (bool(r.get("rehacer")) or bool(motivo.rehacer_default)) and destino == DEST_CORTE
        # toda pieza irrecuperable se rehace (no se pierde la unidad); el rechazo
        # siempre entra PENDIENTE y sale al reingresar. `rehacer` = corta nueva (usa tela).
        tipo = TIPO_REHACER if rehacer else TIPO_REPROCESO
        db.add(OFPaqueteRechazo(
            paquete_id=p.id, motivo_id=motivo_id, cantidad=cant,
            destino=destino, rehacer=rehacer, tipo=tipo,
            estado=RECHAZO_PENDIENTE, usuario_id=usuario_id,
        ))
    db.flush()

    nuevo = ESTADO_STANDBY if _rechazos_abiertos(p.id, db) > 0 else ESTADO_ENTREGADO
    p.estado = nuevo
    db.add(OFPaqueteEvento(paquete_id=p.id, estado=nuevo, usuario_id=usuario_id))
    db.flush()
    if nuevo == ESTADO_ENTREGADO:
        _marcar_of_si_completa(p.of_id, db)   # cierre de OF cuando toda la calidad está lista
    db.commit()
    db.refresh(p)
    return p


def _marcar_of_si_completa(of_id: int, db: Session):
    """Cierra la OF (COMPLETADA) cuando todos sus paquetes están ENTREGADOS.
    Es el 'gate a costura': la OF de corte se cierra por paquetes, no por la
    fase F7 del sistema viejo. Chequeo barato: 2 conteos, sin reconstruir el
    resumen de calidad (evita el N+1 por bulto)."""
    from app.models.of import EstadoOF
    total = db.query(func.count(OFPaquete.id)).filter(OFPaquete.of_id == of_id).scalar()
    if not total:
        return
    pendientes = (db.query(func.count(OFPaquete.id))
                  .filter(OFPaquete.of_id == of_id, OFPaquete.estado != ESTADO_ENTREGADO)
                  .scalar())
    if pendientes == 0:
        of = db.query(OrdenFabricacion).filter_by(id=of_id).first()
        if of and of.estado != EstadoOF.COMPLETADA:
            of.estado = EstadoOF.COMPLETADA


# --------------------------------------------------------------------------- #
# Reprocesos
# --------------------------------------------------------------------------- #
def tomar_reproceso(rechazo_id: int, db: Session, usuario_id: int = None) -> OFPaqueteRechazo:
    """El operario de la estación toma el rechazo: PENDIENTE → EN_REPROCESO
    y registra el inicio (hito con hora) en su estación."""
    r = _get_rechazo(rechazo_id, db)
    if r.estado != RECHAZO_PENDIENTE:
        raise HTTPException(400, f"El rechazo no está pendiente (estado {r.estado})")
    r.estado = RECHAZO_EN_REPROCESO
    db.add(OFReprocesoHito(rechazo_id=r.id, etapa=estacion_de(r), usuario_id=usuario_id))
    db.commit()
    db.refresh(r)
    return r


def reingresar_rechazo(rechazo_id: int, db: Session, usuario_id: int = None) -> OFPaqueteRechazo:
    """La pieza corregida vuelve: rechazo → REINGRESADO. Si el paquete ya no tiene
    rechazos abiertos, vuelve a POR_VALIDAR para que Calidad re-valide."""
    r = _get_rechazo(rechazo_id, db)
    if r.estado not in RECHAZOS_EN_PROCESO:
        raise HTTPException(400, f"El rechazo no está en proceso (estado {r.estado})")
    r.estado = RECHAZO_REINGRESADO
    db.flush()
    _reevaluar_paquete(r.paquete_id, db, usuario_id)
    db.commit()
    db.refresh(r)
    return r


def marcar_falta_tela(rechazo_id: int, db: Session, usuario_id: int = None) -> OFPaqueteRechazo:
    """Corte marca que no hay tela para rehacer → 'esperando tela' (aviso a Planeamiento:
    aumentar consumo + SOLPED en SAP). El pedido físico lo gestiona PCP/Almacén."""
    r = _get_rechazo(rechazo_id, db)
    if not r.rehacer:
        raise HTTPException(400, "Solo aplica a piezas por rehacer")
    if r.estado not in RECHAZOS_EN_PROCESO:
        raise HTTPException(400, f"Estado inválido ({r.estado})")
    r.estado = RECHAZO_ESPERA_TELA
    db.commit()
    db.refresh(r)
    return r


def registrar_solped(rechazo_ids: List[int], solped: str, db: Session, usuario_id: int = None) -> int:
    """Guarda el N° de SOLPED (SAP) en uno o varios requerimientos de tela (trazabilidad).
    Una SOLPED puede cubrir varias piezas."""
    solped = (solped or "").strip()
    if not solped:
        raise HTTPException(400, "Ingresa el N° de SOLPED")
    n = 0
    for rid in rechazo_ids:
        r = db.query(OFPaqueteRechazo).filter_by(id=rid).first()
        if r and r.estado == RECHAZO_ESPERA_TELA:
            r.solped = solped
            n += 1
    db.commit()
    return n


def marcar_tela_recibida(rechazo_id: int, db: Session, usuario_id: int = None) -> OFPaqueteRechazo:
    """Llegó la tela (Almacén entregó): vuelve a Corte para rehacer (tizado + fases).
    Requiere que el N° de SOLPED esté registrado (trazabilidad)."""
    r = _get_rechazo(rechazo_id, db)
    if r.estado != RECHAZO_ESPERA_TELA:
        raise HTTPException(400, "El rechazo no está esperando tela")
    if not (r.solped or "").strip():
        raise HTTPException(400, "Registra el N° de SOLPED antes de marcar la tela como recibida")
    r.estado = RECHAZO_EN_REPROCESO
    db.commit()
    db.refresh(r)
    return r


# --------------------------------------------------------------------------- #
# Reproceso por ESTACIÓN real (no por micro-fase)
# --------------------------------------------------------------------------- #
# Estaciones/equipos físicos que reprocesan (cada uno con su bandeja/módulo).
# Tizado/Tendido/Corte/Numerado son el MISMO equipo de Corte → una sola parada.
ESTACION_CORTE       = DEST_CORTE
ESTACION_FUSIONADO   = DEST_FUSIONADO
ESTACION_DESMANCHADO = DEST_DESMANCHADO
ESTACION_HABILITADO  = DEST_HABILITADO
_DESTINOS_CORTE = (DEST_TIZADO, DEST_TENDIDO, DEST_CORTE, ETAPA_NUMERADO)


def estacion_de(r: OFPaqueteRechazo) -> str:
    """Estación donde se trabaja la pieza AHORA.
    - etapa == FUSIONADO → ya pasó a Fusionado (handoff de Corte)
    - destino Tizado/Tendido/Corte/Numerado (o rehacer) → estación Corte
    - resto (Fusionado/Desmanchado/Habilitado) → su propia estación."""
    if r.etapa == ETAPA_FUSIONADO:
        return ESTACION_FUSIONADO
    dest = r.destino or DEST_CORTE
    if r.rehacer or dest in _DESTINOS_CORTE:
        return ESTACION_CORTE
    return dest


def punto_reinicio(r: OFPaqueteRechazo):
    """Desde qué fase debe reiniciar el equipo de Corte (dato/hint, no un paso clickeable).
    rehacer = desde Tizado; si no, la fase que indica el destino del defecto."""
    if estacion_de(r) != ESTACION_CORTE:
        return None
    if r.rehacer:
        return ETAPA_TIZADO
    dest = r.destino or DEST_CORTE
    return dest if dest in _DESTINOS_CORTE else DEST_CORTE


def _reingresar_a_calidad(r: OFPaqueteRechazo, db: Session, usuario_id: int = None):
    """Cierra el reproceso: rechazo → REINGRESADO y reevalúa el bulto (→ POR_VALIDAR)."""
    r.estado = RECHAZO_REINGRESADO
    db.add(OFReprocesoHito(rechazo_id=r.id, etapa=RECHAZO_REINGRESADO, usuario_id=usuario_id))
    db.flush()
    _reevaluar_paquete(r.paquete_id, db, usuario_id)


def terminar_reproceso(rechazo_id: int, db: Session, usuario_id: int = None) -> OFPaqueteRechazo:
    """El operario de la estación termina su parte:
    - Corte + pieza fusible → 'handoff' al módulo de Fusionado (no reingresa aún)
    - resto → la pieza reingresa a Calidad (→ POR_VALIDAR)."""
    r = _get_rechazo(rechazo_id, db)
    if r.estado == RECHAZO_ESPERA_TELA:
        raise HTTPException(400, "Está esperando tela; primero regístrala como recibida")
    if r.estado != RECHAZO_EN_REPROCESO:
        raise HTTPException(400, "Primero toma la pieza (debe estar en reproceso)")
    if estacion_de(r) == ESTACION_FUSIONADO:
        raise HTTPException(400, "El re-fusionado se termina en el módulo de Fusionado")
    if estacion_de(r) == ESTACION_CORTE and r.paquete and r.paquete.fusiona:
        r.etapa = ETAPA_FUSIONADO          # pasa solo al módulo de Fusionado
        db.commit()
        db.refresh(r)
        return r
    _reingresar_a_calidad(r, db, usuario_id)
    db.commit()
    db.refresh(r)
    return r


# --------------------------------------------------------------------------- #
# Re-fusionado (reproceso que pasa por el módulo de Fusionado, con inicio/fin)
# --------------------------------------------------------------------------- #
def _refusionado_iniciado(r: OFPaqueteRechazo) -> bool:
    return any(h.etapa == ETAPA_FUSIONADO for h in r.hitos)


def iniciar_refusionado(rechazo_id: int, db: Session, usuario_id: int = None) -> OFPaqueteRechazo:
    """El operario de fusionado inicia el re-fusionado de una pieza (marca el inicio)."""
    r = _get_rechazo(rechazo_id, db)
    if estacion_de(r) != ESTACION_FUSIONADO:
        raise HTTPException(400, "La pieza no está en fase de re-fusionado")
    if r.estado not in RECHAZOS_EN_PROCESO:
        raise HTTPException(400, f"Estado inválido ({r.estado})")
    if _refusionado_iniciado(r):
        return r
    r.etapa = ETAPA_FUSIONADO
    r.estado = RECHAZO_EN_REPROCESO
    db.add(OFReprocesoHito(rechazo_id=r.id, etapa=ETAPA_FUSIONADO, usuario_id=usuario_id))
    db.commit()
    db.refresh(r)
    return r


def terminar_refusionado(rechazo_id: int, db: Session, usuario_id: int = None) -> OFPaqueteRechazo:
    """Termina el re-fusionado (marca el fin) y la pieza reingresa a Calidad."""
    r = _get_rechazo(rechazo_id, db)
    if estacion_de(r) != ESTACION_FUSIONADO:
        raise HTTPException(400, "La pieza no está en fase de re-fusionado")
    if not _refusionado_iniciado(r):
        raise HTTPException(400, "Primero inicia el re-fusionado")
    _reingresar_a_calidad(r, db, usuario_id)
    db.commit()
    db.refresh(r)
    return r


def refusionado_desde(r: OFPaqueteRechazo):
    """Hora en que se inició el re-fusionado (hito FUSIONADO), si ya arrancó."""
    for h in r.hitos:
        if h.etapa == ETAPA_FUSIONADO:
            return h.at
    return None


def _reevaluar_paquete(paquete_id: int, db: Session, usuario_id: int = None):
    """Si un paquete en STAND_BY ya no tiene rechazos abiertos, avanza:
    - pieza fusible → FUSIONADO (la pieza corregida/rehecha debe re-fusionarse)
    - pieza no fusible → POR_VALIDAR (directo a Calidad)."""
    p = _get_paquete(paquete_id, db)
    if p.estado == ESTADO_STANDBY and _rechazos_abiertos(p.id, db) == 0:
        # Vuelve a Calidad. El re-fusionado (si aplica) ya lo cubre la ruta de rehacer
        # (etapa FUSIONADO) o el reproceso en su área; no se re-fusiona el bulto aparte.
        p.estado = ESTADO_POR_VALIDAR
        db.add(OFPaqueteEvento(paquete_id=p.id, estado=ESTADO_POR_VALIDAR, usuario_id=usuario_id))


# --------------------------------------------------------------------------- #
# Consultas / derivados
# --------------------------------------------------------------------------- #
def listar_paquetes(of_id: int, db: Session) -> List[OFPaquete]:
    # Eager-load para evitar N+1 en talla/color/pieza/fusiona/rechazos (cockpit y PDF).
    return (db.query(OFPaquete)
            .options(selectinload(OFPaquete.sku).selectinload(PrendaSku.prenda),
                     selectinload(OFPaquete.pieza),
                     selectinload(OFPaquete.rechazos).selectinload(OFPaqueteRechazo.motivo))
            .filter_by(of_id=of_id).order_by(OFPaquete.numero).all())


def avanzar_talla(of_id: int, sku_id: int, grupo: str, db: Session, usuario_id: int = None) -> int:
    """Avanza en lote los bultos de una talla. `grupo`:
    - 'fusion'          → HABILITADO fusibles  → FUSIONADO
    - 'calidad'         → HABILITADO no fusibles → POR_VALIDAR
    - 'todo'            → ambos
    - 'fusionado_listo' → FUSIONADO → POR_VALIDAR
    Devuelve cuántos bultos se movieron."""
    bultos = db.query(OFPaquete).filter_by(of_id=of_id, sku_id=sku_id).all()
    n = 0
    for p in bultos:
        if grupo in ("fusion", "todo") and p.estado == ESTADO_HABILITADO and p.fusiona:
            set_estado_paquete(p.id, ESTADO_FUSIONADO, db, usuario_id)
            n += 1
        elif grupo in ("calidad", "todo") and p.estado == ESTADO_HABILITADO and not p.fusiona:
            set_estado_paquete(p.id, ESTADO_POR_VALIDAR, db, usuario_id)
            n += 1
        elif grupo == "fusionado_listo" and p.estado == ESTADO_FUSIONADO:
            set_estado_paquete(p.id, ESTADO_POR_VALIDAR, db, usuario_id)
            n += 1
    return n


# Filtros de la cola de Calidad (transversal a todas las OFs activas)
COLA_FILTROS = {
    "pendientes":  [ESTADO_POR_VALIDAR, ESTADO_STANDBY],
    "por_validar": [ESTADO_POR_VALIDAR],
    "standby":     [ESTADO_STANDBY],
    "entregados":  [ESTADO_ENTREGADO],
}


def listar_cola_calidad(db: Session, filtro: str = "pendientes",
                        of_id: int = None) -> List[OFPaquete]:
    """Paquetes según el filtro de estado (cola del auditor). Si `of_id` se pasa,
    limita a esa OF; si no, cola transversal de todas las OFs activas."""
    estados = COLA_FILTROS.get(filtro, COLA_FILTROS["pendientes"])
    q = (db.query(OFPaquete)
         .join(OrdenFabricacion, OrdenFabricacion.id == OFPaquete.of_id)
         .filter(OrdenFabricacion.estado == EstadoOF.ACTIVA, OFPaquete.estado.in_(estados)))
    if of_id:
        q = q.filter(OFPaquete.of_id == of_id)
    return q.order_by(OrdenFabricacion.numero_of, OFPaquete.numero).all()


def aprobar_talla_calidad(of_id: int, sku_id: int, db: Session, usuario_id: int = None) -> int:
    """Aprueba (sin rechazos) todos los bultos POR_VALIDAR de una talla → ENTREGADO.
    Botón 'Aprobar toda la talla'. Hace TODO en una sola transacción: marca los
    bultos, chequea el cierre de OF una sola vez y un único commit (sin el N+1 de
    llamar a validar_paquete por bulto). Devuelve cuántos aprobó."""
    bultos = (db.query(OFPaquete)
              .filter_by(of_id=of_id, sku_id=sku_id, estado=ESTADO_POR_VALIDAR).all())
    if not bultos:
        return 0
    for p in bultos:
        p.estado = ESTADO_ENTREGADO
        db.add(OFPaqueteEvento(paquete_id=p.id, estado=ESTADO_ENTREGADO, usuario_id=usuario_id))
    db.flush()
    _marcar_of_si_completa(of_id, db)          # una sola vez, al final
    db.commit()
    return len(bultos)


def grupo_reproceso(r: OFPaqueteRechazo) -> str:
    """Etiqueta de agrupación de la bandeja = la ESTACIÓN actual de la pieza,
    para que cada operario vea solo lo que le toca ahora."""
    return estacion_de(r)


def _rechazos_en_bandeja(db: Session, of_id: int = None):
    """Rechazos accionables (pendiente / en reproceso) de OFs activas con destino con
    bandeja. Excluye 'esperando tela' (van a Planeamiento) y Modelista/Gerencia/Externo."""
    q = (db.query(OFPaqueteRechazo)
         .join(OFPaquete, OFPaquete.id == OFPaqueteRechazo.paquete_id)
         .join(OrdenFabricacion, OrdenFabricacion.id == OFPaquete.of_id)
         .filter(OrdenFabricacion.estado == EstadoOF.ACTIVA,
                 OFPaqueteRechazo.estado.in_(RECHAZOS_EN_PROCESO),
                 OFPaqueteRechazo.destino.in_(DESTINOS_CON_BANDEJA)))
    if of_id:
        q = q.filter(OFPaquete.of_id == of_id)
    return q.order_by(OrdenFabricacion.numero_of, OFPaquete.numero).all()


def listar_reprocesos(db: Session, of_id: int = None, area: str = None) -> List[OFPaqueteRechazo]:
    """Bandeja de las estaciones de corte: cada pieza aparece en su ESTACIÓN actual.
    El re-fusionado NO sale aquí (va al módulo de Fusionado). `area` filtra por estación."""
    out = []
    for r in _rechazos_en_bandeja(db, of_id):
        est = estacion_de(r)
        if est == ESTACION_FUSIONADO:     # el re-fusionado se hace en el módulo de Fusionado
            continue
        if area and est != area:
            continue
        out.append(r)
    return out


def listar_refusionado(db: Session, of_id: int = None) -> List[OFPaqueteRechazo]:
    """Piezas en la estación de Fusionado (reproceso), para su módulo."""
    return [r for r in _rechazos_en_bandeja(db, of_id) if estacion_de(r) == ESTACION_FUSIONADO]


def areas_reproceso(db: Session, of_id: int = None) -> list:
    """Estaciones con piezas en la bandeja ahora (para el filtro de la vista)."""
    vistas = []
    for r in listar_reprocesos(db, of_id):
        est = estacion_de(r)
        if est not in vistas:
            vistas.append(est)
    return vistas


def listar_reprocesos_of(of_id: int, db: Session) -> list:
    """Reprocesos ABIERTOS de una OF, para la vista de solo-lectura en la pantalla de la OF.
    Incluye estación actual, punto de reinicio y hora de inicio (trazabilidad)."""
    q = (db.query(OFPaqueteRechazo)
         .join(OFPaquete, OFPaquete.id == OFPaqueteRechazo.paquete_id)
         .filter(OFPaquete.of_id == of_id,
                 OFPaqueteRechazo.estado.in_(RECHAZOS_ABIERTOS))
         .order_by(OFPaquete.numero).all())
    out = []
    for r in q:
        p = r.paquete
        ini = r.hitos[0].at if r.hitos else None
        out.append({
            "id": r.id, "codigo": r.motivo.codigo if r.motivo else None,
            "descripcion": r.motivo.descripcion if r.motivo else None,
            "cantidad": r.cantidad, "estado": r.estado,
            "estacion": estacion_de(r), "reinicio": punto_reinicio(r),
            "rehacer": r.rehacer, "destino": r.destino,
            "pieza": p.pieza_nombre if p else None,
            "talla": p.talla if p else None,
            "numeracion": (f"{p.numero_desde}–{p.numero_hasta}" if p else None),
            "desde": ini.strftime("%d/%m %H:%M") if ini else None,
        })
    return out


def listar_rechazos_of(of_id: int, db: Session) -> List[OFPaqueteRechazo]:
    """TODOS los rechazos (reprocesos) de una OF, histórico completo — para el
    reporte PDF. Incluye abiertos y ya reingresados."""
    return (db.query(OFPaqueteRechazo)
            .join(OFPaquete, OFPaquete.id == OFPaqueteRechazo.paquete_id)
            .options(selectinload(OFPaqueteRechazo.motivo),
                     selectinload(OFPaqueteRechazo.paquete).selectinload(OFPaquete.sku),
                     selectinload(OFPaqueteRechazo.paquete).selectinload(OFPaquete.pieza))
            .filter(OFPaquete.of_id == of_id)
            .order_by(OFPaquete.numero).all())


def listar_espera_tela(db: Session) -> List[OFPaqueteRechazo]:
    """Piezas por rehacer detenidas por falta de tela (para el panel de Planeamiento)."""
    return (db.query(OFPaqueteRechazo)
            .join(OFPaquete, OFPaquete.id == OFPaqueteRechazo.paquete_id)
            .join(OrdenFabricacion, OrdenFabricacion.id == OFPaquete.of_id)
            .filter(OrdenFabricacion.estado == EstadoOF.ACTIVA,
                    OFPaqueteRechazo.estado == RECHAZO_ESPERA_TELA)
            .order_by(OrdenFabricacion.numero_of, OFPaquete.numero).all())


def listar_derivados(db: Session, of_id: int = None) -> List[OFPaqueteRechazo]:
    """Rechazos ABIERTOS derivados fuera de corte: Modelista, Gerencia, Externo."""
    derivados = (DEST_MODELISTA, DEST_GERENCIA, DEST_EXTERNO)
    q = (db.query(OFPaqueteRechazo)
         .join(OFPaquete, OFPaquete.id == OFPaqueteRechazo.paquete_id)
         .join(OrdenFabricacion, OrdenFabricacion.id == OFPaquete.of_id)
         .filter(OrdenFabricacion.estado == EstadoOF.ACTIVA,
                 OFPaqueteRechazo.estado.in_(RECHAZOS_ABIERTOS),
                 OFPaqueteRechazo.destino.in_(derivados)))
    if of_id:
        q = q.filter(OFPaquete.of_id == of_id)
    return q.order_by(OFPaqueteRechazo.destino, OrdenFabricacion.numero_of, OFPaquete.numero).all()


# --------------------------------------------------------------------------- #
# Aprobación del gerente de planta (defectos con destino Gerencia)
# --------------------------------------------------------------------------- #
def listar_gerencia(db: Session, of_id: int = None) -> List[OFPaqueteRechazo]:
    """Rechazos con destino Gerencia, pendientes de la decisión del gerente de planta."""
    q = (db.query(OFPaqueteRechazo)
         .join(OFPaquete, OFPaquete.id == OFPaqueteRechazo.paquete_id)
         .join(OrdenFabricacion, OrdenFabricacion.id == OFPaquete.of_id)
         .filter(OrdenFabricacion.estado == EstadoOF.ACTIVA,
                 OFPaqueteRechazo.estado.in_(RECHAZOS_ABIERTOS),
                 OFPaqueteRechazo.destino == DEST_GERENCIA))
    if of_id:
        q = q.filter(OFPaquete.of_id == of_id)
    return q.order_by(OrdenFabricacion.numero_of, OFPaquete.numero).all()


def aprobar_gerencia(rechazo_id: int, db: Session, usuario_id: int = None) -> OFPaqueteRechazo:
    """El gerente de planta aprueba: la pieza se libera tal cual y vuelve a Calidad para cierre."""
    r = _get_rechazo(rechazo_id, db)
    if r.destino != DEST_GERENCIA:
        raise HTTPException(400, "Este rechazo no está en aprobación de gerencia")
    if r.estado not in RECHAZOS_ABIERTOS:
        raise HTTPException(400, f"Estado inválido ({r.estado})")
    db.add(OFReprocesoHito(rechazo_id=r.id, etapa="APROBADO", usuario_id=usuario_id))
    _reingresar_a_calidad(r, db, usuario_id)
    db.commit()
    db.refresh(r)
    return r


def rehacer_gerencia(rechazo_id: int, db: Session, usuario_id: int = None) -> OFPaqueteRechazo:
    """El gerente de planta manda a rehacer: pasa a Corte por la ruta de rehacer (nunca se pierde la unidad)."""
    r = _get_rechazo(rechazo_id, db)
    if r.destino != DEST_GERENCIA:
        raise HTTPException(400, "Este rechazo no está en aprobación de gerencia")
    if r.estado not in RECHAZOS_ABIERTOS:
        raise HTTPException(400, f"Estado inválido ({r.estado})")
    r.destino = DEST_CORTE
    r.rehacer = True
    r.etapa = None
    r.estado = RECHAZO_PENDIENTE
    db.add(OFReprocesoHito(rechazo_id=r.id, etapa="A_REHACER", usuario_id=usuario_id))
    db.commit()
    db.refresh(r)
    return r


# --------------------------------------------------------------------------- #
# Dar OK (Modelista / Externo / Desmanchado: arreglan y devuelven)
# --------------------------------------------------------------------------- #
def listar_para_ok(db: Session, of_id: int = None) -> List[OFPaqueteRechazo]:
    """Piezas en Modelista / Externo / Desmanchado, esperando el OK para reingresar a Calidad."""
    q = (db.query(OFPaqueteRechazo)
         .join(OFPaquete, OFPaquete.id == OFPaqueteRechazo.paquete_id)
         .join(OrdenFabricacion, OrdenFabricacion.id == OFPaquete.of_id)
         .filter(OrdenFabricacion.estado == EstadoOF.ACTIVA,
                 OFPaqueteRechazo.estado.in_(RECHAZOS_ABIERTOS),
                 OFPaqueteRechazo.destino.in_(DESTINOS_OK)))
    if of_id:
        q = q.filter(OFPaquete.of_id == of_id)
    return q.order_by(OFPaqueteRechazo.destino, OrdenFabricacion.numero_of, OFPaquete.numero).all()


def dar_ok(rechazo_id: int, db: Session, usuario_id: int = None) -> OFPaqueteRechazo:
    """Marca la pieza como arreglada (Modelista/Externo/Desmanchado) → reingresa a Calidad."""
    r = _get_rechazo(rechazo_id, db)
    if r.destino not in DESTINOS_OK:
        raise HTTPException(400, "Este rechazo no se resuelve con OK")
    if r.estado not in RECHAZOS_ABIERTOS:
        raise HTTPException(400, f"Estado inválido ({r.estado})")
    db.add(OFReprocesoHito(rechazo_id=r.id, etapa=r.destino, usuario_id=usuario_id))
    _reingresar_a_calidad(r, db, usuario_id)
    db.commit()
    db.refresh(r)
    return r


def listar_motivos(db: Session, solo_activos: bool = True) -> List[MotivoRechazo]:
    q = db.query(MotivoRechazo)
    if solo_activos:
        q = q.filter(MotivoRechazo.activo == True)  # noqa: E712
    return q.order_by(MotivoRechazo.codigo).all()


def _get_paquete(paquete_id: int, db: Session) -> OFPaquete:
    p = db.query(OFPaquete).filter_by(id=paquete_id).first()
    if not p:
        raise HTTPException(404, "Paquete no encontrado")
    return p


def _get_rechazo(rechazo_id: int, db: Session) -> OFPaqueteRechazo:
    r = db.query(OFPaqueteRechazo).filter_by(id=rechazo_id).first()
    if not r:
        raise HTTPException(404, "Rechazo no encontrado")
    return r


def _rechazos_abiertos(paquete_id: int, db: Session) -> int:
    """Unidades con rechazo aún sin resolver (pendiente o en reproceso)."""
    total = db.query(func.coalesce(func.sum(OFPaqueteRechazo.cantidad), 0)).filter(
        OFPaqueteRechazo.paquete_id == paquete_id,
        OFPaqueteRechazo.estado.in_(RECHAZOS_ABIERTOS),
    ).scalar()
    return int(total or 0)


def _merma_material_paquete(paquete_id: int, db: Session) -> int:
    """Piezas viejas descartadas al rehacer (desperdicio de material). No baja el
    entregable — siempre se corta una nueva que la reemplaza."""
    total = db.query(func.coalesce(func.sum(OFPaqueteRechazo.cantidad), 0)).filter(
        OFPaqueteRechazo.paquete_id == paquete_id,
        OFPaqueteRechazo.rehacer == True,  # noqa: E712
    ).scalar()
    return int(total or 0)


def resumen_paquete(p: OFPaquete, db: Session) -> dict:
    """Aprobadas / en reproceso / merma-material / entregable de un paquete."""
    abiertos = _rechazos_abiertos(p.id, db)
    merma = _merma_material_paquete(p.id, db)
    return {
        "en_reproceso": abiertos,
        "merma": merma,                     # desperdicio de material (informativo)
        "aprobadas": p.cantidad - abiertos,
        "entregable": p.cantidad,           # siempre se completa (rehacer reemplaza)
    }


def corte_real(of_id: int, db: Session) -> int:
    """Corte real en PRENDAS. Como hay un bulto por pieza, las prendas de cada
    talla se cuentan una sola vez (por eso se deduplica por pieza)."""
    rows = (db.query(OFPaquete.sku_id, OFPaquete.pieza_id,
                     func.coalesce(func.sum(OFPaquete.cantidad), 0))
            .filter(OFPaquete.of_id == of_id)
            .group_by(OFPaquete.sku_id, OFPaquete.pieza_id).all())
    por_talla = {}
    for sku_id, _pieza_id, s in rows:
        por_talla[sku_id] = max(por_talla.get(sku_id, 0), int(s or 0))
    return sum(por_talla.values())


def resumen_calidad_por_talla(of_id: int, db: Session) -> dict:
    """Estado derivado de los paquetes por sku_id, para el cockpit.
    numeracion/habilitado = hay hoja; calidad = % entregado."""
    out = {}
    for p in listar_paquetes(of_id, db):
        d = out.setdefault(p.sku_id, {"total": 0, "entregado": 0,
                                      "fus_total": 0, "fus_ok": 0,
                                      "en_reproceso": 0, "merma": 0,
                                      "num_paq": 0, "num_paq_env": 0,
                                      "num_min": None, "num_max": None, "_desde": set(),
                                      "fus_paq": 0, "fus_paq_ok": 0, "fus_paq_ini": 0,
                                      "fus_inicio": None, "fus_fin": None})
        # rechazos ya vienen eager-loaded → cálculo en memoria (sin N+1)
        en_reproceso = sum(r.cantidad for r in p.rechazos if r.estado in RECHAZOS_ABIERTOS)
        merma = sum(r.cantidad for r in p.rechazos if r.rehacer)
        d["total"] += p.cantidad
        d["en_reproceso"] += en_reproceso
        d["merma"] += merma
        # Avance de numeración = bultos enviados (salieron de HABILITADO a Fusionado/Calidad)
        d["num_paq"] += 1
        if p.estado != ESTADO_HABILITADO:
            d["num_paq_env"] += 1
        d["num_min"] = p.numero_desde if d["num_min"] is None else min(d["num_min"], p.numero_desde)
        d["num_max"] = p.numero_hasta if d["num_max"] is None else max(d["num_max"], p.numero_hasta)
        d["_desde"].add(p.numero_desde)   # cada rango distinto = 1 paquete de numeración (por prenda)
        if p.fusiona:                                   # solo piezas fusibles
            d["fus_total"] += p.cantidad
            # Avance de fusionado = bultos terminados de fusionar (por bulto, como F4)
            d["fus_paq"] += 1
            if p.fusionado_inicio:                      # iniciado (en proceso o terminado)
                d["fus_paq_ini"] += 1
                if d["fus_inicio"] is None or p.fusionado_inicio < d["fus_inicio"]:
                    d["fus_inicio"] = p.fusionado_inicio
            if p.estado in ESTADOS_POST_FUSIONADO:      # terminado
                d["fus_ok"] += p.cantidad
                d["fus_paq_ok"] += 1
                if p.fusionado_fin and (d["fus_fin"] is None or p.fusionado_fin > d["fus_fin"]):
                    d["fus_fin"] = p.fusionado_fin
        if p.estado == ESTADO_ENTREGADO:
            d["entregado"] += p.cantidad
    for d in out.values():
        tot = d["total"]
        np_, npe = d["num_paq"], d["num_paq_env"]
        fp, fpo = d["fus_paq"], d["fus_paq_ok"]
        d["paq_prenda"] = len(d.pop("_desde"))          # paquetes de numeración (por prenda) de la talla
        d["numeracion"] = tot > 0                       # hay hoja
        d["numeracion_pct"] = round(npe / np_ * 100) if np_ else 0
        d["numeracion_done"] = np_ > 0 and npe == np_
        d["fusionado_pct"] = (round(fpo / fp * 100) if fp else 100) if tot else 0
        d["fusionado_done"] = tot > 0 and (fp == 0 or fpo == fp)
        d["fusionado_iniciado"] = d["fus_paq_ini"] > 0
        d["calidad_pct"] = round(d["entregado"] / tot * 100) if tot else 0
        d["calidad_done"] = tot > 0 and d["entregado"] == tot
        # F7 "Liberado" = tras el OK de Calidad (= entregado)
        d["liberado_pct"] = d["calidad_pct"]
        d["liberado_done"] = d["calidad_done"]
    return out


def resumen_calidad_of(of_id: int, db: Session, porsku: dict = None) -> dict:
    """Agregado de la OF para la franja del cockpit (F4/F5/F6/F7 derivados).
    `porsku` opcional: si ya se calculó `resumen_calidad_por_talla`, se pasa para
    no recalcularlo (evita duplicar el escaneo de paquetes)."""
    porsku = porsku if porsku is not None else resumen_calidad_por_talla(of_id, db)
    total = sum(d["total"] for d in porsku.values())
    entregado = sum(d["entregado"] for d in porsku.values())
    en_reproceso = sum(d["en_reproceso"] for d in porsku.values())
    num_paq = sum(d["num_paq"] for d in porsku.values())
    num_paq_env = sum(d["num_paq_env"] for d in porsku.values())
    fus_paq = sum(d["fus_paq"] for d in porsku.values())
    fus_paq_ok = sum(d["fus_paq_ok"] for d in porsku.values())
    fus_paq_ini = sum(d["fus_paq_ini"] for d in porsku.values())
    fus_inicios = [d["fus_inicio"] for d in porsku.values() if d["fus_inicio"]]
    fus_fines = [d["fus_fin"] for d in porsku.values() if d["fus_fin"]]
    fus_done = total > 0 and (fus_paq == 0 or fus_paq_ok == fus_paq)
    return {
        "hay_hoja": total > 0,
        "total": total,
        "entregado": entregado,
        "en_reproceso": en_reproceso,
        "numeracion_pct": (round(num_paq_env / num_paq * 100) if num_paq else 0),
        "numeracion_done": num_paq > 0 and num_paq_env == num_paq,
        "fusionado_pct": (round(fus_paq_ok / fus_paq * 100) if fus_paq else 100) if total else 0,
        "fusionado_done": fus_done,
        "fusionado_iniciado": fus_paq_ini > 0,
        "fusionado_inicio": min(fus_inicios) if fus_inicios else None,
        "fusionado_fin": (max(fus_fines) if (fus_done and fus_fines) else None),
        "calidad_pct": round(entregado / total * 100) if total else 0,
        "calidad_done": total > 0 and entregado == total,
        "liberado_pct": round(entregado / total * 100) if total else 0,
        "liberado_done": total > 0 and entregado == total,
    }


def merma_of(of_id: int, db: Session) -> int:
    """Merma de MATERIAL: piezas viejas descartadas al rehacer (desperdicio de tela).
    No baja el entregable — cada una se reemplaza con una nueva."""
    total = (db.query(func.coalesce(func.sum(OFPaqueteRechazo.cantidad), 0))
             .join(OFPaquete, OFPaquete.id == OFPaqueteRechazo.paquete_id)
             .filter(OFPaquete.of_id == of_id, OFPaqueteRechazo.rehacer == True)  # noqa: E712
             .scalar())
    return int(total or 0)


def rehacer_of(of_id: int, db: Session) -> int:
    """Piezas marcadas 'rehacer' aún abiertas (cortan tela nueva → aviso a Planeamiento)."""
    total = (db.query(func.coalesce(func.sum(OFPaqueteRechazo.cantidad), 0))
             .join(OFPaquete, OFPaquete.id == OFPaqueteRechazo.paquete_id)
             .filter(OFPaquete.of_id == of_id,
                     OFPaqueteRechazo.rehacer == True,  # noqa: E712
                     OFPaqueteRechazo.estado.in_(RECHAZOS_ABIERTOS))
             .scalar())
    return int(total or 0)


def espera_tela_of(of_id: int, db: Session) -> int:
    """Piezas por rehacer que esperan tela (SOLPED/rollo en SAP)."""
    total = (db.query(func.coalesce(func.sum(OFPaqueteRechazo.cantidad), 0))
             .join(OFPaquete, OFPaquete.id == OFPaqueteRechazo.paquete_id)
             .filter(OFPaquete.of_id == of_id, OFPaqueteRechazo.estado == RECHAZO_ESPERA_TELA)
             .scalar())
    return int(total or 0)


def _proyectado(of: OrdenFabricacion, db: Session) -> int:
    curva = db.query(func.coalesce(func.sum(OFTallaDistribucion.cantidad), 0)).filter(
        OFTallaDistribucion.of_id == of.id).scalar()
    return int(curva or of.total_juegos or 0)


def resumen_desvio(of: OrdenFabricacion, db: Session) -> dict:
    """Proyectado vs corte real + desvío + merma + entregable."""
    proy = _proyectado(of, db)
    real = corte_real(of.id, db)
    merma = merma_of(of.id, db)
    rehacer = rehacer_of(of.id, db)
    desvio = real - proy
    return {
        "proyectado": proy,
        "real": real,
        "merma": merma,                     # desperdicio de material (informativo, no baja entregable)
        "rehacer": rehacer,                 # piezas a rehacer → tela adicional (avisar a Planeamiento)
        "espera_tela": espera_tela_of(of.id, db),   # rehacer detenido por falta de tela (SOLPED en SAP)
        "entregable": real,                 # siempre se completa (rehacer reemplaza)
        "desvio": desvio,
        "desvio_pct": round(desvio / proy * 100, 1) if proy else None,
        "estado": "ok" if desvio == 0 else ("sobrante" if desvio > 0 else "faltante"),
    }
