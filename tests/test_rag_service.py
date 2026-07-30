"""R2 · RAG Text-to-SQL. Esquema del whitelist, prompt, limpieza y generación
(con el LLM mockeado; no se ejecuta SQL ni se llama a la red)."""
import pytest

from app.services import rag_service as svc


def test_esquema_solo_incluye_whitelist():
    esquema = svc.construir_esquema()
    assert "TABLA ordenes_fabricacion" in esquema
    assert "TABLA of_paquetes" in esquema
    # tablas fuera del whitelist NO deben aparecer
    assert "tokens_revocados" not in esquema
    assert "parametros_sistema" not in esquema


def test_esquema_trae_columnas_y_notas():
    esquema = svc.construir_esquema()
    assert "numero_of" in esquema                     # columna real
    assert "BORRADOR | ACTIVA | EN_PROCESO | COMPLETADA" in esquema   # nota de estado


def test_esquema_incluye_vista_de_fases():
    esquema = svc.construir_esquema()
    assert "VISTA vw_of_fases" in esquema
    assert "Fusionado" in esquema and "Calidad" in esquema


def test_guard_permite_la_vista():
    from app.services import rag_guard as g
    out = g.validar_sql("SELECT fase, minutos FROM vw_of_fases WHERE numero_of='X'")
    assert "vw_of_fases" in out


def test_prompt_incluye_glosario_reglas_y_pregunta():
    p = svc.construir_prompt("¿cuántas OF activas?")
    assert "GLOSARIO" in p
    assert "SELECT" in p and "TOP" in p
    assert "Prohibido INSERT" in p
    assert "¿cuántas OF activas?" in p


@pytest.mark.parametrize("crudo,esperado", [
    ("```sql\nSELECT 1\n```", "SELECT 1"),
    ("SQL: SELECT 1;", "SELECT 1"),
    ("  SELECT 1 ;  ", "SELECT 1"),
    ("```\nSELECT a FROM t\n```", "SELECT a FROM t"),
])
def test_limpiar_sql(crudo, esperado):
    assert svc.limpiar_sql(crudo) == esperado


def test_generar_sql_usa_llm_mock(monkeypatch):
    llamado = {}
    def fake(prompt):
        llamado["prompt"] = prompt
        return "```sql\nSELECT COUNT(*) FROM ordenes_fabricacion;\n```"
    monkeypatch.setattr(svc, "_invocar_llm", fake)

    sql = svc.generar_sql("¿cuántas OF hay?")
    assert sql == "SELECT COUNT(*) FROM ordenes_fabricacion"
    assert "ESQUEMA DISPONIBLE" in llamado["prompt"]   # se le pasó el contexto


def test_generar_sql_pregunta_vacia_falla():
    with pytest.raises(ValueError):
        svc.generar_sql("   ")


# ── Orquestador responder (R4) ───────────────────────────────────────────────
def _fake_llm(sql_out):
    """Devuelve SQL en la 1ª llamada (prompt con esquema) y un resumen en la 2ª."""
    def fake(prompt):
        if "ESQUEMA DISPONIBLE" in prompt:
            return sql_out
        return "Hay 0 OFs registradas."
    return fake


def test_responder_flujo_completo(db, monkeypatch):
    monkeypatch.setattr(svc, "_invocar_llm",
                        _fake_llm("SELECT COUNT(*) AS n FROM ordenes_fabricacion"))
    out = svc.responder("¿cuántas OF hay?", db, incluir_sql=True)
    assert out["columnas"] == ["n"]
    assert out["filas"] == [{"n": 0}]
    assert out["respuesta"] == "Hay 0 OFs registradas."   # resumen NL (LLM #2)
    assert out["sql"].upper().startswith("SELECT")


def test_responder_oculta_sql_por_defecto(db, monkeypatch):
    monkeypatch.setattr(svc, "_invocar_llm",
                        _fake_llm("SELECT COUNT(*) AS n FROM ordenes_fabricacion"))
    out = svc.responder("¿cuántas OF hay?", db)   # incluir_sql=False
    assert out["sql"] is None


def test_responder_bloquea_sql_malicioso(db, monkeypatch):
    from app.services.rag_guard import SQLNoPermitido
    monkeypatch.setattr(svc, "_invocar_llm", _fake_llm("DELETE FROM ordenes_fabricacion"))
    with pytest.raises(SQLNoPermitido):
        svc.responder("borra todo", db)


