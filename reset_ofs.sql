-- ============================================================
-- RESET OFs - Samitex Planta
-- Borra SOLO datos transaccionales de OFs.
-- Conserva: usuarios, parametros_sistema, fases_catalogo,
--            plantilla_piezas, plantas_externas.
-- ============================================================
-- Ejecutar en orden (hijos antes que padre por FK)

DELETE FROM avance_registros;
DELETE FROM of_fases_estado;
DELETE FROM of_fase_tiempos;
DELETE FROM of_fase_paradas;
DELETE FROM terc_recepciones;
DELETE FROM terc_historial_fechas;
DELETE FROM documentos_of;
DELETE FROM of_piezas;
DELETE FROM ordenes_fabricacion;

-- Opcional: reiniciar el contador de IDs (solo si usas IDENTITY)
-- DBCC CHECKIDENT ('ordenes_fabricacion', RESEED, 0);
-- DBCC CHECKIDENT ('of_piezas', RESEED, 0);
-- DBCC CHECKIDENT ('of_fases_estado', RESEED, 0);
