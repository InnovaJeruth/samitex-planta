from sqlalchemy import Column, Integer, String, Boolean, DateTime, Date, ForeignKey, Enum, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import datetime as _dt
import enum

from app.database.connection import Base


class EstadoOF(str, enum.Enum):
    BORRADOR   = "BORRADOR"
    ACTIVA     = "ACTIVA"
    EN_PROCESO = "EN_PROCESO"
    COMPLETADA = "COMPLETADA"
    ANULADA    = "ANULADA"


# Mantenido para compatibilidad con vistas/filtros existentes.
# El campo DB ya es String(50) libre — este Enum solo se usa en Python para validacion.
class TipoPrendaEnum(str, enum.Enum):
    SACO     = "SACO"
    PANTALON = "PANTALON"
    CAMISA   = "CAMISA"
    OTRO     = "OTRO"


class TipoClienteEnum(str, enum.Enum):
    INSTITUCION = "INSTITUCION"
    MARCA       = "MARCA"


class EstadoDocsEnum(str, enum.Enum):
    PENDIENTE        = "PENDIENTE"
    EN_DOCUMENTACION = "EN_DOCUMENTACION"
    COMPLETA         = "COMPLETA"


class TipoDocumentoOF(str, enum.Enum):
    FICHA_TECNICA      = "FICHA_TECNICA"
    HOJA_COSTOS        = "HOJA_COSTOS"
    MUESTRA_APROBADA   = "MUESTRA_APROBADA"
    REPORTE_TALLAS     = "REPORTE_TALLAS"
    MOLDES_LECTRA      = "MOLDES_LECTRA"
    CONFIRMACION_STOCK = "CONFIRMACION_STOCK"


class OrdenFabricacion(Base):
    __tablename__ = "ordenes_fabricacion"

    id                   = Column(Integer, primary_key=True, index=True)
    numero_of            = Column(String(30), unique=True, index=True, nullable=False)
    cliente              = Column(String(200), nullable=False)
    tipo_prenda          = Column(String(50),  nullable=False)
    prenda_catalogo_id   = Column(Integer, ForeignKey("prendas_catalogo.id"), nullable=True)
    total_juegos         = Column(Integer, nullable=False)
    fecha_creacion       = Column(Date, nullable=False, default=_dt.date.today)  # fecha de creación en ESTE sistema
    fecha_sap            = Column(Date, nullable=True)   # fecha en que la OF se creó/subió en SAP
    fecha_apt            = Column(Date, nullable=True)
    estado               = Column(Enum(EstadoOF), default=EstadoOF.BORRADOR)
    tipo_cliente         = Column(Enum(TipoClienteEnum), default=TipoClienteEnum.INSTITUCION, nullable=False)
    estado_docs          = Column(Enum(EstadoDocsEnum), default=EstadoDocsEnum.PENDIENTE, nullable=False)
    estampado_activo     = Column(Boolean, default=False)
    solped_prenda        = Column(String(50), nullable=True)
    orden_compra         = Column(String(50), nullable=True)
    solped_mp            = Column(String(50), nullable=True)
    fecha_inicio_plan    = Column(Date, nullable=True)
    orden_plan           = Column(Integer, nullable=True)
    tercerizado          = Column(Boolean, default=False, nullable=False)
    planta_id            = Column(Integer, ForeignKey("plantas_externas.id"), nullable=True)
    planta_externa       = Column(String(120), nullable=True)
    fecha_envio          = Column(Date, nullable=True)
    fecha_recepcion_est  = Column(Date, nullable=True)
    fecha_recepcion_real = Column(Date, nullable=True)
    estado_tercerizado   = Column(String(20), nullable=True)
    juegos_recibidos     = Column(Integer, default=0, nullable=False)
    es_muestra           = Column(Boolean, default=False, nullable=False)  # Requerimiento de Muestra (sin gates)
    omitir_gates         = Column(Boolean, default=False, nullable=False)  # OF de prueba: se activa sin gates documentales
    max_capas            = Column(Integer, nullable=True)   # tope de capas por placa (override; default global MAX_CAPAS_DEFAULT)
    responsable_id       = Column(Integer, ForeignKey("usuarios.id"))
    created_at           = Column(DateTime, server_default=func.now())
    updated_at           = Column(DateTime, server_default=func.now(), onupdate=func.now())

    responsable           = relationship("Usuario",             back_populates="of_creadas")
    prenda_catalogo       = relationship("PrendaCatalogo",      back_populates="ofs", foreign_keys=[prenda_catalogo_id])
    planta                = relationship("PlantaExterna",       back_populates="ofs_tercerizadas", foreign_keys=[planta_id])
    documentos            = relationship("DocumentoOF",         back_populates="of", cascade="all, delete-orphan")
    piezas                = relationship("OFPieza",             back_populates="of", cascade="all, delete-orphan")
    fases_estado          = relationship("OFFaseEstado",        back_populates="of", cascade="all, delete-orphan")
    fase_tiempos          = relationship("OFFaseTiempos",       back_populates="of", cascade="all, delete-orphan")
    avance_registros      = relationship("AvanceRegistro",      back_populates="of", cascade="all, delete-orphan")
    fase_paradas          = relationship("OFFaseParada",        back_populates="of", cascade="all, delete-orphan",
                                         foreign_keys="OFFaseParada.of_id")
    historial_fechas_terc = relationship("TercHistorialFecha",  back_populates="of", cascade="all, delete-orphan")
    recepciones_terc      = relationship("TercRecepcion",       back_populates="of", cascade="all, delete-orphan")
    talla_distribucion    = relationship("OFTallaDistribucion", back_populates="of", cascade="all, delete-orphan")
    terc_logs             = relationship("TercSubprocesoLog",   back_populates="of", cascade="all, delete-orphan", foreign_keys="TercSubprocesoLog.of_id")


