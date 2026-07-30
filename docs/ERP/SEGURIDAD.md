# Seguridad — Samitex Planta

Resumen de los controles de seguridad del ERP: autenticación, autorización por
roles, protección CSRF, límites de abuso, seguridad del Chat analítico (RAG) y
endurecimiento para producción.

## 1. Autenticación (JWT)

- **Login** (`POST /auth/login`): valida credenciales con **bcrypt** (coste 12).
  Emite un **JWT** firmado (`JWT_SECRET_KEY`, HS256) con `sub=username`, `rol`,
  `exp` y un `jti` único.
- **Transporte del token:** cookie **HttpOnly** `samitex_token` (`samesite=lax`,
  `secure` solo en producción); como fallback se acepta `Authorization: Bearer`.
- **Expiración:** `JWT_EXPIRE_MINUTES` (default **240 min = 4 h**). La cookie usa
  el mismo `max_age`.
- **Revocación (logout):** el `jti` del token se guarda en `tokens_revocados`;
  cada request rechaza tokens revocados. Se limpian los expirados.
- **Anti-enumeración de usuarios:** el login siempre computa un hash (real o
  señuelo `_DUMMY_HASH`) para mantener tiempo de respuesta constante, y devuelve
  un error genérico ("Usuario o contraseña incorrectos").

## 2. Autorización por roles

15 roles (`RolEnum`): `ADMIN`, `GERENTE_PLANTA`, `JEFE_PLANTA`, `GERENCIA`,
`PLANEADOR`, `SUPERVISOR_CORTE`, `SOLO_LECTURA`, `UDP`, `COMERCIAL`,
`COMERCIAL_MARCA`, `PLANEAMIENTO_MARCA`, `INGENIERIA`, `LOGISTICA`, `CALIDAD`.

Los permisos se centralizan en **`app/roles.py`** como conjuntos `ROLES_*`
(fuente única). Cada router importa los conjuntos que necesita y verifica
`rol_de(user) in ROLES_X`, o usa `require_roles(...)`. Se exponen flags `puede_*`
a las plantillas para ocultar/mostrar controles.

Conjuntos principales (resumen):

| Conjunto | Para qué | Roles |
|---|---|---|
| `ROLES_PLANEAMIENTO` | Mutar OF (crear, activar, planificar, piezas) | ADMIN, PLANEADOR |
| `ROLES_CORTE` / `ROLES_NUMERAR` / `ROLES_TRAZO` | Avance de corte / numerar / placas | ADMIN, PLANEADOR, SUPERVISOR_CORTE |
| `ROLES_CALIDAD` | Bandeja de Calidad | ADMIN, PLANEADOR, SUPERVISOR_CORTE, CALIDAD |
| `ROLES_REPROCESO` / `ROLES_FUSIONADO` | Reprocesos / fusionado | ADMIN, SUPERVISOR_CORTE, (CORTE/FUSIONADO) |
| `ROLES_GERENCIA` | Aprobación de gerencia | ADMIN, GERENTE_PLANTA |
| `ROLES_IMPORT_OF` / `ROLES_PRUEBA` | Importar SAP / OF de prueba | ADMIN, PLANEADOR |
| `ROLES_COMERCIAL` / `ROLES_REQ_EDITAR` | Comercial / requerimientos | Comercial(es), Planeamiento, Gerencia, ADMIN |
| `ROLES_EDITOR_CATALOGO` | Editar catálogo | ADMIN, UDP, COMERCIAL_MARCA |
| `ROLES_EDITOR_HDC` / `ROLES_APROBAR_HDC` / `ROLES_TC` | Hoja de costos / aprobar / tipo de cambio | ADMIN, UDP, INGENIERIA / ADMIN, INGENIERIA / ADMIN, LOGISTICA |
| `ROLES_ANALITICA` | Process Mining + Chat RAG (solo lectura) | ADMIN, gerencias, PLANEADOR |

> El módulo de **Administración** (`/admin/*`) exige `ADMIN` con `require_roles`.
> El detalle completo de conjuntos está en [API_ENDPOINTS.md](API_ENDPOINTS.md).

## 3. Protección CSRF

