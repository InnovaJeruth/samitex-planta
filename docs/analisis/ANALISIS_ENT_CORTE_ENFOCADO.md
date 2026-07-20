# Análisis ENT — Enfocado: Insumos en Planta → Piezas a Costura
**Base:** ENT_Modulo_Corte_Samitex_v1.docx — Etapas C, D, E, F  
**Premisa:** OF creada y activada. MP + avíos ya disponibles en planta.  
**Fecha:** Julio 2026

---

## Avance global en este alcance

```
██████░░░░░░░░░░░░░░  28%
```

| Etapa ENT | Pasos | % logrado | Semáforo |
|---|---|---|---|
| C — Trazado | C1–C6 | 18% | 🔴 |
| D — Tendido y corte | D1–D6 | 32% | 🔴 |
| E — Habilitado y fusionado | E1–E6 | 35% | 🟡 |
| F — Calidad y despacho | F1–F5 | 18% | 🔴 |
| Estados OF (EN CORTE en adelante) | 4 de 6 | 33% | 🔴 |
| Estados Paquete | 0 de 6 | 0% | 🔴 |
| Entidades nuevas requeridas | 9 entidades | 12% | 🔴 |
| Validaciones bloqueantes | 4 reglas | 8% | 🔴 |
| **Total ponderado** | | **28%** | 🔴 |

---

## Qué tiene el sistema como base (antes de ver brechas)

El modelo de datos tiene más de lo que parece en pantalla:

| Lo que existe | Dónde | Sirve para |
|---|---|---|
| Fases F1=Tizado, F2=Tendido, F3=Corte, F4=Numerado, F5=Fusionado, F6=Calidad, F7=Habilitado | `constants.py`, `FaseCatalogo` | Columna vertebral del flujo |
| Avance por pieza × fase con cantidad y fecha | `OFFaseEstado`, `registrar_avance()` | C4, D5, E1, F1 parciales |
| Tiempos inicio/fin real por fase | `OFFaseTiempos` | D5, E6 parciales |
| Paradas con motivo y duración | `OFFaseParada` | D5 incidencias |
| `eficiencia_tizado` Float | `OFFaseEstado` | C4 — en DB, **sin UI** |
| `temperatura_fusion` Float | `OFFaseEstado` | E5/E6 — en DB, **sin UI** |
| `tratamiento_orillo` Boolean | `OFFaseEstado` | D4 — en DB, **sin UI** |
| `motivo_rechazo` Text | `OFFaseEstado` | F1/F2 — en DB, **sin UI** |
| `OFPieza.fusionado` por pieza | `pieza.py` | E4 derivación |
| UI de seguimiento: tabs, bulk, historial | `seguimiento.html` | Base de toda la UI de planta |
| PDF de reporte de corte | `pdf_report.py` | F5 parcial |
| Semáforo + WebSocket tiempo real | `semaforo_service.py`, `ws.py` | F5 parcial |

---

## Etapa C — Trazado — 18%

```
████░░░░░░░░░░░░░░░░  18%
```

| Paso | Descripción ENT | % | Brecha | Modificar / Agregar | Esfuerzo |
|---|---|---|---|---|---|
| C1 | Recibir variantes por talla de Modelaje (versión vigente) | 0% | No hay repositorio de moldes ni entidad Variante | Agregar repositorio de archivos por OF (upload de variantes por talla) | Alto |
| C2 | Agrupar variantes por talla y cantidad según curva de tallas | 25% | Curva de tallas existe pero no hay agrupación formal para armar el trazo | Agregar lógica que tome `CurvaTallasDetalle` y genere la matriz talla×cantidad | Medio |
| C3 | Crear trazo: adjuntar archivo Marker + metadatos (largo, ancho, capas propuestas) | 10% | F1=Tizado registra piezas pero no hay entidad `Trazo` ni adjunto de archivo | **Agregar** entidad `Trazo` (of_id, archivo, versión, hash, largo_cm, ancho_cm, capas_propuestas, eficiencia, estado) + endpoint upload + UI | Alto |
| C4 | Registrar eficiencia: obligatoria, alerta si <85% o >87%, justificación supervisor si fuera de rango | 30% | Campo `eficiencia_tizado` existe en DB; sin input en UI, sin alerta, sin bloqueo | **Modificar** modal de F1 en `seguimiento.html`: agregar input numérico de eficiencia + alerta CSS + campo justificación condicional | Bajo |
| C5 | Bloquear áreas de fusionado dentro del trazo (cuello/puño/pechera) | 0% | No existe | Agregar campo `areas_fusionado` JSON o checkbox en entidad Trazo | Bajo |
| C6 | Publicar trazo a carpeta compartida con hash y versión controlada | 0% | No existe integración con sistema de archivos externo | Agregar campo `publicado_en` + hash SHA256 al guardar el archivo; carpeta compartida = fuera de alcance del sistema web | Medio |

