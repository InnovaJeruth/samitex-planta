-- ============================================================
-- SAMITEX-PLANTA · Script 01 · Creación de tablas
-- BD: SAMITEX-PLANTA · Servidor: PANO0142\SQLEXPRESS
-- ============================================================

USE [SAMITEX-PLANTA];
GO

-- ── USUARIOS ─────────────────────────────────────────────────
CREATE TABLE usuarios (
    id            INT           IDENTITY(1,1) PRIMARY KEY,
    nombre        NVARCHAR(100) NOT NULL,
    email         NVARCHAR(150) NOT NULL UNIQUE,
    username      NVARCHAR(50)  NOT NULL UNIQUE,
    password_hash NVARCHAR(255) NOT NULL,
    rol           NVARCHAR(30)  NOT NULL DEFAULT 'SOLO_LECTURA'
                  CHECK (rol IN ('ADMIN','GERENTE_PLANTA','JEFE_PLANTA','GERENCIA',
                                 'PLANEADOR','SUPERVISOR_CORTE','SOLO_LECTURA')),
    activo        BIT           NOT NULL DEFAULT 1,
    created_at    DATETIME2     NOT NULL DEFAULT GETDATE(),
    updated_at    DATETIME2     NOT NULL DEFAULT GETDATE()
);
GO

-- ── ÓRDENES DE FABRICACIÓN ───────────────────────────────────
CREATE TABLE ordenes_fabricacion (
    id               INT           IDENTITY(1,1) PRIMARY KEY,
    numero_of        NVARCHAR(30)  NOT NULL UNIQUE,
    cliente          NVARCHAR(200) NOT NULL,
    tipo_prenda      NVARCHAR(20)  NOT NULL
                     CHECK (tipo_prenda IN ('SACO','PANTALON','CAMISA','OTRO')),
    total_juegos     INT           NOT NULL,
    fecha_creacion   DATE          NOT NULL DEFAULT CAST(GETDATE() AS DATE),
    fecha_apt        DATE          NULL,
    estado           NVARCHAR(20)  NOT NULL DEFAULT 'BORRADOR'
                     CHECK (estado IN ('BORRADOR','ACTIVA','EN_PROCESO','COMPLETADA','ANULADA')),
    estampado_activo BIT           NOT NULL DEFAULT 0,
    solped_prenda    NVARCHAR(50)  NULL,
    orden_compra     NVARCHAR(50)  NULL,
    solped_mp        NVARCHAR(50)  NULL,
    responsable_id   INT           NULL REFERENCES usuarios(id),
    created_at       DATETIME2     NOT NULL DEFAULT GETDATE(),
    updated_at       DATETIME2     NOT NULL DEFAULT GETDATE()
);
GO

-- ── DOCUMENTOS DE LA OF ──────────────────────────────────────
CREATE TABLE documentos_of (
    id             INT           IDENTITY(1,1) PRIMARY KEY,
    of_id          INT           NOT NULL REFERENCES ordenes_fabricacion(id) ON DELETE CASCADE,
    tipo           NVARCHAR(30)  NOT NULL
                   CHECK (tipo IN ('FICHA_TECNICA','HOJA_COSTOS','MUESTRA_APROBADA',
                                   'REPORTE_TALLAS','MOLDES_LECTRA','CONFIRMACION_STOCK')),
    nombre_archivo NVARCHAR(255) NOT NULL,
    ruta_archivo   NVARCHAR(500) NOT NULL,
    uploaded_at    DATETIME2     NOT NULL DEFAULT GETDATE(),
    usuario_id     INT           NULL REFERENCES usuarios(id)
);
GO

-- ── CATÁLOGO DE FASES ────────────────────────────────────────
CREATE TABLE fases_catalogo (
    id          INT          IDENTITY(1,1) PRIMARY KEY,
    fase_id     NVARCHAR(5)  NOT NULL UNIQUE,   -- F1..F9
    nombre      NVARCHAR(50) NOT NULL,
    proceso     NVARCHAR(50) NOT NULL DEFAULT 'CORTE',
    orden       INT          NOT NULL,
    obligatoria BIT          NOT NULL DEFAULT 1,
    descripcion NVARCHAR(255) NULL
);
GO

