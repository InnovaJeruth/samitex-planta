from sqlalchemy import Column, Integer, String, Boolean, DateTime, Date, ForeignKey, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database.connection import Base


class PlantaExterna(Base):
    __tablename__ = "plantas_externas"

    id         = Column(Integer, primary_key=True, index=True)
    nombre     = Column(String(150), nullable=False)
    ruc        = Column(String(11),  nullable=False)
    encargado  = Column(String(120), nullable=False)
    direccion  = Column(String(300), nullable=False)
    activo     = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, server_default=func.now())

    ofs_tercerizadas  = relationship("OrdenFabricacion",   back_populates="planta",    foreign_keys="OrdenFabricacion.planta_id")
    historial_fechas  = relationship("TercHistorialFecha", back_populates="planta",    cascade="all, delete-orphan")
    recepciones       = relationship("TercRecepcion",      back_populates="planta",    cascade="all, delete-orphan")
    terc_logs         = relationship("TercSubprocesoLog",  back_populates="planta",    cascade="all, delete-orphan")


class TercHistorialFecha(Base):
    __tablename__ = "terc_historial_fechas"

    id             = Column(Integer, primary_key=True, index=True)
    of_id          = Column(Integer, ForeignKey("ordenes_fabricacion.id"), nullable=False)
    planta_id      = Column(Integer, ForeignKey("plantas_externas.id"),    nullable=False)
    fecha_anterior = Column(Date, nullable=True)
    fecha_nueva    = Column(Date, nullable=False)
    motivo         = Column(String(300), nullable=True)
    usuario_id     = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    created_at     = Column(DateTime, server_default=func.now())

    of      = relationship("OrdenFabricacion", back_populates="historial_fechas_terc")
    planta  = relationship("PlantaExterna",    back_populates="historial_fechas")
    usuario = relationship("Usuario")


class TercRecepcion(Base):
    __tablename__ = "terc_recepciones"

    id               = Column(Integer, primary_key=True, index=True)
    of_id            = Column(Integer, ForeignKey("ordenes_fabricacion.id"), nullable=False)
    planta_id        = Column(Integer, ForeignKey("plantas_externas.id"),    nullable=False)
    fase_id          = Column(String(5),  nullable=True)
    juegos_recibidos = Column(Integer, nullable=False)
    fecha_recepcion  = Column(Date, nullable=False)
    observacion      = Column(String(500), nullable=True)
    usuario_id       = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    created_at       = Column(DateTime, server_default=func.now())

    of      = relationship("OrdenFabricacion", back_populates="recepciones_terc")
    planta  = relationship("PlantaExterna",    back_populates="recepciones")
    usuario = relationship("Usuario")


class TercSubprocesoLog(Base):
    """Audit trail completo del ciclo de tercerización:
    PROGRAMADO → ENVIADO → RECIBIDO → COMPLETADO"""
    __tablename__ = "terc_subproceso_log"

    id                   = Column(Integer,     primary_key=True, index=True)
    of_id                = Column(Integer,     ForeignKey("ordenes_fabricacion.id", ondelete="CASCADE"), nullable=False, index=True)
    planta_id            = Column(Integer,     ForeignKey("plantas_externas.id"),   nullable=False)
    fase_id              = Column(String(5),   nullable=True)     # NULL = OF completa, "F3" = solo esa fase
    estado               = Column(String(20),  nullable=False, default="PROGRAMADO")  # PROGRAMADO | ENVIADO | RECIBIDO | COMPLETADO
    juegos_enviados      = Column(Integer,     nullable=True)
    juegos_recibidos     = Column(Integer,     nullable=True)
    fecha_envio          = Column(Date,        nullable=True)
    fecha_recepcion_est  = Column(Date,        nullable=True)
    fecha_recepcion_real = Column(Date,        nullable=True)
    fecha_completado     = Column(DateTime,    nullable=True)
    observacion          = Column(String(500), nullable=True)
    usuario_creo_id      = Column(Integer,     ForeignKey("usuarios.id"), nullable=True)
    usuario_recepcion_id = Column(Integer,     ForeignKey("usuarios.id"), nullable=True)
    created_at           = Column(DateTime,    server_default=func.now())

    of     = relationship("OrdenFabricacion", back_populates="terc_logs", foreign_keys=[of_id])
    planta = relationship("PlantaExterna",    back_populates="terc_logs")
    usuario_creo      = relationship("Usuario", foreign_keys=[usuario_creo_id])
    usuario_recepcion = relationship("Usuario", foreign_keys=[usuario_recepcion_id])
