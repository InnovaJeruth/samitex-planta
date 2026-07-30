"""
Constantes globales compartidas por routers y servicios.
Centraliza definiciones que antes estaban duplicadas en múltiples archivos.
"""

# Tope de capas (paños) por placa por defecto (editable por OF).
# Ej.: el pantalón de drill corta hasta 80 capas.
MAX_CAPAS_DEFAULT = 80

# Tope de unidades por paquete de numeración por defecto (editable por OF).
UNIDADES_POR_PAQUETE_DEFAULT = 49

# Orden de ejecución de fases del proceso de corte
ORDEN_FASES = ["F1", "F2", "F3", "F4", "F8", "F9", "F5", "F6", "F7"]

# Nombres legibles de cada fase
NOMBRES_FASE = {
    "F1": "Tizado",
    "F2": "Tendido",
    "F3": "Corte",
    "F4": "Numerado",
    "F8": "Estampado",
    "F9": "Auditoría",
    "F5": "Fusionado",
    "F6": "Calidad",
    "F7": "Liberado",
}

# Fases que aparecen en el Gantt (sin estampado/auditoría)
FASES_GANTT = ["F1", "F2", "F3", "F4", "F5", "F6", "F7"]

# Etiquetas cortas para el Gantt
FASES_GANTT_LBL = {
    "F1": "TZ", "F2": "TN", "F3": "CR", "F4": "NM",
    "F5": "FS", "F6": "CL", "F7": "LB",
}

# --- Clases de orden SAP (import de OF desde la COIS) ----------------------
# Mapeo configurable clase_orden → comportamiento en el sistema.
#   tipo_cliente: a qué TipoClienteEnum mapea (None = sin definir / neutro).
#   gates:        True = pasa por gates documentales; False = sin gates.
#   pendiente:    True = clase aún no mapeada por planta (marca visible).
# Editar aquí (sin tocar código de negocio) cuando planta defina ZP43/ZP44.
CLASES_ORDEN_SAP = {
    "ZP41": {"nombre": "Institución",      "tipo_cliente": "INSTITUCION", "gates": True,  "pendiente": False},
    "ZP42": {"nombre": "Marca",            "tipo_cliente": "MARCA",       "gates": True,  "pendiente": False},
    "ZP43": {"nombre": "Reprocesos",       "tipo_cliente": None,          "gates": False, "pendiente": True},
    "ZP44": {"nombre": "Servicios terceros","tipo_cliente": None,         "gates": False, "pendiente": True},
}

# Comportamiento por defecto si llega una clase no listada arriba.
CLASE_ORDEN_DEFAULT = {"nombre": None, "tipo_cliente": None, "gates": False, "pendiente": True}


def clase_orden_info(clase: str) -> dict:
    """Devuelve la config de una clase de orden SAP; default seguro si no está mapeada."""
    return CLASES_ORDEN_SAP.get((clase or "").strip().upper(), CLASE_ORDEN_DEFAULT)