def test_router_chat_expone_ruta():
    from app.routers import rag_chat
    paths = {r.path for r in rag_chat.router.routes}
    assert "/chat" in paths


# ── Fase 1: cupo de concurrencia del LLM (no agotar el threadpool) ───────────
def test_responder_rechaza_sin_cupo(db, monkeypatch):
    """Si el semáforo ya está agotado, responder rechaza de inmediato (429)
    sin llegar a llamar al LLM."""
    import threading
    sem = threading.BoundedSemaphore(1)
    sem.acquire()                                  # ocupa el único slot
    monkeypatch.setattr(svc, "_llm_sem", sem)
    # el LLM no debería llegar a llamarse
    monkeypatch.setattr(svc, "_invocar_llm",
                        lambda p: pytest.fail("no debió llamar al LLM sin cupo"))
    with pytest.raises(svc.RAGOcupado):
        svc.responder("¿cuántas OF hay?", db)
    sem.release()


def test_responder_libera_cupo_tras_exito(db, monkeypatch):
    """Un request exitoso devuelve el slot: el siguiente puede adquirirlo."""
    import threading
    sem = threading.BoundedSemaphore(1)
    monkeypatch.setattr(svc, "_llm_sem", sem)
    monkeypatch.setattr(svc, "_invocar_llm",
                        _fake_llm("SELECT COUNT(*) AS n FROM ordenes_fabricacion"))
    svc.responder("¿cuántas OF hay?", db)
    # el slot volvió a estar libre
    assert sem.acquire(blocking=False)
    sem.release()


def test_responder_libera_cupo_tras_error(db, monkeypatch):
    """Aunque el SQL sea bloqueado, el slot se libera (no queda tomado)."""
    import threading
    from app.services.rag_guard import SQLNoPermitido
    sem = threading.BoundedSemaphore(1)
    monkeypatch.setattr(svc, "_llm_sem", sem)
    monkeypatch.setattr(svc, "_invocar_llm", _fake_llm("DELETE FROM ordenes_fabricacion"))
    with pytest.raises(SQLNoPermitido):
        svc.responder("borra todo", db)
    assert sem.acquire(blocking=False)             # se liberó pese al error
    sem.release()


# ── Provider switch: Gemini / Ollama (R4.1) ──────────────────────────────────
def test_dispatch_usa_ollama(monkeypatch):
    monkeypatch.setattr(svc.settings, "RAG_LLM_PROVIDER", "ollama", raising=False)
    monkeypatch.setattr(svc, "_invocar_ollama", lambda p: "SQL_OLLAMA")
    monkeypatch.setattr(svc, "_invocar_gemini", lambda p: "SQL_GEMINI")
    assert svc._invocar_llm("x") == "SQL_OLLAMA"


def test_dispatch_usa_gemini_por_defecto(monkeypatch):
    monkeypatch.setattr(svc.settings, "RAG_LLM_PROVIDER", "gemini", raising=False)
    monkeypatch.setattr(svc, "_invocar_ollama", lambda p: "SQL_OLLAMA")
    monkeypatch.setattr(svc, "_invocar_gemini", lambda p: "SQL_GEMINI")
    assert svc._invocar_llm("x") == "SQL_GEMINI"


def test_invocar_ollama_arma_request(monkeypatch):
    capturado = {}

    class _Resp:
        def raise_for_status(self): pass
        def json(self): return {"response": "SELECT 1"}

    def fake_post(url, **kw):
        capturado["url"] = url
        capturado["json"] = kw.get("json")
        return _Resp()

    import httpx
    monkeypatch.setattr(httpx, "post", fake_post)
    monkeypatch.setattr(svc.settings, "RAG_OLLAMA_URL", "http://localhost:11434", raising=False)
    monkeypatch.setattr(svc.settings, "RAG_OLLAMA_MODEL", "qwen2.5-coder:7b", raising=False)

    out = svc._invocar_ollama("dame el sql")
    assert out == "SELECT 1"
    assert capturado["url"].endswith("/api/generate")
    assert capturado["json"]["model"] == "qwen2.5-coder:7b"
    assert capturado["json"]["stream"] is False
