# Despliegue y concurrencia — Samitex Planta

Guía para dimensionar la app en producción. No hay cambios de código aquí:
resume cómo funciona la concurrencia del sistema y cómo configurarla.

## 1. Modelo de concurrencia (cómo corre hoy)

- **Driver de BD:** `mssql+pyodbc` — **síncrono/bloqueante**.
- **Endpoints:** todos los de negocio son `def` (sync). FastAPI los ejecuta en
  un **threadpool** (no en el event loop), así que el I/O de BD nunca congela
  el loop. Este es el patrón correcto para un driver bloqueante.
- **Código async** (middleware CSRF, WebSockets, handlers de error): no hace
  I/O bloqueante. El event loop queda libre para aceptar conexiones.
- **Threadpool de FastAPI:** por defecto **40 hilos** (límite de AnyIO). Es el
  número real de peticiones sync que un worker puede atender *a la vez*.
- **Pool de BD:** `pool_size=20` + `max_overflow=30` = **50 conexiones** máx.
  Es mayor que los 40 hilos a propósito: ningún request se queda esperando una
  conexión bajo carga máxima.

Regla mental: **concurrencia real ≈ (nº de workers) × 40 hilos**, acotada por
las 50 conexiones de BD por proceso.

## 2. Workers (uvicorn / gunicorn)

Un solo proceso = techo de ~40 requests sync concurrentes.

### Arranque recomendado — empezar con 1 worker

Arrancar con **1 worker** primero: el comportamiento es idéntico al de hoy y no
rompe el estado en memoria (suscriptores WebSocket, contador de rate-limit de
login, semáforos), que son **por proceso**. Escalar a N workers recién cuando
ese estado esté compartido (ver "Escalar a varios workers").

- **Windows (host actual):** Gunicorn NO corre en Windows. Usar uvicorn directo:

  ```
  uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1 --ws-ping-interval 20
  ```

  Para que reinicie solo y arranque con el servidor, envolver en un servicio de
  Windows (p. ej. NSSM) o tarea programada. **NUNCA** usar `--reload`.

- **Linux / contenedor (recomendado a futuro):** Gunicorn como gestor de
  procesos con UvicornWorker:

  ```
  gunicorn app.main:app -k uvicorn.workers.UvicornWorker \
      --workers 1 --bind 0.0.0.0:8000 --timeout 120
  ```

### Escalar a varios workers

- Punto de partida CPU-bound-ish: **workers = nº de núcleos** (o `2×núcleos` si
  el trabajo es mayormente I/O de BD y esperas).
- Requisito ANTES de subir de 1 worker: compartir el estado en memoria (WebSocket
  y rate-limit) vía Redis; si no, las notificaciones en vivo y los límites se
  comportan mal entre procesos.
- Cada worker tiene su **propio** threadpool (40) y su **propio** pool de BD
  (50). Con 4 workers → hasta 200 conexiones a SQL Server. **Verifica el límite
  de conexiones del servidor SQL** y ajusta `pool_size`/`max_overflow` o el nº
  de workers para no agotarlo.
- **NUNCA** dejar `--reload` en producción (es solo para desarrollo).

## 3. Ajuste del threadpool (opcional)

Si midiendo ves que 40 hilos por worker se quedan cortos (muchos requests
lentos de BD en paralelo), se puede subir el límite de AnyIO al arrancar. No
lo cambies sin medir: más hilos = más contención por el GIL y más conexiones
de BD en uso.

## 4. Topes de tareas pesadas (ya implementados)

Dos semáforos evitan que trabajo pesado sature el threadpool/CPU. Se
configuran por `.env` y son **por worker**:

| Variable | Default | Qué limita |
|---|---|---|
| `RAG_MAX_CONCURRENCIA` | 3 | Consultas del Chat analítico al LLM en vuelo. Exceso → 429. |
| `HEAVY_MAX_CONCURRENCIA` | 2 | Tareas CPU-bound (PDF, import Excel SAP, DFG/animación de process mining). Exceso → 429. |

Como son por worker, con N workers el total permitido es `N × valor`. Ajusta a
la baja si el servidor tiene pocos núcleos.

Relacionado: `RAG_LLM_TIMEOUT` (segundos máx. por llamada al LLM). Con Ollama
local en frío conviene 90–180 s; con Gemini nube, 30–60 s basta.

## 4b. Keepalive de WebSocket

El keepalive de las conexiones WebSocket se maneja a **nivel de servidor**
(uvicorn), no en la app. Uvicorn envía ping/pong de protocolo automáticamente;
se controla con:

```
uvicorn app.main:app --ws-ping-interval 20 --ws-ping-timeout 20 ...
```

Esto evita que proxies/balanceadores cierren conexiones ociosas y que queden
sockets "zombi". Por eso NO hay heartbeat a nivel de aplicación (sería
redundante). Se eliminó la antigua config `WS_HEARTBEAT_SECONDS` (no se usaba).
Si tu proxy (nginx/IIS) tiene un timeout de inactividad, deja el
`--ws-ping-interval` por debajo de ese valor.

## 4c. Endurecimiento de borde y secretos

- **Host header:** la app valida la cabecera `Host` con `TrustedHostMiddleware`
  contra `ALLOWED_HOSTS` (CSV en `.env`). En producción, listar los hosts reales
  (`ALLOWED_HOSTS=erp.samitex.local,10.0.0.5`); el default `*` no bloquea nada
  y sirve para desarrollo. Evita ataques de Host header injection.
- **TLS / HTTPS:** la app NO termina TLS; va detrás de un **reverse proxy**
  (IIS en Windows, o nginx) que sirve HTTPS y reenvía a uvicorn en localhost.
  Con el proxy delante, poner `TRUST_PROXY=true` para que el rate-limit lea bien
  la IP real (`X-Forwarded-For`). Las cookies ya se marcan `secure` cuando
  `APP_ENV=production` (requiere HTTPS).
- **Secretos:** en producción, inyectar `SECRET_KEY`, `JWT_SECRET_KEY`,
  credenciales de BD y `GEMINI_API_KEY` como **variables de entorno del
  servicio/orquestador**, no en un `.env` en texto plano en disco. Pydantic las
  lee igual. El `.env` queda solo para desarrollo.

## 5. Checklist de producción

- [ ] `APP_ENV=production` en el `.env` → deshabilita `/docs`, `/redoc` y
  `/openapi.json` (no exponer el mapa de endpoints).
- [ ] Varios workers (no 1), sin `--reload`.
- [ ] `RAG_DB_URL` apuntando al login de **solo lectura** (`rag_readonly`), no
  a la cuenta de la app.
- [ ] Revisar el límite de conexiones de SQL Server vs (workers × 50).
- [ ] `SECRET_KEY` / `JWT_SECRET_KEY` fuertes y fuera del repo.
- [ ] Cookies seguras: en producción el middleware ya marca `secure=True`
  (requiere HTTPS).
- [ ] Contraseñas de cuentas sensibles (`admin`, `gerencia`) rotadas.

## 6. Pendientes conocidos (no bloqueantes)

- **CPU-bound real:** los topes del punto 4 evitan la saturación, pero no dan
  paralelismo real (el GIL sigue). Si el import de Excel crece mucho, evaluar
  moverlo a un `ProcessPoolExecutor` o a una cola de trabajos (fuera de alcance
  hasta medir que molesta).
