"""
Modelos de ingeniería industrial — Samitex Planta
Prefijo: ing_  (tablas independientes, no modifican las operativas)
"""
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, Date, DateTime, Text, Index
)
from sqlalchemy.sql import func

from app.database.connection import Base


class IngSamRegistro(Base):
    """Registros de estudio de tiempos (Cronometraje OIT / SAM)."""
    __tablename__ = "ing_sam_registros"

    id               = Column(Integer, primary_key=True, index=True)
    of_numero        = Column(String(50),  nullable=False, index=True)
    fecha            = Column(Date,        nullable=False)
    operario         = Column(String(100), nullable=False)
    fase             = Column(String(50),  nullable=False)
    elemento         = Column(String(200), nullable=False)
    # Lecturas individuales almacenadas como JSON: "[1.23, 1.45, ...]"
    tiempos_json     = Column(Text,        nullable=True)
    factor_valoracion = Column(Float,      nullable=False, default=100.0)
    suplementos_pct  = Column(Float,       nullable=False, default=15.0)
    tiempo_normal    = Column(Float,       nullable=True)   # seg
    sam              = Column(Float,       nullable=True)   # seg
    created_at       = Column(DateTime,    server_default=func.now())

    __table_args__ = (
        Index("ix_ing_sam_of_fecha", "of_numero", "fecha"),
    )


class IngParadaRegistro(Base):
    """Registro de paradas por turno."""
    __tablename__ = "ing_paradas_registro"

    id          = Column(Integer,    primary_key=True, index=True)
    of_numero   = Column(String(50), nullable=False, index=True)
    fecha       = Column(Date,       nullable=False)
    turno       = Column(String(20), nullable=False)
    fase        = Column(String(50), nullable=False)
    causa       = Column(String(100),nullable=False)
    duracion_min = Column(Float,     nullable=False)
    observacion = Column(Text,       nullable=True)
    created_at  = Column(DateTime,   server_default=func.now())

    __table_args__ = (
        Index("ix_ing_paradas_of_fecha", "of_numero", "fecha"),
    )


class IngMuestreoObs(Base):
    """Observación de muestreo de trabajo (método Tippett)."""
    __tablename__ = "ing_muestreo_obs"

    id          = Column(Integer,    primary_key=True, index=True)
    of_numero   = Column(String(50), nullable=False, index=True)
    fecha       = Column(Date,       nullable=False)
    hora        = Column(String(10), nullable=False)   # HH:MM
    fase        = Column(String(50), nullable=False)
    estado      = Column(String(30), nullable=False)  # Activo / En espera / Parado
    observacion = Column(Text,       nullable=True)
    created_at  = Column(DateTime,   server_default=func.now())

    __table_args__ = (
        Index("ix_ing_muestreo_of_fecha", "of_numero", "fecha"),
    )


class IngTendidoFicha(Base):
    """Ficha de tendido por tender."""
    __tablename__ = "ing_tendido_fichas"

    id                  = Column(Integer,    primary_key=True, index=True)
    fecha               = Column(Date,       nullable=False)
    of_numero           = Column(String(50), nullable=False, index=True)
    tipo_prenda         = Column(String(100),nullable=False)
    tela_partida        = Column(String(100),nullable=False)
    largo_tender_m      = Column(Float,      nullable=False)
    num_capas           = Column(Integer,    nullable=False)
    ancho_tela_m        = Column(Float,      nullable=False)
    num_prendas         = Column(Integer,    nullable=False)
    retazo_kg           = Column(Float,      nullable=False, default=0.0)
    area_tizado_m2      = Column(Float,      nullable=False)
    pct_aprovechamiento = Column(Float,      nullable=True)   # calculado
    area_tendida_m2     = Column(Float,      nullable=True)   # calculado
    created_at          = Column(DateTime,   server_default=func.now())

    __table_args__ = (
        Index("ix_ing_tendido_of_fecha", "of_numero", "fecha"),
    )


