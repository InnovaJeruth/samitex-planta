from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum

from app.database.connection import Base


class RolEnum(str, enum.Enum):
    ADMIN              = "ADMIN"
    GERENTE_PLANTA     = "GERENTE_PLANTA"
    JEFE_PLANTA        = "JEFE_PLANTA"
    GERENCIA           = "GERENCIA"
    PLANEADOR          = "PLANEADOR"
    SUPERVISOR_CORTE   = "SUPERVISOR_CORTE"
    SOLO_LECTURA       = "SOLO_LECTURA"
    # Roles de documentación
    UDP                = "UDP"
    COMERCIAL          = "COMERCIAL"
    COMERCIAL_MARCA    = "COMERCIAL_MARCA"
    PLANEAMIENTO_MARCA = "PLANEAMIENTO_MARCA"
    INGENIERIA         = "INGENIERIA"
    LOGISTICA          = "LOGISTICA"
    CALIDAD            = "CALIDAD"


class Usuario(Base):
    __tablename__ = "usuarios"

    id            = Column(Integer, primary_key=True, index=True)
    nombre        = Column(String(100), nullable=False)
    email         = Column(String(150), unique=True, index=True, nullable=False)
    username      = Column(String(50),  unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    rol           = Column(Enum(RolEnum), nullable=False, default=RolEnum.SOLO_LECTURA)
    activo        = Column(Boolean, default=True)
    created_at    = Column(DateTime, server_default=func.now())
    updated_at    = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relaciones
    of_creadas         = relationship("OrdenFabricacion", back_populates="responsable")
    registros_avance   = relationship("AvanceRegistro",   back_populates="usuario")
    documentos_subidos = relationship("DocumentoOF",      back_populates="usuario")
