# Motor Text-to-SQL (RAG tabular) — Análisis de arquitectura

_Como Arquitecto de Software, sobre el código actual de `samitex-planta`. Solo
análisis y diseño; no se programa hasta aprobar._

Objetivo: que Planeamiento/Gerencia hagan preguntas de negocio en lenguaje natural
("¿qué OFs están atrasadas?", "¿cuántas prendas se rechazaron esta semana y por qué?")
y el sistema genere y ejecute SQL **de solo lectura** contra SQL Server, usando un LLM
vía API Key.

Punto de partida real del stack: FastAPI 0.110, SQLAlchemy 2.0.36 (`DeclarativeBase`),
`mssql+pyodbc` con Windows Auth, `get_db()` como dependencia, auth JWT + roles en
`app/roles.py` (ya existe `ROLES_ANALITICA`), CSRF middleware activo. Python 3.10.

---

## 1. Análisis — tablas relevantes para preguntas de negocio y trazabilidad

De las 56 tablas del sistema, **NO** se deben exponer todas al LLM (ruido, tokens,
riesgo). Se propone un **whitelist curado** por dominio, que es lo que responde el
90% de las preguntas analíticas:

**Núcleo de la OF (trazabilidad y estado)**
- `ordenes_fabricacion` — la tabla central: estado, total_juegos, cliente, tipo_cliente, clase_orden, fechas (creación/SAP/APT), prenda_catalogo_id, omitir_gates.
- `of_talla_distribucion` — cantidades por SKU/talla dentro de la OF.
- `of_piezas` — piezas de cada OF.

**Corte y tela (F1–F3)**
- `of_trazos`, `of_trazo_tallas` — placas/tizado, capas, prendas por placa.
- `of_fase_tiempos` — inicio/fin real por fase (tiempos, cuellos).
- `of_fases_estado` — estado por pieza×talla×fase.
- `of_fase_paradas` — paradas (para OEE/tiempo perdido).

**Numeración, fusionado, calidad, reprocesos (F4–F7)**
- `of_paquetes` — bultos (estado, cantidad, fusionado_inicio/fin).
- `of_paquete_eventos` — transiciones de estado con timestamp y usuario (traza fina).
- `of_paquete_rechazos` + `motivos_rechazo` — rechazos de calidad y su causa.
- `of_reproceso_hitos` — hitos del reproceso.

**Catálogo y comercial**
- `prendas_catalogo`, `prenda_skus` — prenda/variantes/tallas.
- `requerimientos`, `requerimiento_lineas`, `requerimiento_linea_tallas` — demanda comercial (Fase 1).

**Costos (opcional, 2ª ola)**
- `hojas_costos`, `hojas_costos_lineas`, `catalogo_servicios`, `catalogo_mod`, `precios_historicos`.

**Logística / tercerización (opcional, 2ª ola)**
- `terc_recepciones`, `terc_subproceso_log`, `terc_historial_fechas`, `plantas_externas`.

**Soporte de identidad**
- `usuarios` — para "¿quién hizo X?" (unir por `usuario_id` en eventos/hitos).

**Se excluyen del whitelist** (ruido o sensibles): `tokens_revocados`,
`auditoria_documento_of`, la mayoría de `ing_*` (registros de ingeniería finos),
`parametros_sistema`, tablas de configuración de avíos/MP. Se pueden sumar después.

> Recomendación de arranque: **Ola 1 = núcleo OF + F1–F7 + catálogo** (≈15 tablas).
> Cubre estado, avance, tiempos, calidad y trazabilidad, que es lo que pide Planeamiento.

**Capa semántica (clave para que el LLM acierte).** El esquema crudo no basta: hay
que darle al modelo un glosario del negocio como contexto, porque los estados y fases
son códigos. Ej.: `estado` de OF (BORRADOR/ACTIVA/EN_PROCESO/COMPLETADA), fases
F1 Tizado · F2 Tendido · F3 Corte · F4 Numerado · F5 Fusionado · F6 Costura · F7 Liberado,
estados de bulto (HABILITADO→FUSIONADO→POR_VALIDAR→ENTREGADO/STAND_BY), y qué significa
"atrasada" (APT < hoy y estado ≠ COMPLETADA). Esto vive en el servicio como few-shot + diccionario.

---

## 2. Integración — diseño de `services/rag_service.py`

**Principio rector: la seguridad NO se delega al LLM.** El modelo solo *propone* SQL;
la garantía de solo-lectura se impone en la capa de ejecución, con varias barreras.

