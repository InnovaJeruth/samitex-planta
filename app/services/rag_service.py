"""RAG Text-to-SQL — R2: generación de SQL (sin ejecutar).

Arma el contexto para el LLM (esquema del whitelist + glosario de negocio +
ejemplos) y pide a Gemini una consulta SELECT de SQL Server. NO ejecuta nada:
la ejecución y las barreras de seguridad viven en R3 (`rag_guard` / router).

El esquema se extrae de `Base.metadata` (columnas y tipos reales, sin drift),
filtrado al whitelist y enriquecido con descripciones de negocio.
"""
import re
import threading
from typing import List, Tuple

from app.config import settings
from app.database.connection import Base


class RAGOcupado(RuntimeError):
    """No hay cupo de concurrencia para atender la consulta al LLM ahora mismo."""


# Límite de consultas RAG al LLM en vuelo a la vez. Protege el threadpool de
# FastAPI (compartido con el resto de endpoints): si el chat se satura, se
# rechaza el sobrante con 429 en vez de agotar los hilos y frenar todo el ERP.
_LLM_SLOTS = max(1, int(settings.RAG_MAX_CONCURRENCIA))
_llm_sem = threading.BoundedSemaphore(_LLM_SLOTS)

# Registrar en Base.metadata los modelos del whitelist (el __init__ está vacío)
import app.models.of          # noqa: F401
import app.models.pieza       # noqa: F401
import app.models.fase        # noqa: F401
import app.models.paquete     # noqa: F401
import app.models.trazo       # noqa: F401
import app.models.catalogo    # noqa: F401
import app.models.requerimiento  # noqa: F401
import app.models.usuario     # noqa: F401


# ── Vistas de negocio (no son modelos ORM; se describen a mano) ──────────────
# Deben existir en SQL Server (scripts/sql/vw_of_fases.sql).
VISTAS = {
    "vw_of_fases": {
        "desc": "Tiempos por fase de cada OF ya UNIFICADOS y con nombre. "
                "USAR ESTA para preguntas de tiempos/duración por fase o proceso de una OF.",
        "columns": [
            ("numero_of", "VARCHAR", "número de la OF"),
            ("fase", "VARCHAR", "Tizado | Tendido | Corte | Numerado | Fusionado | Calidad"),
            ("inicio", "DATETIME", "inicio real de la fase"),
            ("fin", "DATETIME", "fin real de la fase"),
            ("minutos", "INT", "duración de la fase en minutos"),
            ("orden", "INT", "1..6 (orden del proceso)"),
        ],
    },
    "vw_of_rechazos": {
        "desc": "Rechazos de calidad ya aplanados por OF (fila = un rechazo). "
                "USAR ESTA para preguntas de rechazos/reprocesos/calidad por OF o por motivo.",
        "columns": [
            ("numero_of", "VARCHAR", "número de la OF"),
            ("motivo_codigo", "VARCHAR", "código del motivo (CR01…)"),
            ("motivo", "VARCHAR", "descripción del motivo de rechazo"),
            ("cantidad", "INT", "prendas rechazadas en ese registro"),
            ("estado", "VARCHAR", "estado del rechazo/reproceso"),
        ],
    },
    "vw_usuarios": {
        "desc": "Usuarios del sistema SIN datos sensibles (solo para 'quién hizo X'). "
                "No contiene contraseñas ni tokens. USAR ESTA para resolver usuario_id → nombre.",
        "columns": [
            ("id", "INT", "id de usuario (para joins con *.usuario_id)"),
            ("nombre", "VARCHAR", "nombre para mostrar"),
            ("username", "VARCHAR", "usuario de acceso"),
            ("rol", "VARCHAR", "rol del sistema"),
            ("activo", "BIT", "1 activo / 0 inactivo"),
        ],
    },
}

