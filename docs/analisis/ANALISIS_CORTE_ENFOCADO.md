# Análisis Enfocado: OF Creada + MP/Avíos Listos → Piezas a Costura
**Alcance:** Desde que la OF está creada y los materiales están disponibles, hasta que los paquetes salen a Costura.

---

## Avance global de este alcance

```
████████████░░░░░░░░  58%
```

| Categoría | % logrado | Detalle |
|---|---|---|
| Estructura de datos (modelos DB) | 82% | Casi todo está modelado |
| Lógica de negocio (backend) | 65% | Fases, avances, semáforo funcionan |
| Interfaz de usuario (UI) | 45% | Seguimiento existe; varias pantallas faltan |
| Trazabilidad end-to-end | 30% | Sin paquetes ni despacho formal |
| **Total ponderado** | **58%** | |

---

## Flujo cubierto y % por etapa

```
OF activada                              ████████████████░░░░  80%
    ↓
Almacén → Nota de Salida → Corte recibe  ████░░░░░░░░░░░░░░░░  10%  (solo confirmación básica)
    ↓
F1 · Tizado                              ████████████░░░░░░░░  60%
F2 · Tendido                             ██████████░░░░░░░░░░  50%
F3 · Corte                               █████████████░░░░░░░  65%
F4 · Numerado                            ████████░░░░░░░░░░░░  40%
F5 · Fusionado                           ██████████████░░░░░░  70%
F6 · Calidad                             ████████░░░░░░░░░░░░  40%
F7 · Habilitado / Despacho Costura       ████░░░░░░░░░░░░░░░░  20%
```

---

## Lo que el sistema SÍ tiene — 82% del modelo de datos

### ✅ Completo o muy cercano

| Elemento | Dónde está | % |
|---|---|---|
| OF con piezas heredadas del catálogo | `OFPieza`, `PlantillaPieza` | 100% |
| Gates documentales para activar la OF | `gate_service.py` | 100% |
| 9 fases de proceso definidas (F1–F9) | `constants.py`, `FaseCatalogo` | 100% |
| Registro de avance por pieza × fase con cantidad y fecha | `OFFaseEstado`, `registrar_avance()` | 100% |
| Tiempos inicio/fin programado y real por fase | `OFFaseTiempos` | 100% |
| Registro de paradas con motivo | `OFFaseParada` | 100% |
| Fusionado opcional por pieza | `OFPieza.fusionado` | 100% |
| Estampado/Auditoría opcionales por OF | `of.estampado_activo` | 100% |
| Campo eficiencia tizado (RF-073) | `OFFaseEstado.eficiencia_tizado` | 50% — en DB, sin UI |
| Campo temperatura fusionado (RF-095) | `OFFaseEstado.temperatura_fusion` | 50% — en DB, sin UI |
| Campo tratamiento orillo (RF-079) | `OFFaseEstado.tratamiento_orillo` | 50% — en DB, sin UI |
| Campo motivo rechazo calidad (RF-097) | `OFFaseEstado.motivo_rechazo` | 50% — en DB, sin UI |
| UI seguimiento: tabs, registro bulk, historial | `corte/seguimiento.html` | 80% |
| PDF reporte de corte | `pdf_report.py` | 70% |
| Semáforo y estado en tiempo real | `semaforo_service.py`, WebSocket | 85% |

---

## Lo que el modelo tiene pero la UI NO expone — costo bajo, impacto alto

Campos ya en DB — solo falta agregar inputs en la pantalla de seguimiento.

| RF | Dato faltante en UI | Campo en modelo | Esfuerzo | % actual |
|---|---|---|---|---|
| RF-073 | % eficiencia del trazo + alerta si < 85% | `eficiencia_tizado` | Bajo | 50% |
| RF-079 | Tratamiento de orillo (Instituciones) | `tratamiento_orillo` | Bajo | 50% |
| RF-094/095 | Temperatura fusionado (150–155°C) | `temperatura_fusion` | Bajo | 50% |
| RF-097 | Motivo de rechazo de calidad | `motivo_rechazo` | Bajo | 50% |
| RF-080 | Operador que ejecuta el corte | Sin campo `operador_id` | Bajo | 0% |
| RF-077 | Parámetros de máquina (velocidad, presión, capas) | Sin tabla | Medio | 0% |

---

## Lo que NO existe — brechas reales

### ❌ 1. Almacén → Corte: Picking y Nota de Salida — 10%
**RFs:** 065, 066, 067, 068

El sistema no sabe qué tela/avíos entregó Almacén a Corte para cada OF. Es el "portón de entrada" a planta.

- El SRS exige picking por rollo, escaneo QR, nota de salida con descarga de stock
- **Alternativa rápida (Bajo):** Botón "Confirmar insumos recibidos" en la OF — sin kardex, solo registra fecha y quién confirmó. Cubre trazabilidad mínima.
- **Versión completa (Muy Alto):** Requiere módulo de Almacén con kardex completo

**% logrado: 10%** (solo el modelo de OF tiene campos para la tela, nada del flujo Almacén)

---

