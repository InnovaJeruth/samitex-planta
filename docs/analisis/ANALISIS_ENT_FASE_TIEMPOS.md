# Análisis ENT — Alcance: Cumplimiento de Fase + Tiempos
**Premisa:** OF activa, insumos en planta.  
**Scope:** Solo registrar si cada fase se cumplió y cuándo (inicio/fin). Sin data interna de cada fase.

---

## Avance global

```
████████████████░░░░  80%
```

---

## Qué tiene el sistema exactamente para este scope

| Necesidad | Elemento del sistema | Estado |
|---|---|---|
| Marcar inicio de fase | `POST /corte/api/{of_id}/fases/{fase_id}/iniciar` → graba `inicio_real` | ✅ |
| Marcar fase completada | `POST /corte/api/{of_id}/completar-bulk` → graba `fin_real` | ✅ |
| Guardar `inicio_real` y `fin_real` por fase | `OFFaseTiempos` (of_id, fase_id, inicio_real, fin_real) | ✅ |
| Bloqueo secuencial (no iniciar F2 sin F1 iniciada) | Validación en `iniciar_fase()` en `corte_service.py` | ✅ |
| Botón "▶ Iniciar" por fase en UI | `btn-iniciar` en fase-strip de `seguimiento.html` | ✅ |
| Mostrar inicio_real y fin_real en pantalla | Fase-strip muestra `● dd/mm HH:MM → dd/mm HH:MM` | ✅ |
| Estado visual por fase: pendiente / en curso / completada / bloqueada | `.fsc-pendiente`, `.fsc-en_proceso`, `.fsc-completada`, `.fsc-bloqueada` | ✅ |
| F5=Fusionado opcional por pieza | Se omite si `OFPieza.fusionado = False` | ✅ |
| F8=Estampado y F9=Auditoría opcionales | Se omiten si `of.estampado_activo = False` | ✅ |
| Paradas durante una fase con motivo y duración | `OFFaseParada` + UI modal de pausa | ✅ |
| WebSocket: actualización en tiempo real del estado | `ws.py` | ✅ |
| Semáforo de riesgo vs. fecha APT | `semaforo_service.py` | ✅ |

---

## Por fase — cumplimiento

| Fase | Iniciar | Tiempos | Completar | Estado UI | % |
|---|---|---|---|---|---|
| F1 · Tizado | ✅ | ✅ | ✅ | ✅ | 90% |
| F2 · Tendido | ✅ | ✅ | ✅ | ✅ | 90% |
| F3 · Corte | ✅ | ✅ | ✅ | ✅ | 90% |
| F4 · Numerado | ✅ | ✅ | ✅ | ✅ | 90% |
| F5 · Fusionado | ✅ | ✅ | ✅ | ✅ | 90% |
| F6 · Calidad | ✅ | ✅ | ✅ | ✅ | 80% |
| F7 · Habilitado | ✅ | ✅ | ✅ | ✅ | 80% |
| Despacho a Costura (cierre del ciclo) | ❌ | ❌ | ❌ | ❌ | 0% |
| Reporte diario a Planeamiento | 🟡 | — | — | — | 30% |

---

## Las 3 brechas reales para este scope

### ❌ 1. "Completar fase" requiere registrar cantidad de piezas
**El problema:** el botón "Completar" de la UI pide seleccionar piezas y cantidades. Si solo se quiere marcar que una fase terminó (sin contar piezas), el flujo actual es más tedioso de lo necesario.

**Qué modificar:** agregar un botón **"Marcar fase completa"** a nivel de OF (no por pieza) en la fase-strip que llame a `completar-bulk` con todas las piezas a su `max_cantidad` automáticamente. Un clic, fase cerrada, `fin_real` grabado.

**Esfuerzo:** Bajo (3–4 horas — endpoint ya existe, solo es un botón en la UI que llama `completar-bulk` con todas las piezas de la fase).

---

### ❌ 2. No hay evento de cierre "Despacho a Costura"
**El problema:** cuando F7=Habilitado se completa, la OF pasa a COMPLETADA pero no hay ningún evento formal de "estas piezas salieron a Costura en esta fecha y las recibió esta persona". Para el reporte de Planeamiento es importante saber cuándo salió físicamente.

**Qué agregar:** un botón **"Despachar a Costura"** en la OF completa que grabe `fecha_despacho_costura` y `despachado_por` en la OF (2 campos nuevos, sin entidad Paquete). Simple timestamp.

**Esfuerzo:** Bajo (campo en OF + migración + botón en detalle + endpoint — 1 día).

---

### ❌ 3. Reporte diario automático a Planeamiento — 30%
**El problema:** el avance existe en tiempo real vía WebSocket, pero Planeamiento tiene que entrar al sistema para verlo. El ENT pide que el sistema lo envíe automáticamente al cierre del día.

**Qué modificar:** agregar una tarea cron (18:00 diario) en el Telegram Bot existente que itere las OFs activas y envíe: OF, qué fases están completas, qué fases están en curso, semáforo de riesgo.

**Esfuerzo:** Bajo (el Bot ya existe, es configurar un cron job — 1 día).

---

## Resumen

| Brecha | Acción | Esfuerzo |
|---|---|---|
| "Completar fase" sin contar piezas | Botón "Marcar completa" en fase-strip → llama completar-bulk automático | Bajo — 4 horas |
| Sin evento de despacho a Costura | 2 campos en OF + botón + endpoint | Bajo — 1 día |
| Sin reporte diario a Planeamiento | Cron 18:00 en Telegram Bot | Bajo — 1 día |

**Total para llegar al 95%: ~3 días de trabajo.**

El sistema ya tiene la infraestructura completa — fases definidas, endpoints de inicio/fin, tiempos reales grabados, UI con estados visuales. Solo falta pulir el UX del cierre de fase y agregar el evento final de despacho.
