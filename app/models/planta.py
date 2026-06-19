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

    # Relaciones
    ofs_tercerizadas  = relationship("OrdenFabricacion",   back_populates="planta",    foreign_keys="OrdenFabricacion.planta_id")
    historial_fechas  = relationship("TercHistorialFecha", back_populates="planta",    cascade="all, delete-orphan")
    recepciones       = relationship("TercRecepcion",      back_populates="planta",    cascade="all, delete-orphan")


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
    juegos_recibidos = Column(Integer, nullable=False)
    fecha_recepcion  = Column(Date, nullable=False)
    observacion      = Column(String(500), nullable=True)
    usuario_id       = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    created_at       = Column(DateTime, server_default=func.now())

    of      = relationship("OrdenFabricacion", back_populates="recepciones_terc")
    planta  = relationship("PlantaExterna",    back_populates="recepciones")
    usuario = relationship("Usuario")