**Qué agregar:** modelo `Trazo` + migración Alembic + endpoint POST/GET + sección en `seguimiento.html` para registrar trazo antes de iniciar F1.  
**Qué modificar:** modal de avance de F1 — agregar input `eficiencia` con validación JS y alerta roja si <85% o >87%.

---

## Etapa D — Tendido y corte — 32%

```
███████░░░░░░░░░░░░░  32%
```

| Paso | Descripción ENT | % | Brecha | Modificar / Agregar | Esfuerzo |
|---|---|---|---|---|---|
| D1 | Imprimir guía visual del trazo + log de impresión | 5% | No existe | Agregar botón "Imprimir guía" en sección Trazo que genere PDF + registre `impreso_por`, `impreso_at` | Bajo |
| D2 | Configurar parámetros de máquina: velocidad, presión, capas, plantillas por tipo de tela | 0% | No existe ninguna tabla de parámetros de máquina | **Agregar** entidad `ParametrosMaquina` (trazo_id o tendido_id, velocidad, presión, altura_capas, tipo_tela) o campo JSON en Tendido | Medio |
| D3 | Registrar tendido: mesa, capas reales, rollos consumidos, metraje real por rollo | 10% | F2=Tendido registra solo cantidad de piezas; sin mesa, sin capas, sin rollos | **Agregar** entidad `Tendido` (trazo_id, mesa_id, capas_reales, metraje_consumido, operador_id) + lista de rollos usados | Medio |
| D4 | Tratamiento de orillo de marca (solo canal INSTITUCIÓN) | 30% | Campo `tratamiento_orillo` Boolean en DB pero sin input en UI ni condicional por canal | **Modificar** modal de F2 en `seguimiento.html`: agregar checkbox "Orillo tratado" visible solo si `of.tipo_cliente == 'INSTITUCION'` | Bajo |
| D5 | Registrar corte: inicio/fin real, operador, incidencias → estado CORTADO | 50% | `OFFaseTiempos` tiene inicio/fin real; `OFFaseParada` tiene incidencias; sin campo `operador_id` | **Modificar** `OFFaseEstado`: agregar FK `operador_id → usuarios.id` + migración + select de operario en UI de F3 | Bajo |
| D6 | Contador de refilados de cuchilla (cada 3–4 m) | 0% | No existe | **Agregar** campo `refilados_cuchilla` Integer en entidad Corte o en `OFFaseEstado` F3 + botón "+1 refilado" en UI | Bajo |

**Qué agregar:** entidades `Tendido` + `ParametrosMaquina` + migración.  
**Qué modificar:** `OFFaseEstado` — agregar `operador_id`; modal de F2 en seguimiento — agregar campos de tendido; modal de F3 — agregar selector de operario y contador de refilados.

---

## Etapa E — Habilitado y fusionado — 35%

```
███████░░░░░░░░░░░░░  35%
```

