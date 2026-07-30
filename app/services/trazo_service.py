"""
Servicio de trazos / placas (Fase A — fases de tela F1–F3), alineado al Excel.

Cada trazo es una PLACA (dibujo/marker):
  - prendas por talla = capas × veces (veces que la talla entra en el dibujo)
  - metros tendidos    = capas × largo del tizado
El tope de capas por placa sale de la OF (max_capas) o del default global.
Aditivo: no toca el motor de corte por pieza.
"""
from datetime import datetime
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.of import OrdenFabricacion, OFTallaDistribucion
from app.models.catalogo import PrendaSku, CatalogoMp, PrendaCatalogo
from app.models.fase import OFFaseTiempos, OFFaseEstado
from app.models.trazo import (
    OFTrazo, OFTrazoTalla, OFTrazoMovimiento,
    ESTADO_HECHO, ESTADO_EN_CURSO, ESTADO_PENDIENTE, MOV_TENDIDO, MOV_CORTE,
)
from app.constants import MAX_CAPAS_DEFAULT, NOMBRES_FASE

# Fase de tela → fase_id de OFFaseTiempos (la franja de la OF)
FASE_TELA = {"tizado": "F1", "tendido": "F2", "corte": "F3"}
ORDEN_TELA = ["tizado", "tendido", "corte"]


def _fmt(dt):
    return dt.strftime("%d/%m %H:%M") if dt else None


def fases_tela_info(of_id: int, db: Session) -> list[dict]:
    """Estado y tiempos (inicio/fin real) de F1–F3 desde OFFaseTiempos."""
    res, prev_iniciada = [], True
    for ft in ORDEN_TELA:
        fase_id = FASE_TELA[ft]
        row = db.query(OFFaseTiempos).filter_by(of_id=of_id, fase_id=fase_id).first()
        inicio = row.inicio_real if row else None
        fin = row.fin_real if row else None
        estado = "hecho" if fin else ("en_curso" if inicio else "pendiente")
        res.append({
            "fase": ft, "fase_id": fase_id, "nombre": NOMBRES_FASE.get(fase_id, ft.title()),
            "inicio": _fmt(inicio), "fin": _fmt(fin), "estado": estado,
            "habilitada": inicio is None and prev_iniciada,
        })
        prev_iniciada = inicio is not None
    return res


def iniciar_fase_tela(of_id: int, fase_tela: str, db: Session) -> OFFaseTiempos:
    """Marca el inicio_real de una fase de tela (clic del supervisor)."""
    if fase_tela not in FASE_TELA:
        raise HTTPException(400, "Fase de tela inválida")
    fase_id = FASE_TELA[fase_tela]
    idx = ORDEN_TELA.index(fase_tela)
    if idx > 0:
        prev_id = FASE_TELA[ORDEN_TELA[idx - 1]]
        prev = db.query(OFFaseTiempos).filter_by(of_id=of_id, fase_id=prev_id).first()
        if not (prev and prev.inicio_real):
            raise HTTPException(400, f"Primero inicia {ORDEN_TELA[idx - 1]}")
    ft = db.query(OFFaseTiempos).filter_by(of_id=of_id, fase_id=fase_id).first()
    if not ft:
        ft = OFFaseTiempos(of_id=of_id, fase_id=fase_id)
        db.add(ft)
    if ft.inicio_real is None:
        ft.inicio_real = datetime.now()
        db.commit()
    return ft


def _stamp_fin_if_complete(of_id: int, fase_tela: str, db: Session) -> None:
    """Marca fin_real de la fase (F1/F2/F3) en OFFaseTiempos cuando TODAS las placas
    terminaron esa fase y el pedido está cubierto. El inicio lo pone el clic en la franja."""
    fase_id = FASE_TELA[fase_tela]
    trazos = db.query(OFTrazo).filter_by(of_id=of_id).all()
    if not trazos:
        return
    attr = "estado_" + fase_tela
    if not all(getattr(tz, attr) == ESTADO_HECHO for tz in trazos):
        return
    if not validar_cobertura(of_id, db)["cubierto"]:
        return
    ft = db.query(OFFaseTiempos).filter_by(of_id=of_id, fase_id=fase_id).first()
    if not ft:
        ft = OFFaseTiempos(of_id=of_id, fase_id=fase_id)
        db.add(ft)
    if ft.fin_real is None:
        ft.fin_real = datetime.now()
        # Sincronizar la grilla por pieza: la tela (F1–F3) se gestiona por placas,
        # así que al cerrarse la fase se marcan completadas sus filas por pieza.
        for e in db.query(OFFaseEstado).filter_by(of_id=of_id, fase_id=fase_id).all():
            e.cantidad_actual = e.max_cantidad
            e.completada = True
            if e.fecha_completado is None:
                e.fecha_completado = datetime.now()
        db.commit()


