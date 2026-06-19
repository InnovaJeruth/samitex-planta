import logging
from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import settings
from app.database.connection import engine, Base, get_db
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

        # Refrescar cookie en cada respuesta
        response.set_cookie(
            CSRF_COOKIE,
            signed,
            httponly=False,      # JS necesita leerla
            samesite="lax",
            path="/",
            secure=False,        # cambiar a True si se agrega HTTPS
        )
        return response


# App
app = FastAPI(
    title=settings.APP_NAME,
    description="Sistema de seguimiento de Ordenes de Fabricacion - Area de Planta",
    version="1.0.0",
    docs_url="/api/docs" if settings.DEBUG else None,
    redoc_url="/api/redoc" if settings.DEBUG else None,
)


app.add_middleware(CSRFMiddleware)

# 401 - redirigir al login en paginas HTML
@app.exception_handler(401)
async def redirect_to_login(request: Request, exc):
    accept = request.headers.get("accept", "")
    path   = request.url.path
    if "text/html" in accept and "/api/" not in path and path != "/auth/login":
        return RedirectResponse(f"/auth/login?next={path}", status_code=302)
    from fastapi.responses import JSONResponse
    return JSONResponse({"detail": "No autenticado"}, status_code=401)


# 403 - pagina de error
@app.exception_handler(403)
async def forbidden_handler(request: Request, exc):
    from fastapi.responses import JSONResponse
    return JSONResponse({"detail": "Sin permisos para esta accion"}, status_code=403)

# ── Health check ─────────────────────────────────────────────
@app.get("/health", tags=["Sistema"])
def health_check():
    """Verifica que la app y la BD están operativas."""
    from sqlalchemy import text
    try:
        db = next(get_db())
        db.execute(text("SELECT 1"))
        db.close()
        db_ok = True
    except Exception as e:
        logger.error("Health check BD falló: %s", e, exc_info=True)
        db_ok = False
    status = "ok" if db_ok else "degraded"
    return {"status": status, "db": "ok" if db_ok else "error", "app": settings.APP_NAME}

# Archivos estaticos
app.mount("/static", StaticFiles(directory="static"), name="static")

# Routers
app.include_router(auth.router,       prefix="/auth",        tags=["Autenticacion"])
app.include_router(dashboard.router,  prefix="",             tags=["Dashboard"])
app.include_router(of.router,         prefix="/of",          tags=["Ordenes de Fabricacion"])
app.include_router(corte.router,      prefix="/corte",       tags=["Proceso de Corte"])
app.include_router(piezas.router,     prefix="/piezas",      tags=["Piezas"])
app.include_router(admin.router,      prefix="/admin",       tags=["Administracion"])
app.include_router(ws.router,         prefix="/ws",          tags=["WebSocket"])
app.include_router(plantas.router,    prefix="/plantas",     tags=["Plantas Externas"])
app.include_router(comercial.router,  prefix="/comercial",   tags=["Comercial"])
app.include_router(supervisor.router, prefix="/supervisor",  tags=["Supervisor"])
app.include_router(telegram_bot.router, tags=["Telegram Bot"])
