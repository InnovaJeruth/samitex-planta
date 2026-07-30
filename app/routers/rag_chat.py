"""Router del Chat analítico (RAG Text-to-SQL) — R4.

`POST /api/chat`: recibe una pregunta en lenguaje natural, genera SQL con Gemini,
lo valida y ejecuta en modo solo lectura (`get_db_ro`), y devuelve filas + un
resumen. Acceso restringido a ROLES_ANALITICA. No escribe en el ERP.
"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import settings
from app.core.auth import get_current_user
from app.core.templates import templates
from app.database.readonly import get_db_ro
from app.models.usuario import Usuario
from app.roles import ROLES_ANALITICA, rol_de
from app.services import rag_service
from app.services.rag_service import RAGOcupado
from app.services.rag_guard import SQLNoPermitido

log = logging.getLogger("rag_chat")
router = APIRouter()


def _check(user: Usuario):
    if not settings.RAG_ENABLED:
        raise HTTPException(503, "El chat analítico está deshabilitado.")
    if rol_de(user) not in ROLES_ANALITICA:
        raise HTTPException(403, "Sin permiso para el chat analítico.")


class ChatIn(BaseModel):
    pregunta: str
    incluir_sql: bool = False


class ChatOut(BaseModel):
    respuesta: str
    sql: Optional[str] = None
    columnas: list = []
    filas: list = []


@router.get("/chat", response_class=HTMLResponse)
def pagina(request: Request, current_user: Usuario = Depends(get_current_user)):
    _check(current_user)
    return templates.TemplateResponse("analitica/chat.html", {
        "request": request, "current_user": current_user,
    })


@router.post("/chat", response_model=ChatOut)
def chat(body: ChatIn, db_ro: Session = Depends(get_db_ro),
         current_user: Usuario = Depends(get_current_user)):
    _check(current_user)
    pregunta = (body.pregunta or "").strip()
    if not pregunta:
        raise HTTPException(400, "La pregunta no puede estar vacía.")
    if len(pregunta) > 500:
        raise HTTPException(400, "La pregunta es demasiado larga (máx. 500 caracteres).")

    try:
        res = rag_service.responder(pregunta, db_ro, incluir_sql=body.incluir_sql)
    except RAGOcupado as e:
        log.info("RAG ocupado usuario=%s (sin cupo de concurrencia)", current_user.id)
        raise HTTPException(429, str(e))
    except SQLNoPermitido as e:
        log.warning("RAG bloqueado usuario=%s pregunta=%r motivo=%s",
                    current_user.id, pregunta, e)
        raise HTTPException(400, f"Consulta no permitida: {e}")
    except Exception as e:  # error del LLM / ejecución
        log.exception("RAG error usuario=%s pregunta=%r", current_user.id, pregunta)
        msg = str(e).lower()
        es_ollama = settings.RAG_LLM_PROVIDER.lower() == "ollama"
        if "quota" in msg or "resource_exhausted" in msg or "429" in msg:
            raise HTTPException(429, "Se alcanzó el límite de uso de Gemini. "
                                     "Reintenta en un minuto o revisa la cuota/clave de la API.")
        if es_ollama and ("404" in msg or "not found" in msg):
            raise HTTPException(502, f"El modelo local no está descargado. "
                                     f"Ejecuta: ollama pull {settings.RAG_OLLAMA_MODEL}")
        if "timed out" in msg or "timeout" in msg or "readtimeout" in msg:
            raise HTTPException(504, "El modelo local tardó demasiado en responder. "
                                     "La primera consulta carga el modelo en memoria; reintenta. "
                                     "Si sigue lento, usa un modelo más liviano (qwen2.5-coder:1.5b).")
        if "refused" in msg or "connecterror" in msg or "max retries" in msg or "failed to establish" in msg:
            raise HTTPException(502, "No se pudo conectar al modelo local (Ollama). "
                                     "Verifica que esté corriendo (ollama serve).")
        if "api key" in msg or "permission" in msg or "unauthenticated" in msg or "401" in msg:
            raise HTTPException(502, "Error de autenticación con Gemini: revisa GEMINI_API_KEY.")
        raise HTTPException(502, "No se pudo procesar la consulta. Intenta reformularla.")

    log.info("RAG ok usuario=%s pregunta=%r filas=%d",
             current_user.id, pregunta, len(res["filas"]))
    return res
