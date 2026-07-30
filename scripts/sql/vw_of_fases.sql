/* ============================================================================
   Vista vw_of_fases — tiempos por fase de cada OF, unificados y con nombre.

   Une las fases de tela y numerado (of_fase_tiempos: F1..F4) con Fusionado y
   Calidad (derivados de of_paquetes / of_paquete_eventos), igual que hace el
   módulo de Analítica. La usa el Chat analítico (RAG) para responder preguntas
   de tiempos/duración por fase de forma consistente.

   Ejecutar en SSMS sobre la base SAMITEX-PLANTA. Es de solo lectura (una vista);
   no modifica datos. Reejecutable (CREATE OR ALTER).

   Revisa los nombres de columnas/estados si tu esquema difiere:
   - of_paquetes.fusionado_inicio / fusionado_fin / of_id
   - of_paquete_eventos.estado ('POR_VALIDAR','ENTREGADO') / created_at / paquete_id
   ============================================================================ */
CREATE OR ALTER VIEW dbo.vw_of_fases AS
WITH tela AS (   -- F1..F4 desde of_fase_tiempos
    SELECT o.numero_of,
           CASE t.fase_id WHEN 'F1' THEN 'Tizado'
                          WHEN 'F2' THEN 'Tendido'
                          WHEN 'F3' THEN 'Corte'
                          WHEN 'F4' THEN 'Numerado' END AS fase,
           t.inicio_real AS inicio,
           t.fin_real    AS fin,
           CASE t.fase_id WHEN 'F1' THEN 1 WHEN 'F2' THEN 2
                          WHEN 'F3' THEN 3 WHEN 'F4' THEN 4 END AS orden
    FROM of_fase_tiempos t
    JOIN ordenes_fabricacion o ON o.id = t.of_id
    WHERE t.fase_id IN ('F1','F2','F3','F4')
),
fus AS (         -- Fusionado desde of_paquetes
    SELECT o.numero_of, CAST('Fusionado' AS VARCHAR(20)) AS fase,
           MIN(p.fusionado_inicio) AS inicio,
           MAX(p.fusionado_fin)    AS fin,
           5 AS orden
    FROM of_paquetes p
    JOIN ordenes_fabricacion o ON o.id = p.of_id
    WHERE p.fusionado_inicio IS NOT NULL
    GROUP BY o.numero_of
),
cal AS (         -- Calidad desde los eventos de bulto (POR_VALIDAR -> ENTREGADO)
    SELECT o.numero_of, CAST('Calidad' AS VARCHAR(20)) AS fase,
           MIN(CASE WHEN e.estado = 'POR_VALIDAR' THEN e.created_at END) AS inicio,
           MAX(CASE WHEN e.estado = 'ENTREGADO'   THEN e.created_at END) AS fin,
           6 AS orden
    FROM of_paquete_eventos e
    JOIN of_paquetes p          ON p.id = e.paquete_id
    JOIN ordenes_fabricacion o  ON o.id = p.of_id
    GROUP BY o.numero_of
)
SELECT numero_of, fase, inicio, fin,
       DATEDIFF(MINUTE, inicio, fin) AS minutos, orden
FROM (
    SELECT numero_of, fase, inicio, fin, orden FROM tela
    UNION ALL SELECT numero_of, fase, inicio, fin, orden FROM fus
    UNION ALL SELECT numero_of, fase, inicio, fin, orden FROM cal
) x
WHERE inicio IS NOT NULL AND fase IS NOT NULL;
