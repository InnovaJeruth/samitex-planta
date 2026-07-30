/* ============================================================================
   RESET_AVANCE_OF.sql — Deja una OF "recién por iniciar"
   Borra TODO el avance de corte (placas/tela, avances, tiempos, paradas) y
   pone las fases en cero, SIN borrar la OF, su curva de tallas ni las piezas.
   Correr en SSMS sobre [SAMITEX-PLANTA]. Es transaccional: si algo falla, revierte.
   ============================================================================ */
USE [SAMITEX-PLANTA];
GO

SET XACT_ABORT ON;
BEGIN TRAN;

-- >>> Cambia aquí el número de OF a resetear <<<
DECLARE @of_numero VARCHAR(30) = '15151515';

DECLARE @of_id INT = (SELECT id FROM ordenes_fabricacion WHERE numero_of = @of_numero);
IF @of_id IS NULL
BEGIN
    RAISERROR('No existe la OF %s', 16, 1, @of_numero);
    ROLLBACK TRAN;
    RETURN;
END

-- 1) Log de avances
DELETE FROM avance_registros WHERE of_id = @of_id;

-- 2) Placas / tela (trazos + sus tallas)
DELETE FROM of_trazo_tallas WHERE trazo_id IN (SELECT id FROM of_trazos WHERE of_id = @of_id);
DELETE FROM of_trazos       WHERE of_id = @of_id;

-- 3) Paradas y tiempos programados/reales por fase
DELETE FROM of_fase_paradas WHERE of_id = @of_id;
DELETE FROM of_fase_tiempos WHERE of_id = @of_id;

-- 4) Poner TODAS las fases de las piezas en cero (mantiene la estructura pieza×talla)
UPDATE of_fases_estado
   SET cantidad_actual   = 0,
       completada        = 0,
       fecha_inicio      = NULL,
       fecha_completado  = NULL,
       eficiencia_tizado = NULL,
       temperatura_fusion= NULL,
       tratamiento_orillo= NULL,
       motivo_rechazo    = NULL
 WHERE of_id = @of_id;

-- 5) Volver la OF a ACTIVA (por si avanzó a EN_PROCESO/COMPLETADA)
UPDATE ordenes_fabricacion
   SET estado = 'ACTIVA',
       juegos_recibidos = 0
 WHERE id = @of_id;

PRINT CONCAT('OF ', @of_numero, ' (id=', @of_id, ') reseteada: avance borrado, fases en cero, estado ACTIVA.');

COMMIT TRAN;
GO


/* ----------------------------------------------------------------------------
   OPCIÓN B — RESET TOTAL (además borra piezas y fases para regenerarlas)
   Descomenta este bloque SOLO si querés volver a "Generar piezas desde catálogo"
   desde cero (perderás la estructura pieza×talla actual; la curva se conserva).
   ----------------------------------------------------------------------------
USE [SAMITEX-PLANTA];
SET XACT_ABORT ON;
BEGIN TRAN;
DECLARE @of_numero2 VARCHAR(30) = '15151515';
DECLARE @of_id2 INT = (SELECT id FROM ordenes_fabricacion WHERE numero_of = @of_numero2);
DELETE FROM avance_registros WHERE of_id = @of_id2;
DELETE FROM of_trazo_tallas  WHERE trazo_id IN (SELECT id FROM of_trazos WHERE of_id = @of_id2);
DELETE FROM of_trazos        WHERE of_id = @of_id2;
DELETE FROM of_fase_paradas  WHERE of_id = @of_id2;
DELETE FROM of_fase_tiempos  WHERE of_id = @of_id2;
DELETE FROM of_fases_estado  WHERE of_id = @of_id2;
DELETE FROM of_piezas        WHERE of_id = @of_id2;
UPDATE ordenes_fabricacion SET estado = 'ACTIVA', juegos_recibidos = 0 WHERE id = @of_id2;
COMMIT TRAN;
GO
---------------------------------------------------------------------------- */
