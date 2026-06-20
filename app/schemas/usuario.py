from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional
from app.models.usuario import RolEnum


class UsuarioCreate(BaseModel):
    username: str
    email: EmailStr
    nombre: str
    password: str
    rol: RolEnum = RolEnum.SUPERVISOR_CORTE


class UsuarioResponse(BaseModel):
    id: int
    username: str
    email: Optional[str] = None
    nombre: str
    rol: str
    activo: bool

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    nombre: str
    rol: str
    username: str
