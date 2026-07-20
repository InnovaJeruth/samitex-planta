-- ============================================================
-- CAMISA SCHELLENGER — Seed para Supabase (PostgreSQL)
-- Generado: 2026-07-01
-- Variantes: 3LC471–3LC479 (9 colores)
-- ============================================================
-- INSTRUCCIONES:
--   1. Ejecutar SCRIPT_1 primero (limpia variantes existentes)
--   2. Ejecutar SCRIPT_2 (inserta BASE + piezas + MP + avíos + variantes + SKUs)
--   Puedes correr ambos en el SQL Editor de Supabase uno seguido del otro.
-- ============================================================


-- ============================================================
-- SCRIPT 1 — Eliminar variantes existentes (tipo_cliente != 'BASE')
-- ============================================================

-- Eliminar SKUs de variantes
DELETE FROM prenda_skus
WHERE prenda_catalogo_id IN (
    SELECT id FROM prendas_catalogo WHERE tipo_cliente != 'BASE'
);

-- Eliminar configuraciones de MP por SKU
DELETE FROM prenda_sku_mp_config
WHERE prenda_catalogo_id IN (
    SELECT id FROM prendas_catalogo WHERE tipo_cliente != 'BASE'
);

-- Eliminar configuraciones de avíos por SKU
DELETE FROM prenda_sku_avio_config
WHERE prenda_catalogo_id IN (
    SELECT id FROM prendas_catalogo WHERE tipo_cliente != 'BASE'
);

-- Eliminar config MP de variantes
DELETE FROM prenda_mp_config
WHERE prenda_catalogo_id IN (
    SELECT id FROM prendas_catalogo WHERE tipo_cliente != 'BASE'
);

-- Eliminar config avíos de variantes
DELETE FROM prenda_avio_config
WHERE prenda_catalogo_id IN (
    SELECT id FROM prendas_catalogo WHERE tipo_cliente != 'BASE'
);

-- Eliminar MP de variantes
DELETE FROM catalogo_mp
WHERE prenda_catalogo_id IN (
    SELECT id FROM prendas_catalogo WHERE tipo_cliente != 'BASE'
);

-- Eliminar avíos de variantes
DELETE FROM catalogo_avios
WHERE prenda_catalogo_id IN (
    SELECT id FROM prendas_catalogo WHERE tipo_cliente != 'BASE'
);

-- Eliminar documentos de variantes
DELETE FROM prenda_documentos
WHERE prenda_catalogo_id IN (
    SELECT id FROM prendas_catalogo WHERE tipo_cliente != 'BASE'
);

-- Eliminar hojas de costos de variantes
DELETE FROM hojas_costos_lineas
WHERE hoja_id IN (
    SELECT hc.id FROM hojas_costos hc
    JOIN prendas_catalogo pc ON hc.prenda_catalogo_id = pc.id
    WHERE pc.tipo_cliente != 'BASE'
);
DELETE FROM hojas_costos
WHERE prenda_catalogo_id IN (
    SELECT id FROM prendas_catalogo WHERE tipo_cliente != 'BASE'
);

-- Finalmente eliminar las variantes
DELETE FROM prendas_catalogo WHERE tipo_cliente != 'BASE';


-- ============================================================
-- SCRIPT 2 — Insertar CAMISA SCHELLENGER BASE + variantes
-- ============================================================

DO $$
DECLARE
    base_id       INTEGER;
    v1 INTEGER; v2 INTEGER; v3 INTEGER; v4 INTEGER; v5 INTEGER;
    v6 INTEGER; v7 INTEGER; v8 INTEGER; v9 INTEGER;

BEGIN

-- ── 1. BASE ────────────────────────────────────────────────────

INSERT INTO prendas_catalogo (codigo, nombre, tipo_base, tipo_cliente, composicion, activo)
VALUES ('CAMISA-SCHELL', 'CAMISA SCHELLENGER', 'CAMISA', 'BASE',
        '60%ALGODÓN 40%POLIESTER', TRUE)
ON CONFLICT (codigo) DO UPDATE SET nombre = EXCLUDED.nombre
RETURNING id INTO base_id;

-- ── 2. Plantilla de piezas (21 piezas) ────────────────────────

INSERT INTO plantilla_piezas
    (prenda_catalogo_id, nombre, material_default, cantidad_x_prenda, fusionado_default, orden)