### 2.1 Framework: recomendación
- **Recomendado: LangChain** con `langchain_community.utilities.SQLDatabase` +
  `create_sql_query_chain`. Motivo: `SQLDatabase.from_uri(..., include_tables=[whitelist])`
  reutiliza tu misma cadena `mssql+pyodbc` y refleja el esquema automáticamente; y
  `create_sql_query_chain` **solo genera** el SQL (no lo autoejecuta), que es justo lo
  que queremos para meter nuestras barreras antes de correrlo.
- **Evitar** el "SQL Agent" completo de LangChain que ejecuta solo y encadena pasos:
  más difícil de auditar y de blindar en modo lectura.
- **Alternativa mínima (sin framework):** llamar al SDK del LLM directamente pasándole
  el esquema del whitelist como texto. Menos dependencias, más control, pero reimplementas
  el reflejo de esquema. Viable si quieres mantener el stack ultra-liviano.

### 2.2 Extracción de esquema desde tus modelos actuales
- Reutilizar `Base.metadata` (ya lo tienes en `app/database/connection.py`) filtrado al
  whitelist, o `SQLDatabase.from_uri(settings.DATABASE_URL, include_tables=WHITELIST, sample_rows_in_table_info=3)`.
- Añadir descripciones de columnas y el glosario de la capa semántica al `table_info`.

### 2.3 Ejecución segura — modo lectura estricto (varias capas)
1. **Conexión de solo lectura dedicada (la barrera más fuerte).** Crear un **login SQL
   Server independiente con solo `db_datareader`** y un **segundo engine** para el RAG
   (`RAG_DATABASE_URL`), separado del engine transaccional. Aunque el LLM alucinara un
   DELETE, la BD lo rechaza. (Hoy usas Windows Auth con permisos plenos → NO usar esa
   conexión para el RAG.)
2. **Guardia sintáctica con `sqlparse`.** Antes de ejecutar: exigir **una sola sentencia**,
   que sea **SELECT** (o WITH…SELECT), y **rechazar** por lista negra INSERT/UPDATE/DELETE/
   MERGE/DROP/ALTER/TRUNCATE/EXEC/GRANT/`;` múltiple/comentarios sospechosos.
3. **Whitelist de tablas en tiempo de ejecución.** Verificar que todas las tablas
   referidas por el SQL están en el whitelist (defensa contra fuga a `usuarios`/tokens si no se listaron).
4. **Tope de filas y timeout.** Forzar `SELECT TOP N` (SQL Server) si no lo trae, y fijar
   timeout de consulta (`SET LOCK_TIMEOUT` / timeout del engine). Evita escaneos gigantes.
5. **Transacción de solo lectura** y rollback siempre al final.
6. **Auditoría.** Loguear pregunta + SQL generado + usuario + filas devueltas (para revisar y mejorar prompts).

### 2.4 Forma del servicio (contrato, sin código)
- `responder(pregunta: str, db_ro) -> {sql, columnas, filas, resumen}`:
  1. arma contexto (esquema whitelist + glosario + few-shots),
  2. pide SQL al LLM,
  3. pasa las 6 barreras,
  4. ejecuta en la conexión read-only,
  5. (opcional) segunda llamada al LLM para redactar la respuesta en lenguaje natural a partir de las filas.
- LLM: reutilizar el patrón de API Key que ya tienes (`GEMINI_API_KEY` en `settings`)
  o añadir `OPENAI_API_KEY`. Config nuevo: `RAG_LLM_PROVIDER`, `RAG_MODEL`, `RAG_MAX_ROWS`, `RAG_DATABASE_URL`.

---

## 3. Endpoint — `POST /api/chat` respetando tu DI y sesión

- **Nuevo router** `app/routers/rag_chat.py`, registrado en `main.py` con
  `app.include_router(rag_chat.router, prefix="/api", tags=["Chat analítico"])` → ruta final `POST /api/chat`.
- **Inyección de dependencias, igual que el resto del proyecto:**
  - `current_user: Usuario = Depends(get_current_user)` + chequeo de rol reutilizando
    **`ROLES_ANALITICA`** (ADMIN, GERENTE_PLANTA, JEFE_PLANTA, GERENCIA, PLANEADOR) — la
    misma que ya usa Process Mining. Coherente y sin inventar roles.
  - **NO** usar `get_db()` (engine con permisos de escritura) para ejecutar el SQL del
    LLM. Añadir una dependencia nueva **`get_db_ro()`** que use el engine read-only. El
    `get_db()` normal solo si necesitas leer metadatos propios.
- **Esquema** (Pydantic): `ChatIn { pregunta: str, incluir_sql: bool = False }` →
  `ChatOut { respuesta: str, sql: str | None, columnas: list, filas: list }`.
