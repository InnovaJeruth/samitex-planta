# Configuración — Samitex Planta

Todos los ajustes viven en `app/config.py` (`Settings`, pydantic-settings), se
leen del archivo `.env` (o de variables de entorno del sistema) y son
**case-sensitive** (MAYÚSCULAS). En producción, inyectar los secretos como
variables de entorno del servicio en vez de dejarlos en `.env` en disco.

Plantilla de referencia: `.env.example`.

## Aplicación

| Variable | Default | Propósito |
|---|---|---|
| `APP_NAME` | `Samitex Planta` | Nombre de la app. |
| `APP_ENV` | `development` | `development` \| `production`. En producción oculta docs/redoc/openapi y activa cookies `secure`. |
| `DEBUG` | `False` | Modo debug / echo SQL. |
| `SECRET_KEY` | *(requerido)* | Clave de firma de cookies/CSRF. |
| `ALLOWED_HOSTS` | `*` | CSV de hosts permitidos (cabecera Host). En producción, hosts reales. |
| `TRUST_PROXY` | `False` | Confiar en `X-Forwarded-For` (solo si hay reverse proxy delante). |

## Base de datos (SQL Server)

| Variable | Default | Propósito |
|---|---|---|
| `DB_SERVER` | *(requerido)* | Servidor/instancia SQL Server. |
| `DB_NAME` | *(requerido)* | Nombre de la base de datos. |
| `DB_DRIVER` | `ODBC Driver 17 for SQL Server` | Driver ODBC. |
| `DB_TRUSTED_CONNECTION` | `True` | Autenticación integrada de Windows. |
| `DB_USER` / `DB_PASSWORD` | `""` | Usuario/clave (si no es trusted). |

`DATABASE_URL` se arma automáticamente (`mssql+pyodbc://…`).

## Autenticación (JWT)

| Variable | Default | Propósito |
|---|---|---|
| `JWT_SECRET_KEY` | *(requerido)* | Clave de firma del JWT. |
| `JWT_ALGORITHM` | `HS256` | Algoritmo. |
| `JWT_EXPIRE_MINUTES` | `240` | Expiración del token (4 h). |

## Archivos / uploads

| Variable | Default | Propósito |
|---|---|---|
| `UPLOAD_DIR` | `uploads` | Carpeta de subidas. |
| `MAX_UPLOAD_MB` | `20` | Tamaño máximo de subida (MB). |

## Concurrencia (estabilidad)

| Variable | Default | Propósito |
|---|---|---|
| `HEAVY_MAX_CONCURRENCIA` | `2` | Máx. tareas CPU-bound en paralelo (PDF, import Excel, process mining). Exceso → 429. |
| `RAG_MAX_CONCURRENCIA` | `3` | Máx. consultas del Chat al LLM en vuelo. Exceso → 429. |

> Son **por worker**: con N workers, el total permitido es N × valor.

## Chat analítico (RAG Text-to-SQL)

| Variable | Default | Propósito |
|---|---|---|
| `RAG_ENABLED` | `False` | Activa el chat analítico. |
| `RAG_DB_URL` | `""` | Conexión de **solo lectura** (login `db_datareader`); si vacía, cae a `DATABASE_URL`. |
| `RAG_LLM_PROVIDER` | `gemini` | `gemini` (nube) \| `ollama` (local). |
| `RAG_MODEL` | `gemini-2.0-flash` | Modelo Gemini. |
| `RAG_OLLAMA_URL` | `http://localhost:11434` | Endpoint de Ollama. |
| `RAG_OLLAMA_MODEL` | `qwen2.5-coder:7b` | Modelo local. |
| `RAG_MAX_ROWS` | `200` | Tope de filas por consulta (`SELECT TOP N`). |
| `RAG_QUERY_TIMEOUT` | `20` | Segundos máx. por consulta SQL. |
| `RAG_LLM_TIMEOUT` | `30` | Segundos máx. por llamada al LLM (subir a 90–180 con Ollama en frío). |
| `RAG_INCLUIR_RESUMEN` | `True` | Segunda llamada al LLM para redactar la respuesta en lenguaje natural. |

## Integraciones (opcionales / heredadas)

| Variable | Default | Propósito |
|---|---|---|
| `GEMINI_API_KEY` | `""` | API key de Gemini (usada por RAG en modo nube). |
| `TELEGRAM_TOKEN` / `TELEGRAM_ALLOWED_IDS` / `NGROK_URL` / `BOT_SECRET_KEY` | `""` | Legado del bot de Telegram (**módulo retirado**; inertes). |

## Constantes de dominio (`app/constants.py`)

No son configurables por `.env`, pero conviene conocerlas:

- `MAX_CAPAS_DEFAULT = 80` — tope de capas por placa si la OF no lo define.
- `UNIDADES_POR_PAQUETE_DEFAULT = 49` — tamaño de bulto por defecto.
- `ORDEN_FASES`, `NOMBRES_FASE`, `FASES_GANTT` — fases del proceso.
- `CLASES_ORDEN_SAP` (ZP41–ZP44) — mapeo para el import SAP.
