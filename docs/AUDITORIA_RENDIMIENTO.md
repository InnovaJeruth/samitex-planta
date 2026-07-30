# Auditoría de Rendimiento — SAMITEX-PLANTA (FastAPI ERP)

_Enfoque: concurrencia, event loop, N+1, eficiencia de BD, pool de conexiones,
paginación. Contexto: picos concurrentes de usuarios de logística/producción._

---

## 0. Nota de arquitectura (clave)

La mayoría de rutas son **`def` síncronas** → FastAPI las ejecuta en su **threadpool**
(anyio, 40 hilos por defecto), por lo que su I/O bloqueante (pyodbc, archivos) **no
bloquea el event loop**. Es la elección correcta para un conector `pyodbc` síncrono.
El riesgo estaba solo en las pocas rutas `async def` que hacían trabajo síncrono.

---

## 1. Resumen de hallazgos

| # | Severidad | Área | Hallazgo | Estado |
|---|-----------|------|----------|--------|
| P1 | Crítica | `of.py`, `curvas.py` | Rutas `async def` con trabajo síncrono pesado (import SAP, uploads) → bloquean el event loop | **✅ Aplicado** |
| P2.1 | Media→Alta | `dashboard.py` | Cargaba todo el universo de OFs + relaciones en cada request | **✅ Aplicado** (ventana temporal: vivo siempre + completadas últimos 90 días) |
| P2.2–2.3 | Media | `dashboard.py` | Agregación en SQL + caché TTL | **Diferido** — poco retorno (la cascada obliga a cargar piezas/fases igual; la ventana ya resolvió la carga). Reevaluar **solo si se mide lento** en producción |
| P3 | Media | `dashboard.py` `/api/ofs-resumen` | `.all()` sin límite ni paginación | **✅ Aplicado** (solo operativas + orden + limit 500) |
| P4 | Media | `database/connection.py` | Pool máx. 30 < 40 hilos del threadpool | **✅ Aplicado** (pool 20+30=50, `pool_timeout=10`, `pool_recycle=1800`) |
| P5 | Media | `of_import_service.py` | `commit` por fila en el bucle de import → N transacciones | **✅ Aplicado** (flag `commit`; el lote hace flush + 1 commit final) |
| P6 | Baja | `pdf_report.py`, `process_mining/*` | Render PDF y analítica CPU-intensivos en el threadpool | **Diferido** — poco frecuente/pocos usuarios; actuar solo si se observa saturación real |

---

## 2. Detalle y solución

### P1 — Bloqueo del event loop  ✅ CORREGIDO
`import_sap`, `subir_documento` (`of.py`) y `api_adjuntar_doc` (`curvas.py`) eran
`async def` pero parseaban Excel / escribían archivos / hacían writes de BD de forma
**síncrona** dentro del coroutine. Un import SAP grande congelaba a todos los usuarios.
**Aplicado:** convertidas a `def` (corren en threadpool) + `archivo.file.read()`. Verificado con 296 tests en verde.

### P2 — Dashboard: carga total + agregación en Python  (Media→Alta)
`GET /` trae **todas** las OFs no anuladas con piezas, fases_estado, recepciones y
tiempos, y calcula KPIs/OTD/heatmap/cascada en Python en cada carga. Crece linealmente
con el histórico; es el hot-path (muchos usuarios, alta frecuencia).
**Solución por capas (menor→mayor esfuerzo):**
1. **Ventana de datos:** cargar solo lo operativo (BORRADOR/ACTIVA/EN_PROCESO + COMPLETADAS de los últimos 60–90 días). No cambia el shape que consume la plantilla.
2. **Agregar en SQL:** KPIs por estado y `SUM(total_juegos)` → `GROUP BY estado`; heatmap por fase → `GROUP BY fase_id` con conteo de `completada`. Evita materializar piezas/fases solo para contarlas.
3. **Caché corta (30–60 s):** el payload es idéntico entre usuarios; cachear en memoria con TTL corta las ráfagas.

