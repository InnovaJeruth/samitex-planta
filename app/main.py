import hmac
import logging
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import settings
from app.database.connection import engine, Base
from app.routers import auth, dashboard, of, corte, piezas, admin, ws, plantas, comercial, supervisor, pdf_report
from app.routers import ingenieria, catalogo, curvas, hoja_costos, trazos, paquetes
from app.routers import process_mining, requerimientos, rag_chat
from app.core.csrf import (
    new_token, sign_token, verify_signed, is_exempt,
    CSRF_COOKIE, CSRF_HEADER,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

Base.metadata.create_all(bind=engine)


class CSRFMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path   = request.url.path
        method = request.method

        signed = request.cookies.get(CSRF_COOKIE, "")
        token  = verify_signed(signed, settings.SECRET_KEY) if signed else None
        if not token:
            token  = new_token()
            signed = sign_token(token, settings.SECRET_KEY)

        if not is_exempt(path, method):
            submitted = request.headers.get(CSRF_HEADER, "")
            if not hmac.compare_digest(submitted, token):
                logger.warning("CSRF token invalido en %s %s", method, path)
                return JSONResponse(
                    {"detail": "Token CSRF invalido o ausente. Recarga la pagina."},
                    status_code=403,
                )

        response = await call_next(request)

        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"]        = "SAMEORIGIN"
        response.headers["Referrer-Policy"]        = "strict-origin-when-cross-origin"

        response.set_cookie(
            key=CSRF_COOKIE,
            value=signed,
            httponly=False,
            samesite="lax",
            secure=settings.APP_ENV == "production",
        )
        return response


app = FastAPI(
    title="Sistema de seguimiento de Ordenes de Fabricacion - Area de Planta",
    version="1.0.0",
    docs_url=settings.DOCS_URL,
    redoc_url=settings.REDOC_URL,
    openapi_url=settings.OPENAPI_URL,
)

app.add_middleware(CSRFMiddleware)

# Valida la cabecera Host contra ALLOWED_HOSTS (anti Host header injection).
# Default "*" no bloquea nada; en producción se listan los hosts reales.
from starlette.middleware.trustedhost import TrustedHostMiddleware
app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.ALLOWED_HOSTS_LIST)


@app.on_event("startup")
async def _capturar_loop():
    """Guarda el event loop para que los endpoints síncronos puedan emitir
    notificaciones WebSocket (ws_manager.notify_of)."""
    import asyncio
    from app.core.websocket_manager import ws_manager
    ws_manager.set_loop(asyncio.get_running_loop())


@app.on_event("startup")
def _seed_referencia():
    """Seed idempotente de datos de referencia (fases_catalogo). Corre en el
    arranque (no en el import del módulo) para no acoplar la importación a que
    la BD esté viva; si la BD no responde, se loguea sin tumbar el arranque.
    Sin estas 9 fases, una BD recién creada falla al crear of_fases_estado (FK)."""
    try:
        from app.database.seed import seed_fases_catalogo
        n = seed_fases_catalogo()
        if n:
            logger.info("Seed: %d fases insertadas en fases_catalogo", n)
    except Exception as e:
        logger.warning("No se pudo sembrar fases_catalogo: %s", e)


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
    if request.url.path.endswith("/login"):
        return JSONResponse({"detail": "Usuario o contrasena incorrectos"}, status_code=401)
    return JSONResponse({"detail": exc.errors()}, status_code=422)


app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/health", tags=["Infra"])
def health():
    """Healthcheck para balanceador/orquestador. Público, sin auth y exento de
    CSRF (GET). Siempre responde 200 (liveness); informa el estado de la BD sin
    fallar si está caída, para que un blip de BD no marque el proceso como muerto."""
    from sqlalchemy import text
    from app.database.connection import engine
    db_ok = True
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as e:
        db_ok = False
        logger.warning("Healthcheck: BD no responde: %s", e)
    return {"status": "ok", "db": "up" if db_ok else "down"}


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
app.include_router(pdf_report.router,                         tags=["Reportes"])
app.include_router(ingenieria.router,                         tags=["Ingenieria"])
app.include_router(catalogo.router,    prefix="/catalogo",    tags=["Catalogo de Prendas"])
app.include_router(hoja_costos.router, prefix="/catalogo",    tags=["Hoja de Costos"])
app.include_router(curvas.router,      prefix="/curvas",      tags=["Curvas de Tallas"])
app.include_router(trazos.router,      prefix="/trazos",      tags=["Trazos de Corte"])
app.include_router(paquetes.router,    prefix="/paquetes",    tags=["Paquetes / Numeración"])
app.include_router(process_mining.router, prefix="/analitica", tags=["Analítica / Process Mining"])
app.include_router(requerimientos.router, prefix="/requerimientos", tags=["Requerimientos comerciales"])
app.include_router(rag_chat.router,       prefix="/api",           tags=["Chat analítico (RAG)"])