class DocumentoOF(Base):
    __tablename__ = "documentos_of"

    id             = Column(Integer, primary_key=True, index=True)
    of_id          = Column(Integer, ForeignKey("ordenes_fabricacion.id"), nullable=False)
    tipo           = Column(String(50), nullable=False)
    nombre_archivo = Column(String(255), nullable=False)
    ruta_archivo   = Column(String(500), nullable=False)
    area           = Column(String(30),  nullable=True)
    usuario_id     = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    uploaded_at    = Column(DateTime, server_default=func.now())

    of      = relationship("OrdenFabricacion", back_populates="documentos")
    usuario = relationship("Usuario",          back_populates="documentos_subidos")


class AuditoriaDocumentoOF(Base):
    """Historial de acciones sobre documentos de una OF.
    accion: SUBIDO | REEMPLAZADO | ELIMINADO"""
    __tablename__ = "auditoria_documento_of"

    id             = Column(Integer,     primary_key=True, index=True)
    of_id          = Column(Integer,     ForeignKey("ordenes_fabricacion.id", ondelete="CASCADE"), nullable=False, index=True)
    tipo           = Column(String(50),  nullable=False)
    accion         = Column(String(20),  nullable=False)
    nombre_archivo = Column(String(255), nullable=True)
    usuario_id     = Column(Integer,     ForeignKey("usuarios.id"), nullable=True)
    created_at     = Column(DateTime,    server_default=func.now())

    usuario = relationship("Usuario")


class OFTallaDistribucion(Base):
    """Distribucion de unidades por talla (SKU) dentro de una OF.
    Una OF apunta a la variante; esta tabla desglosa cuantas prendas
    se fabrican por cada talla especifica."""
    __tablename__ = "of_talla_distribucion"

    id      = Column(Integer, primary_key=True, index=True)
    of_id   = Column(Integer, ForeignKey("ordenes_fabricacion.id", ondelete="CASCADE"),  nullable=False, index=True)
    sku_id  = Column(Integer, ForeignKey("prenda_skus.id",         ondelete="NO ACTION"), nullable=False)
    cantidad = Column(Integer, nullable=False, default=0)

    of  = relationship("OrdenFabricacion", back_populates="talla_distribucion")
    sku = relationship("PrendaSku")

    __table_args__ = (
        Index("ix_of_talla_dist_of_sku", "of_id", "sku_id", unique=True),
    )
