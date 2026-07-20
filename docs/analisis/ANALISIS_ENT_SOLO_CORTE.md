# Análisis ENT — Solo Proceso de Corte
**Premisa:** La OF ya existe y está activa. Los insumos ya están en planta.  
**Alcance:** Trazado → Tendido → Corte → Numerado → Fusionado → Calidad → Despacho a Costura  
**Referencia ENT:** Etapas C, D, E, F

---

## Avance global

```
████░░░░░░░░░░░░░░░░  22%
```

| Etapa | Pasos | % |
|---|---|---|
| C · Trazado | C1–C6 | 10% |
| D · Tendido y corte | D1–D6 | 18% |
| E · Habilitado y fusionado | E1–E6 | 28% |
| F · Calidad y despacho | F1–F5 | 14% |

---

## Base existente que sí aplica al proceso de corte

| Qué tiene el sistema | Cubre |
|---|---|
| Fases F1–F7 con avance por pieza, cantidad y fechas | Columna vertebral del flujo |
| `OFFaseTiempos` — inicio/fin real por fase | D5, E6 parciales |
| `OFFaseParada` — paradas con motivo y duración | D5 incidencias |
| `OFPieza.fusionado` flag por pieza | E4 derivación |
| `eficiencia_tizado` Float en DB | C4 — sin UI |
| `temperatura_fusion` Float en DB | E5/E6 — sin UI |
| `tratamiento_orillo` Boolean en DB | D4 — sin UI |
| `motivo_rechazo` Text en DB | F1 — sin UI |
| UI seguimiento: tabs de fase, bulk, historial | Base para toda la UI de planta |
| WebSocket + semáforo en tiempo real | F5 parcial |
| PDF reporte de corte | F5 parcial |

---

## C · Trazado — 10%

```
██░░░░░░░░░░░░░░░░░░  10%
```

| Paso | % | Qué falta | Acción | Esfuerzo |
|---|---|---|---|---|
| C1 · Recibir variantes por talla de Modelaje | 0% | No hay repositorio de archivos de variantes | Agregar sección de upload de variantes por talla en la OF (por ahora sin Modelaje) | Medio |
| C2 · Agrupar variantes por talla/cantidad según curva | 20% | Curva de tallas existe; no hay agrupación formal para el trazo | Usar `CurvaTallasDetalle` para generar la matriz talla×cantidad automáticamente | Medio |
| C3 · Crear trazo: adjuntar archivo Marker + largo, ancho, capas | 10% | F1 registra piezas pero no hay entidad `Trazo` ni adjunto | **Agregar** modelo `Trazo` (of_id, archivo, versión, hash, largo, ancho, capas, eficiencia, estado) + upload + UI | Alto |
| C4 · Eficiencia obligatoria; alerta si <85% o >87%; justificación supervisor | 30% | Campo `eficiencia_tizado` en DB; sin input en UI, sin alerta, sin bloqueo | **Modificar** modal F1: agregar input eficiencia + alerta roja + campo justificación condicional | Bajo |
| C5 · Bloquear áreas de fusionado en el trazo | 0% | No existe | Agregar campo `areas_fusionado` JSON en entidad Trazo | Bajo |
| C6 · Publicar trazo a carpeta compartida con versión y hash | 0% | No existe integración con sistema de archivos | Agregar campo `publicado_en` + hash SHA256 al guardar; carpeta = infraestructura IT | Medio |

---

## D · Tendido y corte — 18%

```
████░░░░░░░░░░░░░░░░  18%
```

| Paso | % | Qué falta | Acción | Esfuerzo |
|---|---|---|---|---|
| D1 · Imprimir guía visual del trazo + log | 0% | No existe | Botón "Imprimir guía" → PDF del trazo + registro `impreso_por/at` | Bajo |
| D2 · Parámetros de máquina: velocidad, presión, capas, plantillas | 0% | No existe ninguna tabla de parámetros | **Agregar** campos JSON de parámetros en entidad `Tendido` o tabla `ParametrosMaquina` | Medio |
| D3 · Tendido: mesa, capas reales, rollos, metraje consumido | 10% | F2 registra solo cantidad de piezas; sin mesa ni capas | **Agregar** modelo `Tendido` (trazo_id, mesa, capas_reales, metraje_consumido, operador_id) | Medio |
| D4 · Orillo de marca (solo INSTITUCIÓN) | 30% | `tratamiento_orillo` en DB; sin input UI ni condicional por canal | **Modificar** modal F2: checkbox orillo visible solo si `tipo_cliente == INSTITUCIÓN` | Bajo |
| D5 · Corte: inicio/fin real, operador, incidencias → CORTADO | 50% | `OFFaseTiempos` existe; `OFFaseParada` existe; sin `operador_id` en fase | **Modificar** `OFFaseEstado`: agregar FK `operador_id` + migración + select operario en modal F3 | Bajo |
| D6 · Contador refilados de cuchilla (cada 3–4 m) | 0% | No existe | Agregar campo `refilados` Integer en `OFFaseEstado` F3 + botón "+1" en UI | Bajo |

