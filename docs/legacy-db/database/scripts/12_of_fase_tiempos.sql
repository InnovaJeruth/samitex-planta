-- =============================================================
-- Migración 12: Tabla of_fase_tiempos
-- Almacena tiempos programados y reales por OF × Fase (nivel OF)
-- A diferencia de of_fases_estado (nivel pieza × fase),
-- esta tabla tiene UNA fila por OF × fase.
-- =============================================================

IF NOT EXISTS (
    SELECT 1 FROM INFORMATION_SCHEMA.TABLES
    WHERE TABLE_NAME = 'of_fase_tiempos'
)
BEGIN
    CREATE TABLE of_fase_tiempos (
        id                  INT IDENTITY(1,1) PRIMARY KEY,
        of_id               INT          NOT NULL,
        fase_id             VARCHAR(5)   NOT NULL,
        inicio_programado   DATETIME     NULL,   -- Supervisor ingresa (fecha + hora)
        fin_programado      DATETIME     NULL,   -- Supervisor ingresa (fecha + hora)
        inicio_real         DATETIME     NULL,   -- Auto al presionar "Iniciar fase"
        fin_real            DATETIME     NULL,   -- Auto al completar todas las piezas

        CONSTRAINT fk_oft_of
            FOREIGN KEY (of_id) REFERENCES ordenes_fabricacion(id),
        CONSTRAINT uq_oft_of_fase
            UNIQUE (of_id, fase_id)
    );

    PRINT 'Tabla of_fase_tiempos creada correctamente.';
END
ELSE
BEGIN
    PRINT 'La tabla of_fase_tiempos ya existe — sin cambios.';
END
