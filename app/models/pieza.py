from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, Enum, Index
from sqlalchemy.orm import relationship

from app.database.connection import Base


class PlantillaPieza(Base):
    """Plantillas de piezas por prenda del catálogo."""
    __tablename__ = "plantilla_piezas"

    id                 = Column(Integer, primary_key=True, index=True)
    prenda_catalogo_id = Column(Integer, ForeignKey("prendas_catalogo.id"), nullable=False, index=True)
    codigo             = Column(String(50),  unique=True, nullable=True)   # único en todo el sistema
    nombre             = Column(String(100), nullable=False)
    material_default   = Column(String(50),  default="TELA")
    cantidad_x_prenda  = Column(Integer,     default=1)
    fusionado_default  = Column(Boolean,     default=False)
    orden              = Column(Integer,     default=0)
    imagen_ruta        = Column(String(500), nullable=True)    # ruta relativa static/uploads/piezas/

    # Relaciones
    prenda_catalogo = relationship("PrendaCatalogo", back_populates="plantilla_piezas")

    __table_args__ = (
        Index("ix_plantilla_piezas_prenda_orden", "prenda_catalogo_id", "orden"),
    )


class OFPieza(Base):
    """Piezas reales asignadas a una OF específica."""
    __tablename__ = "of_piezas"

    id               = Column(Integer, primary_key=True, index=True)
    of_id            = Column(Integer, ForeignKey("ordenes_fabricacion.id"), nullable=False)
    codigo_pieza     = Column(String(50),  nullable=True)    # código del catálogo, para trazabilidad
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
