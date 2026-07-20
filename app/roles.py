"""Matriz central de roles (Fase 8 · H8 opción A).

Fuente única de los conjuntos de roles usados por los routers. Las membresías
son IDÉNTICAS a las definiciones que antes estaban dispersas por cada router;
esto es una relocalización 1:1 (sin cambiar quién puede hacer qué).

Los `ROLES_EDITOR` que colisionaban entre módulos (catálogo / curvas / hoja de
costos) se renombran por dominio para eliminar la ambigüedad; cada router los
importa con alias a su nombre local, así que su uso interno no cambia.
"""


def rol_de(user) -> str:
    """Nombre del rol del usuario como string ('ADMIN', 'UDP', …)."""
    return user.rol.value if hasattr(user.rol, "value") else str(user.rol)


# ── Corte / paquetes ────────────────────────────────────────────────────────
ROLES_CORTE = {"ADMIN", "PLANEADOR", "SUPERVISOR_CORTE"}
ROLES_DOCS = {
    "UDP", "COMERCIAL", "COMERCIAL_MARCA", "PLANEAMIENTO_MARCA",
    "INGENIERIA", "LOGISTICA", "CALIDAD",
}
ROLES_NUMERAR = {"ADMIN", "PLANEADOR", "SUPERVISOR_CORTE"}
ROLES_CALIDAD = {"ADMIN", "PLANEADOR", "SUPERVISOR_CORTE", "CALIDAD"}
ROLES_REPROCESO = {"ADMIN", "SUPERVISOR_CORTE", "CORTE", "FUSIONADO"}
ROLES_FUSIONADO = {"ADMIN", "SUPERVISOR_CORTE", "FUSIONADO"}
ROLES_PLANEAMIENTO = {"ADMIN", "PLANEADOR"}
ROLES_PLANTA_CORTE = ROLES_CALIDAD | ROLES_REPROCESO | ROLES_FUSIONADO
ROLES_GERENCIA = {"ADMIN", "GERENTE_PLANTA"}          # aprobación del gerente de planta
ROLES_DAR_OK = {"ADMIN", "SUPERVISOR_CORTE"}          # Modelista / Externo / Desmanchado dan OK
ROLES_REABRIR_NUMERACION = {"ADMIN", "GERENTE_PLANTA", "SUPERVISOR_CORTE", "JEFE_PLANTA"}
ROLES_TRAZO = {"ADMIN", "PLANEADOR", "SUPERVISOR_CORTE"}

# ── OF ──────────────────────────────────────────────────────────────────────
ROLES_PLAN_CORTE = {"ADMIN", "PLANEADOR", "GERENTE_PLANTA", "JEFE_PLANTA", "GERENCIA"}
ROLES_PRUEBA = {"ADMIN", "PLANEADOR"}
ROLES_IMPORT_OF = {"ADMIN", "PLANEADOR"}

# ── Comercial ───────────────────────────────────────────────────────────────
ROLES_COMERCIAL = {
    "ADMIN", "PLANEADOR", "COMERCIAL", "COMERCIAL_MARCA",
    "PLANEAMIENTO_MARCA", "GERENTE_PLANTA", "JEFE_PLANTA", "GERENCIA",
}
ROLES_CREAR = {"ADMIN", "PLANEADOR", "COMERCIAL", "COMERCIAL_MARCA"}

# ── Catálogo ────────────────────────────────────────────────────────────────
ROLES_EDITOR_CATALOGO = {"ADMIN", "UDP", "COMERCIAL_MARCA"}

# ── Curvas de tallas ────────────────────────────────────────────────────────
ROLES_EDITOR_CURVAS = {"ADMIN", "UDP", "GERENCIA", "GERENTE_PLANTA"}
ROLES_LECTURA_CURVAS = {"SUPERVISOR_CORTE", "PLANEADOR"}
ROLES_ACCESO_CURVAS = ROLES_EDITOR_CURVAS | ROLES_LECTURA_CURVAS

# ── Hoja de costos ──────────────────────────────────────────────────────────
ROLES_EDITOR_HDC = {"ADMIN", "UDP", "INGENIERIA"}
ROLES_APROBAR_HDC = {"ADMIN", "INGENIERIA"}
ROLES_TC = {"ADMIN", "LOGISTICA"}   # quién fija el tipo de cambio del día

# ── Plantas ─────────────────────────────────────────────────────────────────
ROLES_PLANTAS = {"ADMIN", "PLANEADOR", "GERENTE_PLANTA", "JEFE_PLANTA", "GERENCIA"}

# ── Supervisor ──────────────────────────────────────────────────────────────
ROLES_SUPERVISOR = {"ADMIN", "SUPERVISOR_CORTE", "GERENTE_PLANTA", "JEFE_PLANTA",
                    "PLANEADOR", "GERENCIA", "UDP"}
ROLES_PROGRAMAR = {"ADMIN", "SUPERVISOR_CORTE", "GERENTE_PLANTA", "JEFE_PLANTA",
                   "PLANEADOR", "GERENCIA"}
