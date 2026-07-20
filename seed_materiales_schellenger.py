"""
Carga materiales (MP) + avíos en las bases Schellenger (SCH-MF y SCH-SF) desde el HDC.
Las variantes de color los heredan (no se copian).

Códigos '400000XXX' = placeholder (pendiente de código SAP real → ingeniería lo completa).

Uso:  python seed_materiales_schellenger.py   (idempotente: si la base ya tiene MP, no repite)
"""
from app.database.connection import SessionLocal
import app.models.usuario, app.models.of, app.models.pieza, app.models.fase       # noqa: F401
import app.models.planta, app.models.catalogo, app.models.curva_tallas            # noqa: F401
import app.models.ingenieria, app.models.parametro, app.models.trazo, app.models.paquete  # noqa: F401
from app.models.catalogo import PrendaCatalogo, CatalogoMp, CatalogoAvio

PEND = "400000XXX"  # placeholder de código SAP pendiente

# --- Materiales (MP) por base: (nombre, tipo, ancho, consumo, %adic, precio, codigo) ---
MP_MODERN = [
    ("50%COTTON 50%POLYESTER",                    "TELA_PRINCIPAL", 1.48, 1.42, 0.01, 10.00, PEND),
    ("TELA CONTRASTE A - PIE DE CUELLO",          "TELA_PRINCIPAL", 1.50, 0.03, 0.01, 12.00, PEND),
    ("ENTRETELA 3161 100%ALG 145GR BLANCO SOFT",  "ENTRETELA",      1.08, 0.10, 0.01,  5.63, "4000022752"),
    ("ENTRETELA 3173 100%ALG 170GR BLANCO SOFT",  "ENTRETELA",      1.08, 0.08, 0.01,  5.99, "4000022753"),
]
MP_SLIM = [
    ("50% COTTON 47%POLYESTER 3% SP",             "TELA_PRINCIPAL", 1.48, 1.42, 0.01, 10.00, PEND),
    ("TELA CONTRASTE A - PIE DE CUELLO",          "TELA_PRINCIPAL", 1.50, 0.03, 0.01, 12.00, PEND),
    ("ENTRETELA 3161 100%ALG 145GR BLANCO SOFT",  "ENTRETELA",      1.08, 0.10, 0.01,  5.63, "4000022752"),
    ("ENTRETELA 3173 100%ALG 170GR BLANCO SOFT",  "ENTRETELA",      1.08, 0.08, 0.01,  5.99, "4000022753"),
]

