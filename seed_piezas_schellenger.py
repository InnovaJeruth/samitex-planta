"""
Carga las 21 piezas de la Schellenger Modern (del checklist FR) en la BASE SCH-MF.
Las variantes de color heredan estas piezas (no se copian).

Uso:  python seed_piezas_schellenger.py   (idempotente: si la base ya tiene piezas, no repite)
"""
from app.database.connection import SessionLocal
import app.models.usuario, app.models.of, app.models.pieza, app.models.fase       # noqa: F401
import app.models.planta, app.models.catalogo, app.models.curva_tallas            # noqa: F401
import app.models.ingenieria, app.models.parametro, app.models.trazo, app.models.paquete  # noqa: F401
from app.models.catalogo import PrendaCatalogo
from app.models.pieza import PlantillaPieza

# (nombre, tejido, cantidad, fusiona, codigo)  — del checklist Schellenger Modern 3LC471
PIEZAS = [
    ("ESPALDA",                 "TELA",      1, False, "3LC471 73"),
    ("DELANTERO DERECHO",       "TELA",      1, False, "3LC471 26"),
    ("DELANTERO IZQUIERDO",     "TELA",      1, False, "3LC471 25"),
    ("MANGA LARGA",             "TELA",      2, False, "3LC471 29"),
    ("CANESU",                  "TELA",      2, False, "3LC471 72"),
    ("PECHERA IZQUIERDA",       "TELA",      1, True,  "3LC471 14"),
    ("PUÑO EXTERIOR",           "TELA",      2, True,  "3LC471 10"),
    ("PUÑO INTERIOR",           "TELA",      2, False, "3LC471 79"),
    ("PATA INTERIOR",           "TELA",      1, False, "3LC471 28"),
    ("CUELLO INTERIOR",         "TELA",      1, False, "3LC471 16"),
    ("CUELLO EXTERIOR",         "TELA",      1, True,  "3LC471 22"),
    ("BOLSILLO",                "TELA",      1, False, "3LC471 20"),
    ("PIE DE CUELLO EXTERIOR",  "TELA",      1, True,  "3LC471 PDC"),
    ("ENTRETELA DE PATA",       "ENTRETELA", 1, False, "3LC471 27"),
    ("ENTRETELA DE CUELLO",     "ENTRETELA", 1, True,  "3LC471 17"),
    ("PECHERA IZQUIERDA (ENT)", "ENTRETELA", 1, False, "3LC471 15"),
    ("ENTRETELA DE PUÑO",       "REFUERZO",  2, False, "3LC471 11"),
    ("ENTRETELA DE REFUERZO",   "REFUERZO",  1, False, "3LC471 18"),
    ("BOLSA BARBILLA",          "TELA",      2, False, "3LC471 DE"),
    ("YUGO EXTERIOR",           "TELA",      2, False, "3LC471 23"),
    ("YUGO INTERIOR",           "TELA",      2, False, "3LC471 24"),
]


def main():
    db = SessionLocal()
    try:
        base = db.query(PrendaCatalogo).filter_by(codigo="SCH-MF").first()
        if not base:
            print("No existe la base SCH-MF. Corre primero seed_schellenger.py")
            return
        if base.plantilla_piezas:
            print(f"La base {base.codigo} ya tiene {len(base.plantilla_piezas)} piezas. No se repite.")
            return
        for i, (nombre, tejido, cant, fus, cod) in enumerate(PIEZAS):
            db.add(PlantillaPieza(
                prenda_catalogo_id=base.id,
                codigo=cod,
                nombre=nombre,
                material_default=tejido,
                cantidad_x_prenda=cant,
                fusionado_default=fus,
                orden=i,
            ))
        base.estado_ficha = "PENDIENTE"   # aún faltan materiales/avíos (ingeniería)
        db.commit()
        print(f"Cargadas {len(PIEZAS)} piezas en la base {base.codigo}.")
        print("Las variantes Modern heredan estas piezas (hereda_ficha=True).")
    except Exception as e:
        db.rollback()
        print("ERROR:", e)
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
