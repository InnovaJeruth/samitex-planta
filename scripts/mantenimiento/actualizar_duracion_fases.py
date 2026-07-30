"""
Script único: setea duracion_horas_std = 1.0 en todas las fases del catálogo.
Ejecutar una sola vez:  python actualizar_duracion_fases.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

# Importar todos los modelos para evitar errores de mapper
import app.models.catalogo, app.models.of, app.models.fase
import app.models.usuario, app.models.pieza, app.models.planta

from app.database.connection import get_db
from sqlalchemy import text

db = next(get_db())
try:
    result = db.execute(text("UPDATE fases_catalogo SET duracion_horas_std = 1.0"))
    db.commit()
    filas = result.rowcount
    print(f"OK — {filas} fases actualizadas a 1.0 h")
    rows = db.execute(text("SELECT fase_id, duracion_horas_std FROM fases_catalogo ORDER BY fase_id")).fetchall()
    for r in rows:
        print(f"  {r[0]}: {r[1]} h")
except Exception as e:
    db.rollback()
    print(f"ERROR: {e}")
finally:
    db.close()