---

## E · Habilitado y fusionado — 28%

```
██████░░░░░░░░░░░░░░  28%
```

| Paso | % | Qué falta | Acción | Esfuerzo |
|---|---|---|---|---|
| E1 · Numerado correlativo por trazo/capa/talla | 30% | F4 registra avance; sin correlativo por talla ni vínculo a trazo | Agregar `correlativo_inicio/fin` en `Paquete`; F4 genera el rango | Medio |
| E2 · Paquetes 1:1 (40 piezas): talla, cantidad, correlativos → HABILITADO | 0% | **No existe entidad Paquete** — es la brecha más crítica | **Agregar** modelo `Paquete` (of_id, talla, cantidad, correlativo_inicio/fin, requiere_fusionado, estado) + endpoints + UI | Alto |
| E3 · Ticket de paquete con QR: OF, talla, cantidad, correlativo | 0% | No existe generación QR | **Agregar** endpoint `/paquete/{id}/ticket` → PDF con QR (`qrcode` + `weasyprint`) | Alto |
| E4 · Derivar a fusionado según ficha técnica | 60% | `OFPieza.fusionado` existe; falta derivación automática sobre el Paquete | **Modificar** creación de Paquete: si `requiere_fusionado` → estado inicial EN_FUSIONADO | Bajo |
| E5 · Prueba de temperatura previa → bloquea E6 si no conforme | 25% | `temperatura_fusion` en DB; sin entidad `PruebaFusionado` ni bloqueo | **Agregar** modelo `PruebaFusionado` (of_id, temperatura_medida, resultado, inspector_id, fecha) + bloqueo en endpoint F5 | Medio |
| E6 · Fusionado 150–155°C: temperatura aplicada, máquina, operario; alerta fuera de rango | 20% | F5 registra avance; sin input temperatura, sin alerta, sin máquina | **Modificar** modal F5: input temperatura + alerta JS (<150 o >155) + select máquina/operario | Bajo |

---

## F · Calidad y despacho — 14%

```
███░░░░░░░░░░░░░░░░░  14%
```

| Paso | % | Qué falta | Acción | Esfuerzo |
|---|---|---|---|---|
| F1 · Inspección por paquete: checklist, conforme/NC, foto | 20% | F6 existe con `motivo_rechazo`; sin inspección por paquete, sin checklist, sin foto | **Agregar** modelo `InspeccionCalidad` (paquete_id, resultado, checklist_json, motivo_nc, foto_ruta, inspector_id) + UI en F6 | Alto |
| F2 · Reproceso: paquete NC → regresa a HABILITADO con historial | 10% | `motivo_rechazo` en DB; sin flujo de retorno ni historial por paquete | **Modificar** endpoint de inspección: si NC → `Paquete.estado = HABILITADO` + insertar evento en historial | Medio |
| F3 · V°B° digital: usuario, fecha, hora → APROBADO (evento inmutable) | 0% | No existe | **Agregar** endpoint `POST /paquete/{id}/vobo` (rol CALIDAD) → inserta registro con timestamp inmutable | Medio |
| F4 · Despacho a Costura: escaneo tickets, acuse → DESPACHADO | 0% | No existe entidad `DespachoCostura` | **Agregar** modelo `DespachoCostura` (paquetes_ids[], receptor_id, fecha, acuse_at) + endpoint + UI escaneo | Medio |
| F5 · Reporte diario automático a Planeamiento | 30% | WebSocket tiempo real existe; sin reporte diario automático | **Modificar** Telegram Bot: cron 18:00 que calcule avance y envíe resumen | Bajo |

---

## Máquina de estados que falta