# ── Whitelist (Ola 1: núcleo OF + F1–F7 + catálogo + comercial) ──────────────
WHITELIST: List[str] = [
    "vw_of_fases", "vw_of_rechazos", "vw_usuarios",
    "ordenes_fabricacion", "of_talla_distribucion", "of_piezas",
    "of_trazos", "of_trazo_tallas", "of_fase_tiempos", "of_fases_estado", "of_fase_paradas",
    "of_paquetes", "of_paquete_eventos", "of_paquete_rechazos", "motivos_rechazo", "of_reproceso_hitos",
    "prendas_catalogo", "prenda_skus",
    "requerimientos", "requerimiento_lineas", "requerimiento_linea_tallas",
]

# Descripción de negocio por tabla (contexto para el LLM)
DESCRIPCIONES_TABLA = {
    "ordenes_fabricacion": "Orden de fabricación (OF): unidad central de producción. estado, total_juegos, cliente, fechas.",
    "of_talla_distribucion": "Cantidades por talla (SKU) dentro de una OF.",
    "of_piezas": "Piezas que componen cada OF.",
    "of_trazos": "Placas/tizados de corte (fases de tela F1–F3): capas, prendas por placa.",
    "of_trazo_tallas": "Tallas dibujadas en cada placa.",
    "of_fase_tiempos": "Inicio y fin real por fase de una OF (para tiempos y cuellos).",
    "of_fases_estado": "Estado por pieza×talla×fase de corte.",
    "of_fase_paradas": "Paradas registradas por fase (tiempo perdido).",
    "of_paquetes": "Bultos de prendas numeradas: estado, cantidad, tiempos de fusionado.",
    "of_paquete_eventos": "Transiciones de estado de cada bulto con fecha y usuario (traza fina).",
    "of_paquete_rechazos": "Rechazos de calidad por bulto, con motivo y cantidad.",
    "motivos_rechazo": "Catálogo de motivos de rechazo (código y descripción).",
    "of_reproceso_hitos": "Hitos del reproceso de un rechazo.",
    "prendas_catalogo": "Catálogo de prendas (código, nombre, tipo).",
    "prenda_skus": "Variantes por talla de cada prenda del catálogo.",
    "requerimientos": "Requerimientos comerciales (Muestra/Producción/Stock): cabecera.",
    "requerimiento_lineas": "Líneas (ítems) de un requerimiento.",
    "requerimiento_linea_tallas": "Curva de tallas por línea de requerimiento.",
    "vw_usuarios": "Usuarios del sistema SIN datos sensibles (para 'quién hizo X'): id, nombre, username, rol.",
}

# Notas sobre columnas ambiguas (opcional, se anexan a la columna)
NOTAS_COLUMNA = {
    ("ordenes_fabricacion", "estado"): "BORRADOR | ACTIVA | EN_PROCESO | COMPLETADA",
    ("ordenes_fabricacion", "numero_of"): "número de la OF (ej. '4000010011')",
    ("ordenes_fabricacion", "tipo_cliente"): "INSTITUCION | MARCA",
    ("ordenes_fabricacion", "total_juegos"): "cantidad total de prendas de la OF",
    ("ordenes_fabricacion", "fecha_apt"): "fecha de entrega comprometida (APT)",
    ("of_fase_tiempos", "fase_id"): "F1..F7 (fase del proceso)",
    ("of_fase_tiempos", "inicio_real"): "inicio real de la fase",
    ("of_fase_tiempos", "fin_real"): "fin real de la fase",
    ("of_paquetes", "estado"): "HABILITADO | FUSIONADO | POR_VALIDAR | ENTREGADO | STAND_BY",
}

# ── Glosario de negocio ──────────────────────────────────────────────────────
GLOSARIO = """GLOSARIO DEL NEGOCIO (planta de corte textil):
- Fases de producción: F1 Tizado, F2 Tendido, F3 Corte (tela); F4 Numerado,
  F5 Fusionado, F6 Costura, F7 Liberado (calidad).
- Una OF (orden de fabricación) produce una prenda en varias tallas.
- "OF atrasada" = fecha_apt < fecha de hoy Y estado <> 'COMPLETADA'.
- "Rework" o "reproceso" = bultos rechazados en calidad (of_paquete_rechazos / of_reproceso_hitos).
- "Bulto" o "paquete" = grupo de prendas numeradas (of_paquetes)."""

