from pydantic import BaseModel, field_validator
from typing import Optional
from datetime import datetime


class AvanceCreate(BaseModel):
    pieza_id: int
    fase_id: str
    cantidad: int
    observacion: Optional[str] = None

    @field_validator("cantidad")
    @classmethod
    def cantidad_positiva(cls, v):
        if v < 1:
            raise ValueError("La cantidad debe ser mayor a 0")
        return v

    @field_validator("fase_id")
    @classmethod
    def fase_valida(cls, v):
        validas = {"F1", "F2", "F3", "F4", "F5", "F6", "F7", "F8", "F9"}
        if v not in validas:
            raise ValueError(f"fase_id debe ser una de: {validas}")
        return v


class CompletarRequest(BaseModel):
    pieza_id: int
    fase_id: str

    @field_validator("fase_id")
    @classmethod
    def fase_valida(cls, v):
        validas = {"F1", "F2", "F3", "F4", "F5", "F6", "F7", "F8", "F9"}
        if v not in validas:
            raise ValueError(f"fase_id debe ser una de: {validas}")
        return v


class EstadoFaseResponse(BaseModel):
    pieza_id: int
    fase_id: str
    cantidad_actual: int
    max_cantidad: int
    completada: bool
    porcentaje: float

    model_config = {"from_attributes": True}


class AvanceRegistroResponse(BaseModel):
    id: int
    pieza_id: int
    pieza_nombre: str
    fase_id: str
    cantidad: int
    usuario_nombre: str
    observacion: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}
