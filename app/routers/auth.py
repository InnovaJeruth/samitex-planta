import time
import threading
from collections import defaultdict
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.models.usuario import Usuario
from app.core.auth import (
    verify_password, create_access_token,
    get_current_user, get_current_user_optional, COOKIE_NAME,
)
from app.schemas.usuario import TokenResponse, UsuarioResponse
from app.config import settings
from app.core.templates import templates

router = APIRouter()

COOKIE_MAX_AGE = settings.JWT_EXPIRE_MINUTES * 60  # segundos

# ── Rate limiting para login ───────────────────────────────────
# Máx. 5 intentos fallidos por IP en ventana de 5 minutos
_LOGIN_MAX_INTENTOS = 5
_LOGIN_VENTANA_SEG  = 300   # 5 min

_login_lock = threading.Lock()
# {ip: [timestamp, ...]}  — solo timestamps de intentos FALLIDOS
_login_intentos: dict[str, list[float]] = defaultdict(list)


def _get_ip(request: Request) -> str:
    """Extrae IP real respetando X-Forwarded-For (proxy/ngrok)."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _check_rate_limit(ip: str) -> None:
    now = time.time()
    with _login_lock:
        # Limpiar intentos fuera de la ventana
        _login_intentos[ip] = [t for t in _login_intentos[ip] if now - t < _LOGIN_VENTANA_SEG]
        if len(_login_intentos[ip]) >= _LOGIN_MAX_INTENTOS:
            segundos_restantes = int(_LOGIN_VENTANA_SEG - (now - _login_intentos[ip][0]))
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Demasiados intentos fallidos. Intenta en {segundos_restantes // 60 + 1} min.",
            )


def _registrar_fallo(ip: str) -> None:
    with _login_lock:
        _login_intentos[ip].append(time.time())


def _limpiar_intentos(ip: str) -> None:
    with _login_lock:
        _login_intentos.pop(ip, None)


# ── Login página ──────────────────────────────────────────────
@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request, user=Depends(get_current_user_optional)):
    if user:
        return RedirectResponse("/", status_code=302)
    return templates.TemplateResponse("auth/login.html", {"request": request})


# ── Login POST (form + JSON) ──────────────────────────────────
@router.post("/login")
def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    ip = _get_ip(request)
    _check_rate_limit(ip)   # bloquea si superó el límite

    user = db.query(Usuario).filter(
        Usuario.username == form_data.username,
        Usuario.activo == True,
    ).first()
    if not user or not verify_password(form_data.password, user.password_hash):
        _registrar_fallo(ip)   # contabilizar intento fallido
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario o contraseña incorrectos",
        )

    _limpiar_intentos(ip)   # login exitoso: resetear contador
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
        secure=settings.APP_ENV == "production",
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
