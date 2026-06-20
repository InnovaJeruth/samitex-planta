from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel as PydanticBase
from typing import Optional

from app.database.connection import get_db
from app.models.usuario import Usuario, RolEnum
from app.core.auth import get_current_user, hash_password
from app.core.templates import templates

router = APIRouter()


def _solo_admin(user: Usuario):
    rol = user.rol.value if hasattr(user.rol, "value") else str(user.rol)
    if rol != "ADMIN":
        raise HTTPException(403, "Solo ADMIN puede acceder")


# ── Página usuarios ───────────────────────────────────────────
@router.get("/", response_class=HTMLResponse)
def lista_usuarios(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    _solo_admin(current_user)
    usuarios = db.query(Usuario).order_by(Usuario.nombre).all()
    return templates.TemplateResponse("admin/usuarios.html", {
        "request": request,
        "usuarios": usuarios,
        "roles": list(RolEnum),
        "current_user": current_user,
    })


# ── API: crear usuario ────────────────────────────────────────
class UsuarioCreate(PydanticBase):
    nombre:   str
    username: str
    email:    str
    password: str
    rol:      str = "SOLO_LECTURA"


@router.post("/api/usuarios")
def crear_usuario(
    body: UsuarioCreate,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    _solo_admin(current_user)
    if db.query(Usuario).filter_by(username=body.username).first():
        raise HTTPException(400, f"Username '{body.username}' ya existe")
    hashed = hash_password(body.password)
    user = Usuario(
        nombre=body.nombre.strip(),
        username=body.username.strip(),
        email=body.email.strip(),
        password_hash=hashed,
        rol=RolEnum(body.rol),
        activo=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"id": user.id, "username": user.username}


# ── API: toggle activo ────────────────────────────────────────
@router.patch("/api/usuarios/{user_id}/toggle")
def toggle_usuario(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    _solo_admin(current_user)
    user = db.query(Usuario).filter_by(id=user_id).first()
    if not user:
        raise HTTPException(404, "Usuario no encontrado")
    if user.id == current_user.id:
        raise HTTPException(400, "No puedes desactivarte a ti mismo")
    user.activo = not user.activo
    db.commit()
    return {"activo": user.activo}


# ── API: cambiar contraseña ───────────────────────────────────
class CambiarPasswordBody(PydanticBase):
    password: str


@router.patch("/api/usuarios/{user_id}/password")
def cambiar_password(
    user_id: int,
    body: CambiarPasswordBody,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    _solo_admin(current_user)
    user = db.query(Usuario).filter_by(id=user_id).first()
    if not user:
        raise HTTPException(404, "Usuario no encontrado")
    user.password_hash = hash_password(body.password)
    db.commit()
    return {"ok": True}