### P3 — `/api/ofs-resumen` sin paginación  (Media)
`.all()` sobre todas las OFs no anuladas. **Solución:** filtrar a OFs relevantes (activas/en proceso o ventana temporal) y/o paginar como `lista_ofs` (offset/limit + count).

### P4 — Pool de conexiones vs threadpool  (Media)
`connection.py`: `pool_size=10, max_overflow=20` → **máx. 30** conexiones. El threadpool
de FastAPI admite **40** requests sync concurrentes; cada uno pide una sesión (`get_db`).
Con >30 concurrentes, los hilos sobrantes **esperan** una conexión (timeout por defecto 30 s) → latencia/errores bajo carga.
**Solución:** alinear capacidades. Ej.:
```python
# opción A: subir el pool para cubrir el threadpool
engine = create_engine(_url, pool_pre_ping=True, pool_size=20, max_overflow=30,  # 50 > 40
                       pool_timeout=10)
# opción B (además): limitar el threadpool a ~pool size
# en startup: anyio.to_thread.current_default_thread_limiter().total_tokens = 30
```
Considerar el límite de conexiones de SQL Server Express (generoso, pero finito) y usar `pool_recycle` (p. ej. 1800 s) para conexiones largas.

### P5 — `commit` por fila en el import  (Media)
`crear_of_desde_sap` hace `db.commit()` por cada OF dentro del bucle de `importar_excel_sap`
→ N transacciones y N round-trips a SQL Server. **Solución:** un solo `commit` al final del
lote (o por bloques de N), reduciendo drásticamente el tiempo de import. (Ya no bloquea el
loop tras P1, pero sigue siendo lento de por sí.)

### P6 — Operaciones CPU-intensivas en el threadpool  (Baja)
Generación de PDF (`pdf_report.py`, xhtml2pdf) y `process_mining`/`animacion` (construyen
event logs y grafos en memoria) son costosas en CPU. Corren en el threadpool (no bloquean
el loop), pero varias en paralelo pueden **agotar los 40 hilos** y degradar a todos.
**Solución:** para PDFs, `BackgroundTasks` o cola si son frecuentes; para analítica, cachear
resultados o limitar el nº de OFs por consulta (ya hay `limit(300)` en `api/ofs`). Baja
prioridad: son operaciones poco frecuentes y de pocos usuarios (gerencia/analítica).

---

## 3. Buenas prácticas confirmadas (sin cambios)

- **Sin N+1:** dashboard y servicios de listado usan `selectinload`/`joinedload` (eager loading en ~29 puntos de `paquete_service`). Los arreglos previos (Calidad, Planeamiento, corte bulk) siguen vigentes.
- **Paginación:** `lista_ofs` pagina en BD (offset/limit + count). ✔
- **Sesiones:** `get_db`/`get_db_ro` cierran con `try/finally` (sin fugas). El bot usa `SessionLocal()` con `finally: db.close()`.
- **Consultas acotadas:** los `.all()` de `corte.py`/`hoja_costos` filtran por `of_id`/`prenda_id` (no barren tablas completas).
- **Índices:** FKs indexadas (auditoría previa: `of_piezas.of_id`, `documentos_of.of_id`, `of_fases_estado.pieza_id`, `avance_registros.pieza_id`, etc.).
- **`pool_pre_ping=True`:** evita usar conexiones muertas.

---

## 4. Plan de aplicación sugerido (por riesgo/impacto)

1. **P1** — ✅ hecho (bajo riesgo, alto impacto).
2. **P4** (pool) — muy bajo riesgo, solo config; alto impacto bajo concurrencia. **Recomendado siguiente.**
3. **P3** (`ofs-resumen` filtro) — bajo riesgo.
4. **P2 paso 1** (ventana en dashboard) — bajo riesgo, alto impacto; pasos 2–3 (SQL agg + caché) después.
5. **P5** (commit por lote en import) — riesgo medio (toca lógica del import); con tests de `test_of_import_sap` cubriendo.
6. **P6** — opcional, según se observe saturación real.
