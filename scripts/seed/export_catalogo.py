"""
Exporta el CATÁLOGO + usuarios a catalogo_backup.json (preservando IDs).
Correr ANTES de recrear la BD:  python export_catalogo.py

Respalda: usuarios, prendas (base y variantes), tallas/SKU, piezas,
materias primas, avíos y sus configs base↔variante. NO respalda OFs ni
nada transaccional.
"""
import json
import datetime as _dt

from sqlalchemy import create_engine, select

from app.config import settings
from app.database.connection import Base
# Importa los modelos para poblar Base.metadata (sin ORM/mappers)
import app.models.usuario   # noqa: F401
import app.models.catalogo  # noqa: F401
import app.models.pieza     # noqa: F401

# Orden FK-safe para el import posterior
TABLES = [
    "usuarios",
    "prendas_catalogo",
    "prenda_skus",
    "plantilla_piezas",
    "catalogo_mp",
    "catalogo_avios",
    "prenda_mp_config",
    "prenda_avio_config",
    "prenda_sku_mp_config",
    "prenda_sku_avio_config",
]


def _ser(v):
    if isinstance(v, (_dt.datetime, _dt.date)):
        return v.isoformat()
    return v


def main():
    engine = create_engine(settings.DATABASE_URL)
    md = Base.metadata
    out = {"_orden": TABLES}
    with engine.connect() as conn:
        for name in TABLES:
            tbl = md.tables.get(name)
            if tbl is None:
                print(f"  ⚠ tabla {name} no encontrada en metadata — la salto")
                continue
            rows = [
                {c.name: _ser(r[c.name]) for c in tbl.columns}
                for r in conn.execute(select(tbl)).mappings()
            ]
            out[name] = rows
            print(f"  {name}: {len(rows)} filas")
    with open("catalogo_backup.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2, default=str)
    print("\n✓ Backup escrito en catalogo_backup.json")


if __name__ == "__main__":
    main()
