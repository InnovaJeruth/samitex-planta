import logging
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import settings
from app.database.connection import engine, Base
from app.routers import auth, dashboard, of, corte, piezas, admin, ws, plantas, comercial, supervisor, telegram_bot
from app.core.csrf import (
    new_token, sign_token, verify_signed, is_exempt,
    CSRF_COOKIE, CSRF_HEADER,
)

# ── Logging ───────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# Crear tablas si no existen (desarrollo)
# En producción usar Alembic: alembic upgrade head
Base.metadata.create_all(bind=engine)


# ── CSRF Middleware ───────────────────────────────────────────
class CSRFMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path   = request.url.path
        method = request.method

        # Leer o generar token
        signed = request.cookies.get(CSRF_COOKIE, "")
        token  = verify_signed(signed, settings.SECRET_KEY) if signed else None
        if not token:
            token  = new_token()
            signed = sign_token(token, settings.SECRET_KEY)

        # Validar en métodos mutantes no exentos
        if not is_exempt(path, method):
            submitted = request.headers.get(CSRF_HEADER, "")
            if submitted != token:
                logger.warning("CSRF token inválido en %s %s", method, path)
                return JSONResponse(
                    {"detail": "Token CSRF inválido o ausente. Recarga la página."},
                    status_code=403,
                )

        response = await call_next(request)

        # ── Headers de seguridad HTTP ─────────────────────────
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"]        = "DENY"
        response.headers["Referrer-Policy"]        = "strict-origin-when-cross-origin"

        # Refrescar cookie CSRF
        response.set_cookie(
            key=CSRF_COOKIE,
            value=signed,
            httponly=False,
            samesite="lax",
            secure=False,
        )
        return response


# ── Aplicación FastAPI ────────────────────────────────────────
app = FastAPI(
    title="Sistema de seguimiento de Ordenes de Fabricacion - Area de Planta",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

app.add_middleware(CSRFMiddleware)


# ── Exception handlers ────────────────────────────────────────
@app.exception_handler(401)
async def redirect_to_login(request: Request, exc):
    if "text/html" in request.headers.get("accept", "") and "/api/" not in request.url.path:
        return RedirectResponse(url=f"/auth/login?next={request.url.path}", status_code=302)
    return JSONResponse({"detail": "No autenticado"}, status_code=401)


@app.exception_handler(403)
async def forbidden_handler(request: Request, exc):
    return JSONResponse({"detail": "Sin permisos para esta accion"}, status_code=403)


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    # Login: campo vacío → tratar como credenciales incorrectas
    if request.url.path.endswith("/login"):
        return JSONResponse({"detail": "Usuario o contrasena incorrectos"}, status_code=401)
    return JSONResponse({"detail": exc.errors()}, status_code=422)


# ── Archivos estáticos ────────────────────────────────────────
app.mount("/static", StaticFiles(directory="static"), name="static")


# ── Routers ───────────────────────────────────────────────────
app.include_router(auth.router,         prefix="/auth",       tags=["Autenticacion"])
app.include_router(dashboard.router,                          tags=["Dashboard"])
app.include_router(of.router,           prefix="/of",         tags=["Ordenes de Fabricacion"])
app.include_router(corte.router,        prefix="/corte",      tags=["Proceso de Corte"])
app.include_router(piezas.router,       prefix="/piezas",     tags=["Piezas"])
app.include_router(admin.router,        prefix="/admin",      tags=["Administracion"])
app.include_router(ws.router,           prefix="/ws",         tags=["WebSocket"])
app.include_router(plantas.router,      prefix="/plantas",    tags=["Plantas Externas"])
app.include_router(comercial.router,    prefix="/comercial",  tags=["Comercial"])
app.include_router(supervisor.router,   prefix="/supervisor", tags=["Supervisor"])
app.include_router(telegram_bot.router,                       tags=["Telegram"])
