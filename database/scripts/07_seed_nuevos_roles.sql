-- ============================================================
-- SAMITEX-PLANTA · Script 07 · Usuarios nuevos roles documentales
-- BD: SAMITEX-PLANTA · Servidor: PANO0142\SQLEXPRESS
--
-- Hashes generados con bcrypt rounds=12 (Python bcrypt 4.2.1)
-- ┌──────────────┬──────────────────┬───────────────────┐
-- │ Username     │ Contraseña       │ Rol               │
-- ├──────────────┼──────────────────┼───────────────────┤
-- │ udp          │ UDP2026!         │ UDP               │
-- │ comercial    │ Comercial2026!   │ COMERCIAL         │
-- │ cmarca       │ CMarca2026!      │ COMERCIAL_MARCA   │
-- │ pmarca       │ PMarca2026!      │ PLANEAMIENTO_MARCA│
-- │ ingenieria   │ Ingenieria2026!  │ INGENIERIA        │
-- │ logistica    │ Logistica2026!   │ LOGISTICA         │
-- │ calidad      │ Calidad2026!     │ CALIDAD           │
-- └──────────────┴──────────────────┴───────────────────┘
-- ============================================================

USE [SAMITEX-PLANTA];
GO

-- UDP
UPDATE usuarios SET password_hash = '$2b$12$J1NRGOdgnbiuNpM.1v0PwuXV1GHMvZ8zILxEZlroHjnC6qGUaFm7q' WHERE username = 'udp';
INSERT INTO usuarios (nombre, email, username, password_hash, rol, activo)
SELECT 'Equipo UDP', 'udp@samitex.com.pe', 'udp',
       '$2b$12$J1NRGOdgnbiuNpM.1v0PwuXV1GHMvZ8zILxEZlroHjnC6qGUaFm7q',
       'UDP', 1
WHERE NOT EXISTS (SELECT 1 FROM usuarios WHERE username = 'udp');
GO

-- COMERCIAL
UPDATE usuarios SET password_hash = '$2b$12$geCLax4NuSXz/jcmFklY7OUnWeXjAZYCm.naQ48MZKPn/pN1/pzI.' WHERE username = 'comercial';
INSERT INTO usuarios (nombre, email, username, password_hash, rol, activo)
SELECT 'Comercial Instituciones', 'comercial@samitex.com.pe', 'comercial',
       '$2b$12$geCLax4NuSXz/jcmFklY7OUnWeXjAZYCm.naQ48MZKPn/pN1/pzI.',
       'COMERCIAL', 1
WHERE NOT EXISTS (SELECT 1 FROM usuarios WHERE username = 'comercial');
GO

-- COMERCIAL_MARCA
UPDATE usuarios SET password_hash = '$2b$12$oM53A/IEN3qg8uDEvGzEfuEwhMwI2B1x6aP1uYSpoFFHAxNAyirOO' WHERE username = 'cmarca';
INSERT INTO usuarios (nombre, email, username, password_hash, rol, activo)
SELECT 'Comercial Marca', 'cmarca@samitex.com.pe', 'cmarca',
       '$2b$12$oM53A/IEN3qg8uDEvGzEfuEwhMwI2B1x6aP1uYSpoFFHAxNAyirOO',
       'COMERCIAL_MARCA', 1
WHERE NOT EXISTS (SELECT 1 FROM usuarios WHERE username = 'cmarca');
GO

-- PLANEAMIENTO_MARCA
UPDATE usuarios SET password_hash = '$2b$12$ePsFCefxXiT.SktiZikmDegHqgXYzysDJFosKU90FJ4vz.AxnCYlW' WHERE username = 'pmarca';
INSERT INTO usuarios (nombre, email, username, password_hash, rol, activo)
SELECT 'Planeamiento Marca', 'pmarca@samitex.com.pe', 'pmarca',
       '$2b$12$ePsFCefxXiT.SktiZikmDegHqgXYzysDJFosKU90FJ4vz.AxnCYlW',
       'PLANEAMIENTO_MARCA', 1
WHERE NOT EXISTS (SELECT 1 FROM usuarios WHERE username = 'pmarca');
GO

-- INGENIERIA
UPDATE usuarios SET password_hash = '$2b$12$X3VhhPUZBmnCZZTCIWeTm.kbNAP96csvMFiWg3Ll1Ii3wXfZU9GAe' WHERE username = 'ingenieria';
INSERT INTO usuarios (nombre, email, username, password_hash, rol, activo)
SELECT 'Ingeniería', 'ingenieria@samitex.com.pe', 'ingenieria',
       '$2b$12$X3VhhPUZBmnCZZTCIWeTm.kbNAP96csvMFiWg3Ll1Ii3wXfZU9GAe',
       'INGENIERIA', 1
WHERE NOT EXISTS (SELECT 1 FROM usuarios WHERE username = 'ingenieria');
GO

-- LOGISTICA
UPDATE usuarios SET password_hash = '$2b$12$zz3v0HuyhZ6WvrlFrjC4aOgD4NNlzTO8IzuTNssIRDKXpNeEV6vsq' WHERE username = 'logistica';
INSERT INTO usuarios (nombre, email, username, password_hash, rol, activo)
SELECT 'Logística', 'logistica@samitex.com.pe', 'logistica',
       '$2b$12$zz3v0HuyhZ6WvrlFrjC4aOgD4NNlzTO8IzuTNssIRDKXpNeEV6vsq',
       'LOGISTICA', 1
WHERE NOT EXISTS (SELECT 1 FROM usuarios WHERE username = 'logistica');
GO

-- CALIDAD
UPDATE usuarios SET password_hash = '$2b$12$fJcxbcHzNh8nVBLM82wEjODPPrXHV0Dh/OuRRn3uC7WhJqNKVRPae' WHERE username = 'calidad';
INSERT INTO usuarios (nombre, email, username, password_hash, rol, activo)
SELECT 'Calidad de Corte', 'calidad@samitex.com.pe', 'calidad',
       '$2b$12$fJcxbcHzNh8nVBLM82wEjODPPrXHV0Dh/OuRRn3uC7WhJqNKVRPae',
       'CALIDAD', 1
WHERE NOT EXISTS (SELECT 1 FROM usuarios WHERE username = 'calidad');
GO

PRINT 'Script 07 ejecutado — 7 usuarios de roles documentales insertados/actualizados.';
GO
