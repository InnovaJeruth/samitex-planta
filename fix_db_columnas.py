"""
Script para agregar columnas faltantes en modelos SQLAlchemy que no tienen migración.
Ejecutar desde la carpeta del proyecto:
    python fix_db_columnas.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from sqlalchemy import text
from app.database.connection import engine

# (tabla, columna, tipo_sql)
COLUMNAS = [
    # of_fases_estado — campos extra de proceso
    ("of_fases_estado", "eficiencia_tizado",   "FLOAT"),
    ("of_fases_estado", "temperatura_fusion",  "FLOAT"),
    ("of_fases_estado", "tratamiento_orillo",  "BIT"),
    ("of_fases_estado", "motivo_rechazo",      "NVARCHAR(MAX)"),
    # of_piezas — campo booleano para estampado/bordado
    ("of_piezas",       "estampado_bordado",   "BIT"),
]

def col_exists(conn, tabla, columna):
    r = conn.execute(text(
        "SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS "
        "WHERE TABLE_NAME=:t AND COLUMN_NAME=:c"
    ), {"t": tabla, "c": columna})
    return r.scalar() > 0

with engine.connect() as conn:
    agregadas = []
    for tabla, nombre, tipo in COLUMNAS:
        if col_exists(conn, tabla, nombre):
            print(f"  [OK]  {tabla}.{nombre} ya existe")
        else:
            default = " DEFAULT 0" if tipo == "BIT" else ""
            conn.execute(text(
                f"ALTER TABLE {tabla} ADD {nombre} {tipo} NULL{default}"
            ))
            conn.commit()
            agregadas.append(f"{tabla}.{nombre}")
            print(f"  [+]   {tabla}.{nombre} agregada ({tipo})")

    if agregadas:
        print(f"\n✓ Columnas agregadas: {', '.join(agregadas)}")
        print("  Reinicia uvicorn y recarga la página.")
    else:
        print("\n✓ Todas las columnas ya existían. No se necesitó cambiar nada.")
