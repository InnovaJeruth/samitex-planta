"""
Router: Hoja de Costos
Prefijo: /catalogo  (se monta junto al router de catálogo)
Endpoints bajo /catalogo/api/{prenda_id}/hoja-costos/...

Flujo:
  - GET  prefill  → devuelve líneas pre-llenadas desde la prenda BASE (sin guardar)
  - GET  /        → devuelve la hoja guardada (última) o 404
  - POST /        → crea o reemplaza la hoja en BORRADOR
  - POST aprobar  → cambia estado a APROBADA (solo INGENIERIA / ADMIN)
  - GET  export   → genera PDF de la hoja aprobada (próxima fase)
"""
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel as _PBase
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.core.auth import get_current_user
from app.models.usuario import Usuario
from app.models.catalogo import (
    PrendaCatalogo,
    CatalogoMp, PrendaMpConfig,
    CatalogoAvio, PrendaAvioConfig,
    HojaCostos, HojaCostosLinea,
    PrecioHistorico,
    ESTADOS_HOJA_COSTOS,
)

router = APIRouter()

from app.roles import (ROLES_EDITOR_HDC as ROLES_EDITOR,
                       ROLES_APROBAR_HDC as ROLES_APROBAR, ROLES_TC)


def _rol(u: Usuario) -> str:
    return u.rol.value if hasattr(u.rol, "value") else str(u.rol)


# ── Schemas ───────────────────────────────────────────────────

class LineaIn(_PBase):
    tipo:             str            # MP | AVIO
    item_id:          int
    seccion:          Optional[str]  = None
    nombre:           str
    unidad_medida:    Optional[str]  = None
    unidad_compra:    Optional[str]  = None
    factor_conversion: float         = 1.0
    consumo_unitario: float          = 1.0
    pct_adicional:    float          = 0.0
    precio_snapshot:  Optional[float] = None
    moneda:           Optional[str]  = None
    notas:            Optional[str]  = None
    orden:            int            = 0


class HojaIn(_PBase):
    moneda_base: str           = "SO"
    tipo_cambio: Optional[float] = None   # si no viene, se usa el TC del día (tc_hoy)
    notas:       Optional[str] = None
    lineas:      List[LineaIn] = []


# ── Helpers ───────────────────────────────────────────────────

def _get_prenda(prenda_id: int, db: Session) -> PrendaCatalogo:
    p = db.query(PrendaCatalogo).filter_by(id=prenda_id).first()
    if not p:
        raise HTTPException(404, "Prenda no encontrada")
    return p


def _hoja_dict(h: HojaCostos) -> dict:
    return {
        "id":          h.id,
        "version":     getattr(h, 'version', 1) or 1,
        "estado":      h.estado,
        "moneda_base": h.moneda_base,
        "tipo_cambio": h.tipo_cambio,
        "notas":       h.notas,
        "total_mp":    h.total_mp,
        "total_avios": h.total_avios,
        "total_general": h.total_general,
        "aprobado_at": h.aprobado_at.isoformat() if h.aprobado_at else None,
        "aprobado_por": h.aprobado_por.nombre if h.aprobado_por else None,
        "created_at":  h.created_at.isoformat() if h.created_at else None,
        "updated_at":  h.updated_at.isoformat() if h.updated_at else None,
        "lineas": [
            {
                "id":               l.id,
                "tipo":             l.tipo,
                "item_id":          l.item_id,
                "seccion":          l.seccion,
                "nombre":           l.nombre,
                "unidad_medida":    l.unidad_medida,
                "unidad_compra":    l.unidad_compra,
                "factor_conversion": l.factor_conversion,
                "consumo_unitario": l.consumo_unitario,
                "pct_adicional":    l.pct_adicional,
                "precio_snapshot":  l.precio_snapshot,
                "moneda":           l.moneda,
                "subtotal":         l.subtotal,
                "editado_manual":   l.editado_manual,
                "notas":            l.notas,
                "orden":            l.orden,
            }
            for l in h.lineas
        ],
    }


def _calcular_subtotal(
    consumo: float,
    pct: float,
    precio: Optional[float],
    factor_conversion: float = 1.0,
    moneda: Optional[str] = None,
    tipo_cambio: float = 3.45,
) -> Optional[float]:
    """subtotal en soles = consumo × (1+pct) / factor_conversion × precio_SO_por_UC"""
    if precio is None:
        return None
    factor = max(factor_conversion, 0.000001)
    precio_so = precio * tipo_cambio if (moneda and moneda != 'SO') else precio
    return round(consumo * (1 + pct) / factor * precio_so, 4)