# --- Avíos por base: (seccion, nombre, unidad, consumo, codigo) ---
AVIOS_COMUNES = [
    ("COSTURA",  "HILO CHINO 40/2",                              "Cono", 125,  PEND),
    ("COSTURA",  "HILO CHINO 40/2 - etiquetas",                  "Cono", 0.35, PEND),
    ("COSTURA",  "BARBILLA STX0101 6.50X1CM",                    "Unid", 2,    "40000227721"),
    ("COSTURA",  "BOTON DICHA C/LOGO 14L",                       "Gruesa", 3,  PEND),
    ("COSTURA",  "BOTON DICHA C/LOGO 18L",                       "Gruesa", 12, PEND),
    ("COSTURA",  "ETIQUETA DE COMPOSICION Y CUIDADO",            "Unid", 1,    "IMPRIMIR"),
    ("COSTURA",  "ETIQUETA DE CODIGO DE BARRA",                  "Unid", 1,    "IMPRIMIR"),
    ("ACABADOS", "ALMA CUELLO 46.0 X 3.2 CM DUPLEX",             "Unid", 1,    "4000004197"),
    ("ACABADOS", "PAPEL DE COPIA RESMA",                         "Unid", 1,    "4000004922"),
    ("ACABADOS", "ALMA CAMISA (V2) GRPH C-26",                   "Unid", 1,    "4000004200"),
    ("ACABADOS", "CLIP PLAST STX0122 3.3X1.9CM",                 "Unid", 1,    "4000022724"),
    ("ACABADOS", "COLLARIN STX0113 3.2X48CM",                    "Unid", 1,    "4000022722"),
    ("ACABADOS", "MARIPOSA STX0120 3.2X11CM",                    "Unid", 1,    "4000022723"),
    ("ACABADOS", "HANG TAG CAMISA 72X100 FOLK18",                "Unid", 1,    "4000022869"),
    ("ACABADOS", "HANG TAG HECHO EN PERU",                       "Unid", 1,    "4000020963"),
    ("ACABADOS", "CLIP 1 COCODRILLO",                            "Unid", 1,    "4000022720"),
    ("ACABADOS", "BOLSA CAMISA JH V-TAPER (27X35)",              "Unid", 1,    "4000023037"),
    ("ACABADOS", "FONDO BARNIZADO P/CAMISA JH DUPLEX 18",        "Unid", 1,    "4000004383"),
    ("ACABADOS", "TAPA PLATEADA P/CAMISA JH DUPLEX 14",          "Unid", 1,    "4000004233"),
    ("ACABADOS", "HILO CARMENCITA 999 NEGRO",                    "mt.",  1,    PEND),
    ("EMBALAJE", "CAJA EMBALAJE #2 CAMISA (40 UNID)",            "Unid", 1,    PEND),
    ("EMBALAJE", "CINTA DE EMBALAJE C500 2\"X110YDA",            "mt.",  1,    PEND),
]
# Avíos que difieren por fit (etiqueta de marca, etiqueta de fit, tallero, cintillo)
AVIOS_MODERN = AVIOS_COMUNES + [
    ("COSTURA",  "ETIQUETA TEJIDA JH 25X72MM NEGRO",            "Unid", 1, "4000004952"),
    ("COSTURA",  "ETIQUETA TEJ SPECIAL COLLECTION NEGRO",       "Unid", 1, "4000005238"),
    ("COSTURA",  "ETIQUETA DE TALLA",                           "Unid", 1, "4000005379"),
    ("ACABADOS", "TALLERO JH MODERN FIT",                       "Unid", 1, "4000002960"),
    ("ACABADOS", "CINTILLO CAM. JH COLLECTION 53X1.3",          "Unid", 1, PEND),
]
AVIOS_SLIM = AVIOS_COMUNES + [
    ("COSTURA",  "ETIQUETA MARCA JH NEGRO (25X72)",             "Unid", 1, "4000005051"),
    ("COSTURA",  "ETIQUETA SLIM FIT",                           "Unid", 1, "4000004983"),
    ("COSTURA",  "ETIQUETA DE TALLA",                           "Unid", 1, "4000005399"),
    ("ACABADOS", "TALLERO JH SLIM FIT",                         "Unid", 1, "4000002951"),
    ("ACABADOS", "CINTILLO MATE SLIM FIT 53X1.3",               "Unid", 1, "4000004239"),
]


def _cargar(db, base, mps, avios):
    if base.materiales or base.avios:
        print(f"  {base.codigo} ya tiene ficha de materiales/avíos. No se repite.")
        return 0
    n = 0
    for i, (nom, tipo, ancho, cons, adic, precio, cod) in enumerate(mps):
        db.add(CatalogoMp(prenda_catalogo_id=base.id, nombre=nom, tipo=tipo,
                          ancho_referencia=ancho, consumo_unitario=cons, pct_adicional=adic,
                          unidad_medida="mt.", precio_referencia=precio,
                          codigo_interno=cod, orden=i, activo=True)); n += 1
    for i, (sec, nom, um, cons, cod) in enumerate(avios):
        db.add(CatalogoAvio(prenda_catalogo_id=base.id, seccion=sec, nombre=nom,
                            unidad_medida=um, consumo_unitario=cons,
                            codigo_interno=cod, orden=i, activo=True)); n += 1
    return n


def main():
    db = SessionLocal()
    try:
        base_mf = db.query(PrendaCatalogo).filter_by(codigo="SCH-MF").first()
        base_sf = db.query(PrendaCatalogo).filter_by(codigo="SCH-SF").first()
        if not base_mf or not base_sf:
            print("Faltan las bases SCH-MF/SCH-SF. Corre primero seed_schellenger.py")
            return
        total = 0
        print("Base SCH-MF (Modern):")
        total += _cargar(db, base_mf, MP_MODERN, AVIOS_MODERN)
        print("Base SCH-SF (Slim):")
        total += _cargar(db, base_sf, MP_SLIM, AVIOS_SLIM)
        db.commit()
        print(f"\nCargados {total} ítems (MP + avíos) en las bases. Las variantes los heredan.")
    except Exception as e:
        db.rollback()
        print("ERROR:", e)
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