# ── Relaciones clave (joins) — el modelo no las adivina bien ─────────────────
RELACIONES = """RELACIONES (cómo se unen las tablas):
- of_piezas.of_id → ordenes_fabricacion.id
- of_fase_tiempos.of_id → ordenes_fabricacion.id
- of_fases_estado.of_id → ordenes_fabricacion.id
- of_fase_paradas.of_id → ordenes_fabricacion.id
- of_trazos.of_id → ordenes_fabricacion.id ; of_trazo_tallas.trazo_id → of_trazos.id
- of_talla_distribucion.of_id → ordenes_fabricacion.id ; of_talla_distribucion.sku_id → prenda_skus.id
- of_paquetes.of_id → ordenes_fabricacion.id
- of_paquete_eventos.paquete_id → of_paquetes.id
- of_paquete_rechazos.paquete_id → of_paquetes.id   (NO tiene of_id: para llegar a la OF, une con of_paquetes)
- of_reproceso_hitos.rechazo_id → of_paquete_rechazos.id
- motivos_rechazo.id ← of_paquete_rechazos.motivo_id
- prenda_skus.prenda_catalogo_id → prendas_catalogo.id
- ordenes_fabricacion.prenda_catalogo_id → prendas_catalogo.id
- requerimiento_lineas.requerimiento_id → requerimientos.id
- requerimiento_linea_tallas.linea_id → requerimiento_lineas.id
- vw_usuarios.id ← *.usuario_id (eventos, rechazos, hitos) — usa vw_usuarios, nunca la tabla usuarios"""

# ── Ejemplos (few-shot) ──────────────────────────────────────────────────────
FEW_SHOTS: List[Tuple[str, str]] = [
    ("¿Cuántas OF están activas?",
     "SELECT COUNT(*) AS total FROM ordenes_fabricacion WHERE estado IN ('ACTIVA','EN_PROCESO');"),
    ("Muéstrame las OF atrasadas con su cliente",
     "SELECT TOP 200 numero_of, cliente, fecha_apt, estado FROM ordenes_fabricacion "
     "WHERE fecha_apt < CAST(GETDATE() AS DATE) AND estado <> 'COMPLETADA' ORDER BY fecha_apt;"),
    ("¿Cuántas prendas produce cada OF y de qué prenda es?",
     "SELECT TOP 200 o.numero_of, p.nombre AS prenda, o.total_juegos "
     "FROM ordenes_fabricacion o LEFT JOIN prendas_catalogo p ON p.id = o.prenda_catalogo_id "
     "ORDER BY o.total_juegos DESC;"),
    ("Fechas de inicio y fin de cada proceso/fase de la OF 4000010011",
     "SELECT fase, inicio, fin, minutos FROM vw_of_fases "
     "WHERE numero_of = '4000010011' ORDER BY orden;"),
    ("¿Cuánto duró cada fase de la OF 4000010011?",
     "SELECT fase, minutos FROM vw_of_fases WHERE numero_of = '4000010011' ORDER BY orden;"),
    ("Rechazos de calidad por motivo de la OF 4000010011",
     "SELECT motivo, SUM(cantidad) AS total FROM vw_of_rechazos "
     "WHERE numero_of = '4000010011' GROUP BY motivo ORDER BY total DESC;"),
    ("¿Cuántos rechazos tuvo la OF 4000010011?",
     "SELECT SUM(cantidad) AS total_rechazos FROM vw_of_rechazos WHERE numero_of = '4000010011';"),
]