VALUES
    (base_id, 'ESPALDA',                    'TELA',       1, FALSE,  1),
    (base_id, 'DELANTERO DERECHO',          'TELA',       1, FALSE,  2),
    (base_id, 'DELANTERO IZQUIERDO',        'TELA',       1, FALSE,  3),
    (base_id, 'MANGA LARGA',               'TELA',       2, FALSE,  4),
    (base_id, 'CANESU',                    'TELA',       2, FALSE,  5),
    (base_id, 'PECHERA IZQUIERDA',         'TELA',       1, TRUE,   6),
    (base_id, 'PUÑO EXTERIOR',             'TELA',       2, TRUE,   7),
    (base_id, 'PUÑO INTERIOR',             'TELA',       2, FALSE,  8),
    (base_id, 'PATA INTERIOR',             'TELA',       1, FALSE,  9),
    (base_id, 'CUELLO INTERIOR',           'TELA',       1, FALSE, 10),
    (base_id, 'CUELLO EXTERIOR',           'TELA',       1, TRUE,  11),
    (base_id, 'BOLSILLO',                  'TELA',       1, FALSE, 12),
    (base_id, 'PIE DE CUELLO EXTERIOR',    'TELA',       1, TRUE,  13),
    (base_id, 'ENTRETELA DE PATA',         'ENTRETELA',  1, FALSE, 14),
    (base_id, 'ENTRETELA DE CUELLO',       'ENTRETELA',  1, TRUE,  15),
    (base_id, 'PECHERA IZQUIERDA ENT.',    'ENTRETELA',  1, FALSE, 16),
    (base_id, 'ENTRETELA DE PUÑO',         'REFUERZO',   2, FALSE, 17),
    (base_id, 'ENTRETELA DE REFUERZO',     'REFUERZO',   1, FALSE, 18),
    (base_id, 'BOLSA BARBILLA',            'TELA',       2, FALSE, 19),
    (base_id, 'YUGO EXTERIOR 2 3/4"',     'TELA',       2, FALSE, 20),
    (base_id, 'YUGO INTERIOR 1 3/8"',     'TELA',       2, FALSE, 21);

-- ── 3. Materia Prima (4 telas/entretelas) ─────────────────────

INSERT INTO catalogo_mp
    (prenda_catalogo_id, nombre, tipo, ancho_referencia, consumo_unitario, pct_adicional,
     unidad_medida, unidad_compra, factor_conversion, codigo_interno,
     proveedor, procedencia, moneda, precio_referencia, orden, activo)
VALUES
    (base_id, '50% COTTON 47%POLYESTER 3% SP',
     'TELA_PRINCIPAL', 1.48, 1.37, 0.01, 'mt.', 'mt.', 1,
     '400000XXX', 'TEXCORP', 'LOCAL', 'SO', 10.0, 1, TRUE),

    (base_id, 'TELA CONTRASTE — PIE DE CUELLO',
     'TELA_CONTRASTE', 1.50, 0.03, 0.01, 'mt.', 'mt.', 1,
     '400000XXX', 'TEXCORP', 'LOCAL', 'SO', 12.0, 2, TRUE),

    (base_id, 'ENTRETELA 3161 100%ALG 145GR BLANCO SOFT',
     'ENTRETELA', 1.08, 0.10, 0.01, 'mt.', 'mt.', 1,
     '4000022752', 'BAODINGSHI TIANMA INTERLINING CO.', 'IMPORTADO', 'SO', 5.63, 3, TRUE),

    (base_id, 'ENTRETELA 3173 100%ALG 170GR BLANCO SOFT',
     'ENTRETELA', 1.08, 0.08, 0.01, 'mt.', 'mt.', 1,
     '4000022753', 'BAODINGSHI TIANMA INTERLINING CO.', 'IMPORTADO', 'SO', 5.99, 4, TRUE);

-- ── 4. Avíos (13 ítems: costura + acabados) ───────────────────

INSERT INTO catalogo_avios
    (prenda_catalogo_id, seccion, nombre, codigo_interno, proveedor, procedencia,
     unidad_medida, consumo_unitario, pct_adicional, unidad_compra, factor_conversion,
     moneda, precio, orden, activo)
