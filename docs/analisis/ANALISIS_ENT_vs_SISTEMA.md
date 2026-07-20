# Análisis ENT vs. Sistema Actual — Módulo de Corte
**Documento base:** ENT_Modulo_Corte_Samitex_v1.docx  
**Alcance:** OF formalizada + insumos listos → piezas despachadas a Costura  
**Fecha:** Julio 2026

---

## Avance global contra la ENT

```
█████░░░░░░░░░░░░░░░  27%
```

> La ENT es mucho más específica que el SRS general. Define entidades concretas, una máquina de estados completa, validaciones bloqueantes y requisitos de hardware. Eso explica por qué el % baja del 58% (SRS) al 27% (ENT).

| Sección ENT | % logrado | Semáforo |
|---|---|---|
| Etapa A — OF creation y formalización | 40% | 🟡 |
| Etapa B — Picking y nota de salida | 5% | 🔴 |
| Etapa C — Trazado | 15% | 🔴 |
| Etapa D — Tendido y corte | 30% | 🔴 |
| Etapa E — Habilitado y fusionado | 35% | 🟡 |
| Etapa F — Calidad y despacho | 20% | 🔴 |
| Máquina de estados OF (8 estados) | 30% | 🔴 |
| Máquina de estados Paquete (6 estados) | 0% | 🔴 |
| Modelo de datos (13 entidades nuevas) | 20% | 🔴 |
| Validaciones bloqueantes (7.3) | 10% | 🔴 |
| KPIs del módulo | 15% | 🔴 |
| Hardware + integraciones | 5% | 🔴 |
| **Total ponderado** | **27%** | 🔴 |

---

## Etapa A — Creación y formalización de la OF — 40%

```
████████░░░░░░░░░░░░  40%
```

| Paso ENT | Estado | Brecha | Esfuerzo |
|---|---|---|---|
| A1 · OF vinculada a requerimiento, correlativo automático | 🟡 60% | La OF existe; el correlativo se ingresa manual; no hay relación formal con entidad Requerimiento | Bajo |
| A2 · Ficha técnica y HdC asociadas con versión bloqueada | 🟡 60% | Gates requieren estos docs; la versión NO queda bloqueada (se puede cambiar el archivo) | Bajo |
| A3 · Imprimir OF en PDF estandarizado + log de impresión | 🟡 40% | PDF de reporte de corte existe; no hay PDF de OF formal ni log de impresión | Medio |
| A4 · Formalizar por correo: destinatarios, fecha/hora → estado FORMALIZADA | ❌ 0% | No existe. Solo Telegram. Sin estado FORMALIZADA ni registro de envío | Medio |
| A5 · Entregar OF a Almacén con acuse → estado EN ALMACÉN | ❌ 0% | No existe este paso ni este estado | Bajo |

**Qué modificar:** agregar estados `FORMALIZADA` y `EN ALMACÉN` al enum `EstadoOF` + migración Alembic + endpoints de transición + integración SMTP correo.

---

## Etapa B — Picking y nota de salida — 5%

```
█░░░░░░░░░░░░░░░░░░░  5%
```

| Paso ENT | Estado | Brecha | Esfuerzo |
|---|---|---|---|
| B1 · Pickear tela con escaneo QR de rollos, metraje por rollo asignado a OF | ❌ 0% | No existe picking ni entidad Rollo | Muy alto |
| B2 · Pickear avíos según OF, alerta por faltantes | ❌ 0% | No existe | Alto |
| B3 · Emitir nota de salida → estado INSUMOS DESPACHADOS | ❌ 0% | No existe NotaSalida ni LineaInsumo | Alto |
| B4 · Descargar stock automáticamente (+ conciliación SAP) | ❌ 0% | No existe stock ni integración SAP | Muy alto |

**Alternativa mínima viable (esfuerzo Bajo):** Un botón en la OF "Confirmar insumos recibidos en planta" con usuario y timestamp. No requiere Rollo ni kardex. Cumple la precondición P4 de forma simplificada y habilita el flujo hacia Trazado.

**Qué agregar:** entidades `NotaSalida`, `LineaInsumo`, `Rollo` (simplificado sin kardex completo) + endpoints + UI de picking simple.

---

## Etapa C — Trazado — 15%

```
███░░░░░░░░░░░░░░░░░  15%
```

