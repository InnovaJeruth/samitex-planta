"""
Catálogo de prendas — Samitex Planta
"""
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Index, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database.connection import Base

TIPOS_DOC_PRENDA  = ["FICHA_TECNICA", "MOLDE", "MUESTRA_APROBADA"]
TIPOS_BASE_PRENDA = ["SACO", "PANTALON", "CAMISA", "PULLOVER"]
FITS_PRENDA = [
    ("CLASSIC_FIT", "Classic Fit"),
    ("MODERN_FIT",  "Modern Fit"),
    ("SLIM_FIT",    "Slim Fit"),
]

# Avios: CORTE no aplica — en corte se usa materia prima, no avios
SECCIONES_AVIO  = ["COSTURA", "ACABADOS", "EMBALAJE"]
UNIDADES_MEDIDA = ["mt.", "Unid", "Cono", "Gruesa", "Millar", "Kg.", "Yarda", "Docena"]
MONEDAS_AVIO    = ["SO", "DO", "EU"]

TIPOS_MP        = ["TELA_PRINCIPAL", "ENTRETELA", "FORRO", "ACCESORIO"]
UNIDADES_MP     = ["mt.", "Yarda"]


class PrendaCatalogo(Base):
    """Prenda del catalogo. tipo_cliente=BASE define estructura tecnica;
    INSTITUCION/MARCA son variantes comerciales con color propio."""
    __tablename__ = "prendas_catalogo"

    id             = Column(Integer, primary_key=True, index=True)
    codigo         = Column(String(30),  unique=True, nullable=False, index=True)
    nombre         = Column(String(150), nullable=False)
    tipo_base      = Column(String(20),  nullable=False)
    descripcion    = Column(String(500), nullable=True)
    imagen_ruta    = Column(String(500), nullable=True)
    tipo_cliente   = Column(String(20),  nullable=False, server_default="BASE")
    fit            = Column(String(30),  nullable=True)
    color          = Column(String(50),  nullable=True)   # solo variantes
    composicion    = Column(String(200), nullable=True)   # ej: 50%COTTON 50%POLYESTER
    activo         = Column(Boolean,     default=True,  nullable=False)
    creado_por_rol = Column(String(30),  nullable=True)
    created_at     = Column(DateTime,    server_default=func.now())
    updated_at     = Column(DateTime,    server_default=func.now(), onupdate=func.now())

    plantilla_piezas = relationship("PlantillaPieza",    back_populates="prenda_catalogo",
                                    cascade="all, delete-orphan")
    ofs              = relationship("OrdenFabricacion",  back_populates="prenda_catalogo")
    documentos       = relationship("PrendaDocumento",   back_populates="prenda",
                                    cascade="all, delete-orphan", order_by="PrendaDocumento.created_at")
    avios            = relationship("CatalogoAvio",      back_populates="prenda",
                                    cascade="all, delete-orphan", order_by="CatalogoAvio.orden")
    avio_configs     = relationship("PrendaAvioConfig",  back_populates="prenda",
                                    cascade="all, delete-orphan")
    materiales       = relationship("CatalogoMp",        back_populates="prenda",
                                    cascade="all, delete-orphan", order_by="CatalogoMp.orden")
    mp_configs       = relationship("PrendaMpConfig",    back_populates="prenda",
                                    cascade="all, delete-orphan")
    skus             = relationship("PrendaSku",         back_populates="prenda",
                                    cascade="all, delete-orphan", order_by="PrendaSku.orden")
    hojas_costos     = relationship("HojaCostos",        back_populates="prenda",
                                    cascade="all, delete-orphan", order_by="HojaCostos.created_at")

    __table_args__ = (
        Index("ix_prendas_catalogo_tipo_activo", "tipo_base", "activo"),
    )


class CatalogoAvio(Base):
    """Avio definido en la prenda BASE (o directamente en variante).
    codigo_base = referencia trazabilidad al código SAP del item BASE equivalente."""
    __tablename__ = "catalogo_avios"

    id                 = Column(Integer,      primary_key=True, index=True)
    prenda_catalogo_id = Column(Integer,      ForeignKey("prendas_catalogo.id", ondelete="CASCADE"),
                                nullable=False, index=True)
    seccion            = Column(String(20),   nullable=False)   # COSTURA|ACABADOS|EMBALAJE
    nombre             = Column(String(200),  nullable=False)
    codigo_interno     = Column(String(50),   nullable=True)
    codigo_base        = Column(String(60),   nullable=True)    # trazabilidad BASE→VARIANTE
    proveedor          = Column(String(150),  nullable=True)
    procedencia        = Column(String(20),   nullable=True)
    unidad_medida      = Column(String(20),   nullable=False, server_default="Unid")
    consumo_unitario   = Column(Float,        nullable=False, default=1.0)
    pct_adicional      = Column(Float,        nullable=False, default=0.01)
    unidad_compra      = Column(String(20),   nullable=True)
    factor_conversion  = Column(Float,        nullable=False, server_default='1')  # Unid/UC ej: 4572 mt/cono
    moneda             = Column(String(5),    nullable=True)
    precio             = Column(Float,        nullable=True)
    orden              = Column(Integer,      nullable=False, default=0)
    activo             = Column(Boolean,      default=True,  nullable=False)
    created_at         = Column(DateTime,     server_default=func.now())

    prenda      = relationship("PrendaCatalogo",   back_populates="avios")
    configs     = relationship("PrendaAvioConfig", back_populates="avio", cascade="all, delete-orphan")
    sku_configs = relationship("PrendaSkuAvioConfig", back_populates="avio", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_catalogo_avios_prenda_sec", "prenda_catalogo_id", "seccion"),
    )


