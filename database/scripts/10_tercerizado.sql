-- Migración: Soporte de tercerización de OFs
-- Ejecutar en: PANO0142\SQLEXPRESS → base samitex_planta

ALTER TABLE ordenes_fabricacion
    ADD tercerizado            BIT           NOT NULL DEFAULT 0,
        planta_externa         VARCHAR(120)  NULL,
        fecha_envio            DATE          NULL,
        fecha_recepcion_est    DATE          NULL,
        fecha_recepcion_real   DATE          NULL,
        estado_tercerizado     VARCHAR(20)   NULL;   -- PENDIENTE_ENVIO / ENVIADA / RECIBIDA

-- Verificar
SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE, COLUMN_DEFAULT
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_NAME = 'ordenes_fabricacion'
  AND COLUMN_NAME IN (
      'tercerizado','planta_externa','fecha_envio',
      'fecha_recepcion_est','fecha_recepcion_real','estado_tercerizado'
  );
