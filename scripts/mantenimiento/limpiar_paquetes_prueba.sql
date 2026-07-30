/* Limpia SOLO los paquetes de prueba, dejando las OFs y todo lo demás intacto.
   Ejecutar en SSMS contra SAMITEX-PLANTA. Los eventos se borran por cascada,
   pero los elimino explícito por si el FK no tiene ON DELETE CASCADE activo. */
USE [SAMITEX-PLANTA];

DELETE FROM dbo.of_paquete_eventos;
DELETE FROM dbo.of_paquetes;

-- Verificación (deben quedar en 0)
SELECT COUNT(*) AS paquetes_restantes FROM dbo.of_paquetes;
SELECT COUNT(*) AS eventos_restantes  FROM dbo.of_paquete_eventos;
