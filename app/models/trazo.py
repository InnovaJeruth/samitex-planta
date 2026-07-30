"""
Trazos de corte (Fase A — fases de tela F1–F3).

Un trazo (marker) agrupa varias tallas que se tienden y cortan juntas.
Es aditivo: no modifica el motor de corte existente por pieza.

- OFTrazo: cabecera del trazo con metraje teórico (Lectra) vs real (tendido).
- OFTrazoTalla: qué tallas y cuántas prendas entran en el trazo.
"""
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database.connection import Base


# Estados posibles de cada fase de tela del trazo
ESTADO_PENDIENTE = "PENDIENTE"
ESTADO_EN_CURSO  = "EN_CURSO"
ESTADO_HECHO     = "HECHO"


class OFTrazo(Base):
    __tablename__ = "of_trazos"

    id              = Column(Integer, primary_key=True, index=True)
    of_id           = Column(Integer, ForeignKey("ordenes_fabricacion.id", ondelete="CASCADE"),
                             nullable=False, index=True)
    nombre          = Column(String(30), nullable=False)          # ej: TR-1
    largo           = Column(Float,   nullable=True)              # largo del trazo (m)
    capas           = Column(Integer, nullable=True)              # nº de tendidas planeadas (marker)
    capas_tendidas  = Column(Integer, nullable=False, server_default='0', default=0)  # tendidas acumuladas (por partes)
    capas_cortadas  = Column(Integer, nullable=False, server_default='0', default=0)  # cortadas acumuladas (por partes)
    metraje_teorico = Column(Float,   nullable=True)              # de Lectra (tizado)
    metraje_real    = Column(Float,   nullable=True)              # capturado en el tendido
    eficiencia      = Column(Float,   nullable=True)              # % de Lectra
    estado_tizado   = Column(String(15), nullable=False, default=ESTADO_PENDIENTE)
    estado_tendido  = Column(String(15), nullable=False, default=ESTADO_PENDIENTE)
    estado_corte    = Column(String(15), nullable=False, default=ESTADO_PENDIENTE)
    orden           = Column(Integer, nullable=False, default=0)
    created_at      = Column(DateTime, server_default=func.now())
    updated_at      = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relación una-vía hacia la OF (no toca el modelo OrdenFabricacion)
    of     = relationship("OrdenFabricacion")
    tallas = relationship("OFTrazoTalla", back_populates="trazo",
                          cascade="all, delete-orphan", order_by="OFTrazoTalla.orden")

    __table_args__ = (
        Index("ix_of_trazos_of", "of_id"),
    )

    @property
    def metraje(self):
        """Metros tendidos = capas × largo del tizado. None si falta dato."""
        if self.capas and self.largo:
            return round(self.capas * self.largo, 2)
        return None

    @property
    def desvio_metraje(self):
        """Metros de más (+) o de menos (−) frente al teórico. None si falta dato."""
        if self.metraje_real is not None and self.metraje_teorico is not None:
            return round(self.metraje_real - self.metraje_teorico, 2)
        return None

    @property
    def desvio_pct(self):
        if self.metraje_real is not None and self.metraje_teorico:
            return round((self.metraje_real - self.metraje_teorico) / self.metraje_teorico * 100, 1)
        return None

    @property
    def total_prendas(self):
        return sum((t.cantidad or 0) for t in self.tallas)


class OFTrazoTalla(Base):
    __tablename__ = "of_trazo_tallas"

    id       = Column(Integer, primary_key=True, index=True)
    trazo_id = Column(Integer, ForeignKey("of_trazos.id", ondelete="CASCADE"), nullable=False, index=True)
    sku_id   = Column(Integer, ForeignKey("prenda_skus.id", ondelete="NO ACTION"), nullable=False)
    talla    = Column(String(20), nullable=False)                # desnormalizado para lectura
    veces    = Column(Integer, nullable=False, default=1)         # veces que la talla aparece en el dibujo
    cantidad = Column(Integer, nullable=False, default=0)         # derivado = capas × veces
    orden    = Column(Integer, nullable=False, default=0)

    trazo = relationship("OFTrazo", back_populates="tallas")
    sku   = relationship("PrendaSku")

    __table_args__ = (
        Index("ix_of_trazo_tallas_trazo_sku", "trazo_id", "sku_id", unique=True),
    )


# Tipos de movimiento de tela
MOV_TENDIDO = "TENDIDO"
MOV_CORTE   = "CORTE"


class OFTrazoMovimiento(Base):
    """Historial por sesión de tendido/corte de una placa (auditoría).
    Cada registro = una carga (ej. tendió 30 capas), con quién y cuándo.
    `acumulado` = total tendido/cortado tras esta sesión."""
    __tablename__ = "of_trazo_movimientos"

    id          = Column(Integer, primary_key=True, index=True)
    trazo_id    = Column(Integer, ForeignKey("of_trazos.id", ondelete="CASCADE"), nullable=False, index=True)
    tipo        = Column(String(10), nullable=False)   # TENDIDO | CORTE
    capas       = Column(Integer, nullable=False)      # capas de ESTA sesión
    acumulado   = Column(Integer, nullable=False)      # total tras esta sesión
    usuario_id  = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    observacion = Column(String(300), nullable=True)
    created_at  = Column(DateTime, server_default=func.now())

    trazo   = relationship("OFTrazo")
    usuario = relationship("Usuario")

    __table_args__ = (
        Index("ix_of_trazo_mov_trazo", "trazo_id", "tipo"),
    )
