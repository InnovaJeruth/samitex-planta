"""
Bot Telegram — Samitex Planta
Recibe mensajes, consulta la BD via endpoints internos y responde con Gemini.
"""
import os, json, httpx, logging
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from google import genai as genai_sdk
from app.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()

# ── Config ────────────────────────────────────────────────────
TELEGRAM_TOKEN = settings.TELEGRAM_TOKEN
GEMINI_API_KEY  = settings.GEMINI_API_KEY
_ids_raw = settings.TELEGRAM_ALLOWED_IDS
ALLOWED_IDS = {int(x.strip()) for x in _ids_raw.split(",") if x.strip()}

TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

from app.constants import ORDEN_FASES, NOMBRES_FASE as FASES_NOMBRES

# ── Helpers Telegram ─────────────────────────────────────────
async def send_message(chat_id: int, text: str):
    async with httpx.AsyncClient() as client:
        await client.post(f"{TELEGRAM_API}/sendMessage", json={
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "Markdown"
        })

# ── Consultas internas a la BD ───────────────────────────────
BASE_URL = "http://127.0.0.1:8000"
BOT_KEY = settings.BOT_SECRET_KEY  # clave exclusiva para endpoints internos del bot

async def _get(path: str) -> dict:
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(
                f"{BASE_URL}{path}",
                headers={"X-Bot-Key": BOT_KEY}
            )
            if r.status_code == 200:
                return r.json()
            return {"error": f"HTTP {r.status_code}"}
    except Exception as e:
        return {"error": str(e)}

async def buscar_of_por_numero(numero_of: str) -> dict:
    """Busca una OF por su número y devuelve estado completo de fases y piezas."""
    data = await _get(f"/bot/api/of/{numero_of}")
    return data

async def listar_ofs_activas() -> dict:
    """Lista todas las OFs activas o en proceso."""
    data = await _get("/bot/api/ofs")
    return {"ofs": data}

async def resumen_dashboard() -> dict:
    """Devuelve KPIs generales."""
    data = await _get("/bot/api/ofs")
    return {"resumen": data}

# ── Formatear estado OF para respuesta legible ───────────────
def formatear_estado_of(numero_of: str, data: dict) -> str:
    of_info = data.get("of_info", {})
    estado = data.get("estado", {})

    if "error" in data:
        return f"❌ No encontré la OF *{numero_of}*. Verifica el número."

    cliente  = of_info.get("cliente", "—")
    prenda   = of_info.get("tipo_prenda", of_info.get("prenda", "—"))
    juegos   = of_info.get("total_juegos", "—")
    est      = of_info.get("estado", "—")

    piezas = estado.get("piezas", [])
    if not piezas:
        return f"📋 *OF {numero_of}* — {cliente} | {prenda} | {juegos} juegos\nEstado: {est}\n_(Sin piezas registradas)_"

    # Calcular avance por fase
    fases_avance = {}
    for p in piezas:
        for fase_id, fase_data in p.get("fases", {}).items():
            if fase_id not in fases_avance:
                fases_avance[fase_id] = {"completadas": 0, "en_proceso": 0, "total": 0}
            fases_avance[fase_id]["total"] += 1
            if fase_data.get("completada"):
                fases_avance[fase_id]["completadas"] += 1
            elif fase_data.get("cantidad_actual", 0) > 0:
                fases_avance[fase_id]["en_proceso"] += 1

    lines = [f"📋 *OF {numero_of}* — {cliente} | {prenda} | {juegos} juegos"]
    lines.append(f"Estado: *{est}*\n")
    lines.append("*Avance por fase:*")

    for fase_id in ORDEN_FASES:
        if fase_id not in fases_avance:
            continue
        fa = fases_avance[fase_id]
        nombre = FASES_NOMBRES.get(fase_id, fase_id)
        total = fa["total"]
        comp  = fa["completadas"]
        proc  = fa["en_proceso"]

        if comp == total:
            icon = "✅"
            estado_txt = f"Completada ({comp}/{total})"
        elif comp > 0 or proc > 0:
            icon = "🔄"
            estado_txt = f"En curso — {comp} completadas, {proc} en proceso de {total}"
        else:
            icon = "⏳"
            estado_txt = f"Pendiente (0/{total})"

        lines.append(f"{icon} *{nombre}:* {estado_txt}")

    return "\n".join(lines)

# ── Gemini setup ─────────────────────────────────────────────
async def get_gemini_response(user_message: str, context_data: str) -> str:
    try:
        prompt = f"""Eres el asistente de producción de Samitex Planta.
Respondes preguntas sobre órdenes de fabricación (OF) del área de corte.
Sé conciso y directo. Usa el contexto de datos para responder.
Si el dato no está en el contexto, dilo claramente.
Responde siempre en español.

CONTEXTO DE DATOS:
{context_data}

PREGUNTA DEL USUARIO:
{user_message}

Responde de forma clara y útil para un gerente o comercial."""

        client = genai_sdk.Client(api_key=GEMINI_API_KEY)
        response = client.models.generate_content(
            model="gemini-2.0-flash-lite",
            contents=prompt
        )
        return response.text
    except Exception as e:
        logger.error("Error Gemini API: %s", e, exc_info=True)
        return "No pude procesar esa consulta. Para estado de una OF específica escribe: *Estado OF 12345*"