def max_capas_of(of: OrdenFabricacion) -> int:
    """Tope de capas por placa para la OF (override o default global)."""
    return of.max_capas if getattr(of, "max_capas", None) else MAX_CAPAS_DEFAULT


def meta_por_sku(of_id: int, db: Session) -> dict:
    """Meta de prendas por SKU (talla), desde la distribución/curva.
    {sku_id: {"talla": str, "meta": int}}"""
    filas = (
        db.query(OFTallaDistribucion, PrendaSku)
        .join(PrendaSku, PrendaSku.id == OFTallaDistribucion.sku_id)
        .filter(OFTallaDistribucion.of_id == of_id)
        .all()
    )
    return {d.sku_id: {"talla": s.talla, "meta": d.cantidad or 0} for d, s in filas}


def validar_cobertura(of_id: int, db: Session) -> dict:
    """Compara lo asignado en las placas contra la curva, por talla."""
    metas = meta_por_sku(of_id, db)
    asignado: dict[int, int] = {}
    for tz in db.query(OFTrazo).filter_by(of_id=of_id).all():
        for t in tz.tallas:
            asignado[t.sku_id] = asignado.get(t.sku_id, 0) + (t.cantidad or 0)

    por_talla, todo_ok = [], True
    for sku_id, info in metas.items():
        asig = asignado.get(sku_id, 0)
        ok = asig == info["meta"]
        todo_ok = todo_ok and ok
        por_talla.append({
            "sku_id": sku_id, "talla": info["talla"], "meta": info["meta"],
            "asignado": asig, "restante": info["meta"] - asig, "ok": ok,
        })
    if any(sid not in metas for sid in asignado):
        todo_ok = False

    total_meta = sum(i["meta"] for i in metas.values())
    return {
        "cubierto": todo_ok and total_meta > 0,
        "por_talla": sorted(por_talla, key=lambda x: x["talla"]),
        "total_meta": total_meta,
        "total_asignado": sum(asignado.values()),
    }


def consumo_proyectado(of: OrdenFabricacion, db: Session):
    """Consumo de tela por prenda (m) desde el catálogo. None si no hay.
    Busca la tela (tipo TELA%) en la prenda de la OF; si es una variante y no la
    tiene propia, cae a la prenda BASE (las variantes heredan la MP de la base)."""
    if not of.prenda_catalogo_id:
        return None

    def _tela_de(prenda_id):
        mp = (
            db.query(CatalogoMp)
            .filter(CatalogoMp.prenda_catalogo_id == prenda_id)
            .filter(CatalogoMp.tipo.like("TELA%"))
            .first()
        )
        return mp.consumo_unitario if (mp and mp.consumo_unitario) else None

    val = _tela_de(of.prenda_catalogo_id)
    if val is None:
        prenda = db.query(PrendaCatalogo).filter_by(id=of.prenda_catalogo_id).first()
        if prenda and prenda.tipo_cliente != "BASE":
            base = (
                db.query(PrendaCatalogo)
                .filter_by(tipo_base=prenda.tipo_base, tipo_cliente="BASE", activo=True)
                .first()
            )
            if base:
                val = _tela_de(base.id)
    return round(val, 3) if val else None