Middleware propio (`CSRFMiddleware`): patrón de **doble cookie firmada**. En
métodos mutantes (POST/PUT/PATCH/DELETE) compara el header `x-csrf-token` con el
token firmado en cookie usando `hmac.compare_digest`. Rutas exentas: métodos
seguros (GET/HEAD/OPTIONS), `/auth/login`, `/health` y `/ws/*`. Además añade
cabeceras: `X-Content-Type-Options: nosniff`, `X-Frame-Options: SAMEORIGIN`,
`Referrer-Policy: strict-origin-when-cross-origin`.

## 4. Rate-limit de login

Ventana deslizante **en memoria** por IP: 5 intentos fallidos por 5 minutos →
**429**. La IP se resuelve del socket real, y solo se confía en
`X-Forwarded-For` si `TRUST_PROXY=true` (evita spoofing del header para saltar el
límite). *Nota: el contador vive en memoria del proceso; con varios workers habría
que compartirlo (Redis).*

## 5. Seguridad del Chat analítico (RAG Text-to-SQL)

El SQL generado por el LLM **no se confía**. Defensa en tres capas:

1. **Whitelist de tablas/vistas** — solo se permiten tablas de negocio y vistas
   seguras. Para datos de usuario se usa `vw_usuarios` (sin contraseñas), no la
   tabla `usuarios`.
2. **`rag_guard`** — rechaza: comentarios, múltiples sentencias, cualquier
   DML/DDL/EXEC/INTO, procedimientos `sp_`/`xp_`, **columnas sensibles**
   (`password`, `password_hash`, `token`, `secret`, `api_key`, …), **`SELECT *`**,
   y tablas fuera del whitelist. Inyecta `TOP N` y ejecuta.
3. **Ejecución de solo lectura** — engine de BD **independiente** (idealmente un
   login `db_datareader` sin permisos de escritura, con `DENY SELECT` sobre
   `usuarios`), y `rollback` siempre. El acceso se limita a `ROLES_ANALITICA`.

Además la concurrencia del chat está acotada (`RAG_MAX_CONCURRENCIA`) para no
saturar el servidor; el exceso responde 429.

## 6. Documentación de la API

En **producción** (`APP_ENV=production`) se ocultan `/docs`, `/redoc` y
`/openapi.json` (no se expone el mapa de endpoints). En desarrollo están
disponibles bajo `/api/...`.

## 7. Gestión de secretos

- `.env` está en `.gitignore` y **no se versiona** (solo `.env.example`). No hay
  credenciales hardcodeadas en el código ni en `alembic.ini`.
- **En producción**, los secretos (`SECRET_KEY`, `JWT_SECRET_KEY`, credenciales
  de BD, `GEMINI_API_KEY`) deben inyectarse como **variables de entorno del
  servicio**, no en un `.env` en texto plano en disco.

## 8. Endurecimiento de red

- **`TrustedHostMiddleware`** valida la cabecera `Host` contra `ALLOWED_HOSTS`
  (anti Host header injection). Default `*`; en producción, listar hosts reales.
- **TLS/HTTPS** se termina en un **reverse proxy** (IIS/nginx) delante de uvicorn;
  con proxy, activar `TRUST_PROXY=true` para leer bien la IP real. Las cookies se
  marcan `secure` cuando `APP_ENV=production`.

## 9. Subida y descarga de archivos

- Validación de tipo/tamaño y **firma mágica** en subidas de catálogo.
- Descargas con guardia **anti path-traversal** (la ruta debe quedar dentro de
  `UPLOAD_DIR`).

## 10. Checklist de producción (seguridad)

- [ ] `APP_ENV=production` (oculta docs/openapi, cookies `secure`).
- [ ] `ALLOWED_HOSTS` con los hosts reales.
- [ ] `SECRET_KEY` / `JWT_SECRET_KEY` fuertes e inyectados por entorno.
- [ ] `RAG_DB_URL` apuntando al login de solo lectura (`rag_readonly`).
- [ ] Reverse proxy con TLS + `TRUST_PROXY=true`.
- [ ] Contraseñas de cuentas sensibles (`admin`, `gerencia`) rotadas.
