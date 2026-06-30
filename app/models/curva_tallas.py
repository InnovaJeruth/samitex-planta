"""
Curvas de tallas — Samitex Planta
Módulo de Programación: UDP define la distribución de tallas por pedido.
"""
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database.connection import Base


class CurvaTallas(Base):
    """Cabecera de una curva de tallas.
    Una curva pertenece a una prenda del catálogo y puede vincularse a una o varias OFs."""
    __tablename__ = "curvas_tallas"

    id                 = Column(Integer,     primary_key=True, index=True)
    prenda_catalogo_id = Column(Integer,     ForeignKey("prendas_catalogo.id", ondelete="RESTRICT"),
                                nullable=False, index=True)
    nombre             = Column(String(150), nullable=True)    # ej: "Pedido junio 2026"
    notas              = Column(String(500), nullable=True)
    nombre_archivo     = Column(String(255), nullable=True)    # documento adjunto
    ruta_archivo       = Column(String(500), nullable=True)
    activo             = Column(Boolean,     default=True, nullable=False)
    creado_por_id      = Column(Integer,     ForeignKey("usuarios.id"), nullable=True)
    created_at         = Column(DateTime,    server_default=func.now())
    updated_at         = Column(DateTime,    server_default=func.now(), onupdate=func.now())

    prenda     = relationship("PrendaCatalogo")
    creado_por = relationship("Usuario", foreign_keys=[creado_por_id])
    detalle    = relationship("CurvaTallasDetalle", back_populates="curva",
                              cascade="all, delete-orphan", order_by="CurvaTallasDetalle.orden")
    vinculos   = relationship("CurvaTallasOF", back_populates="curva",
                              cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_curvas_tallas_prenda", "prenda_catalogo_id"),
    )


class CurvaTallasDetalle(Base):
    """Detalle de tallas y cantidades de una curva."""
    __tablename__ = "curvas_tallas_detalle"

    id       = Column(Integer, primary_key=True, index=True)
    curva_id = Column(Integer, ForeignKey("curvas_tallas.id", ondelete="CASCADE"),
                      nullable=False, index=True)
    sku_id   = Column(Integer, ForeignKey("prenda_skus.id",   ondelete="RESTRICT"),
                      nullable=False)
    talla    = Column(String(20), nullable=False)   # desnormalizado para lectura rápida
    cantidad = Column(Integer,    nullable=False, default=0)
    orden    = Column(Integer,    nullable=False, default=0)

    curva = relationship("CurvaTallas",  back_populates="detalle")
    sku   = relationship("PrendaSku")

    __table_args__ = (
        Index("ix_curva_detalle_curva_sku", "curva_id", "sku_id", unique=True),
    )


class CurvaTallasOF(Base):
    """Registro de qué OFs recibieron el documento de una curva de tallas."""
    __tablename__ = "curvas_tallas_of"

    id       = Column(Integer, primary_key=True, index=True)
    curva_id = Column(Integer, ForeignKey("curvas_tallas.id",         ondelete="CASCADE"),  nullable=False)
    of_id    = Column(Integer, ForeignKey("ordenes_fabricacion.id",   ondelete="CASCADE"),  nullable=False)
    enviado_por_id = Column(Integer, ForeignKey("usuarios.id"),       nullable=True)
    created_at     = Column(DateTime, server_default=func.now())

    curva      = relationship("CurvaTallas",        back_populates="vinculos")
    of         = relationship("OrdenFabricacion")
    enviado_por= relationship("Usuario", foreign_keys=[enviado_por_id])

    __table_args__ = (
        Index("ix_curva_of_curva_of", "curva_id", "of_id", unique=True),
    )
