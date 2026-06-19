from pydantic import BaseModel, field_validator
from typing import Optional


class PiezaCreate(BaseModel):
    nombre: str
    codigo_sap: Optional[str] = None
    material: str = "TELA"
    cantidad_x_prenda: int = 1
    fusionado: bool = False
    estampado_bordado: bool = False
    orden: int = 0

    @field_validator("nombre")
    @classmethod
    def nombre_not_empty(cls, v):
        if not v.strip():
            raise ValueError("El nombre de la pieza no puede estar vacío")
        return v.strip()

    @field_validator("cantidad_x_prenda")
    @classmethod
    def cantidad_positiva(cls, v):
        if v < 1:
            raise ValueError("La cantidad por prenda debe ser al menos 1")
        return v


class PiezaUpdate(BaseModel):
    codigo_sap: Optional[str] = None
    material: Optional[str] = None
    fusionado: Optional[bool] = None
    estampado_bordado: Optional[bool] = None


class PiezaResponse(BaseModel):
    id: int
    nombre: str
    codigo_sap: Optional[str] = None
    material: str
    cantidad_x_prenda: int
    fusionado: bool
    estampado_bordado: bool
    orden: int

    model_config = {"from_attributes": True}
