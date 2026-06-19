from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.models.usuario import Usuario
from app.core.auth import (
    verify_password, create_access_token,
    get_current_user, get_current_user_optional, COOKIE_NAME,
)
from app.schemas.usuario import TokenResponse, UsuarioResponse
from app.config import settings

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

COOKIE_MAX_AGE = settings.JWT_EXPIRE_MINUTES * 60  # segundos


# ── Login página ──────────────────────────────────────────────
@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request, user=Depends(get_current_user_optional)):
    if user:
        return RedirectResponse("/", status_code=302)
    return templates.TemplateResponse("auth/login.html", {"request": request})


# ── Login POST (form + JSON) ──────────────────────────────────
@router.post("/login")
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    user = db.query(Usuario).filter(
        Usuario.username == form_data.username,
        Usuario.activo == True,
    ).first()
    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario o contraseña incorrectos",
        )

    token = create_access_token({"sub": user.username, "rol": user.rol})

    response = JSONResponse(content={
        "access_token": token,
        "token_type": "bearer",
        "nombre": user.nombre,
        "rol": user.rol,
        "username": user.username,
    })

    # Setear cookie HttpOnly para el browser
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        max_age=COOKIE_MAX_AGE,
        httponly=True,
        samesite="lax",
        secure=False,  # True en producción con HTTPS
    )
    return response


# ── Usuario actual ────────────────────────────────────────────
@router.get("/me", response_model=UsuarioResponse)
def me(current_user: Usuario = Depends(get_current_user)):
    return current_user


# ── Logout ────────────────────────────────────────────────────
@router.post("/logout")
def logout():
    response = JSONResponse(content={"mensaje": "Sesión cerrada"})
    response.delete_cookie(COOKIE_NAME)
    return response


@router.get("/logout")
def logout_get():
    response = RedirectResponse("/auth/login", status_code=302)
    response.delete_cookie(COOKIE_NAME)
    return response
