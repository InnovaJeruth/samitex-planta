/* ============================================================================
   Vista SEGURA de usuarios para el Chat analítico (RAG).

   Expone SOLO columnas no sensibles para resolver "quién hizo X"
   (usuario_id -> nombre). NUNCA incluye password_hash, tokens ni secretos.

   El RAG referencia vw_usuarios (está en el whitelist); la tabla base
   `usuarios` quedó FUERA del whitelist y además se DENIEGA a nivel de BD
   al login rag_readonly (ver rag_login_readonly.sql).

   ORDEN DE EJECUCIÓN: corre PRIMERO rag_login_readonly.sql (crea el usuario
   rag_readonly) y DESPUÉS este script. Si el usuario aún no existe, la vista
   igual se crea y el GRANT se omite sin error.

   Ejecutar en SSMS sobre PANO0142\SQLEXPRESS.
   ============================================================================ */
USE [SAMITEX-PLANTA];
GO

CREATE OR ALTER VIEW dbo.vw_usuarios AS
    SELECT
        u.id,
        u.nombre,
        u.username,
        u.rol,
        u.activo
    FROM dbo.usuarios AS u;
GO

/* Permitir que el login de solo lectura lea la vista (aunque se le niegue
   la tabla base usuarios). SELECT sobre la vista funciona porque el dueño
   del esquema encadena permisos (ownership chaining).
   Se omite sin error si rag_readonly todavía no existe. */
IF EXISTS (SELECT 1 FROM sys.database_principals WHERE name = 'rag_readonly')
    GRANT SELECT ON dbo.vw_usuarios TO rag_readonly;
ELSE
    PRINT 'AVISO: usuario rag_readonly no existe todavia. Corre rag_login_readonly.sql y vuelve a ejecutar este GRANT.';
GO

PRINT 'Vista vw_usuarios creada — solo columnas no sensibles.';
GO
