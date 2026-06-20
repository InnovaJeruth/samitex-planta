from sqlalchemy import Column, Integer, String, Boolean, DateTime, Date, ForeignKey, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum

from app.database.connection import Base


class EstadoOF(str, enum.Enum):
    BORRADOR   = "BORRADOR"
    ACTIVA     = "ACTIVA"
    EN_PROCESO = "EN_PROCESO"
    COMPLETADA = "COMPLETADA"
    ANULADA    = "ANULADA"


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
    tipo_prenda          = Column(Enum(TipoPrendaEnum), nullable=False)
    total_juegos         = Column(Integer, nullable=False)
    fecha_creacion       = Column(Date, nullable=False)
    fecha_apt            = Column(Date, nullable=True)
    estado               = Column(Enum(EstadoOF), default=EstadoOF.BORRADOR)
    tipo_cliente         = Column(Enum(TipoClienteEnum), default=TipoClienteEnum.INSTITUCION, nullable=False)
    estado_docs          = Column(Enum(EstadoDocsEnum), default=EstadoDocsEnum.PENDIENTE, nullable=False)
    estampado_activo     = Column(Boolean, default=False)
    # Códigos de documentos
    solped_prenda        = Column(String(50), nullable=True)
    orden_compra         = Column(String(50), nullable=True)
    solped_mp            = Column(String(50), nullable=True)
    # Planificación Gantt
    fecha_inicio_plan    = Column(Date, nullable=True)
    orden_plan           = Column(Integer, nullable=True)
    # Tercerización
    tercerizado          = Column(Boolean, default=False, nullable=False)
    planta_id            = Column(Integer, ForeignKey("plantas_externas.id"), nullable=True)
    planta_externa       = Column(String(120), nullable=True)   # texto libre legacy
    fecha_envio          = Column(Date, nullable=True)
    fecha_recepcion_est  = Column(Date, nullable=True)
    fecha_recepcion_real = Column(Date, nullable=True)
    estado_tercerizado   = Column(String(20), nullable=True)
    juegos_recibidos     = Column(Integer, default=0, nullable=False)
    # Metadata
    responsable_id       = Column(Integer, ForeignKey("usuarios.id"))
    created_at           = Column(DateTime, server_default=func.now())
    updated_at           = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relaciones
    responsable           = relationship("Usuario",             back_populates="of_creadas")
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
    usuario = relationship("Usuario")
