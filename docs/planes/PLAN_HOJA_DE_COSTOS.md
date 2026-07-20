# Plan — Hoja de Costos: solicitudes, versionado, aprobación y costo real

_Documento de planificación. No se programa nada hasta aprobar este plan._

---

## 1. Objetivo
Que la Hoja de Costos (estimada) se arme con un **flujo por roles** (cada dueño sube su dato), se **versione**, se **apruebe** en dos niveles y quede como **costo oficial**; y que además el sistema calcule el **costo real por OF** para comparar estimado vs real.

---

## 2. Roles y responsabilidades
| Rol | Aporta |
|---|---|
| **Ingeniero de HDC** | Crea la **solicitud** de hoja de costos y arma/consolida. |
| **Logística** | **Precios** de materiales y avíos. |
| **Planta** (ingeniería/jefe) | **Minutaje MOD** (min_std, %efic, costo/min) y **servicios de terceros**. |
| **Gerente de Planta** | Aprobación nivel 1. |
| **Gerente General** | Aprobación final (puede aprobar directo). |

> **Nota:** el rol "Ingeniero de HDC" no existe hoy en el sistema. Hay que **crearlo** (o mapearlo a INGENIERIA). A decidir.

---

## 3. Flujo del módulo "Solicitud de Hoja de Costos"

```
Ingeniero HDC crea SOLICITUD (para una prenda base)
        │
        ├──▶ Tarea LOGÍSTICA: subir/actualizar precios      ┐
        └──▶ Tarea PLANTA: subir/actualizar minutos+servicios ┘  (en paralelo)
                    │  (ambas "listo")
                    ▼
        Sistema ARMA la hoja (borrador) + calcula costo total
                    │
                    ▼
        APROBACIÓN:
          - Gerente de Planta aprueba  → queda PENDIENTE de Gerencia
          - Gerente General aprueba    → HOJA OFICIAL (versión N)
          - (si Gerente General aprueba primero → oficial directo, no requiere Planta)
```

**Estados de la solicitud/hoja:**
`BORRADOR` → `ESPERANDO_DATOS` (logística/planta) → `ARMADA` → `PENDIENTE_APROB` → `APROB_PLANTA` → `OFICIAL`.
Regla de aprobación: **Gerente General = aprobación final** (desde cualquier estado pendiente). **Gerente de Planta solo** deja la hoja en `APROB_PLANTA` (aún necesita Gerencia). Si Gerencia aprueba primero → `OFICIAL` directo.

---

## 4. Plantillas por rol (Excel, como las OFs)
- **Plantilla LOGÍSTICA (precios):** `código material | nombre | precio | moneda | unidad compra | factor | proveedor`.
- **Plantilla PLANTA (minutaje + servicios):**
  - MOD: `operación | min_std | %efic | costo/min`.
  - Servicios: `servicio | costo`.
- **Comportamiento:** subir → **previsualizar** → si la prenda ya tenía hoja, **comparar vs versión anterior** (qué cambió) → confirmar. Mismo patrón que el import de OF.

---

## 5. Versionado y comparativo
- Cada hoja **OFICIAL** es una **versión** (v1, v2, …). Ya existe `HojaCostos.version` y `PrecioHistorico`.
- **Reedición:** una nueva solicitud **parte de la última versión oficial**; logística/planta **confirman "sin cambios" o actualizan**.
- Al armar la nueva versión, el sistema muestra **comparativo vN vs vN+1**: precio/minutos antes → ahora, y el **impacto en el costo total**.

---

## 6. Costo real por OF (estimado vs real)
- Se calcula al producir/cerrar la OF con lo que el sistema **ya captura**:
  - **Tela real** (metraje de trazos), **cantidad real** (paquetes), **merma** (rechazos), **MOD real** (tiempos por fase × costo/min), **servicios reales**.
  - **Precios:** por ahora **estándar** (de la hoja oficial); luego se enchufan los **precios reales de compra** (SOLPED/OC) sin rehacer el cálculo.
- Entrega **costo real por OF** + **comparativo estimado vs real** (desvío).

---

## 7. Modelo de datos (nuevo / a extender)
- **`SolicitudHojaCostos`** (nueva): prenda_base_id, creado_por (Ingeniero HDC), estado, fechas, notas.
- **Tareas por rol** dentro de la solicitud: estado por rol (logística / planta), quién y cuándo cargó.
- **`HojaCostos`** (existe): agregar campos de aprobación en 2 niveles (aprob_planta_por/at, aprob_gerencia_por/at) y el vínculo a la solicitud.
- **Costo real:** un cálculo/tabla por OF (o derivado en vivo) con los componentes reales.
- Reutiliza: `CatalogoMp/Avio/Servicio/Mod`, `PrecioHistorico`, `HojaCostosLinea`.

---

## 8. Bloques de implementación (aprobables por partes)
- **HC-A · Versionado + aprobación 2 niveles.** Estados de la hoja, firma Gerente de Planta + Gerente General con la regla (Gerencia = final; puede aprobar directo). Base de todo.
- **HC-B · Plantillas por rol + carga.** Excel logística (precios) y planta (minutos+servicios), previsualización y comparativo vs versión anterior.
- **HC-C · Módulo de solicitudes.** Ingeniero HDC crea solicitud → tareas a logística/planta → arman la hoja → pasa a aprobación.
- **HC-D · Costo real por OF.** Cálculo desde lo capturado + comparativo estimado vs real. (Precios reales de compra = fase posterior.)

**Orden sugerido:** HC-A → HC-B → HC-C → HC-D (cada uno se apoya en el anterior).

---

## 9. Dudas pendientes para cerrar antes de programar
1. **Rol "Ingeniero de HDC":** ¿lo creamos como rol nuevo o lo mapeamos a INGENIERIA?
2. **Tareas por rol:** ¿Logística y Planta cargan **en paralelo** (ambas a la vez) o hay orden?
3. **Reedición:** ¿la solicitud de reedición la dispara el Ingeniero de HDC manualmente, o se **sugiere automáticamente** cuando llega una OF de una prenda ya costeada?
4. **Precios reales de compra:** ¿de dónde vendrán a futuro (SOLPED/OC de SAP, o carga manual de logística)?
5. **Costo real:** ¿el **costo de minuto** para MOD real es el mismo de la hoja (estándar) o Planta define uno real distinto?
6. **Notificaciones:** ¿avisamos a logística/planta cuando tienen una solicitud pendiente (correo/telegram/en la app)?