def resumen_consumo(of_id: int, db: Session) -> dict:
    """Consumo proyectado (HDC) vs real ponderado (Σ metros ÷ Σ prendas)."""
    of = db.query(OrdenFabricacion).filter_by(id=of_id).first()
    trazos = db.query(OFTrazo).filter_by(of_id=of_id).all()
    metros = sum((tz.metraje or 0) for tz in trazos)
    prendas = sum(tz.total_prendas for tz in trazos)
    real = round(metros / prendas, 3) if prendas else None
    proy = consumo_proyectado(of, db) if of else None
    desvio = round(real - proy, 3) if (real is not None and proy) else None
    return {
        "proyectado": proy, "real": real, "metros": round(metros, 1),
        "prendas": prendas, "desvio": desvio,
        "desvio_pct": round(desvio / proy * 100, 1) if (desvio is not None and proy) else None,
    }


def crear_trazo(of_id: int, nombre, largo, capas, tallas: list[dict], db: Session) -> OFTrazo:
    """Crea una placa. `tallas` = [{"sku_id": int, "veces": int}].
    Deriva cantidad = capas × veces. Valida el tope de capas."""
    of = db.query(OrdenFabricacion).filter_by(id=of_id).first()
    if not of:
        raise HTTPException(404, "OF no encontrada")
    metas = meta_por_sku(of_id, db)
    if not metas:
        raise HTTPException(400, "La OF no tiene distribución de tallas (curva). Vincula la curva primero.")
    if not capas or capas <= 0:
        raise HTTPException(400, "Las capas deben ser mayor a 0")
    tope = max_capas_of(of)
    if capas > tope:
        raise HTTPException(400, f"Las capas ({capas}) superan el tope de la máquina ({tope})")

    # No exceder el pedido por talla: capas × veces ≤ restante de cada talla
    asignado = {}
    for tz in db.query(OFTrazo).filter_by(of_id=of_id).all():
        for t in tz.tallas:
            asignado[t.sku_id] = asignado.get(t.sku_id, 0) + (t.cantidad or 0)
    for t in (tallas or []):
        sku_id = t.get("sku_id")
        veces = int(t.get("veces") or 0)
        if veces <= 0:
            continue
        if sku_id not in metas:
            raise HTTPException(400, f"La talla (sku {sku_id}) no pertenece a la curva de esta OF")
        nueva = capas * veces
        restante = metas[sku_id]["meta"] - asignado.get(sku_id, 0)
        if nueva > restante:
            raise HTTPException(
                400,
                f"Talla {metas[sku_id]['talla']}: {nueva} prendas supera lo que falta "
                f"({restante}). No puedes exceder el pedido.",
            )

    n = db.query(OFTrazo).filter_by(of_id=of_id).count()
    trazo = OFTrazo(
        of_id=of_id, nombre=nombre or f"Placa {n + 1}",
        largo=largo, capas=capas,
        estado_tizado=ESTADO_HECHO if largo else ESTADO_PENDIENTE,
        orden=n,
    )
    db.add(trazo)
    db.flush()

    for i, t in enumerate(tallas or []):
        sku_id = t.get("sku_id")
        veces = int(t.get("veces") or 0)
        if veces <= 0:
            continue
        if sku_id not in metas:
            raise HTTPException(400, f"La talla (sku {sku_id}) no pertenece a la curva de esta OF")
        db.add(OFTrazoTalla(
            trazo_id=trazo.id, sku_id=sku_id, talla=metas[sku_id]["talla"],
            veces=veces, cantidad=capas * veces, orden=i,
        ))

    db.commit()
    db.refresh(trazo)
    _stamp_fin_if_complete(of_id, "tizado", db)
    return trazo


def eliminar_trazo(trazo_id: int, db: Session) -> None:
    tz = db.query(OFTrazo).filter_by(id=trazo_id).first()
    if not tz:
        raise HTTPException(404, "Placa no encontrada")
    db.delete(tz)
    db.commit()


