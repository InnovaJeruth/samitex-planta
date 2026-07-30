-- ============================================================
-- SAMITEX-PLANTA · Script 08 · Ampliar CHECK constraint rol
-- Ejecutar ANTES de 07_seed_nuevos_roles.sql (o re-ejecutar 07)
-- ============================================================

USE [SAMITEX-PLANTA];
GO

-- ── 1. Eliminar el CHECK constraint existente en rol ──────────
DECLARE @constraint_name NVARCHAR(200);
SELECT @constraint_name = cc.name
FROM sys.check_constraints cc
JOIN sys.columns c ON cc.parent_object_id = c.object_id
                  AND cc.parent_column_id = c.column_id
WHERE OBJECT_NAME(cc.parent_object_id) = 'usuarios'
  AND c.name = 'rol';

IF @constraint_name IS NOT NULL
BEGIN
    EXEC('ALTER TABLE usuarios DROP CONSTRAINT [' + @constraint_name + ']');
    PRINT 'CHECK constraint eliminado: ' + @constraint_name;
END
ELSE
    PRINT 'No se encontró CHECK constraint en rol — omitido.';
GO

-- ── 2. Agregar nuevo CHECK constraint con todos los roles ─────
ALTER TABLE usuarios
ADD CONSTRAINT CK_usuarios_rol CHECK (
    rol IN (
        'ADMIN',
        'GERENTE_PLANTA',
        'JEFE_PLANTA',
        'GERENCIA',
        'PLANEADOR',
        'SUPERVISOR_CORTE',
        'SOLO_LECTURA',
        'UDP',
        'COMERCIAL',
        'COMERCIAL_MARCA',
        'PLANEAMIENTO_MARCA',
        'INGENIERIA',
        'LOGISTICA',
        'CALIDAD'
    )
);
PRINT 'CHECK constraint CK_usuarios_rol creado con 14 roles.';
GO

PRINT 'Script 08 ejecutado correctamente. Ahora puede ejecutar 07_seed_nuevos_roles.sql.';
GO
