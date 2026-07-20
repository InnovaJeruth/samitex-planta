"""
Importación de Órdenes de Fabricación desde el export de SAP (COIS).

El Excel de la COIS trae una OF por fila con columnas administrativas. La OF se
crea con esos datos; el color / curva de tallas / fit se resuelven aparte
(jalados de la prenda por el material). Ver CAMBIOS_TECNICOS_SAP_CATALOGO_OF.md.
"""
from datetime import datetime, date, time
from io import BytesIO
from typing import List, Optional

import openpyxl
from sqlalchemy.orm import Session

from app.models.of import OrdenFabricacion, EstadoOF, EstadoDocsEnum, TipoClienteEnum
from app.models.catalogo import PrendaCatalogo
from app.constants import clase_orden_info

# Mapa: encabezado del Excel COIS (normalizado) -> clave interna.
# Se normaliza a minúsculas sin acentos ni espacios extra para tolerar variaciones.
_COLS = {
    "orden":                    "numero_of",
    "numero material":          "material_sap",
    "texto breve material":     "texto_material",
    "centro":                   "centro",
    "clase de orden":           "clase_orden",
    "cantidad orden (gmein)":   "cantidad",
    "cantidad orden":           "cantidad",
    "autor":                    "autor_sap",
    "fecha inicio extrema":     "fecha_inicio",
    "fecha fin extrema":        "fecha_fin",
    "area pl.nec.":             "area_planificacion",
    "area pl. nec.":            "area_planificacion",
    "sociedad":                 "sociedad",
    "hora creacion":            "hora_creacion",
    "almacen":                  "almacen",
}


def _norm(s) -> str:
    if s is None:
        return ""
    s = str(s).strip().lower()
    for a, b in (("á", "a"), ("é", "e"), ("í", "i"), ("ó", "o"), ("ú", "u"), ("ñ", "n")):
        s = s.replace(a, b)
    return " ".join(s.split())


def parse_excel_sap(contenido: bytes) -> List[dict]:
    """Lee el Excel de la COIS y devuelve una lista de filas como dicts con las
    claves internas de `_COLS`. Toma la primera hoja."""
    wb = openpyxl.load_workbook(BytesIO(contenido), data_only=True, read_only=True)
    ws = wb.active
    filas = list(ws.iter_rows(values_only=True))
    if not filas:
        return []
    encabezados = [_norm(c) for c in filas[0]]
    idx = {}
    for i, h in enumerate(encabezados):
        if h in _COLS and _COLS[h] not in idx:
            idx[_COLS[h]] = i
    out = []
    for fila in filas[1:]:
        if fila is None or all(c is None or str(c).strip() == "" for c in fila):
            continue
        reg = {}
        for clave, i in idx.items():
            reg[clave] = fila[i] if i < len(fila) else None
        if reg.get("numero_of"):
            out.append(reg)
    return out


def _a_fecha(v) -> Optional[date]:
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    if isinstance(v, str) and v.strip():
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d.%m.%Y"):
            try:
                return datetime.strptime(v.strip()[:10], fmt).date()
            except ValueError:
                continue
    return None


def _a_hora(v) -> Optional[time]:
    if isinstance(v, time):
        return v
    if isinstance(v, datetime):
        return v.time()
    if isinstance(v, str) and v.strip():
        for fmt in ("%H:%M:%S", "%H:%M"):
            try:
                return datetime.strptime(v.strip(), fmt).time()
            except ValueError:
                continue
    return None


def _fecha_sap(reg: dict) -> Optional[datetime]:
    """Combina fecha inicio extrema + hora creación en un DateTime."""
    f = _a_fecha(reg.get("fecha_inicio"))
    if not f:
        return None
    h = _a_hora(reg.get("hora_creacion")) or time(0, 0, 0)
    return datetime.combine(f, h)


def _buscar_prenda(material_sap: str, db: Session) -> Optional[PrendaCatalogo]:
    """Enlaza por número de material SAP (llave única). El catálogo todavía puede
    no tener la columna material_sap (fase prenda pendiente): en ese caso no
    enlaza y la OF queda sin prenda hasta que exista."""
    if not material_sap or not hasattr(PrendaCatalogo, "material_sap"):
        return None
    return db.query(PrendaCatalogo).filter_by(material_sap=str(material_sap).strip()).first()


