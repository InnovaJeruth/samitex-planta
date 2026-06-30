"""
Script: poblar_catalogo_camisa.py
Carga CAMISA VESTIR MANGA LARGA BASE + variante SCHELLENGER en el catalogo Samitex.

Ejecutar desde la raiz del proyecto:
    python poblar_catalogo_camisa.py

Requiere que la DB este accesible y las migraciones aplicadas.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database.connection import SessionLocal
from app.models.catalogo import (
    PrendaCatalogo, CatalogoMp, CatalogoAvio, PrendaSku,
    PrendaAvioConfig, PrendaMpConfig,
)

db = SessionLocal()

# ─────────────────────────────────────────────
# 1. CAMISA VESTIR MANGA LARGA — BASE
# ─────────────────────────────────────────────
base = db.query(PrendaCatalogo).filter_by(codigo='CAM-BASE-001').first()
if not base:
    base = PrendaCatalogo(
        codigo         = 'CAM-BASE-001',
        nombre         = 'CAMISA VESTIR MANGA LARGA',
        tipo_base      = 'CAMISA',
        tipo_cliente   = 'BASE',
        descripcion    = 'Camisa vestir manga larga — estructura base común a todas las variantes',
        creado_por_rol = 'ADMIN',
    )
    db.add(base)
    db.flush()
    print(f"  Prenda BASE creada: id={base.id}")
else:
    print(f"  Prenda BASE ya existe: id={base.id}")

# ─────────────────────────────────────────────
# 2. MATERIA PRIMA (sección CORTE del Excel)
# ─────────────────────────────────────────────
MP_BASE = [
    # tipo, nombre, codigo_sap, proveedor, procedencia, ancho, consumo, pct_adic, unidad, moneda, precio, orden
    ('TELA_PRINCIPAL', 'TELA PRINCIPAL CAMISA (genérica)',       '400000XXX',  'TEXCORP',                           'LOCAL',     1.48, 1.42, 0.01, 'mt.', 'SO', 10.00, 1),
    ('ACCESORIO',      'TELA CONTRASTE PIE DE CUELLO',           '400000XXX',  'TEXCORP',                           'LOCAL',     1.50, 0.03, 0.01, 'mt.', 'SO', 12.00, 2),
    ('ENTRETELA',      'ENTRETELA 3161 100%ALG 145GR BLANCO',    '4000022752', 'BAODINGSHI TIANMA INTERLINING CO.', 'IMPORTADO', 1.08, 0.10, 0.01, 'mt.', 'SO',  5.63, 3),
    ('ENTRETELA',      'ENTRETELA 3173 100%ALG 170GR BLANCO',    '4000022753', 'BAODINGSHI TIANMA INTERLINING CO.', 'IMPORTADO', 1.08, 0.08, 0.01, 'mt.', 'SO',  5.99, 4),
]

for tipo, nombre, codigo, proveedor, proc, ancho, consumo, pct, unidad, moneda, precio, orden in MP_BASE:
    exists = db.query(CatalogoMp).filter_by(prenda_catalogo_id=base.id, nombre=nombre).first()
    if not exists:
        db.add(CatalogoMp(
            prenda_catalogo_id = base.id,
            tipo               = tipo,
            nombre             = nombre,
            codigo_interno     = codigo,
            proveedor          = proveedor,
            procedencia        = proc,
            ancho_referencia   = ancho,
            consumo_unitario   = consumo,
            pct_adicional      = pct,
            unidad_medida      = unidad,
            moneda             = moneda,
            precio_referencia  = precio,
            orden              = orden,
        ))
        print(f"  MP agregada: {nombre}")

# ─────────────────────────────────────────────
# 3. AVÍOS BASE (COSTURA + ACABADOS + EMBALAJE)
# ─────────────────────────────────────────────
AVIOS_BASE = [
    # seccion, nombre, codigo, proveedor, proc, unidad_med, consumo, pct, unidad_compra, moneda, precio, orden
    # COSTURA
    ('COSTURA', 'HILO CHINO 40/2',                             '400000XXX',  'HILOS & DESARROLLOS S.A.C',  'LOCAL', 'mt.',  125.0,  0.01, 'Cono',   'SO',  2.97, 1),
    ('COSTURA', 'HILO CHINO 40/2 ETIQUETAS',                   '400000XXX',  'HILOS & DESARROLLOS S.A.C',  'LOCAL', 'mt.',  0.35,   0.01, 'Cono',   'SO',  2.97, 2),
    ('COSTURA', 'STX0101 BARBILLA 6.50X1CM PP COMPAC TRAN',    '40000227721','COMERCIAL PASAMANERÍAS',      'LOCAL', 'Unid', 2.0,    0.01, 'Millar', 'SO', 20.00, 3),
    ('COSTURA', 'BOTON DICHA C/LOGO 14L',                      '400000XXX',  'LR MODA & ACCESORIOS TEXTIL','LOCAL', 'Unid', 3.0,    0.01, 'Gruesa', 'SO', 11.52, 4),
    ('COSTURA', 'BOTON DICHA C/LOGO 18L',                      '400000XXX',  'LR MODA & ACCESORIOS TEXTIL','LOCAL', 'Unid', 12.0,   0.01, 'Gruesa', 'SO', 11.52, 5),
    ('COSTURA', 'ETIQUETA DE TALLA',                            '4000005379', 'TEXTILES SAN MIGUEL S.A.C',  'LOCAL', 'Unid', 1.0,    0.01, 'Millar', 'SO', 30.00, 6),
    ('COSTURA', 'ETIQUETA DE COMPOSICION Y CUIDADO',            'IMPRIMIR',   'SAMITEX CORTE',              'LOCAL', 'Unid', 1.0,    0.01, 'Millar', 'DO', 20.00, 7),
    ('COSTURA', 'ETIQUETA CODIGO DE BARRA NYLON BLANCO',        'IMPRIMIR',   'SAMITEX CORTE',              'LOCAL', 'Unid', 1.0,    0.01, 'Millar', 'DO', 20.00, 8),
    # ACABADOS
    ('ACABADOS','ALMA CUELLO 46.0 X 3.2 CM DUPLEX RC C18',     '4000004197', 'DISTRIBUIDORA GALVIC S.R.L', 'LOCAL', 'Unid', 1.0,    0.01, 'Millar', 'SO', 70.00,  1),
    ('ACABADOS','PAPEL DE COPIA RESMA',                         '4000004922', 'DISTRIBUIDORA GALVIC S.R.L', 'LOCAL', 'Unid', 1.0,    0.01, 'Millar', 'SO', 60.00,  2),
    ('ACABADOS','ALMA CAMISA V2 GRPH C-26 36.20 X 23.30',      '4000004200', 'INDUSTRIAS DEL ENVASE S.A',  'LOCAL', 'Unid', 1.0,    0.01, 'Millar', 'SO', 270.00, 3),
    ('ACABADOS','STX0122 CLIP PLAST 3.3X1.9CM PP COMP TRA',    '4000022724', 'COMERCIAL PASAMANERIAS',     'LOCAL', 'Unid', 1.0,    0.01, 'Millar', 'SO', 22.60,  4),
    ('ACABADOS','STX0113 COLLARIN 3.2X48CM PP COMPAC TRAN',    '4000022722', 'COMERCIAL PASAMANERIAS',     'LOCAL', 'Unid', 1.0,    0.01, 'Millar', 'SO', 105.35, 5),
    ('ACABADOS','STX0120 MARIPOSA 3.2X11CM PP COMPAC TRAN',    '4000022723', 'COMERCIAL PASAMANERIAS',     'LOCAL', 'Unid', 1.0,    0.01, 'Millar', 'SO', 20.07,  6),
    ('ACABADOS','CLIP 1 COCODRILLO',                            '4000022720', 'COMERCIAL PASAMANERIAS',     'LOCAL', 'Unid', 3.0,    0.01, 'Millar', 'SO', 20.00,  7),
    ('ACABADOS','HILO CARMENCITA 999 NEGRO',                    '400000XXX',  'COMERCIAL PASAMANERIAS',     'LOCAL', 'mt.',  0.2,    0.01, 'Cono',   'SO', 12.63,  8),
    # EMBALAJE
    ('EMBALAJE','CAJA EMBALAJE #2 CAMISA (40 UNID)',            '400000XXX',  'ING. EN CARTONES & PAPELES','LOCAL', 'Unid', 0.04167,0.01, 'Unid',   'SO',  4.86,  1),
    ('EMBALAJE','CINTA DE EMBALAJE C500 2"X110YDA HABANO',      '400000XXX',  'ING. EN CARTONES & PAPELES','LOCAL', 'mt.',  0.003,  0.01, 'mt.',    'SO',  3.50,  2),
]

for seccion, nombre, codigo, proveedor, proc, unidad, consumo, pct, unidad_c, moneda, precio, orden in AVIOS_BASE:
    exists = db.query(CatalogoAvio).filter_by(prenda_catalogo_id=base.id, nombre=nombre).first()
    if not exists:
        db.add(CatalogoAvio(
            prenda_catalogo_id = base.id,
            seccion            = seccion,
            nombre             = nombre,
            codigo_interno     = codigo,
            proveedor          = proveedor,
            procedencia        = proc,
            unidad_medida      = unidad,
            consumo_unitario   = consumo,
            pct_adicional      = pct,
            unidad_compra      = unidad_c,
            moneda             = moneda,
            precio             = precio,
            orden              = orden,
        ))
        print(f"  Avío BASE [{seccion}]: {nombre}")

db.commit()
print("\n✓ CAMISA BASE cargada")

# ─────────────────────────────────────────────
# 4. CAMISA SCHELLENGER — MODERN FIT
# ─────────────────────────────────────────────
def crear_variante_schellenger(codigo, nombre, fit, tela_nombre, tela_consumo, tela_comp, tallero_nombre, tallero_precio):
    var = db.query(PrendaCatalogo).filter_by(codigo=codigo).first()
    if not var:
        var = PrendaCatalogo(
            codigo         = codigo,
            nombre         = nombre,
            tipo_base      = 'CAMISA',
            tipo_cliente   = 'MARCA',
            fit            = fit,
            descripcion    = f'Camisa Schellenger {fit} — {tela_comp}',
            creado_por_rol = 'ADMIN',
        )
        db.add(var)
        db.flush()
        print(f"\n  Variante creada: {nombre} id={var.id}")
    else:
        print(f"\n  Variante ya existe: {nombre} id={var.id}")

    # Avíos específicos Schellenger para esta variante
    # (se agregan a la BASE como avíos adicionales, luego config en variante)
    AVIOS_SCH = [
        ('COSTURA', 'ETIQUETA TEJIDA JH 25X72MM NEGRO',              '4000004952', 'TEXTILES SAN MIGUEL S.A.C', 'LOCAL', 'Unid', 1.0,  0.01, 'Millar', 'SO',  80.00, 9),
        ('COSTURA', 'ETIQUETA TEJIDA SPECIAL COLLECTION NEGRO',       '4000005238', 'TEXTILES SAN MIGUEL S.A.C', 'LOCAL', 'Unid', 1.0,  0.01, 'Millar', 'SO',  60.00, 10),
        ('ACABADOS',tallero_nombre,                                    '4000002960', 'IDEPRINT S.A.C',            'LOCAL', 'Unid', 1.0,  0.01, 'Millar', 'SO', tallero_precio, 9),
        ('ACABADOS','CINTILLO CAMISA JH COLLECTION 53X1.3CM NEGRO',   '400000XXX',  'COMERCIAL PASAMANERIAS',    'LOCAL', 'Unid', 1.0,  0.01, 'Millar', 'SO',  32.67, 10),
        ('ACABADOS','HANG TAG CAMISA 72X100 FOLK18 LAM MATE',         '4000022869', 'IDEPRINT S.A.C',            'LOCAL', 'Unid', 1.0,  0.01, 'Millar', 'SO', 105.00, 11),
        ('ACABADOS','ETIQUETA AUTOADHESIVA TERMICO 2X1 2 COLUMNAS',   '400000XXX',  'IDEPRINT S.A.C',            'LOCAL', 'Unid', 1.0,  0.01, 'Millar', 'DO',   1.50, 12),
        ('ACABADOS','HANG TAG HECHO EN PERU',                         '4000020963', 'IDEPRINT S.A.C',            'LOCAL', 'Unid', 1.0,  0.01, 'Millar', 'SO',  58.50, 13),
        ('ACABADOS','BOLSA CAMISA JH V-TAPER 27X35 PLATA OSCURO',     '4000023037', 'CONTOMETROS ESPECIALES',    'LOCAL', 'Unid', 1.0,  0.01, 'Millar', 'SO', 170.00, 14),
        ('ACABADOS','HANG TAG CAMISA PRECIO',                         '400000XXX',  'IDEPRINT S.A.C',            'LOCAL', 'Unid', 1.0,  0.01, 'Millar', 'SO', 100.00, 15),
        ('ACABADOS','FONDO BARNIZADO CAMISA JH DUPLEX 18',            '4000004383', None,                        'LOCAL', 'Unid', 1.0,  0.01, 'Millar', 'SO', 693.00, 16),
        ('ACABADOS','TAPA PLATEADA CAMISA JH DUPLEX 14',              '4000004233', None,                        'LOCAL', 'Unid', 1.0,  0.01, 'Millar', 'SO', 567.00, 17),
    ]

    # Agregar avíos Schellenger a la BASE (si no existen ya)
    for seccion, nombre_a, codigo, proveedor, proc, unidad, consumo, pct, unidad_c, moneda, precio, orden in AVIOS_SCH:
        exists = db.query(CatalogoAvio).filter_by(prenda_catalogo_id=base.id, nombre=nombre_a).first()
        if not exists:
            avio = CatalogoAvio(
                prenda_catalogo_id = base.id,
                seccion            = seccion,
                nombre             = nombre_a,
                codigo_interno     = codigo,
                proveedor          = proveedor,
                procedencia        = proc,
                unidad_medida      = unidad,
                consumo_unitario   = consumo,
                pct_adicional      = pct,
                unidad_compra      = unidad_c,
                moneda             = moneda,
                precio             = precio,
                orden              = orden,
            )
            db.add(avio)
            db.flush()
            print(f"  Avío Schellenger [{seccion}]: {nombre_a}")

    # Override MP tela principal para esta variante
    mp_tela = db.query(CatalogoMp).filter_by(prenda_catalogo_id=base.id, tipo='TELA_PRINCIPAL').first()
    if mp_tela:
        cfg_exists = db.query(PrendaMpConfig).filter_by(prenda_id=var.id, mp_id=mp_tela.id).first()
        if not cfg_exists:
            db.add(PrendaMpConfig(
                prenda_id         = var.id,
                mp_id             = mp_tela.id,
                consumo_override  = tela_consumo,
                notas             = f'{fit}: {tela_comp}',
            ))
            print(f"  Override tela: {tela_comp} consumo={tela_consumo}")

    # SKUs comunes Schellenger
    tallas = ['S', 'M', 'L', 'XL', 'XXL']
    for idx, talla in enumerate(tallas):
        cod_sku = f'{codigo}-{talla}'
        sk_exists = db.query(PrendaSku).filter_by(prenda_catalogo_id=var.id, talla=talla).first()
        if not sk_exists:
            db.add(PrendaSku(prenda_catalogo_id=var.id, talla=talla, codigo_sku=cod_sku, orden=idx))
            print(f"  SKU: {talla}")

    db.commit()
    return var

crear_variante_schellenger(
    codigo='CAM-SCH-MF-001',
    nombre='CAMISA SCHELLENGER MODERN FIT',
    fit='MODERN_FIT',
    tela_nombre='TELA PRINCIPAL 50%COTTON 50%POLYESTER',
    tela_consumo=1.42,
    tela_comp='50%COTTON 50%POLYESTER',
    tallero_nombre='TALLERO JH MODERN FIT',
    tallero_precio=160.0,
)

crear_variante_schellenger(
    codigo='CAM-SCH-SF-001',
    nombre='CAMISA SCHELLENGER SLIM FIT',
    fit='SLIM_FIT',
    tela_nombre='TELA PRINCIPAL 50%COTTON 47%POLYESTER 3%SPANDEX',
    tela_consumo=1.42,
    tela_comp='50%COTTON 47%POLYESTER 3%SPANDEX',
    tallero_nombre='TALLERO JH SLIM FIT',
    tallero_precio=160.0,
)

db.close()
print("\n✓ Listo. Catalogo cargado:")
print("  - CAMISA VESTIR MANGA LARGA (BASE) con 4 MP + 18 Avíos")
print("  - CAMISA SCHELLENGER MODERN FIT (MARCA) con override tela + 5 SKUs")
print("  - CAMISA SCHELLENGER SLIM FIT (MARCA) con override tela + 5 SKUs")