### ❌ 2. BOM automático — 15%
**RF:** 031

El catálogo tiene piezas, avíos y consumos por talla, pero el sistema no calcula cuánto material se necesita para la OF.

- Fórmula: `total_juegos × consumo_por_talla × distribución_curva_tallas`
- Sin esto no se puede validar si hay stock suficiente antes de cortar

**Esfuerzo:** Medio-Alto | **% logrado: 15%** (datos en catálogo, cálculo no implementado)

---

### ❌ 3. Registro formal del trazo — 20%
**RFs:** 072, 073, 075, 078

La fase F1=Tizado existe y registra piezas, pero falta:
- Adjuntar archivo de trazo (Marker/Marquesil) con versión controlada
- Registrar capas, metraje utilizado, rollos consumidos en el tendido (F2)
- Alerta visual cuando eficiencia < 85%

**Esfuerzo:** Medio | **% logrado: 20%** (fase existe, campos de eficiencia en DB, sin UI ni adjunto)

---

### ❌ 4. Paquetes y tickets QR — 0%
**RFs:** 090, 091, 092

La fase F4=Numerado registra piezas pero no genera paquetes físicos. Falta:
- Entidad `Paquete` (40 piezas, 1:1 por talla, correlativo único)
- Generación de ticket imprimible con QR codificando: OF, talla, cantidad, correlativo
- Soporte de impresora térmica ZPL

Esta es la brecha más bloqueante porque de ella dependen F6 y F7.

**Esfuerzo:** Alto | **% logrado: 0%**

---

### ❌ 5. Inspección de calidad por paquete — 25%
**RFs:** 096, 097, 098

La fase F6=Calidad existe con `motivo_rechazo`, pero falta:
- Inspección registrada paquete a paquete (no por pieza genérica)
- V°B° digital: evento inmutable con usuario + fecha + hora
- Reproceso trazado: paquete rechazado → vuelve a Habilitado

**Esfuerzo:** Medio-Alto | **% logrado: 25%** (fase + campo motivo_rechazo existen)

---

### ❌ 6. Despacho formal a Costura — 10%
**RF:** 099

El sistema da la OF por "completada" cuando el 100% de piezas pasan todas las fases, pero no hay:
- Evento "Despachar a Costura" con lista de paquetes entregados
- Acuse de recibo por parte de Costura
- Registro de paquetes entregados vs. pendientes

**Esfuerzo:** Bajo (si hay paquetes) / Medio (sin paquetes) | **% logrado: 10%**

---

### ❌ 7. Reporte diario automático a Planeamiento — 30%
**RFs:** 041, 100

El avance en tiempo real existe (WebSocket + semáforo). Falta:
- Tarea programada que genere resumen diario
- Envío automático vía Telegram (Bot ya existe) o correo
- Contenido: % avance por fase por OF, OFs en riesgo de APT, OFs con paradas activas

**Esfuerzo:** Bajo | **% logrado: 30%** (datos existen, solo falta el trigger diario)

---

## Resumen por etapa del flujo

| Etapa | % logrado | Brechas principales | Prioridad |
|---|---|---|---|
| OF activada con gates | 80% | PDF OF formal, notificación correo | 🟡 Media |
| Almacén → entrega a Corte | 10% | Picking, nota de salida (o confirmación simplificada) | 🔴 Alta |
| F1 Tizado | 60% | Adjunto trazo, alerta eficiencia en UI | 🟡 Media |
| F2 Tendido | 50% | Capas, metraje, rollos en UI | 🟡 Media |
| F3 Corte | 65% | Operador, parámetros máquina | 🟡 Media |
| F4 Numerado | 40% | Entidad Paquete, ticket QR | 🔴 Alta |
| F5 Fusionado | 70% | Temperatura en UI, prueba previa | 🟢 Baja |
| F6 Calidad | 40% | Inspección por paquete, V°B° inmutable | 🔴 Alta |
| F7 Habilitado / Despacho | 20% | Despacho formal, acuse de recibo | 🔴 Alta |
| Reporte a Planeamiento | 30% | Trigger diario automático | 🟢 Baja |

---

## Hoja de ruta para llegar al 90%

### Sprint 1 — 1 semana (brechas baratas, impacto inmediato)
- Exponer en UI: eficiencia tizado, orillo, temperatura fusionado, motivo rechazo
- Operador asignado a fase F3
- Confirmación simplificada "Insumos recibidos en Corte"
- Trigger de reporte diario vía Telegram
- **Sube de 58% → 68%**

### Sprint 2 — 2–3 semanas (paquetes, desbloqueador crítico)
- Entidad `Paquete` + correlativo automático
- Generación de ticket PDF/QR por paquete
- Inspección de calidad vinculada a paquete + V°B° digital
- Despacho formal a Costura con acuse
- **Sube de 68% → 83%**

### Sprint 3 — 2 semanas (trazo y tendido completos)
- Entidad `TrazoOF`: adjunto Marker, capas, metraje, rollos
- Alerta visual de eficiencia en UI de F1
- BOM básico (consumo estimado de tela por OF)
- **Sube de 83% → 90%+**
