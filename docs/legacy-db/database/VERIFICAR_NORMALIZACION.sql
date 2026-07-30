/* ============================================================================
   VERIFICAR_NORMALIZACION.sql — SAMITEX-PLANTA
   Correr en SSMS sobre [SAMITEX-PLANTA]. Cada bloque es independiente.
   Sirve para confirmar el estado de la BD recreada + normalizada.
   ============================================================================ */
USE [SAMITEX-PLANTA];
GO

/* 1) Confirmar que planta_externa y fase_tercerizada YA NO EXISTEN
      (deben devolver 0 filas cada uno). */
SELECT c.name AS columna_fantasma
FROM sys.columns c
WHERE c.object_id = OBJECT_ID('ordenes_fabricacion')
  AND c.name IN ('planta_externa', 'fase_tercerizada');
GO

/* 2) Confirmar que las 8 fichas ing_ tienen la columna of_id (deben ser 8 filas). */
SELECT t.name AS tabla, c.name AS columna
FROM sys.columns c
JOIN sys.tables t ON t.object_id = c.object_id
WHERE t.name LIKE 'ing[_]%' AND c.name = 'of_id'
ORDER BY t.name;
GO

/* 3) Todas las FK con su regla de borrado.
      No debe haber ninguna 'RESTRICT' (SQL Server no lo soporta). */
SELECT  fk.name                              AS fk,
        tp.name                              AS tabla_hija,
        cp.name                              AS columna_hija,
        tr.name                              AS tabla_padre,
        fk.delete_referential_action_desc    AS on_delete
FROM sys.foreign_keys fk
JOIN sys.foreign_key_columns fkc ON fkc.constraint_object_id = fk.object_id
JOIN sys.tables  tp ON tp.object_id = fk.parent_object_id
JOIN sys.columns cp ON cp.object_id = tp.object_id AND cp.column_id = fkc.parent_column_id
JOIN sys.tables  tr ON tr.object_id = fk.referenced_object_id
ORDER BY tp.name, fk.name;
GO

/* 4) Tablas SIN llave primaria (debería salir vacío — toda tabla debe tener PK). */
SELECT t.name AS tabla_sin_pk
FROM sys.tables t
WHERE NOT EXISTS (
    SELECT 1 FROM sys.indexes i
    WHERE i.object_id = t.object_id AND i.is_primary_key = 1
)
ORDER BY t.name;
GO

/* 5) Índices UNIQUE (confirma que las junction tables no aceptan duplicados). */
SELECT t.name AS tabla, i.name AS indice_unico
FROM sys.indexes i
JOIN sys.tables t ON t.object_id = i.object_id
WHERE i.is_unique = 1 AND i.is_primary_key = 0
  AND t.name IN ('prenda_mp_config','prenda_avio_config',
                 'prenda_sku_mp_config','prenda_sku_avio_config',
                 'prenda_skus','of_talla_distribucion',
                 'of_trazo_tallas','curvas_tallas_detalle')
ORDER BY t.name;
GO

/* 6) Integridad del catálogo restaurado — SKUs huérfanos
      (SKU cuyo prenda_catalogo_id no existe). Debe salir vacío. */
SELECT s.id, s.prenda_catalogo_id
FROM prenda_skus s
LEFT JOIN prendas_catalogo p ON p.id = s.prenda_catalogo_id
WHERE p.id IS NULL;
GO

/* 7) Configs huérfanas (MP/avío que apuntan a prenda o item inexistente).
      Deben salir vacías. */
SELECT 'mp_config' AS origen, mc.id
FROM prenda_mp_config mc
LEFT JOIN prendas_catalogo p ON p.id = mc.prenda_catalogo_id
LEFT JOIN catalogo_mp m       ON m.id = mc.mp_id
WHERE p.id IS NULL OR m.id IS NULL
UNION ALL
SELECT 'avio_config', ac.id
FROM prenda_avio_config ac
LEFT JOIN prendas_catalogo p ON p.id = ac.prenda_catalogo_id
LEFT JOIN catalogo_avios a    ON a.id = ac.avio_id
WHERE p.id IS NULL OR a.id IS NULL;
GO

/* 8) Conteo final del catálogo restaurado (debe coincidir con el backup). */
SELECT 'usuarios' AS tabla, COUNT(*) AS filas FROM usuarios
UNION ALL SELECT 'prendas_catalogo', COUNT(*) FROM prendas_catalogo
UNION ALL SELECT 'prenda_skus',      COUNT(*) FROM prenda_skus
UNION ALL SELECT 'plantilla_piezas', COUNT(*) FROM plantilla_piezas
UNION ALL SELECT 'catalogo_mp',      COUNT(*) FROM catalogo_mp
UNION ALL SELECT 'catalogo_avios',   COUNT(*) FROM catalogo_avios;
GO
