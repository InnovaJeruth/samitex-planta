-- ============================================================
-- SAMITEX-PLANTA · Script 05 · Columnas de planificación Gantt
-- ============================================================
-- Agrega fecha_inicio_plan y orden_plan a ordenes_fabricacion
-- para soportar el Plan de Corte interactivo (arrastrar y priorizar).
-- Ejecutar UNA SOLA VEZ en SQL Server Management Studio.
-- ============================================================

USE [SAMITEX-PLANTA];
GO

-- Agregar fecha de inicio planificada (la que arrastra el planeador en el Gantt)
IF NOT EXISTS (
    SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_NAME = 'ordenes_fabricacion' AND COLUMN_NAME = 'fecha_inicio_plan'
)
BEGIN
    ALTER TABLE ordenes_fabricacion ADD fecha_inicio_plan DATE NULL;
    PRINT 'Columna fecha_inicio_plan agregada.';
END
ELSE
    PRINT 'Columna fecha_inicio_plan ya existe — omitida.';
GO

-- Agregar orden de prioridad del planeador (1 = más urgente)
IF NOT EXISTS (
    SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_NAME = 'ordenes_fabricacion' AND COLUMN_NAME = 'orden_plan'
)
BEGIN
    ALTER TABLE ordenes_fabricacion ADD orden_plan INT NULL;
    PRINT 'Columna orden_plan agregada.';
END
ELSE
    PRINT 'Columna orden_plan ya existe — omitida.';
GO

PRINT 'Script 05 ejecutado correctamente.';
GO
