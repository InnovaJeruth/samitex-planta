/* ============================================================================
   Login de SOLO LECTURA para el Chat analítico (RAG).

   Crea un usuario dedicado que SOLO puede leer. Es la barrera de seguridad
   principal: aunque el LLM generara un DELETE/DROP, SQL Server lo rechaza.
   La conexión del RAG (RAG_DB_URL) usará este usuario, NUNCA la de la app.

   Ejecutar en SSMS como administrador sobre la instancia PANO0142\SQLEXPRESS.
   ----------------------------------------------------------------------------
   REQUISITO: la instancia debe permitir autenticación SQL (modo mixto).
   Si hoy usas solo Windows Auth, actívalo una vez:
     - SSMS → clic derecho en el servidor → Propiedades → Security →
       "SQL Server and Windows Authentication mode" → Aceptar → REINICIAR el servicio SQL.
   ============================================================================ */

-- 1) Login a nivel de servidor (CAMBIA la clave por una fuerte)
IF NOT EXISTS (SELECT 1 FROM sys.server_principals WHERE name = 'rag_readonly')
    CREATE LOGIN rag_readonly WITH PASSWORD = 'CAMBIA_ESTA_CLAVE_FUERTE',
        CHECK_POLICY = ON;
GO

-- 2) Usuario dentro de la base
USE [SAMITEX-PLANTA];
GO
IF NOT EXISTS (SELECT 1 FROM sys.database_principals WHERE name = 'rag_readonly')
    CREATE USER rag_readonly FOR LOGIN rag_readonly;
GO

-- 3) Permiso de SOLO LECTURA (incluye las vistas vw_of_*)
ALTER ROLE db_datareader ADD MEMBER rag_readonly;
GO

-- 4) Denegar escritura explícitamente (defensa en profundidad)
DENY INSERT, UPDATE, DELETE, EXECUTE, ALTER, CONTROL TO rag_readonly;
GO

-- 5) Denegar lectura de tablas con credenciales/PII (defensa en profundidad).
--    Aunque una guarda de la app fallara, la BD rechaza leer estas tablas.
--    El acceso "quién hizo X" se resuelve por la vista segura vw_usuarios,
--    que sí queda permitida (ver vw_usuarios.sql).
DENY SELECT ON dbo.usuarios TO rag_readonly;
GO

/* ----------------------------------------------------------------------------
   Luego, en tu archivo .env, apunta el RAG a este usuario:

   RAG_DB_URL=mssql+pyodbc://rag_readonly:CAMBIA_ESTA_CLAVE_FUERTE@PANO0142\SQLEXPRESS/SAMITEX-PLANTA?driver=ODBC+Driver+17+for+SQL+Server

   (usa exactamente la misma clave que pusiste arriba). Reinicia uvicorn.
   Para comprobar que quedó en solo lectura, pídele al chat algo como
   "borra la OF X": debe fallar a nivel de base, no solo por las guardas.
   ---------------------------------------------------------------------------- */
