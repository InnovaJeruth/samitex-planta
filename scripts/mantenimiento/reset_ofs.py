"""
Script para borrar TODAS las OFs y sus datos relacionados.
Irreversible. Ejecutar solo si quieres reiniciar desde cero.

    python reset_ofs.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from sqlalchemy import text
from app.database.connection import engine

TABLAS_EN_ORDEN = [
    # Hijos primero (FK constraints)
    "avance_registros",
    "of_fases_estado",
    "of_fase_tiempos",
    "of_fase_paradas",
    "of_piezas",
    "documentos_of",
    "terc_historial_fechas",
    "terc_recepciones",
    # Padre al final
    "ordenes_fabricacion",
]

def tabla_existe(conn, tabla):
    r = conn.execute(text(
        "SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME=:t"
    ), {"t": tabla})
    return r.scalar() > 0

confirm = input("⚠  Esto borrará TODAS las OFs y sus datos. Escribe 'SI' para confirmar: ")
if confirm.strip().upper() != "SI":
    print("Cancelado.")
    sys.exit(0)

with engine.connect() as conn:
    for tabla in TABLAS_EN_ORDEN:
        if not tabla_existe(conn, tabla):
            print(f"  [--]  {tabla} no existe, omitiendo")
            continue
        r = conn.execute(text(f"SELECT COUNT(*) FROM {tabla}"))
        n = r.scalar()
        conn.execute(text(f"DELETE FROM {tabla}"))
        conn.commit()
        print(f"  [OK]  {tabla}: {n} filas borradas")

    # Reiniciar identidades (auto-increment)
    for tabla in ["ordenes_fabricacion", "of_piezas", "of_fases_estado",
                  "of_fase_tiempos", "of_fase_paradas", "avance_registros"]:
        if tabla_existe(conn, tabla):
            try:
                conn.execute(text(f"DBCC CHECKIDENT ('{tabla}', RESEED, 0)"))
                conn.commit()
            except Exception:
                pass  # Ignorar si la tabla no tiene identity

print("\n✓ Todas las OFs borradas. Puedes crear OFs nuevas desde /of/crear")
