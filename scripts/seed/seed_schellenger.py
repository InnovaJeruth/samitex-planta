"""
Piloto: carga la familia Schellenger (Modern + Slim) al catálogo desde la data
real de las fichas técnicas + SAP.

Cada código SAP = una prenda (Camino 1: un material = un color). Se crean las
prendas con material_sap, código, nombre, color, fit y sus tallas (SKUs).
La ficha técnica (piezas / materiales / avíos) se completa aparte → estado_ficha=PENDIENTE.

Uso:  python seed_schellenger.py   (idempotente: salta las que ya existan por material_sap)
"""
from app.database.connection import SessionLocal
# Importar todos los modelos para que el registro de mappers esté completo
import app.models.usuario, app.models.of, app.models.pieza, app.models.fase       # noqa: F401
import app.models.planta, app.models.catalogo, app.models.curva_tallas            # noqa: F401
import app.models.ingenieria, app.models.parametro, app.models.trazo, app.models.paquete  # noqa: F401
from app.models.catalogo import PrendaCatalogo, PrendaSku

TALLAS = ["14", "14½", "15", "15½", "16", "16½", "17", "17½", "18", "18½"]
COMPOSICION = "60%ALGODÓN 40%POLIESTER"

# (material_sap, codigo, nombre, color)
MODERN = [
    ("2000030874", "3LC471", "KEN",    "BLANCO"),
    ("2000030876", "3LC472", "MARK",   "BLANCO"),
    ("2000030878", "3LC473", "OWEN",   "BLANCO"),
    ("2000030880", "3LC474", "ANTON",  "CELESTE"),
    ("2000030882", "3LC475", "EKIR",   "NEGRO"),
    ("2000030884", "3LC476", "IGOR",   "AMARILLO"),
    ("2000030886", "3LC477", "MATT",   "VERDE"),
    ("2000030888", "3LC478", "HASTON", "VERDE"),
    ("2000030890", "3LC479", "REGAN",  "GRIS"),
]
SLIM = [
    ("2000030892", "3LC480", "JAMES",   "BLANCO"),
    ("2000030894", "3LC481", "BRAULIO", "BLANCO"),
    ("2000030896", "3LC482", "RISTO",   "BLANCO"),
    ("2000030898", "3LC483", "FICO",    "BLANCO"),
    ("2000030900", "3LC484", "JULIUS",  "CELESTE"),
    ("2000030902", "3LC485", "DANKER",  "CELESTE"),
    ("2000030904", "3LC486", "HAUS",    "CELESTE"),
    ("2000030906", "3LC487", "RONEL",   "CELESTE"),
    ("2000030908", "3LC488", "ANGELLO", "AZUL"),
    ("2000030910", "3LC489", "RAUL",    "AZUL"),
    ("2000030914", "3LC491", "JUSTO",   "BEIGE"),
    ("2000030916", "3LC492", "KIAN",    "ROJO"),
    ("2000030918", "3LC493", "REDFORD", "VINO"),
    ("2000030920", "3LC494", "SERGIO",  "VERDE"),
    ("2000030922", "3LC495", "DIMAS",   "PLATA"),
]


def _base(db, codigo, nombre, fit, familia):
    """Crea (o reutiliza) la prenda BASE de una familia+fit. Sin color ni material_sap."""
    existe = db.query(PrendaCatalogo).filter_by(codigo=codigo).first()
    if existe:
        return existe
    b = PrendaCatalogo(
        codigo=codigo, nombre=nombre, tipo_base="CAMISA", tipo_cliente="BASE",
        fit=fit, composicion=COMPOSICION, familia=familia,
        estado_ficha="PENDIENTE", activo=True,
    )
    db.add(b)
    db.flush()
    return b


def _variante(db, base, material_sap, codigo, nombre, color, fit, familia):
    # Si ya existe (seed previo), re-engancha a su base y no duplica.
    existe = (db.query(PrendaCatalogo).filter_by(material_sap=material_sap).first()
              or db.query(PrendaCatalogo).filter_by(codigo=codigo).first())
    if existe:
        if not existe.base_id:
            existe.base_id = base.id
            existe.familia = familia
        return False
    p = PrendaCatalogo(
        codigo=codigo,
        nombre=f"CAMISA {nombre} {codigo}",
        tipo_base="CAMISA",
        tipo_cliente="MARCA",
        base_id=base.id,           # ← engancha a su base
        fit=fit,
        color=color,
        composicion=COMPOSICION,
        material_sap=material_sap,
        familia=familia,
        estado_ficha="PENDIENTE",
        activo=True,
    )
    db.add(p)
    db.flush()
    for i, t in enumerate(TALLAS):
        db.add(PrendaSku(prenda_catalogo_id=p.id, talla=t, orden=i, activo=True))
    return True


def main():
    db = SessionLocal()
    creadas = 0
    try:
        base_mf = _base(db, "SCH-MF", "CAMISA SCHELLENGER MODERN (BASE)", "MODERN", "SCHELLENGER MODERN")
        base_sf = _base(db, "SCH-SF", "CAMISA SCHELLENGER SLIM (BASE)", "SLIM", "SCHELLENGER SLIM")
        for m, c, n, col in MODERN:
            if _variante(db, base_mf, m, c, n, col, "MODERN", "SCHELLENGER MODERN"):
                creadas += 1
        for m, c, n, col in SLIM:
            if _variante(db, base_sf, m, c, n, col, "SLIM", "SCHELLENGER SLIM"):
                creadas += 1
        db.commit()
        bases = db.query(PrendaCatalogo).filter_by(tipo_cliente="BASE").count()
        variantes = db.query(PrendaCatalogo).filter(PrendaCatalogo.tipo_cliente != "BASE").count()
        skus = db.query(PrendaSku).count()
        print(f"Variantes Schellenger creadas: {creadas}")
        print(f"Bases: {bases} · Variantes: {variantes} · SKUs (tallas): {skus}")
    except Exception as e:
        db.rollback()
        print("ERROR:", e)
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
