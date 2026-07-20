-- ============================================================
-- SAMITEX-PLANTA · Script 04 · Usuarios de prueba por rol
-- BD: SAMITEX-PLANTA · Servidor: PANO0142\SQLEXPRESS
--
-- Hashes generados con bcrypt rounds=12 (Python bcrypt 4.2.1)
-- ┌─────────────────┬──────────────────┬───────────────────┐
-- │ Username        │ Contraseña       │ Rol               │
-- ├─────────────────┼──────────────────┼───────────────────┤
-- │ admin           │ Admin2026!       │ ADMIN             │
-- │ gerencia        │ Gerencia2026!    │ GERENCIA          │
-- │ planeador       │ Planeador2026!   │ PLANEADOR         │
-- │ supervisor      │ Supervisor2026!  │ SUPERVISOR_CORTE  │
-- │ lectura         │ Lectura2026!     │ SOLO_LECTURA      │
-- └─────────────────┴──────────────────┴───────────────────┘
-- ============================================================

USE [SAMITEX-PLANTA];
GO

-- GERENCIA
UPDATE usuarios
SET password_hash = '$2b$12$4hXuO0t/dO8QkVKVs6ULKeZRXKieY.5pIT090mc6HDHh6ps./Y2p.'
WHERE username = 'gerencia';

INSERT INTO usuarios (nombre, email, username, password_hash, rol, activo)
SELECT 'Gerente de Planta', 'gerencia@samitex.com.pe', 'gerencia',
       '$2b$12$4hXuO0t/dO8QkVKVs6ULKeZRXKieY.5pIT090mc6HDHh6ps./Y2p.',
       'GERENCIA', 1
WHERE NOT EXISTS (SELECT 1 FROM usuarios WHERE username = 'gerencia');

-- PLANEADOR
UPDATE usuarios
SET password_hash = '$2b$12$xb9onFuaR2MeKfv.1X/cqe2AJV6z2uGmKYWXVgSg7QUpBy5gUPSXe'
WHERE username = 'planeador';

INSERT INTO usuarios (nombre, email, username, password_hash, rol, activo)
SELECT 'Planeador de Producción', 'planeador@samitex.com.pe', 'planeador',
       '$2b$12$xb9onFuaR2MeKfv.1X/cqe2AJV6z2uGmKYWXVgSg7QUpBy5gUPSXe',
       'PLANEADOR', 1
WHERE NOT EXISTS (SELECT 1 FROM usuarios WHERE username = 'planeador');

-- SUPERVISOR_CORTE
UPDATE usuarios
SET password_hash = '$2b$12$VrwcQnRxu6NNJ.Hr.HcaxOh/wzk8kMKPpIM/pAWPTmBngP5C5LseW'
WHERE username = 'supervisor';

INSERT INTO usuarios (nombre, email, username, password_hash, rol, activo)
SELECT 'Supervisor de Corte', 'supervisor@samitex.com.pe', 'supervisor',
       '$2b$12$VrwcQnRxu6NNJ.Hr.HcaxOh/wzk8kMKPpIM/pAWPTmBngP5C5LseW',
       'SUPERVISOR_CORTE', 1
WHERE NOT EXISTS (SELECT 1 FROM usuarios WHERE username = 'supervisor');

-- SOLO_LECTURA
UPDATE usuarios
SET password_hash = '$2b$12$aAPR1nusoGZLXacwBAZExOJuCj9id3zH8io8t7SVgpTvOYgRLJVLa'
WHERE username = 'lectura';

INSERT INTO usuarios (nombre, email, username, password_hash, rol, activo)
SELECT 'Usuario Solo Lectura', 'lectura@samitex.com.pe', 'lectura',
       '$2b$12$aAPR1nusoGZLXacwBAZExOJuCj9id3zH8io8t7SVgpTvOYgRLJVLa',
       'SOLO_LECTURA', 1
WHERE NOT EXISTS (SELECT 1 FROM usuarios WHERE username = 'lectura');

GO
PRINT 'Script 04 ejecutado — Contraseñas actualizadas.';
GO
