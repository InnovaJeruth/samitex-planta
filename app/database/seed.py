"""
Seed idempotente de datos de referencia que NO viven en el backup de catálogo.
Se ejecuta al arrancar el app (después de create_all). Si la tabla ya tiene
datos, no hace nada.

Actualmente: fases_catalogo (las 9 fases del proceso de corte). Sin estas filas,
insertar cualquier of_fases_estado falla por FK (fase_id → fases_catalogo).
"""
from app.database.connection import SessionLocal
from app.models.fase import FaseCatalogo

# (fase_id, nombre, orden, obligatoria, descripcion)
FASES_SEED = [
    ("F1", "TIZADO",            1, True,  "Registrar % eficiencia del trazo. Objetivo: 85-87%."),
    ("F2", "TENDIDO",           2, True,  "Si tipo negocio = INSTITUCIÓN: registrar flag tratamiento de orillo."),
    ("F3", "CORTE",             3, True,  "Ejecución del corte."),
    ("F4", "NUMERADO",          4, True,  "Numeración de piezas."),
    ("F8", "ESTAMPADO/BORDADO", 5, False, "Opcional. Activar por OF. Registrar qué piezas van a estampado/bordado."),
    ("F9", "AUDITORIA CALIDAD", 6, False, "Opcional. Se activa automáticamente con F8. Registra resultado por pieza."),
    ("F5", "FUSIONADO",         7, True,  "No toda pieza fusiona. Registrar temperatura (°C). Rango: 150-155°C."),
    ("F6", "CALIDAD",           8, True,  "Validación de piezas. Gateway reproceso: motivo + devolver a EN_PROCESO."),
    ("F7", "HABILITADO",        9, True,  "Despacho final a Costura. Cierra el Proceso de Corte."),
]


def seed_fases_catalogo() -> int:
    """Inserta las fases faltantes en fases_catalogo. Idempotente.
    Devuelve cuántas insertó (0 si ya estaban todas)."""
    db = SessionLocal()
    creadas = 0
    try:
        existentes = {f.fase_id for f in db.query(FaseCatalogo.fase_id).all()}
        for fase_id, nombre, orden, obligatoria, descripcion in FASES_SEED:
            if fase_id in existentes:
                continue
            db.add(FaseCatalogo(
                fase_id=fase_id, nombre=nombre, proceso="CORTE",
                orden=orden, obligatoria=obligatoria, descripcion=descripcion,
            ))
            creadas += 1
        if creadas:
            db.commit()
        return creadas
    finally:
        db.close()