class PrendaAvioConfig(Base):
    """Configuracion de un avio BASE para una prenda variante (excluir / codigo cliente / override)."""
    __tablename__ = "prenda_avio_config"

    id                 = Column(Integer,     primary_key=True, index=True)
    prenda_catalogo_id = Column(Integer,     ForeignKey("prendas_catalogo.id", ondelete="CASCADE"),
                                nullable=False, index=True)
    avio_id            = Column(Integer,     ForeignKey("catalogo_avios.id",   ondelete="NO ACTION"),
                                nullable=False)
    codigo_cliente     = Column(String(50),  nullable=True)
    excluido           = Column(Boolean,     default=False, nullable=False)
    consumo_override   = Column(Float,       nullable=True)
    notas              = Column(String(300), nullable=True)
    created_at         = Column(DateTime,    server_default=func.now())
    updated_at         = Column(DateTime,    server_default=func.now(), onupdate=func.now())

    prenda = relationship("PrendaCatalogo", back_populates="avio_configs")
    avio   = relationship("CatalogoAvio",   back_populates="configs")

    __table_args__ = (
        Index("ix_prenda_avio_config_prenda_avio", "prenda_catalogo_id", "avio_id", unique=True),
    )


class CatalogoMp(Base):
    """Materia prima definida en la prenda BASE (o directamente en variante).
    codigo_base = referencia trazabilidad al código SAP del item BASE equivalente."""
    __tablename__ = "catalogo_mp"

    id                 = Column(Integer,      primary_key=True, index=True)
    prenda_catalogo_id = Column(Integer,      ForeignKey("prendas_catalogo.id", ondelete="CASCADE"),
                                nullable=False, index=True)
    nombre             = Column(String(200),  nullable=False)
    tipo               = Column(String(30),   nullable=False)   # TELA_PRINCIPAL|ENTRETELA|FORRO|ACCESORIO
    ancho_referencia   = Column(Float,        nullable=True)
    consumo_unitario   = Column(Float,        nullable=False, default=1.0)
    pct_adicional      = Column(Float,        nullable=False, default=0.02)
    unidad_medida      = Column(String(10),   nullable=False, server_default="mt.")
    unidad_compra      = Column(String(20),   nullable=True)
    factor_conversion  = Column(Float,        nullable=False, server_default='1')  # Unid/UC ej: 4572 mt/cono
    codigo_interno     = Column(String(50),   nullable=True)
    codigo_base        = Column(String(60),   nullable=True)    # trazabilidad BASE→VARIANTE
    proveedor          = Column(String(150),  nullable=True)
    procedencia        = Column(String(20),   nullable=True)   # LOCAL | IMPORTADO
    moneda             = Column(String(5),    nullable=True)
    precio_referencia  = Column(Float,        nullable=True)
    orden              = Column(Integer,      nullable=False, default=0)
    activo             = Column(Boolean,      default=True,  nullable=False)
    created_at         = Column(DateTime,     server_default=func.now())

    prenda      = relationship("PrendaCatalogo", back_populates="materiales")
    configs     = relationship("PrendaMpConfig", back_populates="mp", cascade="all, delete-orphan")
    sku_configs = relationship("PrendaSkuMpConfig", back_populates="mp", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_catalogo_mp_prenda", "prenda_catalogo_id"),
    )


