from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Float, Text, Index, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database.connection import Base


class FaseCatalogo(Base):
    __tablename__ = "fases_catalogo"
    id                 = Column(Integer, primary_key=True)
    fase_id            = Column(String(5),   unique=True, nullable=False)
    nombre             = Column(String(50),  nullable=False)
    proceso            = Column(String(50),  default="CORTE")
    orden              = Column(Integer,     nullable=False)
    obligatoria        = Column(Boolean,     default=True)
    descripcion        = Column(String(255), nullable=True)
    duracion_horas_std = Column(Float,       nullable=True, default=8.0)


class OFFaseEstado(Base):
    __tablename__ = "of_fases_estado"
    id               = Column(Integer, primary_key=True, index=True)
    of_id            = Column(Integer, ForeignKey("ordenes_fabricacion.id"), nullable=False)
    pieza_id         = Column(Integer, ForeignKey("of_piezas.id"),           nullable=False)
    fase_id          = Column(String(5), nullable=False)
    cantidad_actual  = Column(Integer, default=0)
    max_cantidad     = Column(Integer, nullable=False)
    completada       = Column(Boolean, default=False)
    fecha_inicio     = Column(DateTime, nullable=True)
    fecha_completado = Column(DateTime, nullable=True)
    eficiencia_tizado = Column(Float,   nullable=True)
    temperatura_fusion= Column(Float,   nullable=True)
    tratamiento_orillo= Column(Boolean, nullable=True)
    motivo_rechazo    = Column(Text,    nullable=True)
    of    = relationship("OrdenFabricacion", back_populates="fases_estado")
    pieza = relationship("OFPieza",          back_populates="fases_estado")
    __table_args__ = (
        UniqueConstraint("of_id", "pieza_id", "fase_id", name="uq_of_pieza_fase"),
        Index("ix_of_fase_estado_of_fase", "of_id", "fase_id"),
    )


class OFFaseTiempos(Base):
    __tablename__ = "of_fase_tiempos"
    id                = Column(Integer, primary_key=True, index=True)
    of_id             = Column(Integer, ForeignKey("ordenes_fabricacion.id"), nullable=False)
    fase_id           = Column(String(5), nullable=False)
    inicio_programado = Column(DateTime, nullable=True)
    fin_programado    = Column(DateTime, nullable=True)
    inicio_real       = Column(DateTime, nullable=True)
    fin_real          = Column(DateTime, nullable=True)
    of = relationship("OrdenFabricacion", back_populates="fase_tiempos")


class OFFaseParada(Base):
    """Registra interrupciones/paradas durante una fase activa de una OF."""
    __tablename__ = "of_fase_paradas"
    id                = Column(Integer,   primary_key=True, index=True)
    of_id             = Column(Integer,   ForeignKey("ordenes_fabricacion.id"), nullable=False)
    fase_id           = Column(String(5), nullable=False)
    inicio_parada     = Column(DateTime,  nullable=False, server_default=func.now())
    fin_parada        = Column(DateTime,  nullable=True)
    motivo            = Column(String(30), nullable=False)
    of_emergencia_id      = Column(Integer,   ForeignKey("ordenes_fabricacion.id"), nullable=True)
    numero_requerimiento  = Column(String(50), nullable=True)
    observacion           = Column(Text,      nullable=True)
    usuario_id        = Column(Integer,   ForeignKey("usuarios.id"), nullable=True)
    created_at        = Column(DateTime,  server_default=func.now())
    of            = relationship("OrdenFabricacion", back_populates="fase_paradas",
                                 foreign_keys=[of_id])
    of_emergencia = relationship("OrdenFabricacion", foreign_keys=[of_emergencia_id])
    usuario       = relationship("Usuario")

    @property
    def duracion_minutos(self):
        if self.fin_parada and self.inicio_parada:
            return int((self.fin_parada - self.inicio_parada).total_seconds() // 60)
        return None


class AvanceRegistro(Base):
    __tablename__ = "avance_registros"
    id         = Column(Integer,   primary_key=True, index=True)
    of_id      = Column(Integer,   ForeignKey("ordenes_fabricacion.id"), nullable=False)
    pieza_id   = Column(Integer,   ForeignKey("of_piezas.id"),           nullable=False)
    fase_id    = Column(String(5), nullable=False)
    cantidad   = Column(Integer,   nullable=False)
    usuario_id = Column(Integer,   ForeignKey("usuarios.id"))
    observacion= Column(Text,      nullable=True)
    created_at = Column(DateTime,  server_default=func.now())
    revertido  = Column(Boolean,   default=False)
    of      = relationship("OrdenFabricacion", back_populates="avance_registros")
    pieza   = relationship("OFPieza",          back_populates="avances")
    usuario = relationship("Usuario",          back_populates="registros_avance")
    __table_args__ = (
        Index("ix_avance_registros_of_fecha", "of_id", "created_at"),
    )
