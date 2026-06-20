from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Float, Text, Index, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database.connection import Base


class FaseCatalogo(Base):
    """Catálogo de fases del proceso (F1-F9). Extensible a futuros procesos."""
    __tablename__ = "fases_catalogo"

    id          = Column(Integer, primary_key=True)
    fase_id     = Column(String(5),   unique=True, nullable=False)   # F1, F2... F9
    nombre      = Column(String(50),  nullable=False)                # TIZADO, TENDIDO...
    proceso     = Column(String(50),  default="CORTE")               # extensible: COSTURA, ACABADO...
    orden       = Column(Integer,     nullable=False)
    obligatoria = Column(Boolean,     default=True)
    descripcion = Column(String(255), nullable=True)


class OFFaseEstado(Base):
    """Estado de cada fase para cada pieza dentro de una OF."""
    __tablename__ = "of_fases_estado"

    id               = Column(Integer, primary_key=True, index=True)
    of_id            = Column(Integer, ForeignKey("ordenes_fabricacion.id"), nullable=False)
    pieza_id         = Column(Integer, ForeignKey("of_piezas.id"),           nullable=False)
    fase_id          = Column(String(5), nullable=False)             # F1..F9
    cantidad_actual  = Column(Integer, default=0)
    max_cantidad     = Column(Integer, nullable=False)               # total_juegos x cantidad_x_prenda
    completada       = Column(Boolean, default=False)
    fecha_inicio     = Column(DateTime, nullable=True)
    fecha_completado = Column(DateTime, nullable=True)
    # Datos específicos por fase
    eficiencia_tizado = Column(Float,   nullable=True)              # F1: % eficiencia trazo
    temperatura_fusion= Column(Float,   nullable=True)              # F5: temperatura (C)
    tratamiento_orillo= Column(Boolean, nullable=True)              # F2: flag para INSTITUCION
    motivo_rechazo    = Column(Text,    nullable=True)              # F6: si calidad rechaza

    # Relaciones
    of    = relationship("OrdenFabricacion", back_populates="fases_estado")
    pieza = relationship("OFPieza",          back_populates="fases_estado")

    __table_args__ = (
        # Garantiza que no existan filas duplicadas (of, pieza, fase)
        UniqueConstraint("of_id", "pieza_id", "fase_id", name="uq_of_pieza_fase"),
        # Índice compuesto para la query más frecuente: filter_by(of_id, fase_id)
        Index("ix_of_fase_estado_of_fase", "of_id", "fase_id"),
    )


class OFFaseTiempos(Base):
    """Tiempos programados y reales por OF x Fase (un registro por OF+fase)."""
    __tablename__ = "of_fase_tiempos"

    id                = Column(Integer, primary_key=True, index=True)
    of_id             = Column(Integer, ForeignKey("ordenes_fabricacion.id"), nullable=False)
    fase_id           = Column(String(5), nullable=False)          # F1..F9
    inicio_programado = Column(DateTime, nullable=True)            # Supervisor: fecha + hora
    fin_programado    = Column(DateTime, nullable=True)            # Supervisor: fecha + hora
    inicio_real       = Column(DateTime, nullable=True)            # Auto al presionar "Iniciar fase"
    fin_real          = Column(DateTime, nullable=True)            # Auto al completar todas las piezas

    # Relaciones
    of = relationship("OrdenFabricacion", back_populates="fase_tiempos")


class OFFaseParada(Base):
    """Registra interrupciones/paradas durante una fase activa de una OF.

    Ciclo de vida:
      - Se crea con fin_parada=NULL (parada activa).
      - Se cierra con fin_parada=ahora al reanudar.
    """
    __tablename__ = "of_fase_paradas"

    id                = Column(Integer,   primary_key=True, index=True)
    of_id             = Column(Integer,   ForeignKey("ordenes_fabricacion.id"), nullable=False)
    fase_id           = Column(String(5), nullable=False)          # F1..F9
    inicio_parada     = Column(DateTime,  nullable=False, server_default=func.now())
    fin_parada        = Column(DateTime,  nullable=True)           # NULL = parada activa
    # EMERGENCIA_OF | MATERIAL | MAQUINA | ADMIN | OTRO
    motivo            = Column(String(30), nullable=False)
    of_emergencia_id  = Column(Integer,   ForeignKey("ordenes_fabricacion.id"), nullable=True)
    observacion       = Column(Text,      nullable=True)
    usuario_id        = Column(Integer,   ForeignKey("usuarios.id"), nullable=True)
    created_at        = Column(DateTime,  server_default=func.now())

    # Relaciones
    of            = relationship("OrdenFabricacion", back_populates="fase_paradas",
                                 foreign_keys=[of_id])
    of_emergencia = relationship("OrdenFabricacion",
                                 foreign_keys=[of_emergencia_id])
    usuario       = relationship("Usuario")

    @property
    def duracion_minutos(self) -> int | None:
        """Minutos de parada. None si aún está activa."""
        if self.fin_parada and self.inicio_parada:
            return int((self.fin_parada - self.inicio_parada).total_seconds() // 60)
        return None


class AvanceRegistro(Base):
    """Log inmutable de cada registro de avance (trazabilidad completa)."""
    __tablename__ = "avance_registros"

    id         = Column(Integer,   primary_key=True, index=True)
    of_id      = Column(Integer,   ForeignKey("ordenes_fabricacion.id"), nullable=False)
    pieza_id   = Column(Integer,   ForeignKey("of_piezas.id"),           nullable=False)
    fase_id    = Column(String(5), nullable=False)
    cantidad   = Column(Integer,   nullable=False)
    usuario_id = Column(Integer,   ForeignKey("usuarios.id"))
    observacion= Column(Text,      nullable=True)
    created_at = Column(DateTime,  server_default=func.now())
    revertido  = Column(Boolean,   default=False)                   # marca si fue revertido

    # Relaciones
    of      = relationship("OrdenFabricacion", back_populates="avance_registros")
    pieza   = relationship("OFPieza",          back_populates="avances")
    usuario = relationship("Usuario",          back_populates="registros_avance")

    __table_args__ = (
        # Índice compuesto para historial y reversiones: filter_by(of_id) + order_by(created_at)
        Index("ix_avance_registros_of_fecha", "of_id", "created_at"),
    )