| Paso ENT | Estado | Brecha | Esfuerzo |
|---|---|---|---|
| C1 · Recibir variantes por talla de Modelaje (versión vigente) | ❌ 0% | No hay repositorio de moldes ni entidad Variante | Muy alto |
| C2 · Agrupar variantes por talla/cantidad según programa y curva de tallas | 🟡 20% | Curva de tallas existe; no hay agrupación formal para el trazo | Medio |
| C3 · Crear trazo: adjuntar archivo + metadatos (largo, ancho, capas propuestas) | ❌ 10% | F1=Tizado registra piezas; no hay entidad `Trazo` ni adjunto de archivo Marker | Alto |
| C4 · Registrar eficiencia: obligatorio, alerta <85% o >87%, justificación supervisor | 🟡 30% | Campo `eficiencia_tizado` existe en DB; sin UI, sin alerta, sin bloqueo supervisor | Bajo |
| C5 · Bloquear áreas de fusionado dentro del trazo | ❌ 0% | No existe | Medio |
| C6 · Publicar trazo a carpeta compartida con hash y versión controlada | ❌ 0% | No existe | Medio |

**Qué agregar:** entidad `Trazo` (of_id, archivo, versión, hash, largo, ancho, eficiencia, áreas_fusionado) + migración + endpoints + UI en seguimiento.  
**Qué modificar:** agregar input de eficiencia en UI de F1 + lógica de alerta + campo justificación supervisor.

---

## Etapa D — Tendido y corte — 30%

```
██████░░░░░░░░░░░░░░  30%
```

| Paso ENT | Estado | Brecha | Esfuerzo |
|---|---|---|---|
| D1 · Imprimir guía visual del trazo + log de impresión | ❌ 0% | No existe | Bajo |
| D2 · Parámetros de máquina: velocidad, presión, capas, plantillas por tela | ❌ 0% | No existe. El modelo no tiene tabla de parámetros de máquina | Medio |
| D3 · Registrar tendido: mesa, capas reales, rollos escaneados, metraje consumido | 🟡 10% | F2=Tendido registra cantidad de piezas; sin mesa, capas, rollos, metraje | Medio |
| D4 · Tratamiento de orillo (solo Instituciones) | 🟡 30% | Campo `tratamiento_orillo` en DB; sin UI ni condicional por canal | Bajo |
| D5 · Registrar corte: inicio/fin, operador, incidencias → estado CORTADO | 🟡 50% | F3=Corte existe; `OFFaseTiempos` tiene inicio/fin real; sin operador ni incidencias | Bajo |
| D6 · Contador de refilados de cuchilla | ❌ 0% | No existe | Bajo |

**Qué agregar:** entidad `Tendido` (trazo_id, mesa, capas, rollos[], metraje_consumido, orillo_tratado, operador) + entidad `ParametrosMaquina` o JSON en Corte.  
**Qué modificar:** agregar `operador_id` FK a `OFFaseEstado` o nueva entidad `Corte`; exponer campos D4/D5 en UI de seguimiento.

---

## Etapa E — Habilitado y fusionado — 35%

```
███████░░░░░░░░░░░░░  35%
```

| Paso ENT | Estado | Brecha | Esfuerzo |
|---|---|---|---|
| E1 · Numerar piezas: correlativo por trazo/capa/talla, trazabilidad pieza→paquete→OF | 🟡 30% | F4=Numerado existe y registra cantidad; sin correlativo per capa/talla ni vínculo a trazo | Medio |
| E2 · Habilitar paquetes 1:1 (40 piezas): talla, cantidad, correlativos → estado HABILITADO | ❌ 0% | No existe entidad Paquete | Alto |
| E3 · Emitir ticket de paquete con QR: OF, estilo, talla, cantidad, correlativo | ❌ 0% | No existe generación QR ni impresión de tickets | Alto |
| E4 · Derivar a fusionado condicionalmente (según ficha técnica) | 🟡 60% | `OFPieza.fusionado` flag existe; la derivación es manual, no hay flujo automático | Bajo |
| E5 · Validar temperatura previa: prueba, resultado, inspector → bloquea E6 si no conforme | 🟡 25% | Campo `temperatura_fusion` en DB; sin entidad PruebaFusionado ni bloqueo | Medio |
| E6 · Fusionar a 150–155°C: temperatura aplicada, máquina, operador; alerta fuera de rango | 🟡 20% | F5=Fusionado registra avance; sin temperatura UI, sin alerta, sin máquina/operador | Bajo |

**Qué agregar:** entidad `Paquete` (of_id, talla, cantidad, correlativos, estado, requiere_fusionado) + `PruebaFusionado` + `EventoFusionado` + generación QR (librería `qrcode`) + endpoint de impresión de ticket PDF.  
**Qué modificar:** agregar inputs de temperatura/máquina/operador en UI de F5 + validación bloqueante.

---

## Etapa F — Calidad y despacho a Costura — 20%

```
████░░░░░░░░░░░░░░░░  20%
```

