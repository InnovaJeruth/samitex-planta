from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, Enum
from sqlalchemy.orm import relationship

from app.database.connection import Base
from app.models.of import TipoPrendaEnum


class PlantillaPieza(Base):
    """Plantillas por tipo de prenda (SACO, PANTALÓN, CAMISA)."""
    __tablename__ = "plantilla_piezas"

    id               = Column(Integer, primary_key=True, index=True)
    tipo_prenda      = Column(Enum(TipoPrendaEnum), nullable=False, index=True)
    nombre           = Column(String(100), nullable=False)
    material_default = Column(String(50), default="TELA")
    cantidad_x_prenda= Column(Integer, default=1)
    fusionado_default = Column(Boolean, default=False)
    orden            = Column(Integer, default=0)    # orden de visualización


class OFPieza(Base):
    """Piezas reales asignadas a una OF específica."""
    __tablename__ = "of_piezas"

    id               = Column(Integer, primary_key=True, index=True)
    of_id            = Column(Integer, ForeignKey("ordenes_fabricacion.id"), nullable=False)
    nombre           = Column(String(100), nullable=False)
    codigo_sap       = Column(String(50),  nullable=True)    # obligatorio antes de activar OF
    material         = Column(String(50),  nullable=False, default="TELA")
    cantidad_x_prenda= Column(Integer,     nullable=False, default=1)
    fusionado        = Column(Boolean,     default=False)
    estampado_bordado= Column(Boolean,     default=False)    # si F8 está activo en la OF
    orden            = Column(Integer,     default=0)

    # Relaciones
    of           = relationship("OrdenFabricacion", back_populates="piezas")
    fases_estado = relationship("OFFaseEstado",     back_populates="pieza", cascade="all, delete-orphan")
    avances      = relationship("AvanceRegistro",   back_populates="pieza")