# Parámetros de costeo (del HDC; ajustables luego)
TC_HDC       = 3.45     # tipo de cambio USD→S/ (FALLBACK si Logística no cargó el del día)
GIF_PCT      = 0.124    # gastos indirectos de fabricación (% sobre costo primo)
MARGEN_CV    = 0.90     # el costo de producción es 90% → precio = costo / 0.90

TC_PARAM_KEY = "TC_USD_PEN"   # clave del parámetro editable por Logística


def tc_hoy(db) -> float:
    """Tipo de cambio USD→S/ vigente: lo carga Logística por día (parámetro del
    sistema). Si no hay valor, cae al fallback TC_HDC. Solo aplica a hojas NUEVAS;
    las ya guardadas conservan su propio `tipo_cambio`."""
    from app.models.parametro import ParametroSistema
    try:
        return float(ParametroSistema.get(db, TC_PARAM_KEY, TC_HDC))
    except (TypeError, ValueError):
        return TC_HDC


def _costo_full(prenda, total_mp, total_avios, tc=TC_HDC):
    """Completa el costo estimado: insumos + servicios + MOD + GIF + margen.
    Servicios y MOD vienen del HDC en USD → se pasan a soles con `tc`."""
    total_serv = round(sum((s.costo or 0) for s in prenda.servicios_efectivos) * tc, 2)
    total_mod  = round(sum((m.subtotal or 0) for m in prenda.mod_efectivos) * tc, 2)
    costo_primo = round((total_mp or 0) + (total_avios or 0) + total_serv + total_mod, 2)
    gif = round(costo_primo * GIF_PCT, 2)
    costo_prod = round(costo_primo + gif, 2)
    total = round(costo_prod / MARGEN_CV, 2) if MARGEN_CV else costo_prod
    return {
        "total_servicios":  total_serv,
        "total_mod":        total_mod,
        "costo_primo":      costo_primo,
        "gif":              gif,
        "gif_pct":          GIF_PCT,
        "costo_produccion": costo_prod,
        "margen_cv":        MARGEN_CV,
        "total_general":    total,
    }