class IngCalidadInspeccion(Base):
    """Inspección de calidad (Check Sheet — FPY)."""
    __tablename__ = "ing_calidad_inspeccion"

    id                  = Column(Integer,    primary_key=True, index=True)
    fecha               = Column(Date,       nullable=False)
    of_numero           = Column(String(50), nullable=False, index=True)
    tipo_prenda         = Column(String(100),nullable=False)
    total_inspeccionado = Column(Integer,    nullable=False)
    def_mal_corte       = Column(Integer,    nullable=False, default=0)
    def_fusionado       = Column(Integer,    nullable=False, default=0)
    def_numeracion      = Column(Integer,    nullable=False, default=0)
    def_tela            = Column(Integer,    nullable=False, default=0)
    def_medida          = Column(Integer,    nullable=False, default=0)
    def_otro            = Column(Integer,    nullable=False, default=0)
    total_defectos      = Column(Integer,    nullable=True)   # calculado
    aprobadas           = Column(Integer,    nullable=True)   # calculado
    fpy                 = Column(Float,      nullable=True)   # calculado %
    created_at          = Column(DateTime,   server_default=func.now())

    __table_args__ = (
        Index("ix_ing_calidad_of_fecha", "of_numero", "fecha"),
    )


class IngOleDiario(Base):
    """Parte diario OLE (Overall Labor Effectiveness)."""
    __tablename__ = "ing_ole_diario"

    id                = Column(Integer,    primary_key=True, index=True)
    of_numero         = Column(String(50), nullable=False, index=True)
    fecha             = Column(Date,       nullable=False)
    turno             = Column(String(20), nullable=False)
    fase              = Column(String(50), nullable=False)
    num_operarios     = Column(Integer,    nullable=False)
    horas_programadas = Column(Float,      nullable=False)
    horas_trabajadas  = Column(Float,      nullable=False)
    produccion_real   = Column(Integer,    nullable=False)
    produccion_std    = Column(Integer,    nullable=False)
    piezas_buenas     = Column(Integer,    nullable=False)
    disponibilidad    = Column(Float,      nullable=True)   # % calculado
    rendimiento       = Column(Float,      nullable=True)   # % calculado
    calidad_pct       = Column(Float,      nullable=True)   # % calculado
    ole               = Column(Float,      nullable=True)   # % calculado
    created_at        = Column(DateTime,   server_default=func.now())

    __table_args__ = (
        Index("ix_ing_ole_of_fecha", "of_numero", "fecha"),
    )


class IngFusionadoParam(Base):
    """Parámetros de proceso de fusionado por registro."""
    __tablename__ = "ing_fusionado_params"

    id            = Column(Integer,    primary_key=True, index=True)
    of_numero     = Column(String(50), nullable=False, index=True)
    fecha         = Column(Date,       nullable=False)
    turno         = Column(String(20), nullable=False)
    referencia    = Column(String(200),nullable=False)
    temperatura_c = Column(Float,      nullable=False)
    presion_kgcm2 = Column(Float,      nullable=False)
    tiempo_seg    = Column(Float,      nullable=False)
    num_piezas    = Column(Integer,    nullable=False)
    observacion   = Column(Text,       nullable=True)
    created_at    = Column(DateTime,   server_default=func.now())

    __table_args__ = (
        Index("ix_ing_fusion_of_fecha", "of_numero", "fecha"),
    )


class IngHabilitadoCierre(Base):
    """Cierre de OF en fase Habilitado — entrega a costura."""
    __tablename__ = "ing_habilitado_cierre"

    id                  = Column(Integer,    primary_key=True, index=True)
    of_numero           = Column(String(50), nullable=False, index=True)
    fecha               = Column(Date,       nullable=False)
    turno               = Column(String(20), nullable=False)
    supervisor          = Column(String(100),nullable=False)
    prendas_cortadas    = Column(Integer,    nullable=False)
    prendas_entregadas  = Column(Integer,    nullable=False)
    kit_completo        = Column(String(50), nullable=False)
    pct_entrega         = Column(Float,      nullable=True)   # calculado
    observacion         = Column(Text,       nullable=True)
    created_at          = Column(DateTime,   server_default=func.now())

    __table_args__ = (
        Index("ix_ing_hab_of_fecha", "of_numero", "fecha"),
    )


class IngIshikawaCausa(Base):
    """Catálogo de causas raíz — Análisis Ishikawa + 5 Porqués."""
    __tablename__ = "ing_ishikawa_causas"

    id          = Column(Integer,     primary_key=True, index=True)
    categoria   = Column(String(50),  nullable=False)   # maquina, metodo, material, mano, medio, medicion
    causa_texto = Column(Text,        nullable=False)
    # 5 Porqués almacenados como JSON: ["pq1", "pq2", ...]
    porques_json = Column(Text,       nullable=True)
    causa_raiz  = Column(Text,        nullable=True)
    validada    = Column(Boolean,     default=False)
    created_at  = Column(DateTime,    server_default=func.now())
    updated_at  = Column(DateTime,    server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("ix_ing_ishi_cat_validada", "categoria", "validada"),
    )