# ── Construcción del contexto ────────────────────────────────────────────────
def construir_esquema() -> str:
    """Texto del esquema (solo tablas del whitelist) desde Base.metadata."""
    bloques = []
    for nombre in WHITELIST:
        if nombre in VISTAS:
            v = VISTAS[nombre]
            cols = [f"  {cn} {ct}" + (f"  -- {nota}" if nota else "")
                    for cn, ct, nota in v["columns"]]
            bloques.append(f"VISTA {nombre}  ({v['desc']})\n" + "\n".join(cols))
            continue
        tabla = Base.metadata.tables.get(nombre)
        if tabla is None:
            continue
        desc = DESCRIPCIONES_TABLA.get(nombre, "")
        cols = []
        for c in tabla.columns:
            linea = f"  {c.name} {str(c.type)}"
            nota = NOTAS_COLUMNA.get((nombre, c.name))
            if nota:
                linea += f"  -- {nota}"
            cols.append(linea)
        cab = f"TABLA {nombre}" + (f"  ({desc})" if desc else "")
        bloques.append(cab + "\n" + "\n".join(cols))
    return "\n\n".join(bloques)


def construir_prompt(pregunta: str) -> str:
    ejemplos = "\n".join(f"P: {q}\nSQL: {s}" for q, s in FEW_SHOTS)
    return f"""Eres un analista que traduce preguntas de negocio a SQL de SQL Server (T-SQL).

REGLAS:
- Devuelve EXCLUSIVAMENTE una sentencia SELECT (o WITH ... SELECT). Nada de explicaciones.
- Prohibido INSERT, UPDATE, DELETE, MERGE, DROP, ALTER, TRUNCATE, EXEC o varias sentencias.
- Usa SOLO las tablas y columnas listadas abajo. No inventes nombres.
- Prohibido SELECT *: nombra siempre las columnas concretas que necesitas.
- Para datos de usuario ("quién hizo X") usa SOLO la vista vw_usuarios (id, nombre, username, rol).
  NUNCA uses la tabla usuarios ni pidas contraseñas, hashes ni tokens (no están disponibles).
- Es SQL Server: usa TOP N (no LIMIT). Limita a {settings.RAG_MAX_ROWS} filas salvo agregaciones.
- Fechas: CAST(GETDATE() AS DATE) para "hoy".
- Devuelve la consulta en una sola línea, sin ```.
- CRÍTICO: las tablas of_paquete_rechazos, of_paquete_eventos y of_reproceso_hitos NO tienen
  columna of_id. Para filtrar por OF hay que unir SIEMPRE pasando por of_paquetes:
  of_paquete_rechazos.paquete_id → of_paquetes.id, y of_paquetes.of_id → ordenes_fabricacion.id.
  NUNCA escribas of_paquete_rechazos.of_id ni of_paquete_eventos.of_id (no existen).
- Para tiempos/duración por FASE o PROCESO de una OF, usa SIEMPRE la vista vw_of_fases
  (ya trae nombre de fase, inicio, fin y minutos). No armes el cálculo desde tablas crudas.
- Para RECHAZOS / reprocesos / calidad de una OF, usa SIEMPRE la vista vw_of_rechazos
  (ya trae numero_of, motivo y cantidad). No unas of_paquete_rechazos a mano.

{GLOSARIO}

ESQUEMA DISPONIBLE:
{construir_esquema()}

{RELACIONES}

EJEMPLOS:
{ejemplos}

P: {pregunta}
SQL:"""


# ── Limpieza de la salida del LLM ────────────────────────────────────────────
def limpiar_sql(texto: str) -> str:
    """Quita cercas markdown, prefijos 'sql' y ';' final. Devuelve una sentencia."""
    t = (texto or "").strip()
    # bloque ```sql ... ```
    m = re.search(r"```(?:sql)?\s*(.+?)```", t, re.DOTALL | re.IGNORECASE)
    if m:
        t = m.group(1).strip()
    t = re.sub(r"^\s*sql\s*[:\-]?\s*", "", t, flags=re.IGNORECASE)
    t = t.strip().rstrip(";").strip()
    return t


