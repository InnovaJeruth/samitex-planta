"""
Reimporta el CATÁLOGO + usuarios desde catalogo_backup.json a la BD limpia.
Correr DESPUÉS de recrear la BD (create_all):  python import_catalogo.py

Preserva los IDs originales (usa IDENTITY_INSERT en SQL Server) para que
las relaciones base↔variante, piezas y configs sigan apuntando bien.
Es idempotente-seguro solo sobre BD vacía: si la tabla ya tiene filas, la salta.
"""
import json
import datetime as _dt

from sqlalchemy import create_engine, select, insert, func
from sqlalchemy import Date, DateTime, Time


def _deserializar(tbl, rows):
    """Reconvierte strings ISO a date/datetime/time según el tipo de cada columna."""
    tipos = {}
    for c in tbl.columns:
        t = c.type
        if isinstance(t, DateTime):
            tipos[c.name] = "datetime"
        elif isinstance(t, Date):
            tipos[c.name] = "date"
        elif isinstance(t, Time):
            tipos[c.name] = "time"
    out = []
    for r in rows:
        nr = dict(r)
        for k, kind in tipos.items():
            v = nr.get(k)
            if isinstance(v, str) and v:
                try:
                    if kind == "datetime":
                        nr[k] = _dt.datetime.fromisoformat(v)
                    elif kind == "date":
                        nr[k] = _dt.date.fromisoformat(v)
                    elif kind == "time":
                        nr[k] = _dt.time.fromisoformat(v)
                except ValueError:
                    pass
        out.append(nr)
    return out

from app.config import settings
from app.database.connection import Base
# Importa los modelos para poblar Base.metadata
import app.models.usuario   # noqa: F401
import app.models.catalogo  # noqa: F401
import app.models.pieza     # noqa: F401

BACKUP = "catalogo_backup.json"


def main():
    with open(BACKUP, encoding="utf-8") as f:
        data = json.load(f)

    orden = data.get("_orden") or [k for k in data if not k.startswith("_")]
    engine = create_engine(settings.DATABASE_URL)
    md = Base.metadata
    is_mssql = engine.dialect.name == "mssql"

    with engine.begin() as conn:
        for name in orden:
            tbl = md.tables.get(name)
            rows = data.get(name) or []
            if tbl is None:
                print(f"  ⚠ tabla {name} no está en el modelo — la salto")
                continue
            if not rows:
                print(f"  {name}: 0 filas en backup — nada que importar")
                continue
            ya = conn.execute(select(func.count()).select_from(tbl)).scalar()
            if ya:
                print(f"  ⚠ {name}: ya tiene {ya} filas — la salto (BD no vacía)")
                continue

            # Solo columnas que existen en el modelo actual (tolera cambios de esquema)
            cols = {c.name for c in tbl.columns}
            limpio = [{k: v for k, v in r.items() if k in cols} for r in rows]
            limpio = _deserializar(tbl, limpio)

            has_identity = is_mssql and any(c.primary_key and c.autoincrement for c in tbl.columns)
            if has_identity:
                conn.exec_driver_sql(f"SET IDENTITY_INSERT {tbl.name} ON")
            conn.execute(insert(tbl), limpio)
            if has_identity:
                conn.exec_driver_sql(f"SET IDENTITY_INSERT {tbl.name} OFF")
            print(f"  {name}: {len(limpio)} filas importadas")

    print(f"\n✓ Catálogo restaurado desde {BACKUP}")


if __name__ == "__main__":
    main()
