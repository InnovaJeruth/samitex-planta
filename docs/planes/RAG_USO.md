# Chat analítico (RAG Text-to-SQL) — Guía de uso y operación

Módulo que responde preguntas de negocio en lenguaje natural generando SQL de
**solo lectura** sobre SQL Server. Pensado para Planeamiento y Gerencia.

---

## 1. Cómo se usa

- Entra a **Chat analítico** en el menú (visible para ADMIN, GERENTE_PLANTA,
  JEFE_PLANTA, GERENCIA, PLANEADOR).
- Escribe la pregunta y pulsa **Preguntar** (o Ctrl+Enter).
- Marca **"Ver el SQL generado"** para auditar la consulta.
- Menciona el **número de OF** cuando preguntes por una específica.

Ejemplos que funcionan bien:
- ¿Cuántas OF están activas?
- OF atrasadas con su cliente
- Duración de cada fase de la OF 4000010011
- Rechazos de calidad por motivo de la OF 4000010011
- ¿Cuántos requerimientos hay por tipo?

---

## 2. Configuración (.env)

```
RAG_ENABLED=true                 # enciende/apaga el módulo
RAG_LLM_PROVIDER=ollama          # ollama (local, gratis) | gemini (nube)
RAG_OLLAMA_URL=http://localhost:11434
RAG_OLLAMA_MODEL=qwen2.5-coder:7b
RAG_LLM_TIMEOUT=180              # seg. (subir si el modelo local va lento)
RAG_MODEL=gemini-2.0-flash       # modelo si usas gemini
RAG_DB_URL=                      # conexión de SOLO LECTURA (ver §4). Vacío = usa la de la app
RAG_MAX_ROWS=200                 # tope de filas por consulta
```

- **Local (Ollama):** instala [ollama.com](https://ollama.com), `ollama pull qwen2.5-coder:7b`, deja el servicio corriendo.
- **Nube (Gemini):** `RAG_LLM_PROVIDER=gemini` + `GEMINI_API_KEY` con cuota (requiere billing activo en el proyecto).

---

## 3. Seguridad (cómo está blindado)

- **Solo SELECT:** el SQL generado pasa por guardas (`rag_guard`) que rechazan
  INSERT/UPDATE/DELETE/DROP/EXEC/`SELECT INTO`/múltiples sentencias/comentarios.
- **Whitelist:** solo se permiten las tablas/vistas del listado curado; cualquier
  otra (incl. `sys.*`) se bloquea.
- **Conexión de solo lectura:** usuario `db_datareader` dedicado (ver §4).
- **Tope de filas** y **rollback siempre**. Acceso restringido por rol. Auditoría en logs.

---

## 4. Conexión de solo lectura (recomendado)

Ejecuta `scripts/sql/rag_login_readonly.sql` en SSMS para crear el usuario
`rag_readonly` (db_datareader). Luego pon en `.env`:

```
RAG_DB_URL=mssql+pyodbc://rag_readonly:CLAVE@PANO0142\SQLEXPRESS/SAMITEX-PLANTA?driver=ODBC+Driver+17+for+SQL+Server
```

Sin esto, el chat lee con la conexión de la app (permisos plenos); las guardas
siguen protegiendo, pero la barrera fuerte es este login.

---

## 5. Vistas de negocio (para respuestas complejas)

Cuando una pregunta necesita joins complejos, el modelo local falla; la solución
es una **vista** que aplane la lógica. Ya existen:

- `vw_of_fases` — tiempos por fase de la OF (script `scripts/sql/vw_of_fases.sql`).
- `vw_of_rechazos` — rechazos de calidad por OF (script `scripts/sql/vw_of_rechazos.sql`).

Ejecuta esos scripts en SSMS para habilitarlas.

---

## 6. Cómo mejorar / mantener

- **Añadir un dominio** (costos, tercerización): agrégalo al `WHITELIST` en
  `app/services/rag_service.py`, con su descripción, relaciones y 1–2 few-shots.
- **Pregunta que falla por un join:** crea una **vista** y regístrala en `VISTAS`
  + whitelist + un few-shot (patrón de `vw_of_fases`).
- **Más precisión:** modelo local más grande (`qwen2.5-coder:14b/32b`) o Gemini con billing.
- Fuente de verdad del esquema/semántica: `docs/planes/RAG_DICCIONARIO_DATOS.md`.

---

## 7. Problemas comunes

| Mensaje | Causa | Solución |
|---|---|---|
| "El chat analítico está deshabilitado" | `RAG_ENABLED=false` | Ponlo en `true` y reinicia |
| "No se pudo conectar al modelo local" | Ollama no corre | `ollama serve` / instalar Ollama |
| "El modelo local no está descargado" | Falta el modelo | `ollama pull qwen2.5-coder:7b` |
| "tardó demasiado en responder" | 1ª carga / equipo lento | Reintenta o usa modelo liviano (1.5b) |
| "límite de uso de Gemini" | Sin cuota/billing | Activa billing o usa Ollama |
| "Consulta no permitida: Tablas no permitidas" | El modelo usó una tabla fuera del whitelist | Reformula o añade la tabla/vista al whitelist |