class PrendaMpConfig(Base):
    """Configuracion de un material BASE para una prenda variante (excluir / codigo cliente / override)."""
    __tablename__ = "prenda_mp_config"

    id                 = Column(Integer,     primary_key=True, index=True)
    prenda_catalogo_id = Column(Integer,     ForeignKey("prendas_catalogo.id", ondelete="CASCADE"),
                                nullable=False, index=True)
    mp_id              = Column(Integer,     ForeignKey("catalogo_mp.id", ondelete="NO ACTION"),
                                nullable=False)
    codigo_cliente     = Column(String(50),  nullable=True)
    excluido           = Column(Boolean,     default=False, nullable=False)
    consumo_override   = Column(Float,       nullable=True)
    notas              = Column(String(300), nullable=True)
    created_at         = Column(DateTime,    server_default=func.now())
    updated_at         = Column(DateTime,    server_default=func.now(), onupdate=func.now())

    prenda = relationship("PrendaCatalogo", back_populates="mp_configs")
    mp     = relationship("CatalogoMp",     back_populates="configs")

    __table_args__ = (
        Index("ix_prenda_mp_config_prenda_mp", "prenda_catalogo_id", "mp_id", unique=True),
    )


class PrendaSku(Base):
    """SKU por talla de una prenda variante."""
    __tablename__ = "prenda_skus"

    id                 = Column(Integer,     primary_key=True, index=True)
    prenda_catalogo_id = Column(Integer,     ForeignKey("prendas_catalogo.id", ondelete="CASCADE"),
                                nullable=False, index=True)
    talla              = Column(String(20),  nullable=False)
    codigo_sku         = Column(String(50),  nullable=True)
    orden              = Column(Integer,     nullable=False, default=0)
    activo             = Column(Boolean,     default=True,  nullable=False)
    created_at         = Column(DateTime,    server_default=func.now())

    prenda      = relationship("PrendaCatalogo",      back_populates="skus")
    mp_configs  = relationship("PrendaSkuMpConfig",   back_populates="sku", cascade="all, delete-orphan")
    avio_configs= relationship("PrendaSkuAvioConfig",  back_populates="sku", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_prenda_skus_prenda", "prenda_catalogo_id"),
        Index("ix_prenda_skus_prenda_talla", "prenda_catalogo_id", "talla", unique=True),
    )


class PrendaSkuMpConfig(Base):
    """Override de consumo de MP para un SKU especifico (metraje varía por talla)."""
    __tablename__ = "prenda_sku_mp_config"

    id               = Column(Integer, primary_key=True, index=True)
    sku_id           = Column(Integer, ForeignKey("prenda_skus.id",  ondelete="CASCADE"),  nullable=False, index=True)
    mp_id            = Column(Integer, ForeignKey("catalogo_mp.id",  ondelete="NO ACTION"), nullable=False)
    consumo_override = Column(Float,   nullable=False)
    notas            = Column(String(200), nullable=True)
    created_at       = Column(DateTime, server_default=func.now())
    updated_at       = Column(DateTime, server_default=func.now(), onupdate=func.now())

    sku = relationship("PrendaSku",   back_populates="mp_configs")
    mp  = relationship("CatalogoMp",  back_populates="sku_configs")

    __table_args__ = (
        Index("ix_sku_mp_config_sku_mp", "sku_id", "mp_id", unique=True),
    )


class PrendaSkuAvioConfig(Base):
    """Override de codigo de avio para un SKU especifico."""
    __tablename__ = "prenda_sku_avio_config"

    id              = Column(Integer, primary_key=True, index=True)
    sku_id          = Column(Integer, ForeignKey("prenda_skus.id",    ondelete="CASCADE"),   nullable=False, index=True)
    avio_id         = Column(Integer, ForeignKey("catalogo_avios.id", ondelete="NO ACTION"), nullable=False)
    codigo_override = Column(String(50),  nullable=True)
    notas           = Column(String(200), nullable=True)
    created_at      = Column(DateTime, server_default=func.now())
    updated_at      = Column(DateTime, server_default=func.now(), onupdate=func.now())

    sku   = relationship("PrendaSku",     back_populates="avio_configs")
    avio  = relationship("CatalogoAvio",  back_populates="sku_configs")

    __table_args__ = (
        Index("ix_sku_avio_config_sku_avio", "sku_id", "avio_id", unique=True),
    )


class PrendaDocumento(Base):
    """Documentos adjuntos a una prenda del catalogo."""
    __tablename__ = "prenda_documentos"

    id                 = Column(Integer,     primary_key=True, index=True)
    prenda_catalogo_id = Column(Integer,     ForeignKey("prendas_catalogo.id"), nullable=False, index=True)
    tipo               = Column(String(30),  nullable=False)
    nombre_archivo     = Column(String(255), nullable=False)
    ruta_archivo       = Column(String(500), nullable=False)
    descripcion        = Column(String(300), nullable=True)
    subido_por_id      = Column(Integer,     ForeignKey("usuarios.id"), nullable=True)
    created_at         = Column(DateTime,    server_default=func.now())

    prenda     = relationship("PrendaCatalogo", back_populates="documentos")
    subido_por = relationship("Usuario",        foreign_keys=[subido_por_id])

    __table_args__ = (
        Index("ix_prenda_documentos_prenda", "prenda_catalogo_id"),
    )