-- ── PLANTILLAS DE PIEZAS ─────────────────────────────────────
CREATE TABLE plantilla_piezas (
    id                INT          IDENTITY(1,1) PRIMARY KEY,
    tipo_prenda       NVARCHAR(20) NOT NULL
                      CHECK (tipo_prenda IN ('SACO','PANTALON','CAMISA','OTRO')),
    nombre            NVARCHAR(100) NOT NULL,
    material_default  NVARCHAR(50)  NOT NULL DEFAULT 'TELA',
    cantidad_x_prenda INT           NOT NULL DEFAULT 1,
    fusionado_default BIT           NOT NULL DEFAULT 0,
    orden             INT           NOT NULL DEFAULT 0
);
GO

-- ── PIEZAS DE UNA OF ─────────────────────────────────────────
CREATE TABLE of_piezas (
    id                INT           IDENTITY(1,1) PRIMARY KEY,
    of_id             INT           NOT NULL REFERENCES ordenes_fabricacion(id) ON DELETE CASCADE,
    nombre            NVARCHAR(100) NOT NULL,
    codigo_sap        NVARCHAR(50)  NULL,
    material          NVARCHAR(50)  NOT NULL DEFAULT 'TELA',
    cantidad_x_prenda INT           NOT NULL DEFAULT 1,
    fusionado         BIT           NOT NULL DEFAULT 0,
    estampado_bordado BIT           NOT NULL DEFAULT 0,
    orden             INT           NOT NULL DEFAULT 0
);
GO

-- ── ESTADO DE FASES POR PIEZA ────────────────────────────────
CREATE TABLE of_fases_estado (
    id                 INT           IDENTITY(1,1) PRIMARY KEY,
    of_id              INT           NOT NULL REFERENCES ordenes_fabricacion(id) ON DELETE CASCADE,
    pieza_id           INT           NOT NULL REFERENCES of_piezas(id),
    fase_id            NVARCHAR(5)   NOT NULL,
    cantidad_actual    INT           NOT NULL DEFAULT 0,
    max_cantidad       INT           NOT NULL,
    completada         BIT           NOT NULL DEFAULT 0,
    fecha_inicio       DATETIME2     NULL,
    fecha_completado   DATETIME2     NULL,
    -- Datos específicos por fase
    eficiencia_tizado  DECIMAL(5,2)  NULL,   -- F1: % eficiencia (ej. 86.5)
    temperatura_fusion DECIMAL(5,2)  NULL,   -- F5: temperatura en °C
    tratamiento_orillo BIT           NULL,   -- F2: flag institucional
    motivo_rechazo     NVARCHAR(500) NULL,   -- F6: motivo si calidad rechaza
    CONSTRAINT UQ_of_pieza_fase UNIQUE (of_id, pieza_id, fase_id)
);
GO

-- ── REGISTROS DE AVANCE (LOG INMUTABLE) ──────────────────────
CREATE TABLE avance_registros (
    id          INT           IDENTITY(1,1) PRIMARY KEY,
    of_id       INT           NOT NULL REFERENCES ordenes_fabricacion(id),
    pieza_id    INT           NOT NULL REFERENCES of_piezas(id),
    fase_id     NVARCHAR(5)   NOT NULL,
    cantidad    INT           NOT NULL,
    usuario_id  INT           NULL REFERENCES usuarios(id),
    observacion NVARCHAR(500) NULL,
    created_at  DATETIME2     NOT NULL DEFAULT GETDATE(),
    revertido   BIT           NOT NULL DEFAULT 0
);
GO

-- ── ÍNDICES PARA PERFORMANCE ─────────────────────────────────
CREATE INDEX IX_of_estado        ON ordenes_fabricacion(estado);
CREATE INDEX IX_of_fecha_apt     ON ordenes_fabricacion(fecha_apt);
CREATE INDEX IX_avance_of_pieza  ON avance_registros(of_id, pieza_id, fase_id);
CREATE INDEX IX_fases_of_pieza   ON of_fases_estado(of_id, pieza_id);
GO

PRINT 'Script 01 ejecutado correctamente — Tablas creadas.';
GO
