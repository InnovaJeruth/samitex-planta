from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional
from app.models.usuario import RolEnum


class UsuarioCreate(BaseModel):
    nombre: str
    email: str
    username: str
    password: str
    rol: RolEnum = RolEnum.SOLO_LECTURA

    @field_validator("username")
    @classmethod
    def username_valido(cls, v):
        if len(v) < 3:
            raise ValueError("El username debe tener al menos 3 caracteres")
        if not v.replace("_", "").replace(".", "").isalnum():
            raise ValueError("El username solo puede contener letras, números, puntos y guiones bajos")
        return v.lower()

    @field_validator("password")
    @classmethod
    def password_seguro(cls, v):
        if len(v) < 6:
            raise ValueError("La contraseña debe tener al menos 6 caracteres")
        return v


class UsuarioUpdate(BaseModel):
    nombre: Optional[str] = None
    email: Optional[str] = None
    rol: Optional[RolEnum] = None
    activo: Optional[bool] = None


class UsuarioResponse(BaseModel):
    id: int
    nombre: str
    email: str
    username: str
    rol: RolEnum
    activo: bool

    model_config = {"from_attributes": True}


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    nombre: str
    rol: str
