from pydantic import BaseModel, field_validator
from datetime import date, datetime
from typing import Optional, List
from app.models.of import EstadoOF, TipoPrendaEnum, TipoDocumentoOF


class OFCreate(BaseModel):
    numero_of: str
    cliente: str
    tipo_prenda: TipoPrendaEnum
    total_juegos: int
    fecha_apt: Optional[date] = None
    responsable_id: Optional[int] = None
    solped_prenda: Optional[str] = None
    orden_compra: Optional[str] = None
    solped_mp: Optional[str] = None
    estampado_activo: bool = False

    @field_validator("numero_of")
    @classmethod
    def numero_of_not_empty(cls, v):
        if not v.strip():
            raise ValueError("El número de OF no puede estar vacío")
        return v.strip()

    @field_validator("total_juegos")
    @classmethod
    def total_juegos_positivo(cls, v):
        if v < 1:
            raise ValueError("Total de prendas debe ser mayor a 0")
        return v


class OFResumen(BaseModel):
    id: int
    numero_of: str
    cliente: str
    tipo_prenda: TipoPrendaEnum
    total_juegos: int
    estado: EstadoOF
    fecha_creacion: date
    fecha_apt: Optional[date] = None

    model_config = {"from_attributes": True}


class DocumentoOFResponse(BaseModel):
    id: int
    tipo: TipoDocumentoOF
    nombre_archivo: str
    uploaded_at: datetime

    model_config = {"from_attributes": True}


class OFResponse(OFResumen):
    estampado_activo: bool
    solped_prenda: Optional[str] = None
    orden_compra: Optional[str] = None
    solped_mp: Optional[str] = None
    documentos: List[DocumentoOFResponse] = []

    model_config = {"from_attributes": True}