| Paso ENT | Estado | Brecha | Esfuerzo |
|---|---|---|---|
| F1 · Inspección por paquete: checklist configurable, conforme/no conforme, foto | 🟡 20% | F6=Calidad existe con `motivo_rechazo`; sin inspección por paquete, sin checklist, sin foto | Alto |
| F2 · Reproceso: paquete NC regresa a HABILITADO con historial | ❌ 10% | El campo `motivo_rechazo` existe; sin flujo de reproceso ni historial por paquete | Medio |
| F3 · V°B° digital: usuario, fecha, hora → evento inmutable → estado APROBADO | ❌ 0% | No existe. El sistema completa fases pero sin V°B° formal | Medio |
| F4 · Despacho a Costura: escaneo tickets, acuse de Costura → estado DESPACHADO | ❌ 0% | No existe entidad DespachoCostura ni acuse | Medio |
| F5 · Reporte diario automático a Planeamiento: paquetes cortados/aprobados/despachados vs. programa | 🟡 30% | WebSocket + semáforo en tiempo real existen; sin reporte diario automático | Bajo |

**Qué agregar:** entidad `InspeccionCalidad` (paquete_id, resultado, motivo, evidencia_foto, inspector, vobo) + entidad `DespachoCostura` + endpoint de V°B° inmutable + trigger de reporte diario vía Telegram.  
**Qué modificar:** F6=Calidad en seguimiento.html → vincular a Paquete en lugar de pieza genérica.

---

## Máquina de estados — brechas

### OF — 30% cubierto

| Estado ENT | Estado actual | Existe |
|---|---|---|
| CREADA | BORRADOR | 🟡 equivalente |
| FORMALIZADA | — | ❌ |
| EN ALMACÉN | — | ❌ |
| INSUMOS DESPACHADOS | — | ❌ |
| EN CORTE | EN_PROCESO | 🟡 equivalente |
| EN HABILITADO | — | ❌ |
| EN CALIDAD | — | ❌ |
| COMPLETADA | COMPLETADA | ✅ |

**Qué modificar:** extender el enum `EstadoOF` de 4 a 8 valores + migración + actualizar toda la lógica de transición en `of_service.py` + actualizar los templates que muestran estado.

### Paquete — 0% cubierto

La entidad Paquete no existe. Sus 6 estados (HABILITADO → EN FUSIONADO → EN INSPECCIÓN → NO CONFORME / APROBADO → DESPACHADO) son todos nuevos.

---

## Modelo de datos — entidades nuevas requeridas

| Entidad ENT | Estado | Esfuerzo de creación |
|---|---|---|
| OF (ampliada: +5 estados, +FK requerimiento, +FK ficha) | 🟡 60% existe | Bajo (migración + ajustes) |
| NotaSalida | ❌ 0% | Medio |
| LineaInsumo | ❌ 0% | Medio |
| Rollo (simplificado) | ❌ 0% | Medio |
| Trazo | ❌ 5% | Medio |
| Tendido | ❌ 5% | Medio |
| Corte (entidad separada con parámetros) | ❌ 10% | Medio |
| Paquete | ❌ 0% | Alto |
| PruebaFusionado | 🟡 20% (campo en OFFaseEstado) | Bajo |
| EventoFusionado | ❌ 0% | Bajo |
| InspeccionCalidad (por paquete) | 🟡 15% (campo motivo_rechazo) | Medio |
| DespachoCostura | ❌ 0% | Medio |
| EstatusDiario | ❌ 0% | Bajo |

---

## Validaciones bloqueantes (§7.3) — 10%

| Regla ENT | Estado | Esfuerzo |
|---|---|---|
| Nota de salida bloqueada si OF no está FORMALIZADA | ❌ 0% | Bajo (si existen los estados) |
| Fusionado bloqueado sin prueba de temperatura conforme | ❌ 0% (campo existe, sin validación) | Bajo |
| Despacho a Costura bloqueado sin paquete APROBADO | ❌ 0% | Bajo (si existe Paquete) |
| Eficiencia de trazo fuera de rango exige justificación supervisor | ❌ 0% (campo existe, sin bloqueo) | Bajo |
| Temperatura de fusionado fuera de 150–155°C alerta + inspección obligatoria | ❌ 0% | Bajo |
| Metraje tendido no puede exceder metraje de nota de salida | ❌ 0% | Bajo (si existen las entidades) |

> Todas las validaciones son de esfuerzo Bajo individualmente — son simples checks en los endpoints. El costo real es crear las entidades que las soportan.

---

## KPIs del módulo (§7.4) — 15%

| KPI | Estado | Esfuerzo |
|---|---|---|
| Eficiencia de trazo % | 🟡 20% — campo en DB, sin dashboard | Bajo |
| Cumplimiento de programa (paquetes a tiempo) | ❌ 0% — no hay Paquete ni programa formal | Alto |
| Tasa de no conformidad (NC/inspeccionados) | ❌ 0% | Medio (si existe InspeccionCalidad) |
| Tasa de reproceso | ❌ 0% | Medio |
| Lead time OF→Costura | 🟡 20% — fechas en modelo, sin cálculo | Bajo |
| Consumo real vs. teórico de tela | ❌ 0% — requiere BOM + Tendido | Alto |

