import time
import threading
from collections import defaultdict
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.models.usuario import Usuario, TokenRevocado
from app.core.auth import (
    verify_password, hash_password, create_access_token, _decode_token,
    get_current_user, get_current_user_optional, COOKIE_NAME,
)
from app.schemas.usuario import TokenResponse, UsuarioResponse
from app.config import settings
from app.core.templates import templates

router = APIRouter()

COOKIE_MAX_AGE = settings.JWT_EXPIRE_MINUTES * 60

_LOGIN_MAX_INTENTOS = 5
_LOGIN_VENTANA_SEG  = 300

_login_lock = threading.Lock()
_login_intentos: dict[str, list[float]] = defaultdict(list)

# Hash "señuelo" para gastar el mismo tiempo cuando el usuario no existe
# (evita enumeración de usuarios por diferencia de latencia).
_DUMMY_HASH = hash_password("no-such-user")


def _get_ip(request: Request) -> str:
    # Solo confiar en X-Forwarded-For si hay un proxy confiable delante (config).
    # Si no, usar la IP real del socket → evita spoofing del header para saltar el rate limit.
    if settings.TRUST_PROXY:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _check_rate_limit(ip: str) -> None:
    now = time.time()
    with _login_lock:
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


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request, user=Depends(get_current_user_optional)):
    if user:
        return RedirectResponse("/", status_code=302)
    return templates.TemplateResponse("auth/login.html", {"request": request})


@router.post("/login")
def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    ip = _get_ip(request)
    _check_rate_limit(ip)

    user = db.query(Usuario).filter(
        Usuario.username == form_data.username,
        Usuario.activo == True,
    ).first()
    # Verificar siempre un hash (real o señuelo) → tiempo constante, sin enumeración
    hash_a_verificar = user.password_hash if user else _DUMMY_HASH
    if not verify_password(form_data.password, hash_a_verificar) or not user:
        _registrar_fallo(ip)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario o contrasena incorrectos",
        )

    _limpiar_intentos(ip)
    token = create_access_token({"sub": user.username, "rol": user.rol})

    response = JSONResponse(content={
        "access_token": token,
        "token_type": "bearer",
        "nombre": user.nombre,
        "rol": user.rol,
        "username": user.username,
    })

    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        max_age=COOKIE_MAX_AGE,
        httponly=True,
        samesite="lax",
        secure=settings.APP_ENV == "production",
    )
    return response


@router.get("/me", response_model=UsuarioResponse)
def me(current_user: Usuario = Depends(get_current_user)):
    return current_user


def _revocar_token(request: Request, db: Session) -> None:
    """Agrega el JTI del token actual a la lista negra y limpia los expirados."""
    from datetime import datetime
    token = request.cookies.get(COOKIE_NAME)
    if token:
        payload = _decode_token(token)
        if payload:
            jti = payload.get("jti")
            exp = payload.get("exp")
            if jti and exp:
                expires_at = datetime.utcfromtimestamp(exp)
                if not db.query(TokenRevocado).filter_by(jti=jti).first():
                    db.add(TokenRevocado(jti=jti, expires_at=expires_at))
                # Limpiar tokens expirados (housekeeping)
                db.query(TokenRevocado).filter(
                    TokenRevocado.expires_at < datetime.utcnow()
                ).delete()
                db.commit()


@router.post("/logout")
def logout(request: Request, db: Session = Depends(get_db)):
    _revocar_token(request, db)
    response = JSONResponse(content={"mensaje": "Sesion cerrada"})
    response.delete_cookie(COOKIE_NAME)
    return response


@router.get("/logout")
def logout_get(request: Request, db: Session = Depends(get_db)):
    _revocar_token(request, db)
    response = RedirectResponse("/auth/login", status_code=302)
    response.delete_cookie(COOKIE_NAME)
    return response