VALUES
    -- COSTURA
    (base_id, 'COSTURA', 'HILO CHINO 40/2',
     '400000XXX', 'HILOS & DESARROLLOS S.A.C', 'LOCAL',
     'mt.', 125, 0.01, 'Cono', 4572, 'SO', 2.97, 1, TRUE),

    (base_id, 'COSTURA', 'HILO CHINO 40/2 — ETIQUETAS',
     '400000XXX', 'HILOS & DESARROLLOS S.A.C', 'LOCAL',
     'mt.', 0.35, 0.01, 'Cono', 4572, 'SO', 2.97, 2, TRUE),

    (base_id, 'COSTURA', 'STX0101 BARBILLA 6.50X1CM PP COMPAC TRAN',
     '40000227721', 'COMERCIAL PASAMANERÍAS', 'LOCAL',
     'Unid', 2, 0.01, 'Millar', 1000, 'SO', 20.0, 3, TRUE),

    (base_id, 'COSTURA', 'BOTON DICHA C/LOGO 14L',
     '400000XXX', 'LR MODA & ACCESORIOS TEXTIL', 'LOCAL',
     'Unid', 3, 0.01, 'Gruesa', 144, 'SO', 11.52, 4, TRUE),

    (base_id, 'COSTURA', 'BOTON DICHA C/LOGO 18L',
     '400000XXX', 'LR MODA & ACCESORIOS TEXTIL', 'LOCAL',
     'Unid', 12, 0.01, 'Gruesa', 144, 'SO', 11.52, 5, TRUE),

    (base_id, 'COSTURA', 'ETIQUETA TEJIDA JH 25X72MM NEGRO',
     '4000004952', 'TEXTILES SAN MIGUEL S.A.C', 'LOCAL',
     'Unid', 1, 0.01, 'Millar', 1000, 'SO', 80.0, 6, TRUE),

    (base_id, 'COSTURA', 'ETIQUETA TEJ SPECIAL COLLECTION NEGRO',
     '4000005238', 'TEXTILES SAN MIGUEL S.A.C', 'LOCAL',
     'Unid', 1, 0.01, 'Millar', 1000, 'SO', 60.0, 7, TRUE),

    (base_id, 'COSTURA', 'ETIQUETA DE TALLA',
     '4000005379', 'TEXTILES SAN MIGUEL S.A.C', 'LOCAL',
     'Unid', 1, 0.01, 'Millar', 1000, 'SO', 30.0, 8, TRUE),

    (base_id, 'COSTURA', 'ETIQUETA DE COMPOSICION Y CUIDADO',
     'IMPRIMIR', 'SAMITEX CORTE', 'LOCAL',
     'Unid', 1, 0.01, 'Millar', 1000, 'DO', 20.0, 9, TRUE),

    (base_id, 'COSTURA', 'ETIQUETA DE CÓDIGO DE BARRA NYLON BLANCO L/NEGRO',
     'IMPRIMIR', 'SAMITEX CORTE', 'LOCAL',
     'Unid', 1, 0.01, 'Millar', 1000, 'DO', 20.0, 10, TRUE),

    -- ACABADOS
    (base_id, 'ACABADOS', 'ALMA CUELLO 46.0 X 3.2 CM DUPLEX RC C18',
     '4000004197', 'DISTRIBUIDORA GALVIC S.R.L', 'LOCAL',
     'Unid', 1, 0.01, 'Millar', 1000, 'SO', 70.0, 11, TRUE),

    (base_id, 'ACABADOS', 'PAPEL DE COPIA RESMA',
     '4000004922', 'DISTRIBUIDORA GALVIC S.R.L', 'LOCAL',
     'Unid', 1, 0.01, 'Millar', 1000, 'SO', 60.0, 12, TRUE),

    (base_id, 'ACABADOS', 'ALMA CAMISA (V2) GRPH C-26 36.20 X 23.30',
     '4000004200', 'INDUSTRIAS DEL ENVASE S.A', 'LOCAL',
     'Unid', 1, 0.01, 'Millar', 1000, 'SO', 270.0, 13, TRUE);

-- ── 5. Variantes (9 colores) ───────────────────────────────────

INSERT INTO prendas_catalogo
    (codigo, nombre, tipo_base, tipo_cliente, fit, color, composicion, activo)
VALUES ('3LC471','CAMISA SCHELLENGER KEN',    'CAMISA','MODA','MODERN FIT','BLANCO',   '60%ALGODÓN 40%POLIESTER',TRUE)
RETURNING id INTO v1;

INSERT INTO prendas_catalogo
    (codigo, nombre, tipo_base, tipo_cliente, fit, color, composicion, activo)
VALUES ('3LC472','CAMISA SCHELLENGER MARK',   'CAMISA','MODA','MODERN FIT','BLANCO',   '60%ALGODÓN 40%POLIESTER',TRUE)
RETURNING id INTO v2;

INSERT INTO prendas_catalogo
    (codigo, nombre, tipo_base, tipo_cliente, fit, color, composicion, activo)
VALUES ('3LC473','CAMISA SCHELLENGER OWEN',   'CAMISA','MODA','MODERN FIT','BLANCO',   '60%ALGODÓN 40%POLIESTER',TRUE)
RETURNING id INTO v3;

INSERT INTO prendas_catalogo
    (codigo, nombre, tipo_base, tipo_cliente, fit, color, composicion, activo)
