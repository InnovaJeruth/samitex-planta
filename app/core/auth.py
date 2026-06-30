from datetime import datetime, timedelta
from jose import JWTError, jwt
import bcrypt as _bcrypt
import uuid
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from typing import Optional

from app.config import settings
from app.database.connection import get_db
from app.models.usuario import Usuario, RolEnum

# OAuth2 para Swagger/API (header Authorization: Bearer)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)

COOKIE_NAME = "samitex_token"


def hash_password(password: str) -> str:
    """Genera hash bcrypt de la contraseña."""
    return _bcrypt.hashpw(password.encode("utf-8"), _bcrypt.gensalt(rounds=12)).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """Verifica contraseña contra su hash bcrypt."""
    try:
        return _bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


def create_access_token(data: dict) -> str:
    payload = data.copy()
    payload["exp"] = datetime.utcnow() + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
    payload["jti"] = uuid.uuid4().hex  # ID único para poder revocar el token
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def _decode_token(token: str) -> Optional[dict]:
    """Decodifica un JWT y retorna el payload completo, o None si es inválido."""
    try:
        return jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    except JWTError:
        return None


def get_current_user(
    request: Request,
    bearer_token: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> Usuario:
    """
    Obtiene el usuario autenticado desde:
    1. Cookie HttpOnly 'samitex_token' (web browser)
    2. Header Authorization: Bearer <token> (API / Swagger)
    """
    token = None

    # 1. Intentar desde cookie
    cookie_token = request.cookies.get(COOKIE_NAME)
    if cookie_token:
        token = cookie_token

    # 2. Fallback: header Bearer
    if not token and bearer_token:
        token = bearer_token

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No autenticado",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = _decode_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido o expirado",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Verificar que el token no haya sido revocado (logout)
    jti = payload.get("jti")
    if jti:
        from app.models.usuario import TokenRevocado
        if db.query(TokenRevocado).filter_by(jti=jti).first():
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Sesión cerrada. Inicia sesión nuevamente.",
                headers={"WWW-Authenticate": "Bearer"},
            )

    username = payload.get("sub")
    if not username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido o expirado",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = db.query(Usuario).filter(
        Usuario.username == username,
        Usuario.activo == True,
    ).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuario no encontrado")

    return user


def get_current_user_optional(
    request: Request,
    bearer_token: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> Optional[Usuario]:
    """Como get_current_user pero retorna None en vez de 401 (para páginas HTML)."""
    try:
        return get_current_user(request, bearer_token, db)
    except HTTPException:
        return None


def get_rol(user: Usuario) -> str:
    """Retorna el rol del usuario como string (compatible con Enum y str)."""
    return user.rol.value if hasattr(user.rol, "value") else str(user.rol)


def require_roles(*roles: RolEnum):
    """Dependendencia FastAPI que lanza 403 si el usuario no tiene alguno de los roles."""
    def _check(current_user: Usuario = Depends(get_current_user)):
        if current_user.rol not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Rol '{current_user.rol}' no tiene acceso a este recurso.",
            )
        return current_user
    return _check
