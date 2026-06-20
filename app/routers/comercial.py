from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from app.models.usuario import Usuario
from app.core.auth import get_current_user
from app.core.templates import templates

router = APIRouter()

ROLES_COMERCIAL = {"ADMIN", "PLANEADOR", "COMERCIAL", "COMERCIAL_MARCA",
                   "PLANEAMIENTO_MARCA", "GERENTE_PLANTA", "GERENCIA"}


def _check_comercial(user: Usuario):
    from fastapi import HTTPException
    rol = user.rol.value if hasattr(user.rol, "value") else str(user.rol)
    if rol not in ROLES_COMERCIAL:
        raise HTTPException(403, "Sin acceso al módulo comercial")


@router.get("/", response_class=HTMLResponse)
def lista_requerimientos(
    request: Request,
    current_user: Usuario = Depends(get_current_user),
):
    _check_comercial(current_user)
    return templates.TemplateResponse("comercial/lista.html", {
        "request": request,
        "current_user": current_user,
        "requerimientos": [],   # Fase 2: vendrá de BD
    })


@router.get("/nuevo", response_class=HTMLResponse)
def nuevo_requerimiento(
    request: Request,
    current_user: Usuario = Depends(get_current_user),
):
    _check_comercial(current_user)
    return templates.TemplateResponse("comercial/requerimiento_form.html", {
        "request": request,
        "current_user": current_user,
    })