| Paso | Descripción ENT | % | Brecha | Modificar / Agregar | Esfuerzo |
|---|---|---|---|---|---|
| E1 | Numerar correlativamente: correlativo por trazo/capa/talla → trazabilidad pieza→paquete→OF | 30% | F4=Numerado registra avance; sin correlativo por capa/talla ni vínculo al trazo | Agregar campo `correlativo_inicio` y `correlativo_fin` en entidad Paquete; F4 genera el rango | Medio |
| E2 | Habilitar paquetes 1:1 (40 piezas): talla, cantidad, correlativos → estado HABILITADO | 0% | **No existe entidad Paquete.** Es la brecha más crítica de todo el módulo | **Agregar** modelo `Paquete` (of_id, talla, cantidad, correlativo_inicio, correlativo_fin, requiere_fusionado, estado) + migración + endpoints CRUD + UI en F4 | Alto |
| E3 | Emitir ticket de paquete con QR: OF, estilo, talla, cantidad, correlativo | 0% | No existe generación QR ni impresión de tickets | **Agregar** endpoint `/paquete/{id}/ticket` → genera PDF con QR usando `qrcode` + `weasyprint` | Alto |
| E4 | Derivar a fusionado condicionalmente según ficha técnica | 60% | `OFPieza.fusionado` flag existe y el sistema omite F5 si es False; falta derivación automática de Paquete | **Modificar** lógica de Paquete al crearse: si `requiere_fusionado`, estado inicial = EN FUSIONADO | Bajo |
| E5 | Validar temperatura previa: prueba, resultado, inspector → bloquea E6 si no conforme | 25% | Campo `temperatura_fusion` en DB; sin entidad `PruebaFusionado`, sin bloqueo de F5 | **Agregar** modelo `PruebaFusionado` (of_id, temperatura_medida, resultado, inspector_id, fecha) + endpoint + UI; bloquear inicio F5 si no existe prueba conforme | Medio |
| E6 | Fusionar a 150–155°C: temperatura aplicada, máquina, operario; alerta fuera de rango | 20% | F5=Fusionado registra avance; sin campo temperatura aplicada en UI, sin alerta, sin máquina | **Modificar** modal de F5: agregar input temperatura + validación JS (alerta si <150 o >155) + selector máquina/operario | Bajo |

**Qué agregar:** modelos `Paquete` + `PruebaFusionado` + migración + endpoints + UI de habilitado + generación QR.  
**Qué modificar:** modal de F5 en seguimiento + lógica de derivación automática por `requiere_fusionado`.

---

## Etapa F — Calidad y despacho — 18%

```
████░░░░░░░░░░░░░░░░  18%
```

| Paso | Descripción ENT | % | Brecha | Modificar / Agregar | Esfuerzo |
|---|---|---|---|---|---|
| F1 | Inspección por paquete: checklist configurable, conforme/no conforme, foto adjunta | 20% | F6=Calidad registra avance general; `motivo_rechazo` en DB; sin inspección por paquete, sin checklist, sin foto | **Agregar** modelo `InspeccionCalidad` (paquete_id, resultado, checklist_json, motivo_nc, foto_ruta, inspector_id, fecha) + endpoint + UI en F6 | Alto |
| F2 | Reproceso: paquete NC → regresa a HABILITADO con historial completo | 10% | `motivo_rechazo` existe; sin flujo de retorno de paquete, sin historial de reprocesos | **Modificar** endpoint de InspeccionCalidad: si resultado=NO_CONFORME → actualizar estado Paquete a HABILITADO + registrar evento en historial | Medio |
| F3 | V°B° digital: usuario, fecha, hora → evento inmutable → paquete estado APROBADO | 0% | No existe entidad de V°B° ni evento inmutable | **Agregar** endpoint `POST /paquete/{id}/vobo` (requiere rol CALIDAD) → inserta `InspeccionCalidad` con resultado=CONFORME + timestamp inmutable | Medio |
| F4 | Despacho a Costura: escaneo de tickets QR + acuse de Costura → paquete DESPACHADO | 0% | No existe entidad `DespachoCostura` ni flujo de escaneo | **Agregar** modelo `DespachoCostura` (paquetes_ids[], receptor_id, fecha, acuse_timestamp) + endpoint + UI de escaneo/selección de paquetes | Medio |
| F5 | Reporte diario automático a Planeamiento: paquetes cortados/aprobados/despachados vs. programa | 30% | WebSocket + semáforo en tiempo real existen; sin reporte diario automático ni consolidado | **Modificar** Telegram Bot: agregar tarea programada (cron 18:00) que calcule avance diario por OF y envíe resumen | Bajo |

