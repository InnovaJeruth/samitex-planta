from pydantic import BaseModel, field_validator
from typing import Optional, List


class AvanceCreate(BaseModel):
    pieza_id: int
    fase_id: str
    cantidad: int
    observacion: Optional[str] = None
    sku_id: Optional[int] = None   # talla (OFs corte_por_talla, fases F4–F7)

    @field_validator("cantidad")
    @classmethod
    def cantidad_positiva(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("cantidad debe ser mayor a 0")
        return v


class CompletarRequest(BaseModel):
    pieza_id: int
    fase_id: str
    sku_id: Optional[int] = None   # talla (OFs corte_por_talla, fases F4–F7)