# ── Endpoints internos (solo con X-Bot-Key) ──────────────────
from fastapi import Header, HTTPException
from app.database.connection import SessionLocal
from app.models.of import OrdenFabricacion, EstadoOF, DocumentoOF
from app.models.pieza import OFPieza
from app.models.fase import OFFaseEstado, OFFaseTiempos, AvanceRegistro

def _verify_bot_key(x_bot_key: str = Header(None)):
    if x_bot_key != settings.BOT_SECRET_KEY:
        raise HTTPException(status_code=403, detail="Forbidden")

def _of_to_str(v):
    """Convierte enums y fechas a string serializable."""
    if hasattr(v, "value"):
        return v.value
    if hasattr(v, "isoformat"):
        return v.isoformat()
    return v

@router.get("/bot/api/ofs")
def bot_ofs(x_bot_key: str = Header(None)):
    _verify_bot_key(x_bot_key)
    db = SessionLocal()
    try:
        ofs = db.query(OrdenFabricacion).filter(
            OrdenFabricacion.estado != EstadoOF.ANULADA
        ).all()
        return [
            {
                "numero_of": of.numero_of,
                "cliente": of.cliente,
                "tipo_prenda": _of_to_str(of.tipo_prenda),
                "total_juegos": of.total_juegos,
                "estado": _of_to_str(of.estado),
                "fecha_creacion": _of_to_str(of.fecha_creacion),
                "fecha_apt": _of_to_str(of.fecha_apt),
                "tercerizado": of.tercerizado,
            }
            for of in ofs
        ]
    finally:
        db.close()

@router.get("/bot/api/of/{numero_of}")
def bot_of_detalle(numero_of: str, x_bot_key: str = Header(None)):
    _verify_bot_key(x_bot_key)
    db = SessionLocal()
    try:
        of = db.query(OrdenFabricacion).filter(
            OrdenFabricacion.numero_of == numero_of
        ).first()
        if not of:
            return {"error": f"OF {numero_of} no encontrada"}

        of_info = {
            "numero_of": of.numero_of,
            "cliente": of.cliente,
            "tipo_prenda": _of_to_str(of.tipo_prenda),
            "total_juegos": of.total_juegos,
            "estado": _of_to_str(of.estado),
            "tipo_cliente": _of_to_str(of.tipo_cliente),
            "fecha_creacion": _of_to_str(of.fecha_creacion),
            "fecha_apt": _of_to_str(of.fecha_apt),
            "fecha_inicio_plan": _of_to_str(of.fecha_inicio_plan),
            "estado_docs": _of_to_str(of.estado_docs),
            "solped_prenda": of.solped_prenda,
            "orden_compra": of.orden_compra,
            "solped_mp": of.solped_mp,
            "tercerizado": of.tercerizado,
            "planta_externa": of.planta_externa,
            "fecha_envio_planta": _of_to_str(of.fecha_envio),
            "fecha_recepcion_est": _of_to_str(of.fecha_recepcion_est),
            "fecha_recepcion_real": _of_to_str(of.fecha_recepcion_real),
            "juegos_recibidos": of.juegos_recibidos,
        }

        # Documentos subidos
        docs = db.query(DocumentoOF).filter(DocumentoOF.of_id == of.id).all()
        docs_data = [
            {
                "tipo": d.tipo,
                "archivo": d.nombre_archivo,
                "area": d.area,
                "fecha_subida": _of_to_str(d.uploaded_at),
            }
            for d in docs
        ]

        # Piezas y fases
        piezas = db.query(OFPieza).filter(OFPieza.of_id == of.id).all()
        piezas_data = []
        for p in piezas:
            fases = db.query(OFFaseEstado).filter(OFFaseEstado.pieza_id == p.id).all()
            fases_dict = {}
            for f in fases:
                fases_dict[f.fase_id] = {
                    "completada": f.completada,
                    "cantidad_actual": f.cantidad_actual or 0,
                    "max_cantidad": f.max_cantidad,
                    "fecha_inicio": _of_to_str(f.fecha_inicio),
                    "fecha_completado": _of_to_str(f.fecha_completado),
                }
            piezas_data.append({"nombre": p.nombre, "material": p.material, "fases": fases_dict})

        # Tiempos de fase (programado vs real)
        tiempos = db.query(OFFaseTiempos).filter(OFFaseTiempos.of_id == of.id).all()
        tiempos_data = [
            {
                "fase": t.fase_id,
                "inicio_prog": _of_to_str(t.inicio_programado),
                "fin_prog": _of_to_str(t.fin_programado),
                "inicio_real": _of_to_str(t.inicio_real),
                "fin_real": _of_to_str(t.fin_real),
            }
            for t in tiempos
        ]

        # Últimos 10 avances registrados
        avances = (
            db.query(AvanceRegistro)
            .filter(AvanceRegistro.of_id == of.id, AvanceRegistro.revertido == False)
            .order_by(AvanceRegistro.created_at.desc())
            .limit(10)
            .all()
        )
        avances_data = [
            {
                "fase": a.fase_id,
                "cantidad": a.cantidad,
                "fecha": _of_to_str(a.created_at),
                "observacion": a.observacion,
            }
            for a in avances
        ]

        return {
            "of_info": of_info,
            "documentos": docs_data,
            "estado": {"piezas": piezas_data},
            "tiempos_fase": tiempos_data,
            "ultimos_avances": avances_data,
        }
    finally:
        db.close()