**Qué agregar:** modelos `InspeccionCalidad` + `DespachoCostura` + migración + endpoints + UI de calidad y despacho.  
**Qué modificar:** F6 y F7 en `seguimiento.html` — vincular a Paquete; cron job en Telegram Bot para reporte diario.

---

## Estados faltantes

### OF — desde EN CORTE (33% cubierto del tramo enfocado)

| Estado ENT | Equivalente actual | Existe |
|---|---|---|
| EN CORTE | EN_PROCESO | 🟡 equivalente |
| EN HABILITADO | — | ❌ |
| EN CALIDAD | — | ❌ |
| COMPLETADA | COMPLETADA | ✅ |

**Qué modificar:** extender `EstadoOF` con `EN_HABILITADO` y `EN_CALIDAD` + migración + transiciones automáticas en `corte_service.py` cuando todas las piezas completan F3 (→ EN_HABILITADO) y F6 (→ EN_CALIDAD).

### Paquete — 0% (entidad nueva completa)

| Estado ENT | Existe |
|---|---|
| HABILITADO | ❌ |
| EN FUSIONADO | ❌ |
| EN INSPECCIÓN | ❌ |
| NO CONFORME | ❌ |
| APROBADO | ❌ |
| DESPACHADO | ❌ |

---

## Validaciones bloqueantes (§7.3) — aplicables a este alcance

| Regla | % | Qué agregar | Esfuerzo |
|---|---|---|---|
| Fusionado (E6) bloqueado sin prueba de temperatura conforme (E5) | 0% | Validación en endpoint inicio F5: verificar existe `PruebaFusionado` conforme para esta OF | Bajo |
| Despacho a Costura bloqueado si paquete no está APROBADO | 0% | Validación en `DespachoCostura`: filtrar solo paquetes con estado=APROBADO | Bajo |
| Eficiencia de trazo fuera de 85–87% exige justificación del supervisor | 0% | Validación en endpoint de Trazo: si eficiencia <85 o >87 → campo `justificacion_supervisor` obligatorio | Bajo |
| Temperatura de fusionado fuera de 150–155°C → alerta + inspección obligatoria del paquete | 0% | Validación en endpoint F5: si temperatura fuera de rango → marcar paquete `inspeccion_obligatoria=True` | Bajo |

> Todas son de esfuerzo **Bajo** individualmente — son checks de 5–10 líneas en los endpoints. El costo real es crear las entidades que las soportan.

---

## Resumen por paso: qué modificar vs. qué agregar

### Modificaciones sobre código existente

| Archivo | Cambio | Esfuerzo |
|---|---|---|
| `models/fase.py` — `OFFaseEstado` | Agregar `operador_id FK → usuarios`, `refilados_cuchilla Integer` | Bajo |
| `models/of.py` — `EstadoOF` | Agregar estados `EN_HABILITADO`, `EN_CALIDAD` | Bajo |
| `services/corte_service.py` | Transiciones automáticas al nuevo estado al completar F3 y F6 | Bajo |
| `templates/corte/seguimiento.html` — modal F1 | Input eficiencia + alerta visual + campo justificación supervisor | Bajo |
| `templates/corte/seguimiento.html` — modal F2 | Campos mesa, capas, metraje + checkbox orillo (condicional INSTITUCIÓN) | Bajo |
| `templates/corte/seguimiento.html` — modal F3 | Select operario + contador refilados | Bajo |
| `templates/corte/seguimiento.html` — modal F5 | Input temperatura aplicada + alerta 150–155°C + select máquina | Bajo |
| `templates/corte/seguimiento.html` — F6/F7 | Sección de paquetes: inspección por paquete, V°B°, despacho | Alto |
| Telegram Bot | Cron diario 18:00 con resumen de avance por OF | Bajo |

### Entidades nuevas que agregar

