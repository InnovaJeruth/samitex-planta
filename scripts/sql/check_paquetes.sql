/* Diagnóstico previo a Q1 — estado de las tablas de paquetes.
   Ejecutar en SSMS contra la base SAMITEX-PLANTA (o con sqlcmd, ver abajo). */
USE [SAMITEX-PLANTA];

-- 1) ¿Existen ya las tablas de paquetes?
SELECT
  CASE WHEN OBJECT_ID('dbo.of_paquetes')        IS NOT NULL THEN 'SI' ELSE 'NO' END AS of_paquetes_existe,
  CASE WHEN OBJECT_ID('dbo.of_paquete_eventos') IS NOT NULL THEN 'SI' ELSE 'NO' END AS of_paquete_eventos_existe,
  CASE WHEN COL_LENGTH('dbo.ordenes_fabricacion','unidades_por_paquete') IS NOT NULL
       THEN 'SI' ELSE 'NO' END AS col_unidades_por_paquete;

-- 2) ¿Hay datos? (solo si existen)
IF OBJECT_ID('dbo.of_paquetes') IS NOT NULL
  SELECT COUNT(*) AS paquetes_filas FROM dbo.of_paquetes;

IF OBJECT_ID('dbo.of_paquete_eventos') IS NOT NULL
  SELECT COUNT(*) AS eventos_filas FROM dbo.of_paquete_eventos;

-- 3) ¿Qué estados hay guardados hoy? (para saber si hay que remapear)
IF OBJECT_ID('dbo.of_paquetes') IS NOT NULL
  SELECT estado, COUNT(*) AS cantidad FROM dbo.of_paquetes GROUP BY estado;

-- 4) ¿En qué migración está Alembic?
IF OBJECT_ID('dbo.alembic_version') IS NOT NULL
  SELECT version_num AS alembic_actual FROM dbo.alembic_version;