def _build_prefill_desde_base(prenda: PrendaCatalogo, db: Session) -> dict:
    """Construye las líneas pre-llenadas desde la prenda BASE.
    Para variantes aplica overrides (consumo_override, excluido).
    Para BASE usa sus propios MP y avíos directamente."""

    if prenda.tipo_cliente == "BASE":
        base = prenda
        mp_configs   = {}
        avio_configs = {}
    else:
        base = prenda.base or (
            db.query(PrendaCatalogo)
            .filter_by(tipo_base=prenda.tipo_base, tipo_cliente="BASE", activo=True)
            .first()
        )
        if not base:
            return {"lineas": [], "aviso": "No hay prenda BASE definida para este tipo."}
        mp_configs   = {c.mp_id:   c for c in prenda.mp_configs}
        avio_configs = {c.avio_id: c for c in prenda.avio_configs}

    tc = tc_hoy(db)            # TC del día (Logística) → prefill de hoja NUEVA
    lineas = []
    orden  = 0

    # ── MP ────────────────────────────────────────────────────
    for mp in sorted(base.materiales, key=lambda m: m.orden):
        if not mp.activo:
            continue
        cfg     = mp_configs.get(mp.id)
        excluir = cfg.excluido if cfg else False
        if excluir:
            continue
        consumo  = cfg.consumo_override if (cfg and cfg.consumo_override) else mp.consumo_unitario
        precio   = mp.precio_referencia
        fc       = getattr(mp, 'factor_conversion', 1.0) or 1.0
        subtotal = _calcular_subtotal(consumo, mp.pct_adicional, precio, fc, mp.moneda, tc)
        lineas.append({
            "tipo":             "MP",
            "item_id":          mp.id,
            "seccion":          mp.tipo,
            "nombre":           mp.nombre,
            "unidad_medida":    mp.unidad_medida,
            "unidad_compra":    getattr(mp, 'unidad_compra', None),
            "factor_conversion": fc,
            "consumo_unitario": consumo,
            "pct_adicional":    mp.pct_adicional,
            "precio_snapshot":  precio,
            "moneda":           mp.moneda,
            "subtotal":         subtotal,
            "editado_manual":   False,
            "notas":            None,
            "orden":            orden,
        })
        orden += 1

    # ── MP específicos de variante ────────────────────────────
    if prenda.tipo_cliente != "BASE":
        for mp in sorted(prenda.materiales, key=lambda m: m.orden):
            if not mp.activo:
                continue
            fc       = getattr(mp, 'factor_conversion', 1.0) or 1.0
            precio   = mp.precio_referencia
            subtotal = _calcular_subtotal(mp.consumo_unitario, mp.pct_adicional, precio, fc, mp.moneda, tc)
            lineas.append({
                "tipo":              "MP",
                "item_id":           mp.id,
                "seccion":           mp.tipo,
                "nombre":            mp.nombre,
                "unidad_medida":     mp.unidad_medida,
                "unidad_compra":     getattr(mp, 'unidad_compra', None),
                "factor_conversion": fc,
                "consumo_unitario":  mp.consumo_unitario,
                "pct_adicional":     mp.pct_adicional,
                "precio_snapshot":   precio,
                "moneda":            mp.moneda,
                "subtotal":          subtotal,
                "editado_manual":    False,
                "notas":             None,
                "orden":             orden,
            })
            orden += 1

    # ── Avíos ─────────────────────────────────────────────────
    for avio in sorted(base.avios, key=lambda a: (a.seccion, a.orden)):
        if not avio.activo:
            continue
        cfg     = avio_configs.get(avio.id)
        excluir = cfg.excluido if cfg else False
        if excluir:
            continue
        consumo  = cfg.consumo_override if (cfg and cfg.consumo_override) else avio.consumo_unitario
        precio   = avio.precio
        fc       = getattr(avio, 'factor_conversion', 1.0) or 1.0
        subtotal = _calcular_subtotal(consumo, avio.pct_adicional, precio, fc, avio.moneda, tc)
        lineas.append({
            "tipo":             "AVIO",
            "item_id":          avio.id,
            "seccion":          avio.seccion,
            "nombre":           avio.nombre,
            "unidad_medida":    avio.unidad_medida,
            "unidad_compra":    getattr(avio, 'unidad_compra', None),
            "factor_conversion": fc,
            "consumo_unitario": consumo,
            "pct_adicional":    avio.pct_adicional,
            "precio_snapshot":  precio,
            "moneda":           avio.moneda,
            "subtotal":         subtotal,
            "editado_manual":   False,
            "notas":            None,
            "orden":            orden,
        })
        orden += 1

    # ── Avíos específicos de variante ─────────────────────────
    if prenda.tipo_cliente != "BASE":
        for avio in sorted(prenda.avios, key=lambda a: (a.seccion, a.orden)):
            if not avio.activo:
                continue
            fc       = getattr(avio, 'factor_conversion', 1.0) or 1.0
            precio   = avio.precio
            subtotal = _calcular_subtotal(avio.consumo_unitario, avio.pct_adicional, precio, fc, avio.moneda, tc)
            lineas.append({
                "tipo":              "AVIO",
                "item_id":           avio.id,
                "seccion":           avio.seccion,
                "nombre":            avio.nombre,
                "unidad_medida":     avio.unidad_medida,
                "unidad_compra":     getattr(avio, 'unidad_compra', None),
                "factor_conversion": fc,
                "consumo_unitario":  avio.consumo_unitario,
                "pct_adicional":     avio.pct_adicional,
                "precio_snapshot":   precio,
                "moneda":            avio.moneda,
                "subtotal":          subtotal,
                "editado_manual":    False,
                "notas":             None,
                "orden":             orden,
            })
            orden += 1

    total_mp    = round(sum(l["subtotal"] for l in lineas if l["tipo"] == "MP"   and l["subtotal"] is not None), 2)
    total_avios = round(sum(l["subtotal"] for l in lineas if l["tipo"] == "AVIO" and l["subtotal"] is not None), 2)

    full = _costo_full(prenda, total_mp, total_avios, tc)
    return {
        "lineas":        lineas,
        "total_mp":      total_mp,
        "total_avios":   total_avios,
        "total_insumos": round(total_mp + total_avios, 2),
        **full,                              # servicios, mod, gif, costo_primo, produccion, total_general
        "tipo_cambio":   tc,
        "aviso":         None,
    }