# ── Llamada al LLM — nube (Gemini) o local (Ollama) ──────────────────────────
def _invocar_gemini(prompt: str) -> str:
    """Gemini (nube). Import perezoso para no exigir el paquete en tests."""
    import google.generativeai as genai  # noqa: WPS433
    genai.configure(api_key=settings.GEMINI_API_KEY)
    modelo = genai.GenerativeModel(settings.RAG_MODEL)
    resp = modelo.generate_content(
        prompt,
        generation_config={"temperature": 0.0},
        request_options={"timeout": settings.RAG_LLM_TIMEOUT},
    )
    return resp.text


def _invocar_ollama(prompt: str) -> str:
    """Ollama (local, gratis). Habla con el endpoint HTTP en RAG_OLLAMA_URL."""
    import httpx  # noqa: WPS433
    url = settings.RAG_OLLAMA_URL.rstrip("/") + "/api/generate"
    r = httpx.post(url, timeout=settings.RAG_LLM_TIMEOUT, json={
        "model": settings.RAG_OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0},
    })
    r.raise_for_status()
    return r.json().get("response", "")


def _invocar_llm(prompt: str) -> str:
    """Despacha al proveedor configurado (RAG_LLM_PROVIDER)."""
    if settings.RAG_LLM_PROVIDER.lower() == "ollama":
        return _invocar_ollama(prompt)
    return _invocar_gemini(prompt)


def generar_sql(pregunta: str) -> str:
    """Pregunta en lenguaje natural → SQL SELECT (string). NO ejecuta."""
    if not (pregunta or "").strip():
        raise ValueError("La pregunta no puede estar vacía.")
    crudo = _invocar_llm(construir_prompt(pregunta))
    return limpiar_sql(crudo)


# ── Resumen en lenguaje natural (2ª llamada al LLM) ──────────────────────────
def construir_prompt_resumen(pregunta: str, filas: list) -> str:
    import json
    muestra = filas[:50]
    datos = json.dumps(muestra, ensure_ascii=False, default=str)
    return (
        "Responde en español, claro y breve (1–3 frases), la pregunta del usuario "
        "usando SOLO estos datos. No inventes cifras. Si la lista está vacía, dilo.\n\n"
        f"PREGUNTA: {pregunta}\n\nDATOS (JSON, hasta 50 filas): {datos}\n\nRESPUESTA:"
    )


def resumir(pregunta: str, filas: list) -> str:
    if not filas:
        return "La consulta no devolvió resultados."
    return _invocar_llm(construir_prompt_resumen(pregunta, filas)).strip()


# ── Orquestador (usado por el router) ────────────────────────────────────────
def responder(pregunta: str, db_ro, *, incluir_sql: bool = False,
              incluir_resumen: bool | None = None) -> dict:
    """Pregunta NL → genera SQL (LLM), lo valida+ejecuta (read-only) y opcionalmente
    redacta un resumen (LLM). Import perezoso de rag_guard para evitar ciclo."""
    from app.services import rag_guard   # evita import circular (guard usa WHITELIST)

    if incluir_resumen is None:
        incluir_resumen = settings.RAG_INCLUIR_RESUMEN

    # Cupo de concurrencia: se toma un slot para TODO el trabajo de LLM del
    # request (SQL + resumen). Si no hay cupo, se rechaza de inmediato (429),
    # sin quedarse ocupando un hilo del threadpool esperando.
    if not _llm_sem.acquire(blocking=False):
        raise RAGOcupado(
            "El chat analítico está atendiendo varias consultas ahora mismo. "
            "Espera unos segundos y reintenta."
        )
    try:
        sql = generar_sql(pregunta)                  # LLM #1
        res = rag_guard.ejecutar(sql, db_ro)         # barreras + ejecución read-only
        resumen = resumir(pregunta, res["filas"]) if incluir_resumen else ""
    finally:
        _llm_sem.release()

    return {
        "respuesta": resumen or f"{len(res['filas'])} fila(s).",
        "sql": res["sql"] if incluir_sql else None,
        "columnas": res["columnas"],
        "filas": res["filas"],
    }