### OF — desde EN CORTE
| Estado ENT | Sistema actual | ¿Existe? |
|---|---|---|
| EN CORTE | EN_PROCESO | 🟡 equivalente |
| EN HABILITADO | — | ❌ agregar |
| EN CALIDAD | — | ❌ agregar |
| COMPLETADA | COMPLETADA | ✅ |

### Paquete — todo nuevo
`HABILITADO → EN FUSIONADO → EN INSPECCIÓN → NO CONFORME / APROBADO → DESPACHADO`

---

## Validaciones bloqueantes que faltan

| Regla ENT | Acción | Esfuerzo |
|---|---|---|
| Fusionado bloqueado sin prueba de temperatura conforme | Check en endpoint inicio F5: requiere `PruebaFusionado.resultado == CONFORME` | Bajo |
| Despacho bloqueado si paquete no está APROBADO | Filtro en `DespachoCostura`: solo paquetes APROBADO | Bajo |
| Eficiencia fuera de 85–87% exige justificación supervisor | Check en endpoint `Trazo`: si fuera de rango → `justificacion` obligatoria | Bajo |
| Temperatura fuera de 150–155°C → paquete con inspección obligatoria | Flag `inspeccion_obligatoria` en Paquete si fusionado fuera de rango | Bajo |

---

## Entidades nuevas requeridas

| Entidad | ¿Existe? | Esfuerzo |
|---|---|---|
| `Trazo` — archivo, versión, hash, largo, ancho, eficiencia, áreas fusionado | ❌ | Alto |
| `Tendido` — trazo_id, mesa, capas, metraje, rollos, operador | ❌ | Medio |
| `Paquete` — of_id, talla, cantidad, correlativos, estado, requiere_fusionado | ❌ | Alto |
| `PruebaFusionado` — of_id, temperatura, resultado, inspector | ❌ (campo existe en OFFaseEstado) | Bajo |
| `InspeccionCalidad` — paquete_id, resultado, checklist, foto, vobo | ❌ | Medio |
| `DespachoCostura` — paquetes[], receptor, acuse | ❌ | Medio |

---

## Plan de desarrollo

### Sprint 1 — 1 semana — campos en DB ya existentes + nuevos estados OF
- Modal F1 → input eficiencia + alerta + justificación supervisor
- Modal F2 → checkbox orillo (condicional INSTITUCIÓN) + campos mesa/capas
- Modal F3 → select operario + contador refilados
- Modal F5 → input temperatura + alerta 150–155°C
- `OFFaseEstado` → agregar `operador_id` + migración
- `EstadoOF` → agregar `EN_HABILITADO`, `EN_CALIDAD` + migración + transiciones auto en `corte_service.py`
- **28% → 40%**

### Sprint 2 — 2–3 semanas — Paquetes (desbloqueador crítico)
- Modelo `Paquete` + estados + migración
- Generar paquetes desde F4 con correlativo automático por talla
- Ticket PDF con QR por paquete
- Modelo `PruebaFusionado` + bloqueo de F5 sin prueba conforme
- Derivación automática `requiere_fusionado` → estado inicial del paquete
- **40% → 57%**

### Sprint 3 — 2 semanas — Calidad y cierre
- Modelo `InspeccionCalidad` por paquete + checklist + foto
- V°B° digital → endpoint inmutable → estado APROBADO
- Reproceso: NC → historial + regresa a HABILITADO
- Modelo `DespachoCostura` + UI de selección/escaneo
- Validaciones bloqueantes (todas bajo esfuerzo)
- Cron Telegram reporte diario 18:00
- **57% → 74%**

### Sprint 4 — 2 semanas — Trazo y Tendido como entidades
- Modelo `Trazo` + adjunto archivo + hash + versión controlada
- Modelo `Tendido` + parámetros máquina + rollos
- UI de registro de trazo antes de iniciar F1
- Botón "Imprimir guía"
- **74% → 83%**

| Sprint | Duración | Acumulado |
|---|---|---|
| Sprint 1 | 1 semana | 40% |
| Sprint 2 | 2–3 semanas | 57% |
| Sprint 3 | 2 semanas | 74% |
| Sprint 4 | 2 semanas | 83% |
| **Total** | **~8 semanas** | **83%** |

> El 17% restante corresponde a: repositorio de moldes/variantes de Modelaje (depende de otro módulo) e integración con carpeta compartida de Marker/Marquesil (infraestructura IT).
