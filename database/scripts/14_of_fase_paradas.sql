-- ============================================================
-- Script 14: Tabla de paradas por fase de OF
-- Captura interrupciones durante el proceso de corte
-- (ej: parar una OF para atender una OF de emergencia)
-- ============================================================

-- Tabla principal de paradas
CREATE TABLE of_fase_paradas (
    id                  INT IDENTITY(1,1) PRIMARY KEY,
    of_id               INT          NOT NULL,
    fase_id             VARCHAR(5)   NOT NULL,          -- F1..F9
    inicio_parada       DATETIME     NOT NULL DEFAULT GETDATE(),
    fin_parada          DATETIME     NULL,               -- NULL = parada activa
    motivo              VARCHAR(30)  NOT NULL,           -- ver CHECK abajo
    of_emergencia_id    INT          NULL,               -- OF que causó la parada (si aplica)
    observacion         NVARCHAR(400) NULL,
    usuario_id          INT          NULL,
    created_at          DATETIME     NOT NULL DEFAULT GETDATE(),

    CONSTRAINT fk_parada_of
        FOREIGN KEY (of_id)            REFERENCES ordenes_fabricacion(id),
    CONSTRAINT fk_parada_of_emergencia
        FOREIGN KEY (of_emergencia_id) REFERENCES ordenes_fabricacion(id),
    CONSTRAINT fk_parada_usuario
        FOREIGN KEY (usuario_id)       REFERENCES usuarios(id),
    CONSTRAINT chk_parada_motivo CHECK (
        motivo IN ('EMERGENCIA_OF','MATERIAL','MAQUINA','ADMIN','OTRO')
    ),
    CONSTRAINT chk_parada_fechas CHECK (
        fin_parada IS NULL OR fin_parada >= inicio_parada
    )
);

-- Índices para las consultas más frecuentes
CREATE INDEX idx_paradas_of_fase   ON of_fase_paradas (of_id, fase_id);
CREATE INDEX idx_paradas_activas   ON of_fase_paradas (of_id, fin_parada)
    WHERE fin_parada IS NULL;       -- paradas sin cerrar
CREATE INDEX idx_paradas_emergencia ON of_fase_paradas (of_emergencia_id)
    WHERE of_emergencia_id IS NOT NULL;