| Entidad | Atributos clave | Migración | Esfuerzo |
|---|---|---|---|
| `Trazo` | of_id, archivo_ruta, versión, hash, largo, ancho, eficiencia, capas, áreas_fusionado, estado | ✅ nueva tabla | Alto |
| `Tendido` | trazo_id, mesa, capas_reales, metraje_consumido, rollos_json, orillo_tratado, operador_id | ✅ nueva tabla | Medio |
| `Paquete` | of_id, talla, cantidad, correlativo_inicio, correlativo_fin, requiere_fusionado, estado | ✅ nueva tabla | Alto |
| `PruebaFusionado` | of_id, temperatura_medida, resultado, inspector_id, fecha | ✅ nueva tabla | Bajo |
| `InspeccionCalidad` | paquete_id, resultado, checklist_json, motivo_nc, foto_ruta, inspector_id, vobo_timestamp | ✅ nueva tabla | Medio |
| `DespachoCostura` | of_id, receptor_id, fecha, acuse_timestamp, paquetes_despachados | ✅ nueva tabla | Medio |

---

## Plan de desarrollo — sprints para este alcance

### Sprint 1 — 1 semana — "Exponer lo que ya está en la base de datos"
Sin crear entidades nuevas, solo UI y lógica menor:

- Modal F1: input eficiencia + alerta <85% / >87% + campo justificación supervisor
- Modal F2: checkbox orillo (condicional INSTITUCIÓN) + campos mesa y capas
- Modal F3: select operario + contador refilados
- Modal F5: input temperatura + alerta fuera de 150–155°C
- `OFFaseEstado`: agregar `operador_id` + migración
- `EstadoOF`: agregar `EN_HABILITADO`, `EN_CALIDAD` + migración + transiciones auto en `corte_service`
- Cron Telegram diario de avance
- **Sube: 28% → 40%**

---

### Sprint 2 — 2–3 semanas — "Paquetes: el eje que desbloquea F y E"
La entidad más crítica del módulo:

- Modelo `Paquete` + migración + estados
- Endpoint generar paquetes desde F4 (Numerado) con correlativo automático por talla
- Generación de ticket PDF con QR (`qrcode` + `weasyprint`)
- Modelo `PruebaFusionado` + endpoint + UI en F5
- Bloqueo de F5 sin prueba conforme
- Derivación automática `requiere_fusionado` → estado inicial del paquete
- **Sube: 40% → 57%**

---

### Sprint 3 — 2 semanas — "Calidad y cierre del ciclo"
Cerrar el flujo hasta Costura:

- Modelo `InspeccionCalidad` por paquete + checklist + foto
- V°B° digital: endpoint inmutable `POST /paquete/{id}/vobo` → estado APROBADO
- Flujo de reproceso: paquete NC → historial + regresa a HABILITADO
- Modelo `DespachoCostura` + endpoint + UI de selección/escaneo de paquetes
- Validaciones bloqueantes: despacho sin APROBADO, fusionado sin prueba
- **Sube: 57% → 72%**

---

### Sprint 4 — 2 semanas — "Trazo como entidad y tendido completo"
Cerrar las etapas C y D:

- Modelo `Trazo` + adjunto archivo Marker + hash SHA256 + versión + eficiencia
- Modelo `Tendido` + parámetros máquina + rollos consumidos
- Validación: eficiencia fuera de rango → bloqueo + justificación supervisor
- UI de registro de trazo antes de iniciar F1
- Botón "Imprimir guía" del trazo
- **Sube: 72% → 82%**

---

## Resumen de esfuerzo

| Sprint | Duración | % ganado | Acumulado | Riesgo |
|---|---|---|---|---|
| Base actual | — | — | 28% | — |
| Sprint 1 — UI campos pendientes + nuevos estados | 1 semana | +12% | 40% | Bajo |
| Sprint 2 — Paquetes + fusionado | 2–3 semanas | +17% | 57% | Medio |
| Sprint 3 — Calidad + despacho Costura | 2 semanas | +15% | 72% | Medio |
| Sprint 4 — Trazo + Tendido como entidades | 2 semanas | +10% | 82% | Bajo |
| **Total** | **~8 semanas** | | **82%** | |

> El 18% restante para el 100% corresponde a: repositorio de moldes de Modelaje (depende de otro módulo), integración con carpeta compartida de Marker/Marquesil (infraestructura IT), y soporte de hardware industrial (impresoras ZPL, PDAs offline). Estos tienen dependencias externas al equipo de desarrollo.
