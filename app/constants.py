"""
Constantes globales compartidas por routers y servicios.
Centraliza definiciones que antes estaban duplicadas en múltiples archivos.
"""

# Tope de capas (paños) por placa por defecto (editable por OF).
# Ej.: el pantalón de drill corta hasta 80 capas.
MAX_CAPAS_DEFAULT = 80

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
    "F7": "Habilitado",
}

# Fases que aparecen en el Gantt (sin estampado/auditoría)
FASES_GANTT = ["F1", "F2", "F3", "F4", "F5", "F6", "F7"]

# Etiquetas cortas para el Gantt
FASES_GANTT_LBL = {
    "F1": "TZ", "F2": "TN", "F3": "CR", "F4": "NM",
    "F5": "FS", "F6": "CL", "F7": "HB",
}