VALUES ('3LC474','CAMISA SCHELLENGER ANTON',  'CAMISA','MODA','MODERN FIT','CELESTE',  '60%ALGODÓN 40%POLIESTER',TRUE)
RETURNING id INTO v4;

INSERT INTO prendas_catalogo
    (codigo, nombre, tipo_base, tipo_cliente, fit, color, composicion, activo)
VALUES ('3LC475','CAMISA SCHELLENGER EKIR',   'CAMISA','MODA','MODERN FIT','NEGRO',    '60%ALGODÓN 40%POLIESTER',TRUE)
RETURNING id INTO v5;

INSERT INTO prendas_catalogo
    (codigo, nombre, tipo_base, tipo_cliente, fit, color, composicion, activo)
VALUES ('3LC476','CAMISA SCHELLENGER IGOR',   'CAMISA','MODA','MODERN FIT','AMARILLO', '60%ALGODÓN 40%POLIESTER',TRUE)
RETURNING id INTO v6;

INSERT INTO prendas_catalogo
    (codigo, nombre, tipo_base, tipo_cliente, fit, color, composicion, activo)
VALUES ('3LC477','CAMISA SCHELLENGER MATT',   'CAMISA','MODA','MODERN FIT','VERDE',    '60%ALGODÓN 40%POLIESTER',TRUE)
RETURNING id INTO v7;

INSERT INTO prendas_catalogo
    (codigo, nombre, tipo_base, tipo_cliente, fit, color, composicion, activo)
VALUES ('3LC478','CAMISA SCHELLENGER HASTON', 'CAMISA','MODA','MODERN FIT','VERDE',    '60%ALGODÓN 40%POLIESTER',TRUE)
RETURNING id INTO v8;

INSERT INTO prendas_catalogo
    (codigo, nombre, tipo_base, tipo_cliente, fit, color, composicion, activo)
VALUES ('3LC479','CAMISA SCHELLENGER REGAN',  'CAMISA','MODA','MODERN FIT','GRIS',     '60%ALGODÓN 40%POLIESTER',TRUE)
RETURNING id INTO v9;

-- ── 6. SKUs — 10 tallas por variante ──────────────────────────

INSERT INTO prenda_skus (prenda_catalogo_id, talla, codigo_sku, activo, orden) VALUES
(v1,'14',  '3LC471-14',  TRUE,1),(v1,'14.5','3LC471-14.5',TRUE,2),(v1,'15',  '3LC471-15',  TRUE,3),
(v1,'15.5','3LC471-15.5',TRUE,4),(v1,'16',  '3LC471-16',  TRUE,5),(v1,'16.5','3LC471-16.5',TRUE,6),
(v1,'17',  '3LC471-17',  TRUE,7),(v1,'17.5','3LC471-17.5',TRUE,8),(v1,'18',  '3LC471-18',  TRUE,9),
(v1,'18.5','3LC471-18.5',TRUE,10);

INSERT INTO prenda_skus (prenda_catalogo_id, talla, codigo_sku, activo, orden) VALUES
(v2,'14',  '3LC472-14',  TRUE,1),(v2,'14.5','3LC472-14.5',TRUE,2),(v2,'15',  '3LC472-15',  TRUE,3),
(v2,'15.5','3LC472-15.5',TRUE,4),(v2,'16',  '3LC472-16',  TRUE,5),(v2,'16.5','3LC472-16.5',TRUE,6),
(v2,'17',  '3LC472-17',  TRUE,7),(v2,'17.5','3LC472-17.5',TRUE,8),(v2,'18',  '3LC472-18',  TRUE,9),
(v2,'18.5','3LC472-18.5',TRUE,10);

INSERT INTO prenda_skus (prenda_catalogo_id, talla, codigo_sku, activo, orden) VALUES
(v3,'14',  '3LC473-14',  TRUE,1),(v3,'14.5','3LC473-14.5',TRUE,2),(v3,'15',  '3LC473-15',  TRUE,3),
(v3,'15.5','3LC473-15.5',TRUE,4),(v3,'16',  '3LC473-16',  TRUE,5),(v3,'16.5','3LC473-16.5',TRUE,6),
(v3,'17',  '3LC473-17',  TRUE,7),(v3,'17.5','3LC473-17.5',TRUE,8),(v3,'18',  '3LC473-18',  TRUE,9),
(v3,'18.5','3LC473-18.5',TRUE,10);

