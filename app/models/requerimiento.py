"""Requerimientos comerciales (Muestra / Producción / Stock) — Fase 1.

Captura estructurada de lo que hoy vive en el Excel de requerimiento. NO genera
OFs (eso lo hará Planeamiento en la Fase 2). Aditivo: no toca modelos existentes.
"""
from sqlalchemy import (Column, Integer, String, Date, DateTime, Text,
                        ForeignKey, Index)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database.connection import Base

TIPOS_REQUERIMIENTO = ("MUESTRA", "PRODUCCION", "STOCK")
ESTADOS_REQUERIMIENTO = ("BORRADOR", "REGISTRADO")

# Sistemas de tallaje del Excel (una línea usa uno)
TALLAJES = {
    "A": ["14.5", "15", "15.5", "16", "16.5", "17", "17.5", "18"],   # cuello
    "B": ["28", "30", "32", "34", "36", "38", "40", "42"],           # numérico
    "C": ["XS", "S", "M", "L", "XL", "2XL", "3XL"],                   # letra
}


class Requerimiento(Base):
    __tablename__ = "requerimientos"

    id               = Column(Integer, primary_key=True, index=True)
    numero_req       = Column(String(40), unique=True, nullable=False, index=True)
    tipo             = Column(String(15), nullable=False, default="PRODUCCION")  # MUESTRA/PRODUCCION/STOCK
    cliente          = Column(String(200), nullable=False)
    proceso          = Column(String(60), nullable=True)     # ej. "PÚBLICO"
    licitacion       = Column(String(150), nullable=True)    # ej. "LICITACIÓN … Nº 001-2026"
    fecha_solicitud  = Column(Date, nullable=True)
    fecha_apt        = Column(Date, nullable=True)
    ejecutivo        = Column(String(120), nullable=True)
    fecha_absolucion = Column(Date, nullable=True)
    nota             = Column(Text, nullable=True)
    estado           = Column(String(15), nullable=False, default="BORRADOR")  # BORRADOR/REGISTRADO
    creado_por_id    = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    created_at       = Column(DateTime, server_default=func.now())
    updated_at       = Column(DateTime, server_default=func.now(), onupdate=func.now())

    lineas = relationship("RequerimientoLinea", back_populates="requerimiento",
                          cascade="all, delete-orphan", order_by="RequerimientoLinea.orden")
    creado_por = relationship("Usuario")

    @property
    def total_general(self):
        return sum(l.total for l in self.lineas)


class RequerimientoLinea(Base):
    __tablename__ = "requerimiento_lineas"

    id                 = Column(Integer, primary_key=True, index=True)
    requerimiento_id   = Column(Integer, ForeignKey("requerimientos.id", ondelete="CASCADE"),
                                nullable=False, index=True)
    grupo              = Column(String(60), nullable=True)   # "PRIMER TERNO", "ZONA SELVA" (texto)
    item_num           = Column(String(20), nullable=True)
    sub_item           = Column(String(20), nullable=True)
    articulo           = Column(String(60), nullable=True)   # código del Excel (LYI278…)
    descripcion        = Column(String(200), nullable=False)
    composicion        = Column(String(200), nullable=True)
    proveedor_tela     = Column(String(120), nullable=True)
    codigo_tela        = Column(String(60), nullable=True)
    color              = Column(String(60), nullable=True)
    tallaje            = Column(String(1), nullable=False, default="C")   # A / B / C
    total              = Column(Integer, nullable=False, default=0)
    prenda_catalogo_id = Column(Integer, ForeignKey("prendas_catalogo.id"), nullable=True)  # OPCIONAL
    orden              = Column(Integer, nullable=False, default=0)

    requerimiento = relationship("Requerimiento", back_populates="lineas")
    tallas = relationship("RequerimientoLineaTalla", back_populates="linea",
                          cascade="all, delete-orphan")
    prenda = relationship("PrendaCatalogo")

    @property
    def total_curva(self):
        return sum(t.cantidad for t in self.tallas)


class RequerimientoLineaTalla(Base):
    __tablename__ = "requerimiento_linea_tallas"

    id       = Column(Integer, primary_key=True, index=True)
    linea_id = Column(Integer, ForeignKey("requerimiento_lineas.id", ondelete="CASCADE"),
                      nullable=False, index=True)
    talla    = Column(String(20), nullable=False)
    cantidad = Column(Integer, nullable=False, default=0)

    linea = relationship("RequerimientoLinea", back_populates="tallas")
