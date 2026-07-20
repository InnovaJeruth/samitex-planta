-- Migración manual equivalente a 20260630_terc_log
-- Ejecutar en SSMS sobre [SAMITEX-PLANTA]

-- 1. Agregar fase_id a terc_recepciones
ALTER TABLE terc_recepciones ADD fase_id NVARCHAR(5) NULL;

-- 2. Crear tabla terc_subproceso_log
CREATE TABLE terc_subproceso_log (
    id                   INT IDENTITY(1,1) PRIMARY KEY,
    of_id                INT NOT NULL REFERENCES ordenes_fabricacion(id),
    planta_id            INT NOT NULL REFERENCES plantas_externas(id),
    fase_id              NVARCHAR(5)  NULL,
    estado               NVARCHAR(20) NOT NULL DEFAULT 'PROGRAMADO',
    juegos_enviados      INT NULL,
    juegos_recibidos     INT NULL,
    fecha_programado     DATETIME     NOT NULL DEFAULT GETDATE(),
    fecha_envio          DATE NULL,
    fecha_recepcion_est  DATE NULL,
    fecha_recepcion_real DATE NULL,
    fecha_completado     DATETIME NULL,
    observacion          NVARCHAR(MAX) NULL,
    usuario_creo_id      INT NULL REFERENCES usuarios(id),
    usuario_envio_id     INT NULL REFERENCES usuarios(id),
    usuario_recepcion_id INT NULL REFERENCES usuarios(id)
);

-- 3. Marcar versión en alembic (verificar si ya hay fila primero)
-- Si alembic_version tiene una fila:
UPDATE alembic_version SET version_num = '20260630_terc_log';
-- Si alembic_version está vacía:
-- INSERT INTO alembic_version (version_num) VALUES ('20260630_terc_log');