- **CSRF:** `/api/chat` **no** está en `CSRF_EXEMPT_*`, así que pasa por el middleware
  actual; el front debe mandar el header `x-csrf-token` (tu `apiFetch` ya lo hace en POST). Correcto, no tocar CSRF.
- **UI (después):** una pestaña "Chat analítico" en el nav, visible solo para `ROLES_ANALITICA`,
  que consuma `/api/chat` — encaja al lado de "Analítica" (Process Mining).
- **Buenas prácticas del endpoint:** rate-limit básico por usuario, tamaño máximo de
  pregunta, y devolver el SQL solo si `incluir_sql=True` (transparencia para power users).

---

## 4. Dependencias exactas a agregar

Tu stack hoy: `fastapi==0.110.1`, `sqlalchemy==2.0.36`, `pyodbc==5.2.0`,
`pydantic==2.10.6`, `pydantic-settings==2.7.0`. **No hay** ningún paquete LLM instalado
(el bot de Telegram usa Gemini por HTTP, no por SDK). `pyodbc` y el driver ODBC ya están,
así que la conexión read-only no necesita nada nuevo salvo el login en SQL Server.

**Opción A — con LangChain (recomendada):**
```
langchain==0.3.*
langchain-community==0.3.*          # SQLDatabase, create_sql_query_chain
sqlparse==0.5.*                     # guardia sintáctica del SQL
# + proveedor LLM (elige uno):
langchain-google-genai==2.*         # reutiliza GEMINI_API_KEY
#   ó
langchain-openai==0.2.*             # requiere OPENAI_API_KEY
```

**Opción B — mínima, sin framework:**
```
sqlparse==0.5.*
google-generativeai==0.8.*          # si sigues con Gemini
#   ó
openai==1.*                          # si usas OpenAI
```

Notas de compatibilidad: LangChain 0.3.x es compatible con Pydantic 2 (tu versión) y
Python 3.10 — sin conflicto con FastAPI 0.110. `sqlparse` es liviano y sin dependencias
pesadas. Fijar versiones al instalar y correr la suite (`pytest`) para descartar choques
de resolución.

---

## 5. Riesgos y decisiones abiertas

**Riesgos**
- **Seguridad de datos:** mitigado con el login `db_datareader` + guardia SQL + whitelist. Es la parte no negociable.
- **Alucinación / SQL incorrecto:** el LLM puede generar SQL válido pero con lógica de
  negocio errónea (p.ej. "atrasada"). Mitigar con glosario + few-shots + mostrar el SQL.
- **Costo/latencia por consulta** (1–2 llamadas al LLM). Cachear preguntas frecuentes.
- **Fuga de PII** si se expone `usuarios` con datos sensibles: limitar columnas.

**Decisiones tomadas (cerradas)**
1. **Proveedor LLM:** **Gemini** (reutiliza `GEMINI_API_KEY`).
2. **Login read-only:** **SÍ** — login SQL Server dedicado con solo `db_datareader`,
   en `RAG_DATABASE_URL` aparte del engine transaccional (Windows Auth). Barrera principal.
3. **Alcance Ola 1:** **Confirmado** — whitelist ≈15 tablas (núcleo OF + F1–F7 + catálogo).
4. **Respuesta:** **Híbrido** — filas + resumen en lenguaje natural (2ª llamada a Gemini,
   desactivable por config); SQL visible solo si `incluir_sql=True`.
5. **Framework:** **Mínimo sin framework** — SDK de Gemini directo + `sqlparse` para la
   guardia. Esquema del whitelist desde `Base.metadata`; menos deps y control total.

**Dependencias finales (Opción B, Gemini):** `google-generativeai==0.8.*` + `sqlparse==0.5.*`.

---

## 6. Plan de trabajo sugerido (cuando aprobemos)

- **R1** · Config + engine read-only (`RAG_DATABASE_URL`, `get_db_ro`) + login `db_datareader`.
- **R2** · `rag_service`: esquema whitelist + glosario + generación de SQL (sin ejecutar).
- **R3** · Barreras de seguridad (`sqlparse` guard + whitelist runtime + TOP/timeout + read-only tx) con tests.
- **R4** · Router `POST /api/chat` con DI, `ROLES_ANALITICA`, Pydantic in/out.
- **R5** · UI mínima (pestaña Chat analítico) + auditoría de prompts.
- **R6** · Tests (guardas rechazan DML, whitelist, tope de filas) + verificación.

Cada paso se entrega y se corre `pytest`, con el mismo ritmo de siempre.
