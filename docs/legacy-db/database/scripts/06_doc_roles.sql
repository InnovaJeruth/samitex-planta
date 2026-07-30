-- ============================================================
-- SAMITEX-PLANTA · Script 06 · Roles documentales y tipo_cliente
-- BD: SAMITEX-PLANTA · Servidor: PANO0142\SQLEXPRESS
-- ============================================================

USE [SAMITEX-PLANTA];
GO

-- ── ordenes_fabricacion: tipo_cliente ────────────────────────
IF NOT EXISTS (
    SELECT 1 FROM sys.columns
    WHERE object_id = OBJECT_ID('ordenes_fabricacion') AND name = 'tipo_cliente'
)
BEGIN
    ALTER TABLE ordenes_fabricacion
    ADD tipo_cliente VARCHAR(20) NOT NULL DEFAULT 'INSTITUCION';
    PRINT 'Columna tipo_cliente agregada.';
END
ELSE
    PRINT 'tipo_cliente ya existe — omitido.';
GO

-- ── ordenes_fabricacion: estado_docs ─────────────────────────
IF NOT EXISTS (
    SELECT 1 FROM sys.columns
    WHERE object_id = OBJECT_ID('ordenes_fabricacion') AND name = 'estado_docs'
)
BEGIN
    ALTER TABLE ordenes_fabricacion
    ADD estado_docs VARCHAR(20) NOT NULL DEFAULT 'PENDIENTE';
    PRINT 'Columna estado_docs agregada.';
END
ELSE
    PRINT 'estado_docs ya existe — omitido.';
GO

-- ── documentos_of: area ───────────────────────────────────────
IF NOT EXISTS (
    SELECT 1 FROM sys.columns
    WHERE object_id = OBJECT_ID('documentos_of') AND name = 'area'
)
BEGIN
    ALTER TABLE documentos_of
    ADD area VARCHAR(30) NULL;
    PRINT 'Columna area agregada a documentos_of.';
END
ELSE
    PRINT 'area ya existe en documentos_of — omitido.';
GO

-- ── Backfill estado_docs para OFs existentes ─────────────────
-- OFs activas/en_proceso/completadas ya tienen docs OK → COMPLETA
UPDATE ordenes_fabricacion
SET estado_docs = 'COMPLETA'
WHERE estado IN ('ACTIVA','EN_PROCESO','COMPLETADA')
  AND estado_docs = 'PENDIENTE';

-- OFs borrador con al menos 1 doc → EN_DOCUMENTACION
UPDATE ordenes_fabricacion
SET estado_docs = 'EN_DOCUMENTACION'
WHERE estado = 'BORRADOR'
  AND estado_docs = 'PENDIENTE'
  AND id IN (SELECT DISTINCT of_id FROM documentos_of);

PRINT 'Backfill de estado_docs completado.';
GO

PRINT 'Script 06 ejecutado correctamente.';
GO
