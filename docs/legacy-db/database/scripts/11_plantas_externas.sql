-- Migración: Catálogo de plantas externas + historial tercerización
-- Ejecutar en: PANO0142\SQLEXPRESS → base samitex_planta

-- 1. Catálogo de plantas externas
CREATE TABLE plantas_externas (
    id          INT IDENTITY(1,1) PRIMARY KEY,
    nombre      VARCHAR(150) NOT NULL,
    ruc         VARCHAR(11)  NOT NULL,
    encargado   VARCHAR(120) NOT NULL,
    direccion   VARCHAR(300) NOT NULL,
    activo      BIT NOT NULL DEFAULT 1,
    created_at  DATETIME NOT NULL DEFAULT GETDATE()
);

-- 2. Historial de cambios de fecha de recepción estimada
CREATE TABLE terc_historial_fechas (
    id              INT IDENTITY(1,1) PRIMARY KEY,
    of_id           INT NOT NULL REFERENCES ordenes_fabricacion(id),
    planta_id       INT NOT NULL REFERENCES plantas_externas(id),
    fecha_anterior  DATE NULL,
    fecha_nueva     DATE NOT NULL,
    motivo          VARCHAR(300) NULL,
    usuario_id      INT NULL REFERENCES usuarios(id),
    created_at      DATETIME NOT NULL DEFAULT GETDATE()
);

-- 3. Registro de recepciones parciales
CREATE TABLE terc_recepciones (
    id               INT IDENTITY(1,1) PRIMARY KEY,
    of_id            INT NOT NULL REFERENCES ordenes_fabricacion(id),
    planta_id        INT NOT NULL REFERENCES plantas_externas(id),
    juegos_recibidos INT NOT NULL,
    fecha_recepcion  DATE NOT NULL,
    observacion      VARCHAR(500) NULL,
    usuario_id       INT NULL REFERENCES usuarios(id),
    created_at       DATETIME NOT NULL DEFAULT GETDATE()
);

-- 4. Columnas nuevas en ordenes_fabricacion
ALTER TABLE ordenes_fabricacion
    ADD planta_id        INT NULL REFERENCES plantas_externas(id),
        juegos_recibidos INT NOT NULL DEFAULT 0;

-- Verificar
SELECT 'plantas_externas'      AS tabla, COUNT(*) AS registros FROM plantas_externas
UNION ALL
SELECT 'terc_historial_fechas', COUNT(*) FROM terc_historial_fechas
UNION ALL
SELECT 'terc_recepciones',      COUNT(*) FROM terc_recepciones;
