-- ============================================================
-- SAMITEX-PLANTA · Script 03 · Plantillas de piezas por prenda
-- ============================================================

USE [SAMITEX-PLANTA];
GO

-- ── SACO (11 piezas) ─────────────────────────────────────────
INSERT INTO plantilla_piezas (tipo_prenda, nombre, material_default, cantidad_x_prenda, fusionado_default, orden) VALUES
('SACO', 'Delantero',       'TELA',  2, 1, 1),
('SACO', 'Espalda',         'TELA',  2, 0, 2),
('SACO', 'Costadillo',      'TELA',  2, 0, 3),
('SACO', 'Manga superior',  'TELA',  2, 0, 4),
('SACO', 'Manga inferior',  'TELA',  2, 0, 5),
('SACO', 'Cuello',          'TELA',  1, 1, 6),
('SACO', 'Vista',           'TELA',  2, 1, 7),
('SACO', 'Tapa de bolsillo','TELA',  2, 1, 8),
('SACO', 'Forro delantero', 'FORRO', 2, 0, 9),
('SACO', 'Forro espalda',   'FORRO', 2, 0, 10),
('SACO', 'Forro manga',     'FORRO', 2, 0, 11);
GO

-- ── PANTALÓN (7 piezas) ──────────────────────────────────────
INSERT INTO plantilla_piezas (tipo_prenda, nombre, material_default, cantidad_x_prenda, fusionado_default, orden) VALUES
('PANTALON', 'Delantero',          'TELA', 2, 0, 1),
('PANTALON', 'Posterior',          'TELA', 2, 0, 2),
('PANTALON', 'Pretina',            'TELA', 1, 1, 3),
('PANTALON', 'Gareta',             'TELA', 1, 1, 4),
('PANTALON', 'Bolsillo delantero', 'TELA', 2, 0, 5),
('PANTALON', 'Bolsillo posterior', 'TELA', 1, 0, 6),
('PANTALON', 'Vista',              'TELA', 2, 0, 7);
GO

-- ── CAMISA (8 piezas) ────────────────────────────────────────
INSERT INTO plantilla_piezas (tipo_prenda, nombre, material_default, cantidad_x_prenda, fusionado_default, orden) VALUES
('CAMISA', 'Delantero',     'TELA', 2, 0, 1),
('CAMISA', 'Espalda',       'TELA', 1, 0, 2),
('CAMISA', 'Canesu',        'TELA', 2, 0, 3),
('CAMISA', 'Manga',         'TELA', 2, 0, 4),
('CAMISA', 'Cuello',        'TELA', 1, 1, 5),
('CAMISA', 'Pie de cuello', 'TELA', 1, 1, 6),
('CAMISA', 'Puño',          'TELA', 2, 1, 7),
('CAMISA', 'Bolsillo',      'TELA', 1, 0, 8);
GO

PRINT 'Script 03 ejecutado correctamente — Plantillas de piezas cargadas.';
GO
