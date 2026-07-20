"""
gate_service.py
---------------
Calcula el estado de los "gates" (requisitos previos) de una OF.

Gates de DOCUMENTOS: pasan cuando existe al menos un archivo subido de ese tipo.
Gates de CÓDIGO:     pasan cuando el campo de código correspondiente está lleno.

Estructura de la cadena documental:
  Cadena 1 (Ingeniería/Comercial/Logística):
    FICHA_TECNICA → HOJA_COSTOS → SOLPED_PRENDA

  Cadena 2 (paralela desde Muestra Aprobada):
    MUESTRA_APROBADA ┬→ SOLPED_MP → ORDEN_COMPRA → CONFIRMACION_STOCK
                     └→ REPORTE_TALLAS → MOLDES_LECTRA
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from sqlalchemy.orm import Session

from app.models.of import OrdenFabricacion, TipoDocumentoOF, DocumentoOF
from app.models.catalogo import HojaCostos


# ── Definición de gates ───────────────────────────────────────
@dataclass
class GateDef:
    gate_id: str
    label: str
    area: str       # Ingeniería | Comercial | Planeamiento | Logística | UDP | Modelista
    tipo: str       # "doc" | "codigo"
    doc_type: Optional[str] = None   # TipoDocumentoOF value si tipo=="doc"
    campo: Optional[str] = None      # nombre del campo en OrdenFabricacion si tipo=="codigo"
    depende_de: List[str] = field(default_factory=list)   # gate_ids previos requeridos


GATES: List[GateDef] = [
    # ── Cadena 1 ──────────────────────────────────────────────
    GateDef("FICHA_TECNICA",    "Ficha Técnica",        "UDP / Com.Marca",    "doc",    doc_type="FICHA_TECNICA"),
    GateDef("HOJA_COSTOS",      "Hoja de Costos",       "Ingeniería",         "doc",    doc_type="HOJA_COSTOS",    depende_de=["FICHA_TECNICA"]),
    GateDef("SOLPED_PRENDA",    "SOLPED Prenda",        "Comercial / P.Marca","codigo", campo="solped_prenda",     depende_de=["HOJA_COSTOS"]),
    # ── Cadena 2: raíz ────────────────────────────────────────
    GateDef("MUESTRA_APROBADA", "Muestra Aprobada",     "Comercial / Com.Marca","doc",   doc_type="MUESTRA_APROBADA"),
    # ── Cadena 2: rama SAP ────────────────────────────────────
    GateDef("SOLPED_MP",        "SOLPED Materia Prima", "Planeamiento",       "codigo", campo="solped_mp",         depende_de=["MUESTRA_APROBADA"]),
    GateDef("ORDEN_COMPRA",     "Orden de Compra",      "Logística",          "codigo", campo="orden_compra",      depende_de=["SOLPED_MP"]),
    GateDef("CONFIRMACION_STOCK","Confirmación Stock",  "Logística",          "doc",    doc_type="CONFIRMACION_STOCK", depende_de=["ORDEN_COMPRA"]),
    # ── Cadena 2: rama técnica ────────────────────────────────
    GateDef("REPORTE_TALLAS",   "Reporte Tallas",       "UDP / Com.Marca",    "doc",    doc_type="REPORTE_TALLAS",  depende_de=["MUESTRA_APROBADA"]),
    GateDef("MOLDES_LECTRA",    "Moldes Lectra",        "Calidad",            "doc",    doc_type="MOLDES_LECTRA",   depende_de=["REPORTE_TALLAS"]),
]

GATES_BY_ID: Dict[str, GateDef] = {g.gate_id: g for g in GATES}

# Gates obligatorios para poder activar la OF
GATES_REQUERIDOS = {
    "FICHA_TECNICA", "HOJA_COSTOS", "SOLPED_PRENDA",
    "MUESTRA_APROBADA", "SOLPED_MP", "ORDEN_COMPRA",
    "CONFIRMACION_STOCK", "REPORTE_TALLAS", "MOLDES_LECTRA",
}

# Colores por área (visual)
AREA_COLORS = {
    "Ingeniería":   "#1a6fbe",
    "Comercial":    "#e67e22",
    "Planeamiento": "#8e44ad",
    "Logística":    "#27ae60",
    "UDP":          "#c0392b",
    "Modelista":    "#16a085",
    "UDP / Com.Marca":      "#c0392b",
    "Comercial / P.Marca":  "#e67e22",
    "Comercial / Com.Marca":"#e67e22",
    "Comercial Marca":      "#e67e22",
    "Planeamiento Marca":   "#8e44ad",
    "Calidad":              "#16a085",
}

# Área que aplica según el tipo de cliente de la OF (etiqueta dinámica).
# Los gates ausentes usan su área fija (igual para institución y marca).
GATE_AREA_TC: Dict[str, Dict[str, str]] = {
    "FICHA_TECNICA":    {"INSTITUCION": "UDP",       "MARCA": "Comercial Marca"},
    "SOLPED_PRENDA":    {"INSTITUCION": "Comercial", "MARCA": "Planeamiento Marca"},
    "MUESTRA_APROBADA": {"INSTITUCION": "Comercial", "MARCA": "Comercial Marca"},
    "REPORTE_TALLAS":   {"INSTITUCION": "UDP",       "MARCA": "Comercial Marca"},
}

# ── Roles autorizados por gate y tipo_cliente ─────────────────
# Formato: { gate_id: { tipo_cliente: [roles_permitidos] } }
GATE_ROLES: Dict[str, Dict[str, List[str]]] = {
    "FICHA_TECNICA":      {"INSTITUCION": ["UDP", "ADMIN"],                          "MARCA": ["COMERCIAL_MARCA", "ADMIN"]},
    "HOJA_COSTOS":        {"INSTITUCION": ["INGENIERIA", "ADMIN"],                   "MARCA": ["INGENIERIA", "ADMIN"]},
    "SOLPED_PRENDA":      {"INSTITUCION": ["COMERCIAL", "ADMIN"],                    "MARCA": ["PLANEAMIENTO_MARCA", "ADMIN"]},
    "MUESTRA_APROBADA":   {"INSTITUCION": ["COMERCIAL", "ADMIN"],                    "MARCA": ["COMERCIAL_MARCA", "ADMIN"]},
    "REPORTE_TALLAS":     {"INSTITUCION": ["UDP", "ADMIN"],                          "MARCA": ["COMERCIAL_MARCA", "ADMIN"]},
    "SOLPED_MP":          {"INSTITUCION": ["PLANEADOR", "ADMIN"],                    "MARCA": ["PLANEADOR", "ADMIN"]},
    "ORDEN_COMPRA":       {"INSTITUCION": ["LOGISTICA", "ADMIN"],                    "MARCA": ["LOGISTICA", "ADMIN"]},
    "CONFIRMACION_STOCK": {"INSTITUCION": ["LOGISTICA", "ADMIN"],                    "MARCA": ["LOGISTICA", "ADMIN"]},
    "MOLDES_LECTRA":      {"INSTITUCION": ["CALIDAD", "ADMIN"],                      "MARCA": ["CALIDAD", "ADMIN"]},
}


def puede_subir_gate(rol: str, gate_id: str, tipo_cliente: str) -> bool:
    """Retorna True si el rol puede subir/editar el gate para el tipo de cliente."""
    roles = GATE_ROLES.get(gate_id, {}).get(tipo_cliente, [])
    return rol in roles


# ── Resultado por gate ────────────────────────────────────────
@dataclass
class GateResult:
    gate_id: str
    label: str
    area: str
    area_color: str
    tipo: str
    pasado: bool
    bloqueado: bool   # True si algún gate previo no pasó
    valor: Optional[str] = None   # código SAP o nombre de archivo


# ── Función principal ─────────────────────────────────────────
def calcular_gates(of: OrdenFabricacion, db: Session) -> Dict[str, GateResult]:
    """
    Retorna el estado de cada gate para una OF.
    Calcula dinámicamente desde documentos subidos y códigos en la OF.
    """
    # Qué tipos de documentos tiene la OF
    docs_subidos: set[str] = {
        str(d.tipo.value if hasattr(d.tipo, "value") else d.tipo)
        for d in of.documentos
    }

    # Tipo de cliente de la OF (para etiquetas de área dinámicas)
    tc = of.tipo_cliente.value if hasattr(of.tipo_cliente, "value") else str(of.tipo_cliente)

    resultados: Dict[str, GateResult] = {}

    for gate in GATES:
        # Verificar si algún gate previo no pasó (bloqueado)
        bloqueado = any(
            not resultados.get(dep_id, GateResult(
                dep_id, "", "", "", "", False, False
            )).pasado
            for dep_id in gate.depende_de
        )

        # Calcular si pasó
        pasado = False
        valor: Optional[str] = None

        if not bloqueado:
            if gate.gate_id == "HOJA_COSTOS":
                # Pasa si la variante vinculada a la OF tiene una HojaCostos APROBADA en catálogo
                # (flujo nuevo), o si hay un archivo subido a la OF (flujo legado).
                hoja_aprobada = (
                    db.query(HojaCostos)
                    .filter_by(
                        prenda_catalogo_id=of.prenda_catalogo_id,
                        estado="APROBADA",
                    )
                    .first()
                ) if of.prenda_catalogo_id else None

                if hoja_aprobada:
                    pasado = True
                    valor  = f"Hoja aprobada · S/. {hoja_aprobada.total_general or 0:.2f}"
                elif gate.doc_type in docs_subidos:
                    pasado = True
                    doc = next(
                        (d for d in of.documentos
                         if str(d.tipo.value if hasattr(d.tipo, "value") else d.tipo) == gate.doc_type),
                        None,
                    )
                    valor = doc.nombre_archivo if doc else None

            elif gate.tipo == "doc" and gate.doc_type:
                pasado = gate.doc_type in docs_subidos
                if pasado:
                    doc = next(
                        (d for d in of.documentos
                         if str(d.tipo.value if hasattr(d.tipo, "value") else d.tipo) == gate.doc_type),
                        None,
                    )
                    valor = doc.nombre_archivo if doc else None
            elif gate.tipo == "codigo" and gate.campo:
                valor = getattr(of, gate.campo, None)
                pasado = bool(valor and str(valor).strip())

        area = GATE_AREA_TC.get(gate.gate_id, {}).get(tc, gate.area)
        resultados[gate.gate_id] = GateResult(
            gate_id=gate.gate_id,
            label=gate.label,
            area=area,
            area_color=AREA_COLORS.get(area, AREA_COLORS.get(gate.area, "#555")),
            tipo=gate.tipo,
            pasado=pasado,
            bloqueado=bloqueado,
            valor=valor,
        )

    return resultados


def gates_para_activar(of: OrdenFabricacion, db: Session) -> Dict[str, GateResult]:
    """Retorna solo los gates requeridos para activar la OF."""
    todos = calcular_gates(of, db)
    return {k: v for k, v in todos.items() if k in GATES_REQUERIDOS}


def puede_activar(of: OrdenFabricacion, db: Session) -> tuple[bool, List[str]]:
    """
    Verifica si la OF puede activarse.
    Retorna (True, []) si todos los gates requeridos pasaron,
    o (False, [lista de gates pendientes]) si alguno falta.
    """
    # Muestras y OFs de prueba (modo corte) no requieren gates documentales
    if getattr(of, 'es_muestra', False) or getattr(of, 'omitir_gates', False):
        return True, []
    gates = gates_para_activar(of, db)
    faltantes = [g.label for g in gates.values() if not g.pasado]
    return (len(faltantes) == 0, faltantes)


def gates_to_dict(gates: Dict[str, GateResult]) -> List[dict]:
    """Serializa gates a lista de dicts para API/JSON."""
    return [
        {
            "gate_id": g.gate_id,
            "label": g.label,
            "area": g.area,
            "area_color": g.area_color,
            "tipo": g.tipo,
            "pasado": g.pasado,
            "bloqueado": g.bloqueado,
            "valor": g.valor,
        }
        for g in gates.values()
    ]
