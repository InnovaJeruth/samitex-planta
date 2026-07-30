-- Migración 16: tabla de parámetros configurables del sistema
CREATE TABLE parametros_sistema (
    clave       VARCHAR(50)  NOT NULL PRIMARY KEY,
    valor       VARCHAR(255) NOT NULL,
    descripcion NVARCHAR(500) NULL,
    updated_at  DATETIME     NOT NULL DEFAULT GETDATE()
);

-- Seed: capacidad máxima de corte por día (en juegos)
INSERT INTO parametros_sistema (clave, valor, descripcion)
VALUES ('corte_cap_diaria_juegos', '500',
        N'Máximo de juegos programables por día en el área de Corte');
