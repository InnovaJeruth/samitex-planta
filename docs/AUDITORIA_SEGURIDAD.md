# Auditoría de Seguridad — SAMITEX-PLANTA (FastAPI ERP)

_White-box / análisis estático de código. Enfoque OWASP Top 10 (A01 Broken Access
Control, A03 Injection, A05 Security Misconfiguration, A07 Auth Failures)._
_Todos los cambios son aditivos, cubiertos por tests (296 passed) y reversibles._

---

## 1. Alcance

Routers y núcleo auditados: `core/auth.py`, `core/csrf.py`, `config.py`, `main.py`,
`of.py`, `paquetes.py`, `hoja_costos.py`, `catalogo.py`, `admin.py`, `telegram_bot.py`,
`comercial.py`, `requerimientos.py`, `supervisor.py`, `curvas.py`, `plantas.py`,
`trazos.py`, `rag_chat.py`, `process_mining.py`.

---

## 2. Hallazgos y estado

| # | Severidad | Módulo | Vulnerabilidad | Estado |
|---|-----------|--------|----------------|--------|
| 1 | Alta | `of.py` | Broken Function-Level Authorization: 8 endpoints mutantes sin chequeo de rol (crear/activar/planificar OF, piezas, plantilla, documentos, ficha, códigos) | **Corregido** (gate `ROLES_PLANEAMIENTO`) |
| 2 | Alta | `auth.py` | Bypass de rate-limit por spoofing de `X-Forwarded-For` | **Corregido** (`TRUST_PROXY`) |
| 3 | Media | `telegram_bot.py` | Webhook público sin verificación de origen (abuso de costo/DoS, spoofing) | **Mitigado** (router desactivado; pendiente borrado) |
| 4 | Baja | `catalogo.py` | Upload sin límite de tamaño ni validación de contenido (DoS / content-spoofing) | **Corregido** (`MAX_UPLOAD_MB` + magic bytes) |
| 5 | Baja | `auth.py` | Enumeración de usuarios por canal lateral de tiempo | **Corregido** (hash señuelo) |
| 6 | Baja | `main.py` | Comparación de token CSRF no constante en tiempo | **Corregido** (`hmac.compare_digest`) |
| 7 | Baja | `config`/`.env` | JWT de vida larga (8 h) | **Corregido** (4 h) |
| 8 | Baja | `admin.py` | Política de contraseñas ausente | **Corregido** (mín. 8, letras+números) |

**Inyección SQL:** sin hallazgos en todo el código. Uso consistente del ORM con
consultas parametrizadas; el único `text()` crudo (chat analítico) está blindado
por whitelist + guardas (`rag_guard`), y el healthcheck de `supervisor` es estático.

---

## 3. Detalle de correcciones

- **RBAC `of.py`:** helper `_require(user, roles, accion)`; gate `ROLES_PLANEAMIENTO`
  (ADMIN, PLANEADOR) en crear, activar, planificar, agregar/plantilla de piezas,
  usar ficha catálogo, actualizar códigos y subir documentos. `editar-piezas` ya lo tenía.
- **Rate-limit:** `settings.TRUST_PROXY` (default False); `_get_ip` usa la IP real del
  socket salvo que haya proxy confiable declarado.
- **Enumeración:** `_DUMMY_HASH` — se ejecuta bcrypt exista o no el usuario (tiempo constante).
- **CSRF:** `hmac.compare_digest` en el middleware.
- **JWT:** `JWT_EXPIRE_MINUTES = 240` (4 h) en config y `.env`.
- **Upload catálogo:** límite `MAX_UPLOAD_MB` (413) + `_magic_doc_ok` (firma vs extensión).
- **Contraseñas:** `field_validator` en `UsuarioCreate` y `CambiarPasswordBody` (8+ con letras y números).
- **Telegram:** `include_router` comentado en `main.py` → webhook fuera de servicio.

---

## 4. Matriz RBAC (endpoints mutantes por router — verificado)

| Router | Cobertura de rol en endpoints mutantes |
|--------|----------------------------------------|
| `of.py` | ✔ (corregido) — `ROLES_PLANEAMIENTO` / `ROLES_IMPORT_OF` / `ROLES_PRUEBA` |
| `paquetes.py` | ✔ granular (`ROLES_FUSIONADO/CALIDAD/NUMERAR/REPROCESO/GERENCIA/DAR_OK/…`) |
| `hoja_costos.py` | ✔ `ROLES_EDITOR_HDC` / `ROLES_APROBAR_HDC` / `ROLES_TC` |
| `catalogo.py` | ✔ `ROLES_EDITOR_CATALOGO` |
| `admin.py` | ✔ `require_roles(RolEnum.ADMIN)` |
| `comercial.py` | ✔ `ROLES_CREAR` |
| `requerimientos.py` | ✔ `ROLES_REQ_EDITAR` |
| `supervisor.py` | ✔ `ROLES_PROGRAMAR` |
| `curvas.py` | ✔ `ROLES_EDITOR_CURVAS` |
| `plantas.py` | ✔ `ROLES_PLANTAS` |
| `trazos.py` | ✔ `ROLES_TRAZO` |
| `rag_chat.py` | ✔ `ROLES_ANALITICA` |
| `process_mining.py` | ✔ solo lectura, `ROLES_ANALITICA` |

Modelo de autorización: **por rol** (no por propietario). Correcto para una planta;
no aplica control de propiedad por usuario (IDOR) en las acciones operativas.

---

## 5. Buenas prácticas confirmadas

- JWT con algoritmo fijado (sin *algorithm confusion*), firma validada, rol releído
  de BD (no del token) → sin escalada vertical vía claim; revocación por `jti`.
- Contraseñas con bcrypt (rounds=12).
- Cookies `HttpOnly`, `SameSite=Lax`, `Secure` en producción.
- CSRF double-submit firmado con HMAC; cabeceras `nosniff`, `X-Frame-Options`, `Referrer-Policy`.
- Sin CORS permisivo; Swagger deshabilitado en producción.
- Uploads de imagen re-codificados con Pillow (neutraliza payloads); nombres `uuid` (sin path traversal).

---

## 6. Pendientes / recomendaciones (no bloqueantes)

- **Infra:** con múltiples workers de uvicorn, mover el contador de rate-limit a un
  store compartido (Redis) o correr con `--workers 1`; hoy el límite es por proceso.
- **Producción:** activar `TRUST_PROXY=True` solo si hay reverse proxy confiable; asegurar `APP_ENV=production` (cookies Secure + docs off).
- **Telegram:** borrado completo del módulo (router, `TELEGRAM_*` en config/.env, exención CSRF `/telegram/*`).
- **JWT (opcional):** refresh token rotatorio si se requieren sesiones largas.
- **Secretos:** rotación periódica de `SECRET_KEY`/`JWT_SECRET_KEY`; `.env` fuera de git (ya confirmado).

---

## 7. Tests de seguridad añadidos

`tests/test_seguridad_auth.py` (rate-limit XFF, hash señuelo, RBAC `_require`),
`tests/test_seguridad_upload_catalogo.py` (magic bytes), `tests/test_seguridad_password.py`
(política de contraseña). Suite completa: **296 passed**.