# ── Webhook principal ─────────────────────────────────────────
@router.post("/telegram/webhook")
async def telegram_webhook(request: Request):
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"ok": True})

    message = body.get("message", {})
    if not message:
        return JSONResponse({"ok": True})

    chat_id  = message.get("chat", {}).get("id")
    text     = message.get("text", "").strip()
    username = message.get("from", {}).get("first_name", "Usuario")

    if not chat_id or not text:
        return JSONResponse({"ok": True})

    # Comando /start — siempre responde y muestra Chat ID
    if text.startswith("/start"):
        msg = (
            f"👋 Hola *{username}*\\! Soy el asistente de *Samitex Planta*.\n\n"
            f"Tu Chat ID es: `{chat_id}`\n\n"
            "Puedes preguntarme:\n"
            "• _¿Cómo va la OF 343?_\n"
            "• _¿Cuántas OFs están activas?_\n"
            "• _Estado de la OF 411444_\n"
        )
        await send_message(chat_id, msg)
        return JSONResponse({"ok": True})

    # Verificar autorización
    if ALLOWED_IDS and chat_id not in ALLOWED_IDS:
        await send_message(chat_id, f"⛔ No tienes acceso. Tu ID es `{chat_id}`. Contacta al administrador.")
        return JSONResponse({"ok": True})

    # Procesar pregunta
    await send_message(chat_id, "⏳ Consultando...")

    text_lower = text.lower()
    context_data = ""
    respuesta = ""

    # Detectar si hay número de OF en el mensaje
    import re
    match = re.search(r'\b(\d{4,7})\b', text)

    if match:
        # Cualquier pregunta que incluya un número de OF → cargar todos los datos y usar Gemini
        numero_of = match.group(1)
        data = await buscar_of_por_numero(numero_of)
        if "error" in data:
            respuesta = f"❌ No encontré la OF *{numero_of}*. Verifica el número."
        else:
            # Si es pregunta simple de estado/avance → respuesta directa formateada
            palabras_estado = ["estado", "avance", "progreso", "cómo va", "como va", "fases"]
            es_pregunta_simple = any(w in text_lower for w in palabras_estado) and len(text.split()) <= 8
            if es_pregunta_simple:
                respuesta = formatear_estado_of(numero_of, data)
            else:
                # Pregunta elaborada → pasar todo el contexto a Gemini
                context_data = json.dumps(data, ensure_ascii=False, indent=2)
                respuesta = await get_gemini_response(text, context_data)

    elif any(w in text_lower for w in ["activas", "en proceso", "resumen", "cuántas", "cuantas", "dashboard", "general", "todas", "listado"]):
        data = await listar_ofs_activas()
        ofs = data.get("ofs", [])
        if isinstance(ofs, list):
            activas = [o for o in ofs if str(o.get("estado","")).upper() in ["ACTIVA","EN_PROCESO"]]
            context_data = f"OFs registradas ({len(ofs)} total, {len(activas)} activas/en proceso):\n"
            for o in ofs[:20]:
                context_data += f"- OF {o.get('numero_of')} | {o.get('cliente')} | {o.get('tipo_prenda')} | {o.get('total_juegos')} juegos | {o.get('estado')} | creada: {o.get('fecha_creacion')} | APT: {o.get('fecha_apt')}\n"
            respuesta = get_gemini_response(text, context_data)
        else:
            respuesta = "No pude obtener el listado de OFs."

    else:
        # Pregunta general — cargar lista completa como contexto
        data = await listar_ofs_activas()
        ofs = data.get("ofs", [])
        context_data = f"Sistema Samitex Planta — {len(ofs) if isinstance(ofs, list) else 0} OFs registradas.\n"
        if isinstance(ofs, list):
            for o in ofs[:15]:
                context_data += f"- OF {o.get('numero_of')} | {o.get('cliente')} | {o.get('estado')}\n"
        respuesta = get_gemini_response(text, context_data)

    await send_message(chat_id, respuesta)
    return JSONResponse({"ok": True})


# ── Endpoint para registrar webhook con Telegram ─────────────
@router.get("/telegram/setup")
async def setup_webhook(request: Request):
    """Llama a este endpoint una vez para registrar el webhook con Telegram."""
    ngrok_url = settings.NGROK_URL.rstrip("/")
    if not ngrok_url:
        return {"error": "Configura NGROK_URL en .env"}

    webhook_url = f"{ngrok_url}/telegram/webhook"
    async with httpx.AsyncClient() as client:
        r = await client.post(
            f"{TELEGRAM_API}/setWebhook",
            json={"url": webhook_url}
        )
    return {"webhook_url": webhook_url, "telegram_response": r.json()}
