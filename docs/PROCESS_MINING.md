# Process Mining — Fase 0 (diseño, sin código)

Diseño previo para un módulo de minería de procesos (estilo Celonis, acotado) sobre el ERP.
**No modifica el esquema transaccional.** Todo se construye como capa de **solo lectura**
encima de las tablas existentes. Este documento define las 3 decisiones que condicionan
todo lo demás: **Case ID**, **taxonomía de actividades** y **diseño del event log**.

---

## 1. Alcance del MVP

- **Proceso a minar primero:** el **ciclo de vida del bulto** (Numerado → Fusionado → Calidad → Liberado, con sus reprocesos). Es el que tiene el log más limpio (`of_paquete_eventos`, append-only).
- **Objetivo:** descubrir el flujo real (DFG), medir tiempos entre actividades y detectar cuellos/esperas.
- Fuera del MVP (fase posterior): proceso macro por OF, conformance, predicción.

---

## 2. Decisión de Case ID

Se manejan **dos granularidades**; el MVP usa la primera:

| Nivel | `case_type` | `case_id` | Cuándo usarlo |
|---|---|---|---|
| **Micro (MVP)** | `BULTO` | `of_paquetes.id` (`paquete_id`) | Flujo fino de numeración→fusionado→calidad→liberado + reprocesos |
| **Macro** | `OF` | `ordenes_fabricacion.id` (`of_id`) | Flujo end-to-end de la orden (tela→corte→confección) |

Todo evento de bulto lleva también su `of_id` (vía `of_paquetes.of_id`) para poder **agrupar bultos por OF** sin perder la granularidad.

---

## 3. Taxonomía de actividades (mapeo a tablas reales)

El sistema hoy usa vocabularios distintos (`estado`, `fase_id`, `etapa`, `accion`). Se unifican así:

### 3.1 Nivel BULTO (MVP)

| Fuente (tabla) | Campo origen | Valor | → Actividad canónica | lifecycle |
|---|---|---|---|---|
| `of_paquete_eventos` | `estado` | `HABILITADO` | **Numerado** | atomic |
| `of_paquete_eventos` | `estado` | `FUSIONADO` | **Enviado a fusionado** | atomic |
| `of_paquete_eventos` | `estado` | `POR_VALIDAR` | **Enviado a calidad** | atomic |
| `of_paquete_eventos` | `estado` | `ENTREGADO` | **Liberado (OK calidad)** | atomic |
| `of_paquete_eventos` | `estado` | `STAND_BY` | **Rechazado (stand-by)** | atomic |
| `of_paquetes` | `fusionado_inicio` | — | **Fusionado** | start |
| `of_paquetes` | `fusionado_fin` | — | **Fusionado** | complete |
| `of_reproceso_hitos` | `etapa` | `TIZADO/TENDIDO/CORTE/NUMERADO/FUSIONADO` | **Reproceso: {etapa}** | atomic |
| `of_reproceso_hitos` | `etapa` | `REINGRESADO` | **Reingreso a calidad** | atomic |

### 3.2 Nivel OF (fase posterior)

| Fuente | Campo | → Actividad | lifecycle |
|---|---|---|---|
| `avance_registros` | `fase_id` (F1…F7) | nombre de fase (`Tizado`, `Tendido`, `Corte`, `Numerado`, `Fusionado`, `Calidad`, `Liberado`) | atomic |
| `of_fase_tiempos` | `inicio_real` / `fin_real` | `{fase}` | start / complete |
| `of_fase_paradas` | `inicio_parada` / `fin_parada` | **Parada: {motivo}** | start / complete |
| `of_trazo_movimientos` | `tipo` (`TENDIDO`/`CORTE`) | **Tela: {tipo}** | atomic |
| `auditoria_documento_of` | `tipo` + `accion` | **Doc: {tipo} {accion}** (gates) | atomic |
| `of_numeracion_reaperturas` | — | **Reapertura numeración** | atomic |

> Nombres de fase: de `app/constants.py → NOMBRES_FASE` (F1 Tizado … F7 Liberado).
> `avance_registros.revertido = 1` se **excluye** (avances deshechos, no son eventos válidos).

---

## 4. Diseño de `vw_event_log` (VIEW de solo lectura — borrador T-SQL)

Estructura de salida única para todo process mining:

```
case_type  VARCHAR(10)   -- 'BULTO' | 'OF'
case_id    INT
of_id      INT           -- roll-up (para BULTO = su OF; para OF = case_id)
activity   VARCHAR(60)
lifecycle  VARCHAR(10)   -- 'start' | 'complete' | 'atomic'
ts         DATETIME      -- timestamp del evento
resource_id INT          -- usuario que lo generó (NULL si no aplica)
source     VARCHAR(40)   -- tabla origen (trazabilidad)
attr       VARCHAR(200)  -- extra (motivo, destino…)
```

**Borrador de la VIEW (MVP · nivel BULTO). No ejecutado — para revisar en Fase 2:**