# ── Endpoints ─────────────────────────────────────────────────

@router.get("/api/{prenda_id}/hoja-costos/prefill")
def api_prefill_hoja(
    prenda_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """Devuelve líneas pre-llenadas desde la BASE sin guardar nada.
    Paulo las revisa, ajusta precios con logística y luego hace POST para guardar."""
    prenda = _get_prenda(prenda_id, db)
    return _build_prefill_desde_base(prenda, db)


# ── Tipo de cambio del día (editable por Logística) ───────────
class TipoCambioIn(_PBase):
    tipo_cambio: float


@router.get("/api/tipo-cambio")
def api_get_tipo_cambio(db: Session = Depends(get_db),
                        current_user: Usuario = Depends(get_current_user)):
    """TC USD→S/ vigente (el que Logística cargó). Cualquiera lo puede ver."""
    from app.models.parametro import ParametroSistema
    row = db.query(ParametroSistema).filter_by(clave=TC_PARAM_KEY).first()
    return {
        "tipo_cambio":  tc_hoy(db),
        "updated_at":   row.updated_at.isoformat() if (row and row.updated_at) else None,
        "puede_editar": _rol(current_user) in ROLES_TC,
        "fallback":     row is None,          # True = usando el valor por defecto
    }


@router.post("/api/tipo-cambio")
def api_set_tipo_cambio(body: TipoCambioIn, db: Session = Depends(get_db),
                        current_user: Usuario = Depends(get_current_user)):
    """Logística fija el TC del día. Solo aplica a hojas NUEVAS; las guardadas
    conservan el suyo."""
    if _rol(current_user) not in ROLES_TC:
        raise HTTPException(403, "Solo Logística puede actualizar el tipo de cambio")
    if not body.tipo_cambio or body.tipo_cambio <= 0:
        raise HTTPException(400, "El tipo de cambio debe ser mayor a 0")
    from app.models.parametro import ParametroSistema
    ParametroSistema.set(db, TC_PARAM_KEY, str(body.tipo_cambio))
    return {"tipo_cambio": tc_hoy(db)}


@router.get("/api/{prenda_id}/hoja-costos")
def api_get_hoja(
    prenda_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """Devuelve la hoja de costos guardada de la variante (la más reciente)."""
    _get_prenda(prenda_id, db)
    hoja = (
        db.query(HojaCostos)
        .filter_by(prenda_catalogo_id=prenda_id)
        .order_by(HojaCostos.updated_at.desc())
        .first()
    )
    if not hoja:
        raise HTTPException(404, "Sin hoja de costos aún")
    return _hoja_dict(hoja)


@router.post("/api/{prenda_id}/hoja-costos")
def api_guardar_hoja(
    prenda_id: int,
    body: HojaIn,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """Crea o reemplaza la hoja de costos en estado BORRADOR.
    Si ya existe una APROBADA, crea una nueva versión BORRADOR sin tocar la aprobada."""
    if _rol(current_user) not in ROLES_EDITOR:
        raise HTTPException(403, "Sin permiso para editar hoja de costos")
    prenda = _get_prenda(prenda_id, db)

    # Registrar cambios de precio en historial si precio_snapshot difiere del catálogo
    for linea in body.lineas:
        if linea.precio_snapshot is None:
            continue
        if linea.tipo == "MP":
            item = db.query(CatalogoMp).filter_by(id=linea.item_id).first()
            precio_actual = item.precio_referencia if item else None
            nombre_item   = item.nombre if item else linea.nombre
        else:
            item = db.query(CatalogoAvio).filter_by(id=linea.item_id).first()
            precio_actual = item.precio if item else None
            nombre_item   = item.nombre if item else linea.nombre

        if item and precio_actual != linea.precio_snapshot:
            db.add(PrecioHistorico(
                tipo              = linea.tipo,
                item_id           = linea.item_id,
                nombre_item       = nombre_item,
                precio_anterior   = precio_actual,
                precio_nuevo      = linea.precio_snapshot,
                moneda            = linea.moneda,
                registrado_por_id = current_user.id,
            ))
            # Actualizar precio en catálogo
            if linea.tipo == "MP" and item:
                item.precio_referencia = linea.precio_snapshot
            elif linea.tipo == "AVIO" and item:
                item.precio = linea.precio_snapshot

    # Calcular totales
    lineas_data = body.lineas
    tc = body.tipo_cambio or tc_hoy(db)
    total_mp    = round(sum(
        _calcular_subtotal(l.consumo_unitario, l.pct_adicional, l.precio_snapshot,
                           l.factor_conversion, l.moneda, tc) or 0
        for l in lineas_data if l.tipo == "MP"), 2)
    total_avios = round(sum(
        _calcular_subtotal(l.consumo_unitario, l.pct_adicional, l.precio_snapshot,
                           l.factor_conversion, l.moneda, tc) or 0
        for l in lineas_data if l.tipo == "AVIO"), 2)
    # Costo completo: + servicios + MOD + GIF + margen (de la base, heredado)
    full = _costo_full(prenda, total_mp, total_avios, tc)

    # Buscar hoja BORRADOR existente para reutilizar (no aprobada)
    hoja = (
        db.query(HojaCostos)
        .filter_by(prenda_catalogo_id=prenda_id, estado="BORRADOR")
        .first()
    )
    if hoja:
        # Reemplazar líneas
        for l in hoja.lineas:
            db.delete(l)
        db.flush()
    else:
        hoja = HojaCostos(
            prenda_catalogo_id = prenda_id,
            creado_por_id      = current_user.id,
        )
        db.add(hoja)
        db.flush()

    hoja.estado        = "BORRADOR"
    hoja.moneda_base   = body.moneda_base
    hoja.tipo_cambio   = body.tipo_cambio or TC_HDC
    hoja.notas         = body.notas
    hoja.total_mp      = total_mp
    hoja.total_avios   = total_avios
    hoja.total_general = full["total_general"]     # costo total (insumos + servicios + MOD + GIF + margen)
    hoja.updated_at    = datetime.utcnow()

    for i, l in enumerate(lineas_data):
        subtotal = _calcular_subtotal(l.consumo_unitario, l.pct_adicional, l.precio_snapshot,
                                      l.factor_conversion or 1.0, l.moneda, tc)
        db.add(HojaCostosLinea(
            hoja_id           = hoja.id,
            tipo              = l.tipo,
            item_id                  = l.item_id,
            seccion           = l.seccion,
            nombre            = l.nombre,
            unidad_medida     = l.unidad_medida,
            unidad_compra     = l.unidad_compra,
            factor_conversion = l.factor_conversion or 1.0,
            consumo_unitario  = l.consumo_unitario,
            pct_adicional     = l.pct_adicional,
            precio_snapshot   = l.precio_snapshot,
            moneda            = l.moneda,
            subtotal          = subtotal,
            notas             = l.notas,
            orden             = i,
        ))

    db.query(HojaCostosLinea).filter_by(hoja_id=hoja.id).filter(
        HojaCostosLinea.orden >= len(lineas_data)
    ).delete(synchronize_session=False)

    db.commit()
    db.refresh(hoja)
    return _hoja_dict(hoja)


@router.post("/api/{prenda_id}/hoja-costos/aprobar")
def api_aprobar_hoja(
    prenda_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """Aprueba la hoja BORRADOR y crea nueva versión BORRADOR. Solo INGENIERIA / ADMIN."""
    if _rol(current_user) not in ROLES_APROBAR:
        raise HTTPException(403, "Solo Ingeniería o Admin pueden aprobar")

    hoja = (
        db.query(HojaCostos)
        .filter_by(prenda_catalogo_id=prenda_id, estado="BORRADOR")
        .first()
    )
    if not hoja:
        raise HTTPException(404, "No hay hoja en BORRADOR para aprobar")
    if not hoja.lineas:
        raise HTTPException(400, "La hoja no tiene líneas. Agrega MP o avíos antes de aprobar.")

    version_actual = getattr(hoja, 'version', 1) or 1

    # Snapshot de líneas antes de congelar
    lineas_snap = [
        {
            "tipo":              l.tipo,
            "item_id":           l.item_id,
            "seccion":           l.seccion,
            "nombre":            l.nombre,
            "unidad_medida":     l.unidad_medida,
            "unidad_compra":     l.unidad_compra,
            "factor_conversion": l.factor_conversion,
            "consumo_unitario":  l.consumo_unitario,
            "pct_adicional":     l.pct_adicional,
            "precio_snapshot":   l.precio_snapshot,
            "moneda":            l.moneda,
            "subtotal":          l.subtotal,
            "notas":             l.notas,
            "orden":             l.orden,
        }
        for l in hoja.lineas
    ]

    # Congelar BORRADOR como APROBADA
    hoja.estado          = "APROBADA"
    hoja.aprobado_por_id = current_user.id
    hoja.aprobado_at     = datetime.utcnow()
    db.flush()

    # Crear nuevo BORRADOR con version+1 copiando líneas actuales
    nueva_hoja = HojaCostos(
        prenda_catalogo_id = prenda_id,
        estado             = "BORRADOR",
        version            = version_actual + 1,
        moneda_base        = hoja.moneda_base,
        tipo_cambio        = hoja.tipo_cambio,
        notas              = None,
        total_mp           = hoja.total_mp,
        total_avios        = hoja.total_avios,
        total_general      = hoja.total_general,
        creado_por_id      = current_user.id,
    )
    db.add(nueva_hoja)
    db.flush()

    for snap in lineas_snap:
        db.add(HojaCostosLinea(
            hoja_id           = nueva_hoja.id,
            tipo              = snap["tipo"],
            item_id           = snap["item_id"],
            seccion           = snap["seccion"],
            nombre            = snap["nombre"],
            unidad_medida     = snap["unidad_medida"],
            unidad_compra     = snap["unidad_compra"],
            factor_conversion = snap["factor_conversion"],
            consumo_unitario  = snap["consumo_unitario"],
            pct_adicional     = snap["pct_adicional"],
            precio_snapshot   = snap["precio_snapshot"],
            moneda            = snap["moneda"],
            subtotal          = snap["subtotal"],
            notas             = snap["notas"],
            orden             = snap["orden"],
        ))

    db.commit()
    return {
        "ok":            True,
        "mensaje":       f"Hoja v{version_actual} aprobada. Nueva versión v{version_actual + 1} en borrador.",
        "nueva_version": version_actual + 1,
    }


@router.get("/api/{prenda_id}/hoja-costos/historial")
def api_historial_hojas(
    prenda_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """Devuelve todas las versiones APROBADAS de la prenda, ordenadas de más reciente a más antigua."""
    _get_prenda(prenda_id, db)
    hojas = (
        db.query(HojaCostos)
        .filter_by(prenda_catalogo_id=prenda_id, estado="APROBADA")
        .order_by(HojaCostos.aprobado_at.desc())
        .all()
    )
    return [
        {
            "id":            h.id,
            "version":       getattr(h, 'version', 1) or 1,
            "total_mp":      h.total_mp,
            "total_avios":   h.total_avios,
            "total_general": h.total_general,
            "moneda_base":   h.moneda_base,
            "tipo_cambio":   h.tipo_cambio,
            "aprobado_at":   h.aprobado_at.isoformat() if h.aprobado_at else None,
            "aprobado_por":  h.aprobado_por.nombre if h.aprobado_por else None,
        }
        for h in hojas
    ]


@router.get("/api/{prenda_id}/hoja-costos/version/{hoja_id}")
def api_get_version_hoja(
    prenda_id: int,
    hoja_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """Devuelve una versión específica (APROBADA) de la hoja de costos para visualización."""
    hoja = (
        db.query(HojaCostos)
        .filter_by(id=hoja_id, prenda_catalogo_id=prenda_id, estado="APROBADA")
        .first()
    )
    if not hoja:
        raise HTTPException(404, "Versión no encontrada")
    return _hoja_dict(hoja)


@router.get("/api/{prenda_id}/hoja-costos/historial-precios/{item_tipo}/{item_id}")
def api_historial_precios(
    prenda_id: int,
    item_tipo: str,
    item_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """Devuelve el historial de cambios de precio de un MP o Avío."""
    registros = (
        db.query(PrecioHistorico)
        .filter_by(tipo=item_tipo.upper(), item_id=item_id)
        .order_by(PrecioHistorico.created_at.desc())
        .limit(20)
        .all()
    )
    return [
        {
            "precio_anterior": r.precio_anterior,
            "precio_nuevo":    r.precio_nuevo,
            "moneda":          r.moneda,
            "fecha":           r.created_at.isoformat() if r.created_at else None,
        }
        for r in registros
    ]
