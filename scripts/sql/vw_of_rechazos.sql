/* ============================================================================
   Vista vw_of_rechazos — rechazos de calidad aplanados por OF.

   Aplana of_paquete_rechazos → of_paquetes → ordenes_fabricacion (+ motivo),
   para que el Chat analítico (RAG) responda preguntas de rechazos/reprocesos
   sin tener que armar el join de 3 saltos (los rechazos NO tienen of_id).

   Solo lectura. Reejecutable. Ejecutar en SSMS sobre SAMITEX-PLANTA.
   Revisa nombres si tu esquema difiere:
   - of_paquete_rechazos.paquete_id / motivo_id / cantidad / estado
   - of_paquetes.of_id ; motivos_rechazo.codigo / descripcion
   ============================================================================ */
CREATE OR ALTER VIEW dbo.vw_of_rechazos AS
SELECT o.numero_of,
       m.codigo      AS motivo_codigo,
       m.descripcion AS motivo,
       r.cantidad,
       r.estado
FROM of_paquete_rechazos r
JOIN of_paquetes         p ON p.id = r.paquete_id
JOIN ordenes_fabricacion o ON o.id = p.of_id
JOIN motivos_rechazo     m ON m.id = r.motivo_id;
