"""RAG Text-to-SQL — R3: barreras de seguridad + ejecución de solo lectura.

El SQL generado por el LLM NO se confía. Antes de ejecutar pasa por varias
barreras; y se ejecuta contra la sesión de solo lectura (`get_db_ro`), que hace
rollback siempre. La garantía fuerte es el login `db_datareader`; esto es la
defensa a nivel de aplicación.
"""
import re
from datetime import date, datetime
from decimal import Decimal

import sqlparse
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings
from app.services.rag_service import WHITELIST

_WHITELIST = {t.lower() for t in WHITELIST}

# Palabras prohibidas (DML/DDL/ejecución). SELECT INTO también escribe → INTO prohibido.
_PROHIBIDAS = re.compile(
    r"\b(INSERT|UPDATE|DELETE|MERGE|DROP|ALTER|TRUNCATE|CREATE|GRANT|REVOKE|"
    r"EXEC|EXECUTE|INTO|BACKUP|RESTORE|SHUTDOWN|RECONFIGURE|OPENROWSET|OPENQUERY)\b",
    re.IGNORECASE,
)
_PROC_PELIGROSA = re.compile(r"\b(sp|xp)_\w+", re.IGNORECASE)

# Columnas sensibles: nunca deben aparecer en el SQL (defensa en profundidad).
_COLUMNAS_SENSIBLES = re.compile(
    r"\b(password_hash|password|passwd|contrasena|contraseña|token|"
    r"secret|api_key|apikey|refresh_token|access_token|salt|private_key)\b",
    re.IGNORECASE,
)
# SELECT * (o alias.*) en la proyección — obliga a columnas explícitas.
# No matchea COUNT(*)/SUM(*) porque ahí el * va tras un '(' precedido de función.
_SELECT_STAR = re.compile(
    r"(?is)\bSELECT\b(?:\s+DISTINCT)?(?:\s+TOP\s+\d+)?\s+(?:[A-Za-z_]\w*\s*\.\s*)?\*",
)


class SQLNoPermitido(ValueError):
    """El SQL propuesto viola una barrera de seguridad."""


# ── Extracción de tablas / CTEs ──────────────────────────────────────────────
def _tablas_referidas(sql: str) -> set:
    return {m.group(1).lower()
            for m in re.finditer(r"(?:FROM|JOIN)\s+([A-Za-z_][\w\.]*)", sql, re.IGNORECASE)}


def _nombres_cte(sql: str) -> set:
    return {m.group(1).lower()
            for m in re.finditer(r"(?:WITH|,)\s+([A-Za-z_]\w*)\s+AS\s*\(", sql, re.IGNORECASE)}


# ── Validación ───────────────────────────────────────────────────────────────
def validar_sql(sql: str, max_rows: int | None = None) -> str:
    """Aplica las barreras y devuelve el SQL saneado (con TOP inyectado si faltaba).
    Lanza SQLNoPermitido ante cualquier violación."""
    max_rows = max_rows or settings.RAG_MAX_ROWS
    if not (sql or "").strip():
        raise SQLNoPermitido("SQL vacío.")

    # 1) sin comentarios (evita trucos con -- o /* */)
    if "--" in sql or "/*" in sql:
        raise SQLNoPermitido("No se permiten comentarios en la consulta.")

    # 2) una sola sentencia
    sentencias = [s for s in sqlparse.split(sql) if s.strip()]
    if len(sentencias) != 1:
        raise SQLNoPermitido("Solo se permite una sentencia.")
    sql = sentencias[0].strip().rstrip(";").strip()

    # 3) debe empezar en SELECT o WITH
    if not re.match(r"(?is)^\s*(SELECT|WITH)\b", sql):
        raise SQLNoPermitido("Solo se permiten consultas SELECT.")

    # 4) palabras prohibidas y procedimientos peligrosos
    if _PROHIBIDAS.search(sql):
        raise SQLNoPermitido("La consulta contiene una operación no permitida (solo lectura).")
    if _PROC_PELIGROSA.search(sql):
        raise SQLNoPermitido("No se permiten procedimientos del sistema.")

    # 4b) columnas sensibles (credenciales/PII) — nunca en el SQL
    if _COLUMNAS_SENSIBLES.search(sql):
        raise SQLNoPermitido("La consulta referencia columnas no permitidas.")

    # 4c) SELECT * prohibido — deben pedirse columnas explícitas
    if _SELECT_STAR.search(sql):
        raise SQLNoPermitido("No se permite SELECT *; especifica las columnas.")

    # 5) todas las tablas deben estar en el whitelist (los CTE se permiten)
    permitidas = _WHITELIST | _nombres_cte(sql)
    referidas = _tablas_referidas(sql)
    fuera = {t for t in referidas if t not in permitidas}
    if fuera:
        raise SQLNoPermitido(f"Tablas no permitidas: {', '.join(sorted(fuera))}.")

    return sql


def inyectar_top(sql: str, max_rows: int) -> str:
    """Inyecta `TOP N` en un SELECT simple sin TOP (solo T-SQL / SQL Server).
    El tope real de filas lo garantiza fetchmany; esto evita escaneos server-side."""
    if re.search(r"\bTOP\b", sql, re.IGNORECASE):
        return sql
    if not re.match(r"(?is)^\s*SELECT\b", sql):   # WITH…/otros: no se toca
        return sql
    return re.sub(r"(?is)^(\s*SELECT\s+)(DISTINCT\s+)?",
                  rf"\1\2TOP {max_rows} ", sql, count=1)


def _fmt_valor(v):
    """Formatea valores para mostrar: fechas legibles (sin T ni microsegundos)."""
    if isinstance(v, datetime):
        s = v.strftime("%Y-%m-%d %H:%M:%S")
        return s[:10] if v.hour == 0 and v.minute == 0 and v.second == 0 else s
    if isinstance(v, date):
        return v.strftime("%Y-%m-%d")
    if isinstance(v, Decimal):
        return float(v)
    return v


# ── Ejecución de solo lectura ────────────────────────────────────────────────
def ejecutar(sql: str, db_ro: Session, max_rows: int | None = None) -> dict:
    """Valida y ejecuta el SQL en la sesión read-only. Devuelve columnas + filas
    (limitadas a max_rows). Nunca hace commit."""
    max_rows = max_rows or settings.RAG_MAX_ROWS
    sql_seguro = validar_sql(sql, max_rows)
    # TOP solo tiene sentido en SQL Server; en otros dialectos (sqlite/tests) se omite
    if db_ro.bind is not None and db_ro.bind.dialect.name == "mssql":
        sql_seguro = inyectar_top(sql_seguro, max_rows)
    try:
        result = db_ro.execute(text(sql_seguro))
        columnas = list(result.keys())
        filas = [{c: _fmt_valor(v) for c, v in zip(columnas, row)}
                 for row in result.fetchmany(max_rows)]
    finally:
        db_ro.rollback()   # jamás persistir; refuerza el modo lectura
    return {"sql": sql_seguro, "columnas": columnas, "filas": filas}