def crear_of_desde_sap(reg: dict, db: Session, usuario_id: int = None, cliente: str = None) -> dict:
    """Crea UNA OF a partir de una fila del export SAP.
    `cliente` lo digita el planeador al importar (SAP no lo trae).
    Devuelve {'ok': bool, 'numero_of': str, 'mensaje': str, 'of_id': int|None}."""
    numero_of = str(reg.get("numero_of") or "").strip()
    if not numero_of:
        return {"ok": False, "numero_of": "", "mensaje": "Fila sin N° de orden", "of_id": None}

    material_sap = str(reg.get("material_sap") or "").strip()
    if not material_sap:
        return {"ok": False, "numero_of": numero_of, "mensaje": "Sin número de material", "of_id": None}

    prenda = _buscar_prenda(material_sap, db)
    texto = str(reg.get("texto_material") or "").strip()
    # tipo_prenda: categoría corta (CAMISA…) de la prenda si enlaza; si no, el texto SAP.
    tipo_prenda = (prenda.tipo_base if prenda else texto) or "POR DEFINIR"

    # ¿Ya existe la OF? Si está sin prenda y ahora sí hay match, re-vincular (no duplicar).
    existente = db.query(OrdenFabricacion).filter_by(numero_of=numero_of).first()
    if existente:
        if prenda and not existente.prenda_catalogo_id:
            existente.prenda_catalogo_id = prenda.id
            existente.tipo_prenda = tipo_prenda
            if cliente and cliente.strip():
                existente.cliente = cliente.strip()
            db.commit()
            return {"ok": True, "numero_of": numero_of, "of_id": existente.id,
                    "mensaje": f"Re-vinculada a {prenda.nombre}"}
        return {"ok": False, "numero_of": numero_of,
                "mensaje": "Ya existe una OF con ese N° de orden", "of_id": None}

    try:
        cantidad = int(reg.get("cantidad") or 0)
    except (TypeError, ValueError):
        cantidad = 0
    if cantidad < 1:
        return {"ok": False, "numero_of": numero_of, "mensaje": "Cantidad inválida", "of_id": None}

    clase = str(reg.get("clase_orden") or "").strip().upper()
    info = clase_orden_info(clase)
    tc = info["tipo_cliente"]
    tipo_cliente = TipoClienteEnum(tc) if tc in ("INSTITUCION", "MARCA") else TipoClienteEnum.INSTITUCION

    of = OrdenFabricacion(
        numero_of          = numero_of,
        cliente            = (cliente.strip() if cliente and cliente.strip() else "POR DEFINIR"),  # SAP no lo trae; lo digita el planeador
        tipo_prenda        = tipo_prenda,
        prenda_catalogo_id = prenda.id if prenda else None,
        total_juegos       = cantidad,
        fecha_creacion     = date.today(),
        fecha_sap          = _fecha_sap(reg),
        fecha_apt          = _a_fecha(reg.get("fecha_fin")),   # APT = fecha fin extrema
        tipo_cliente       = tipo_cliente,
        material_sap       = material_sap,
        clase_orden        = clase or None,
        centro             = (str(reg.get("centro")).strip() if reg.get("centro") else None),
        sociedad           = (str(reg.get("sociedad")).strip() if reg.get("sociedad") else None),
        area_planificacion = (str(reg.get("area_planificacion")).strip() if reg.get("area_planificacion") else None),
        almacen            = (str(reg.get("almacen")).strip() if reg.get("almacen") else None),
        autor_sap          = (str(reg.get("autor_sap")).strip() if reg.get("autor_sap") else None),
        omitir_gates       = not info["gates"],       # ZP43/ZP44 (sin mapear) → sin gates
        estado             = EstadoOF.BORRADOR,
        estado_docs        = EstadoDocsEnum.PENDIENTE,
        responsable_id     = usuario_id,
    )
    db.add(of)
    db.commit()
    db.refresh(of)

    notas = []
    if info["pendiente"]:
        notas.append(f"clase {clase or '—'} pendiente de mapear (sin gates)")
    if not prenda:
        notas.append("prenda no encontrada por material (enlace pendiente)")
    return {"ok": True, "numero_of": numero_of, "of_id": of.id,
            "mensaje": "Creada" + (" · " + "; ".join(notas) if notas else "")}


def importar_excel_sap(contenido: bytes, db: Session, usuario_id: int = None, cliente: str = None) -> dict:
    """Procesa el Excel completo. `cliente` se aplica a todas las OFs del lote."""
    filas = parse_excel_sap(contenido)
    if not filas:
        return {"total": 0, "creadas": 0, "errores": 0, "detalle": [],
                "mensaje": "El archivo no tiene filas válidas o no coincide el formato."}
    detalle, creadas, errores = [], 0, 0
    for reg in filas:
        r = crear_of_desde_sap(reg, db, usuario_id=usuario_id, cliente=cliente)
        detalle.append(r)
        if r["ok"]:
            creadas += 1
        else:
            errores += 1
    return {"total": len(filas), "creadas": creadas, "errores": errores, "detalle": detalle,
            "mensaje": f"{creadas} OF creadas, {errores} con error de {len(filas)} filas."}
