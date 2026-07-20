-- Script: Asignar códigos SAP a las piezas de la OF 1445623
-- Ejecutar en: PANO0142\SQLEXPRESS → base samitex_planta

DECLARE @of_id INT = (
    SELECT id FROM ordenes_fabricacion WHERE numero_of = '1445623'
);

UPDATE p
SET p.codigo_sap = CASE p.nombre
    WHEN 'Delantero'           THEN 'SAP-PAN-001'
    WHEN 'Posterior'           THEN 'SAP-PAN-002'
    WHEN 'Pretina'             THEN 'SAP-PAN-003'
    WHEN 'Gareta'              THEN 'SAP-PAN-004'
    WHEN 'Bolsillo delantero'  THEN 'SAP-PAN-005'
    WHEN 'Bolsillo posterior'  THEN 'SAP-PAN-006'
    WHEN 'Vista'               THEN 'SAP-PAN-007'
    ELSE 'SAP-GEN-' + CAST(p.id AS VARCHAR)
END
FROM of_piezas p
WHERE p.of_id = @of_id
  AND (p.codigo_sap IS NULL OR p.codigo_sap = '');

-- Verificar resultado
SELECT p.nombre, p.codigo_sap
FROM of_piezas p
WHERE p.of_id = @of_id
ORDER BY p.orden;
