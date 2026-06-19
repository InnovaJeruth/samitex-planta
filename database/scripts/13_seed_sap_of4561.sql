-- ============================================================
-- Script: 13_seed_sap_of4561.sql
-- Descripción: Carga códigos SAP de piezas para OF 4561
-- Ejecutar en: PANO0142\SQLEXPRESS > SAMITEX-PLANTA
-- ============================================================

UPDATE p
SET p.codigo_sap = c.codigo_sap
FROM of_piezas p
INNER JOIN ordenes_fabricacion ord ON ord.id = p.of_id
CROSS APPLY (
    SELECT codigo_sap = CASE p.nombre
        WHEN 'Delantero'     THEN 'SAP-CAM-001'
        WHEN 'Espalda'       THEN 'SAP-CAM-002'
        WHEN 'Canesu'        THEN 'SAP-CAM-003'
        WHEN 'Manga'         THEN 'SAP-CAM-004'
        WHEN 'Cuello'        THEN 'SAP-CAM-005'
        WHEN 'Pie de cuello' THEN 'SAP-CAM-006'
        WHEN 'Puño'          THEN 'SAP-CAM-007'
        WHEN 'Bolsillo'      THEN 'SAP-CAM-008'
        ELSE NULL
    END
) c
WHERE ord.numero_of = '4561'
  AND c.codigo_sap IS NOT NULL;

-- Verificar resultado
SELECT p.nombre, p.codigo_sap
FROM of_piezas p
INNER JOIN ordenes_fabricacion ord ON ord.id = p.of_id
WHERE ord.numero_of = '4561'
ORDER BY p.id;
