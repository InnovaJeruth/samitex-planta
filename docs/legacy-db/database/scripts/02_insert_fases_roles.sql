-- ============================================================
-- SAMITEX-PLANTA · Script 02 · Datos base: fases y usuario admin
-- BD: SAMITEX-PLANTA · Servidor: PANO0142\SQLEXPRESS
-- ============================================================

USE [SAMITEX-PLANTA];
GO

-- ── CATÁLOGO DE FASES DEL PROCESO DE CORTE ───────────────────
INSERT INTO fases_catalogo (fase_id, nombre, proceso, orden, obligatoria, descripcion) VALUES
('F1', 'TIZADO',           'CORTE', 1, 1, 'Registrar % eficiencia del trazo. Objetivo: 85-87%.'),
('F2', 'TENDIDO',          'CORTE', 2, 1, 'Si tipo negocio = INSTITUCIÓN: registrar flag tratamiento de orillo.'),
('F3', 'CORTE',            'CORTE', 3, 1, 'Ejecución del corte.'),
('F4', 'NUMERADO',         'CORTE', 4, 1, 'Numeración de piezas.'),
('F8', 'ESTAMPADO/BORDADO','CORTE', 5, 0, 'Opcional. Activar por OF. Registrar qué piezas van a estampado/bordado.'),
('F9', 'AUDITORIA CALIDAD','CORTE', 6, 0, 'Opcional. Se activa automáticamente con F8. Registra resultado por pieza.'),
('F5', 'FUSIONADO',        'CORTE', 7, 1, 'No toda pieza fusiona. Registrar temperatura (°C). Rango: 150-155°C.'),
('F6', 'CALIDAD',          'CORTE', 8, 1, 'Validación de piezas. Gateway reproceso: motivo + devolver a EN_PROCESO.'),
('F7', 'HABILITADO',       'CORTE', 9, 1, 'Despacho final a Costura. Cierra el Proceso de Corte.');
GO

-- ── USUARIO ADMINISTRADOR INICIAL ────────────────────────────
-- Contraseña: Admin2026!   (cambiar en primer ingreso)
-- Hash bcrypt generado con passlib rounds=12
INSERT INTO usuarios (nombre, email, username, password_hash, rol) VALUES
(
    'Administrador del Sistema',
    'admin@samitex.com.pe',
    'admin',
    '$2b$12$C2IxsApoFldxrnYtnneOnedEFTPbhPGx0L6WRhPG8XWTYBnjjfJ2W',
    'ADMIN'
);
GO

PRINT 'Script 02 ejecutado correctamente — Fases y admin creados.';
GO