```sql
CREATE VIEW vw_event_log AS
-- A) Transiciones de estado del bulto
SELECT 'BULTO' AS case_type, e.paquete_id AS case_id, p.of_id,
       CASE e.estado
         WHEN 'HABILITADO'  THEN 'Numerado'
         WHEN 'FUSIONADO'   THEN 'Enviado a fusionado'
         WHEN 'POR_VALIDAR' THEN 'Enviado a calidad'
         WHEN 'ENTREGADO'   THEN 'Liberado (OK calidad)'
         WHEN 'STAND_BY'    THEN 'Rechazado (stand-by)'
         ELSE e.estado END AS activity,
       'atomic' AS lifecycle, e.created_at AS ts, e.usuario_id AS resource_id,
       'of_paquete_eventos' AS source, e.motivo AS attr
FROM of_paquete_eventos e
JOIN of_paquetes p ON p.id = e.paquete_id

UNION ALL
-- B) Fusionado: inicio y fin (intervalo → 2 eventos)
SELECT 'BULTO', p.id, p.of_id, 'Fusionado', 'start', p.fusionado_inicio, NULL,
       'of_paquetes.fusionado_inicio', NULL
FROM of_paquetes p WHERE p.fusionado_inicio IS NOT NULL
UNION ALL
SELECT 'BULTO', p.id, p.of_id, 'Fusionado', 'complete', p.fusionado_fin, NULL,
       'of_paquetes.fusionado_fin', NULL
FROM of_paquetes p WHERE p.fusionado_fin IS NOT NULL

UNION ALL
-- C) Ruta de reproceso (hitos), enlazada al bulto vía el rechazo
SELECT 'BULTO', r.paquete_id, p.of_id,
       CASE h.etapa WHEN 'REINGRESADO' THEN 'Reingreso a calidad'
                    ELSE 'Reproceso: ' + h.etapa END,
       'atomic', h.at, h.usuario_id, 'of_reproceso_hitos', h.etapa
FROM of_reproceso_hitos h
JOIN of_paquete_rechazos r ON r.id = h.rechazo_id
JOIN of_paquetes p ON p.id = r.paquete_id;
```

El nivel **OF** se añade en fase posterior como más `UNION ALL` (avance_registros, of_fase_tiempos, of_fase_paradas, of_trazo_movimientos, auditoria_documento_of, of_numeracion_reaperturas), siguiendo la misma forma de salida.

---

## 5. Consultas de verificación (Fase 2 — validar con 3–4 bultos terminados)

```sql
-- Traza de un bulto (debe leerse como una historia coherente en el tiempo)
SELECT activity, lifecycle, ts, resource_id, source
FROM vw_event_log WHERE case_type='BULTO' AND case_id = :paquete_id
ORDER BY ts;

-- Directly-Follows (qué actividad sigue a cuál) para el DFG
WITH log AS (
  SELECT case_id, activity, ts,
         LEAD(activity) OVER (PARTITION BY case_id ORDER BY ts) AS next_act
  FROM vw_event_log WHERE case_type='BULTO')
SELECT activity, next_act, COUNT(*) veces
FROM log WHERE next_act IS NOT NULL
GROUP BY activity, next_act ORDER BY veces DESC;

-- Tiempo promedio entre actividades consecutivas (minutos)
WITH log AS (
  SELECT case_id, activity, ts,
         LEAD(activity) OVER (PARTITION BY case_id ORDER BY ts) AS next_act,
         LEAD(ts)       OVER (PARTITION BY case_id ORDER BY ts) AS next_ts
  FROM vw_event_log WHERE case_type='BULTO')
SELECT activity, next_act,
       AVG(DATEDIFF(MINUTE, ts, next_ts)) AS min_prom, COUNT(*) n
FROM log WHERE next_act IS NOT NULL
GROUP BY activity, next_act ORDER BY min_prom DESC;
```

---

## 6. Decisiones abiertas / a confirmar antes de Fase 2

1. **Case ID del MVP = bulto.** ¿Confirmas, o prefieres arrancar por OF?
2. **Nombres de actividad** (columna "canónica" de la §3): ¿te gustan esos textos o quieres otros?
3. **Zona horaria:** los `timestamp` son hora del **servidor** (`func.now()`). Confirmar que es consistente (hay un `datetime.utcnow()` deprecado en `auth`, ajeno a esto).
4. **Dónde vive la VIEW:** en SQL Server (`CREATE VIEW`) — recomendado — o como consulta en un `service`. La primera es más limpia y no requiere migración de datos.
5. **Reproceso/loops:** se **conservan** (son el valor del análisis); no se filtran.

---

## 7. Siguiente paso

Con estas 5 decisiones cerradas → **Fase 2**: crear `vw_event_log` (solo la parte BULTO) y validarla con las consultas de la §5 sobre bultos ya terminados. Sin tocar el ERP ni su rendimiento.