---

## Hardware e integraciones — 5%

| Elemento | Estado | Esfuerzo |
|---|---|---|
| PDA/lector QR en planta | ❌ App no está optimizada para PDA | Medio (responsive + offline) |
| Impresora térmica de tickets (ZPL) | ❌ No existe integración | Alto |
| Impresora etiquetas de rollo | ❌ No existe | Alto |
| PC en sala de trazado (acceso a Marker) | ➖ Lectura de archivos desde carpeta compartida | Medio |
| Terminal en mesa de corte | ❌ No existe UI específica para tablet | Medio |
| Marker/Marquesil (lectura metadatos por carpeta) | ❌ No existe | Medio |
| SAP (descarga de stock) | ❌ No existe | Muy alto |
| SMTP correo (formalización OF + alertas) | ❌ Solo Telegram | Bajo |
| Repositorio de moldes (versión vigente) | ❌ No existe | Medio |

---

## Plan de desarrollo para llegar al 80%

### Sprint 1 — 1 semana — "Cerrar lo que está a medias"
**Objetivo:** exponer los campos que ya están en DB + nueva máquina de estados OF

- Agregar estados `FORMALIZADA`, `EN ALMACÉN`, `INSUMOS DESPACHADOS`, `EN HABILITADO`, `EN CALIDAD` al enum EstadoOF + migración
- Exponer en UI de seguimiento: eficiencia tizado + alerta visual (<85%), tratamiento orillo, temperatura fusionado, operador F3
- Botón "Confirmar insumos recibidos" en OF (alternativa mínima a Etapa B)
- Integración SMTP para formalización de OF (paso A4)
- Trigger diario Telegram con resumen de avance por OF (paso F5)
- **Sube: 27% → 38%**

---

### Sprint 2 — 2–3 semanas — "Paquetes: el desbloqueador crítico"
**Objetivo:** implementar la entidad Paquete y todo lo que depende de ella

- Modelo `Paquete` + estados + migración
- Endpoint crear paquetes desde F4 (Numerado) con correlativo automático
- Generación de ticket PDF con QR (`qrcode` + `weasyprint`)
- `InspeccionCalidad` por paquete: checklist, resultado, motivo
- V°B° digital: evento inmutable con usuario/fecha/hora → estado APROBADO
- `DespachoCostura`: escaneo de tickets + acuse → estado DESPACHADO
- Flujo de reproceso: paquete NC → vuelve a HABILITADO con historial
- **Sube: 38% → 58%**

---

### Sprint 3 — 2 semanas — "Trazo y Tendido como entidades"
**Objetivo:** dar cuerpo a las etapas C y D con entidades propias

- Modelo `Trazo` (adjunto archivo, versión, hash, largo, ancho, eficiencia, áreas_fusionado)
- Modelo `Tendido` (trazo_id, mesa, capas, metraje_consumido, rollos[], orillo_tratado, operador)
- Validación bloqueante: eficiencia <85% exige justificación de supervisor
- Validación: metraje tendido ≤ metraje nota de salida
- `PruebaFusionado` como entidad separada + bloqueo de F5 si no conforme
- **Sube: 58% → 72%**

---

### Sprint 4 — 3 semanas — "NotaSalida y hardware básico"
**Objetivo:** cubrir Etapa B y UI para planta

- `NotaSalida` + `LineaInsumo` (sin kardex completo, sin integración SAP)
- `Rollo` simplificado: código QR, metraje, estado (disponible/usado)
- UI responsive optimizada para tablet/PDA (ajustes CSS, inputs grandes)
- Generación de etiqueta de rollo (PDF simple con QR)
- Endpoint de impresión a impresora térmica (ZPL básico o PDF directo)
- **Sube: 72% → 80%**

---

## Resumen de esfuerzo total

| Sprint | Duración | % ganado | Acumulado |
|---|---|---|---|
| Base actual | — | — | 27% |
| Sprint 1 — Estados + campos pendientes | 1 semana | +11% | 38% |
| Sprint 2 — Paquetes (desbloqueador crítico) | 2–3 semanas | +20% | 58% |
| Sprint 3 — Trazo + Tendido como entidades | 2 semanas | +14% | 72% |
| Sprint 4 — NotaSalida + hardware básico | 3 semanas | +8% | 80% |
| **Total** | **~9 semanas** | | **80%** |

> El 20% restante para llegar al 100% corresponde principalmente a: integración SAP (Muy alto), repositorio de moldes de Modelaje (depende de otro módulo), y soporte completo de hardware industrial (impresoras ZPL, PDAs offline-first). Estos tienen dependencias externas que están fuera del control del desarrollo de software.