def registrar_tendido(trazo_id: int, capas: int, db: Session, usuario_id: int = None) -> OFTrazo:
    """Registra tendido, admitiendo carga por PARTES.

    `capas` = capas tendidas EN ESTA SESIÓN (se acumulan sobre lo ya tendido).
    - None/vacío → completar el resto (marca el total planeado como tendido).
    - Se valida no exceder lo planeado (tz.capas).
    - estado_tendido: PENDIENTE → EN_CURSO (parcial) → HECHO (cuando se cubre el plan).
    - Registra un movimiento (auditoría) con las capas de la sesión y el usuario.
    """
    tz = db.query(OFTrazo).filter_by(id=trazo_id).first()
    if not tz:
        raise HTTPException(404, "Placa no encontrada")

    planeado = tz.capas or 0
    ya = tz.capas_tendidas or 0
    restante = max(0, planeado - ya)

    if capas is None:
        # Completar lo que falte de una vez
        tz.capas_tendidas = planeado
    else:
        if capas <= 0:
            raise HTTPException(400, "Las capas de esta sesión deben ser mayor a 0")
        if capas > restante:
            raise HTTPException(
                400,
                f"Excede lo planeado: ya tendidas {ya} de {planeado} (restante {restante})",
            )
        tz.capas_tendidas = ya + capas

    delta = tz.capas_tendidas - ya   # capas realmente agregadas en esta sesión
    if planeado > 0 and tz.capas_tendidas >= planeado:
        tz.estado_tendido = ESTADO_HECHO
        if tz.estado_corte == ESTADO_PENDIENTE:
            tz.estado_corte = ESTADO_EN_CURSO
    elif tz.capas_tendidas > 0:
        tz.estado_tendido = ESTADO_EN_CURSO

    if delta > 0:
        db.add(OFTrazoMovimiento(
            trazo_id=tz.id, tipo=MOV_TENDIDO, capas=delta,
            acumulado=tz.capas_tendidas, usuario_id=usuario_id,
        ))

    db.commit()
    db.refresh(tz)
    if tz.estado_tendido == ESTADO_HECHO:
        _stamp_fin_if_complete(tz.of_id, "tendido", db)
    return tz


def marcar_corte(trazo_id: int, capas: int, db: Session, usuario_id: int = None) -> OFTrazo:
    """Registra corte, admitiendo carga por PARTES (por si hay paradas).

    `capas` = capas cortadas EN ESTA SESIÓN (se acumulan).
    - None/vacío → completar el resto (marca todo lo planeado como cortado).
    - Requiere tendido HECHO. No se puede exceder lo planeado.
    - estado_corte: PENDIENTE/EN_CURSO → EN_CURSO (parcial) → HECHO (cubre el plan).
    - Registra un movimiento (auditoría) con las capas de la sesión y el usuario.
    """
    tz = db.query(OFTrazo).filter_by(id=trazo_id).first()
    if not tz:
        raise HTTPException(404, "Placa no encontrada")
    if tz.estado_tendido != ESTADO_HECHO:
        raise HTTPException(400, "No se puede cortar una placa sin tendido completo")

    planeado = tz.capas or 0
    ya = tz.capas_cortadas or 0
    restante = max(0, planeado - ya)

    if capas is None:
        tz.capas_cortadas = planeado
    else:
        if capas <= 0:
            raise HTTPException(400, "Las capas de esta sesión deben ser mayor a 0")
        if capas > restante:
            raise HTTPException(
                400,
                f"Excede lo planeado: ya cortadas {ya} de {planeado} (restante {restante})",
            )
        tz.capas_cortadas = ya + capas

    delta = tz.capas_cortadas - ya
    if planeado > 0 and tz.capas_cortadas >= planeado:
        tz.estado_corte = ESTADO_HECHO
    elif tz.capas_cortadas > 0:
        tz.estado_corte = ESTADO_EN_CURSO

    if delta > 0:
        db.add(OFTrazoMovimiento(
            trazo_id=tz.id, tipo=MOV_CORTE, capas=delta,
            acumulado=tz.capas_cortadas, usuario_id=usuario_id,
        ))

    db.commit()
    db.refresh(tz)
    if tz.estado_corte == ESTADO_HECHO:
        _stamp_fin_if_complete(tz.of_id, "corte", db)
    return tz


def set_max_capas(of_id: int, max_capas, db: Session) -> int:
    of = db.query(OrdenFabricacion).filter_by(id=of_id).first()
    if not of:
        raise HTTPException(404, "OF no encontrada")
    if max_capas is not None and max_capas <= 0:
        raise HTTPException(400, "El tope de capas debe ser mayor a 0")
    of.max_capas = max_capas
    db.commit()
    return max_capas_of(of)


def listar_trazos(of_id: int, db: Session) -> list[OFTrazo]:
    return db.query(OFTrazo).filter_by(of_id=of_id).order_by(OFTrazo.orden).all()