# ── Hoja de Costos ────────────────────────────────────────────

ESTADOS_HOJA_COSTOS = ["BORRADOR", "APROBADA"]
TIPOS_LINEA_HOJA    = ["MP", "AVIO"]


class HojaCostos(Base):
    """Hoja de costos teorica asociada a una variante del catalogo.
    Se crea una por variante. Para MARCA se reutiliza entre OFs.
    Para INSTITUCION se crea en etapa de muestra y la OF la hereda."""
    __tablename__ = "hojas_costos"

    id                 = Column(Integer,     primary_key=True, index=True)
    prenda_catalogo_id = Column(Integer,     ForeignKey("prendas_catalogo.id", ondelete="CASCADE"),
                                nullable=False, index=True)
    estado             = Column(String(20),  nullable=False, default="BORRADOR")
    notas              = Column(Text,        nullable=True)
    total_mp           = Column(Float,       nullable=True)
    total_avios        = Column(Float,       nullable=True)
    total_general      = Column(Float,       nullable=True)
    moneda_base        = Column(String(5),   nullable=False, default="SO")
    tipo_cambio        = Column(Float,       nullable=False, server_default='3.70')  # USD→SO
    creado_por_id      = Column(Integer,     ForeignKey("usuarios.id"), nullable=True)
    aprobado_por_id    = Column(Integer,     ForeignKey("usuarios.id"), nullable=True)
    aprobado_at        = Column(DateTime,    nullable=True)
    created_at         = Column(DateTime,    server_default=func.now())
    updated_at         = Column(DateTime,    server_default=func.now(), onupdate=func.now())

    prenda       = relationship("PrendaCatalogo", back_populates="hojas_costos")
    lineas       = relationship("HojaCostosLinea", back_populates="hoja",
                                cascade="all, delete-orphan", order_by="HojaCostosLinea.orden")
    creado_por   = relationship("Usuario", foreign_keys=[creado_por_id])
    aprobado_por = relationship("Usuario", foreign_keys=[aprobado_por_id])

    __table_args__ = (
        Index("ix_hojas_costos_prenda", "prenda_catalogo_id"),
    )


class HojaCostosLinea(Base):
    """Linea de detalle de una HojaCostos.
    precio_snapshot = precio al momento de crear la hoja (no cambia si el catalogo se actualiza)."""
    __tablename__ = "hojas_costos_lineas"

    id               = Column(Integer,     primary_key=True, index=True)
    hoja_id          = Column(Integer,     ForeignKey("hojas_costos.id", ondelete="CASCADE"),
                              nullable=False, index=True)
    tipo             = Column(String(10),  nullable=False)
    item_id          = Column(Integer,     nullable=False)
    seccion          = Column(String(30),  nullable=True)
    nombre           = Column(String(200), nullable=False)
    unidad_medida      = Column(String(20),  nullable=True)
    unidad_compra      = Column(String(20),  nullable=True)
    factor_conversion  = Column(Float,       nullable=False, server_default='1')
    consumo_unitario   = Column(Float,       nullable=False, default=1.0)
    pct_adicional      = Column(Float,       nullable=False, default=0.0)
    precio_snapshot    = Column(Float,       nullable=True)
    moneda           = Column(String(5),   nullable=True)
    subtotal         = Column(Float,       nullable=True)
    editado_manual   = Column(Boolean,     default=False)
    notas            = Column(String(300), nullable=True)
    orden            = Column(Integer,     nullable=False, default=0)
    created_at       = Column(DateTime,    server_default=func.now())

    hoja = relationship("HojaCostos", back_populates="lineas")

    __table_args__ = (
        Index("ix_hojas_costos_lineas_hoja", "hoja_id"),
    )


# ── Historial de precios ──────────────────────────────────────

class PrecioHistorico(Base):
    """Registra cada cambio de precio en MP o Avio del catalogo.
    Se inserta automaticamente antes de sobreescribir el precio actual."""
    __tablename__ = "precios_historicos"

    id                = Column(Integer,     primary_key=True, index=True)
    tipo              = Column(String(10),  nullable=False)
    item_id           = Column(Integer,     nullable=False)
    nombre_item       = Column(String(200), nullable=False)
    precio_anterior   = Column(Float,       nullable=True)
    precio_nuevo      = Column(Float,       nullable=True)
    moneda            = Column(String(5),   nullable=True)
    registrado_por_id = Column(Integer,     ForeignKey("usuarios.id"), nullable=True)
    created_at        = Column(DateTime,    server_default=func.now())

    registrado_por = relationship("Usuario", foreign_keys=[registrado_por_id])

    __table_args__ = (
        Index("ix_precios_historicos_item", "tipo", "item_id"),
    )