INSERT INTO prenda_skus (prenda_catalogo_id, talla, codigo_sku, activo, orden) VALUES
(v4,'14',  '3LC474-14',  TRUE,1),(v4,'14.5','3LC474-14.5',TRUE,2),(v4,'15',  '3LC474-15',  TRUE,3),
(v4,'15.5','3LC474-15.5',TRUE,4),(v4,'16',  '3LC474-16',  TRUE,5),(v4,'16.5','3LC474-16.5',TRUE,6),
(v4,'17',  '3LC474-17',  TRUE,7),(v4,'17.5','3LC474-17.5',TRUE,8),(v4,'18',  '3LC474-18',  TRUE,9),
(v4,'18.5','3LC474-18.5',TRUE,10);

INSERT INTO prenda_skus (prenda_catalogo_id, talla, codigo_sku, activo, orden) VALUES
(v5,'14',  '3LC475-14',  TRUE,1),(v5,'14.5','3LC475-14.5',TRUE,2),(v5,'15',  '3LC475-15',  TRUE,3),
(v5,'15.5','3LC475-15.5',TRUE,4),(v5,'16',  '3LC475-16',  TRUE,5),(v5,'16.5','3LC475-16.5',TRUE,6),
(v5,'17',  '3LC475-17',  TRUE,7),(v5,'17.5','3LC475-17.5',TRUE,8),(v5,'18',  '3LC475-18',  TRUE,9),
(v5,'18.5','3LC475-18.5',TRUE,10);

INSERT INTO prenda_skus (prenda_catalogo_id, talla, codigo_sku, activo, orden) VALUES
(v6,'14',  '3LC476-14',  TRUE,1),(v6,'14.5','3LC476-14.5',TRUE,2),(v6,'15',  '3LC476-15',  TRUE,3),
(v6,'15.5','3LC476-15.5',TRUE,4),(v6,'16',  '3LC476-16',  TRUE,5),(v6,'16.5','3LC476-16.5',TRUE,6),
(v6,'17',  '3LC476-17',  TRUE,7),(v6,'17.5','3LC476-17.5',TRUE,8),(v6,'18',  '3LC476-18',  TRUE,9),
(v6,'18.5','3LC476-18.5',TRUE,10);

INSERT INTO prenda_skus (prenda_catalogo_id, talla, codigo_sku, activo, orden) VALUES
(v7,'14',  '3LC477-14',  TRUE,1),(v7,'14.5','3LC477-14.5',TRUE,2),(v7,'15',  '3LC477-15',  TRUE,3),
(v7,'15.5','3LC477-15.5',TRUE,4),(v7,'16',  '3LC477-16',  TRUE,5),(v7,'16.5','3LC477-16.5',TRUE,6),
(v7,'17',  '3LC477-17',  TRUE,7),(v7,'17.5','3LC477-17.5',TRUE,8),(v7,'18',  '3LC477-18',  TRUE,9),
(v7,'18.5','3LC477-18.5',TRUE,10);

INSERT INTO prenda_skus (prenda_catalogo_id, talla, codigo_sku, activo, orden) VALUES
(v8,'14',  '3LC478-14',  TRUE,1),(v8,'14.5','3LC478-14.5',TRUE,2),(v8,'15',  '3LC478-15',  TRUE,3),
(v8,'15.5','3LC478-15.5',TRUE,4),(v8,'16',  '3LC478-16',  TRUE,5),(v8,'16.5','3LC478-16.5',TRUE,6),
(v8,'17',  '3LC478-17',  TRUE,7),(v8,'17.5','3LC478-17.5',TRUE,8),(v8,'18',  '3LC478-18',  TRUE,9),
(v8,'18.5','3LC478-18.5',TRUE,10);

INSERT INTO prenda_skus (prenda_catalogo_id, talla, codigo_sku, activo, orden) VALUES
(v9,'14',  '3LC479-14',  TRUE,1),(v9,'14.5','3LC479-14.5',TRUE,2),(v9,'15',  '3LC479-15',  TRUE,3),
(v9,'15.5','3LC479-15.5',TRUE,4),(v9,'16',  '3LC479-16',  TRUE,5),(v9,'16.5','3LC479-16.5',TRUE,6),
(v9,'17',  '3LC479-17',  TRUE,7),(v9,'17.5','3LC479-17.5',TRUE,8),(v9,'18',  '3LC479-18',  TRUE,9),
(v9,'18.5','3LC479-18.5',TRUE,10);

RAISE NOTICE 'CAMISA SCHELLENGER insertada correctamente.';
RAISE NOTICE 'BASE id=%', base_id;
RAISE NOTICE 'Variantes: v1=% v2=% v3=% v4=% v5=% v6=% v7=% v8=% v9=%',
    v1, v2, v3, v4, v5, v6, v7, v8, v9;

END $$;
