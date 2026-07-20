# Diseño — Módulo de Paquetes / Hoja de numeración

Modelo de datos (normalizado, 3FN) y plan de implementación para el numerado por
paquetes, el corte real y el flujo Numerado → Habilitado → Calidad → Entregado.

---

## 1. Principios de normalización aplicados

- **Nada derivable se guarda.** El corte real, el `numero_hasta` del rango, el color y el
  texto del sticker **se calculan**, no se almacenan (evita datos repetidos/inconsistentes).
- **Color y talla salen del SKU.** Un paquete referencia `sku_id`; de ahí se obtiene la talla
  (`prenda_skus.talla`) y el color (`prenda_skus → prenda_catalogo.color`). No se guarda color como texto.
- **Estado actual = caché del último evento.** Se guarda `estado` en el paquete para lectura
  rápida y el detalle (quién/cuándo) en una tabla de eventos. Es el **mismo patrón** que ya usa
  el sistema (`of_fases_estado`+`avance_registros`, `of_trazos`+`of_trazo_movimientos`).

---

## 2. Tablas nuevas

### `of_paquetes` — un paquete de numeración (1 paquete = 1 talla + 1 color)

| Columna | Tipo | Regla |
|---|---|---|
| `id` | Integer PK | |
| `of_id` | Integer FK → `ordenes_fabricacion.id` (CASCADE), index, NOT NULL | |
| `sku_id` | Integer FK → `prenda_skus.id` (NO ACTION), NOT NULL | define talla + color (vía variante) |
| `numero` | Integer NOT NULL | nº de paquete dentro de la OF (etiqueta del sticker) |
| `numero_desde` | Integer NOT NULL | inicio del rango de numeración |
| `cantidad` | Integer NOT NULL | unidades del paquete (`hasta = desde + cantidad − 1`, **derivado**) |
| `estado` | String(15) NOT NULL, default `NUMERADO` | caché del último evento |
| `created_at` / `updated_at` | DateTime | |

Restricciones: `UniqueConstraint(of_id, numero)` · `Index(of_id, sku_id)` · `cantidad > 0`.

**No se guarda:** `numero_hasta` (derivado), `color`/`talla` (vía `sku_id`), `corte_real`
(suma), texto del sticker (derivado).

### `of_paquete_eventos` — historial/auditoría del flujo del paquete

| Columna | Tipo | Regla |
|---|---|---|
| `id` | Integer PK | |
| `paquete_id` | Integer FK → `of_paquetes.id` (CASCADE), index, NOT NULL | |
| `estado` | String(15) NOT NULL | `NUMERADO` \| `HABILITADO` \| `CALIDAD_OK` \| `CALIDAD_RECHAZO` \| `ENTREGADO` |
| `motivo` | String(200) NULL | para rechazo de calidad |
| `usuario_id` | Integer FK → `usuarios.id` NULL | quién hizo la transición |
| `created_at` | DateTime | cuándo |

El `estado` del paquete = estado del último evento (caché).

## 3. Columna nueva en tabla existente

`ordenes_fabricacion.unidades_por_paquete` — `Integer NULL`. Tope de unidades por paquete
para esa OF (override). Si es NULL, se usa el default global `UNIDADES_POR_PAQUETE_DEFAULT`
(constante, p. ej. 49). Mismo patrón que `max_capas` (tope de capas por placa).

---

## 4. Datos derivados (calculados, nunca guardados)

| Dato | Cálculo |
|---|---|
| `numero_hasta` de un paquete | `numero_desde + cantidad − 1` |
| Talla del paquete | `paquete.sku.talla` |
| Color del paquete | `paquete.sku.prenda_catalogo.color` |
| **Corte real (OF)** | `Σ of_paquetes.cantidad` de la OF |
| Corte real por talla/color | `Σ cantidad` agrupado por `sku_id` |
| **Desvío** | `corte_real − proyectado` (proyectado = curva / `total_juegos`) |
| Sticker/lote (texto) | `f"{numero_of}-{talla}-P{numero} ({desde}-{hasta})"` |

> Si más adelante se necesita un **código escaneable persistente** (QR/barras) del paquete,
> se agrega una columna `codigo_lote` opcional; hoy se deja derivado para no duplicar.

---

## 5. Relación con el modelo actual (decisiones abiertas)

1. **Paquetes vs `of_fases_estado` (F4–F7).** Hoy F4–F7 se llevan por pieza×talla en cantidades.
   El paquete es la unidad real del flujo Numerado→Entrega. **Decisión:** el **estado del paquete**
   pasa a ser la fuente de verdad de Numerado/Habilitado/Calidad/Entregado; el % de esas fases en
   el cockpit se **deriva de los paquetes** (no doble captura). Fusionado (F5) sigue por pieza si
   se necesita ese detalle. → Confirmar antes de codear.
2. **OF multicolor (Brecha 4).** El modelo de paquete ya soporta color vía `sku_id`, **pero** hoy
   una OF apunta a **una** variante (un color). Para OFs de 2+ colores hay que permitir que la
   curva/distribución tenga SKUs de **más de una variante**. → Decidir si se aborda ahora o después.
3. **Corte real > proyectado.** El numerado **debe permitir** exceder lo proyectado (sobró tela),
   al revés que las placas. La validación de "no exceder pedido" **no aplica** al numerado.

---

## 6. Plan de implementación (por fases)

**P1 · Modelo + migración**
- Modelos `OFPaquete` y `OFPaqueteEvento`; constante `UNIDADES_POR_PAQUETE_DEFAULT`.
- Columna `unidades_por_paquete` en `ordenes_fabricacion`.
- Migración Alembic (crea 2 tablas + 1 columna).

**P2 · Servicio `paquete_service`**
- `generar_paquetes(of, reales_por_sku, size, usuario)`: arma paquetes por talla/color, rangos
  correlativos, valida 1 talla/color por paquete, admite real ≠ proyectado; registra evento `NUMERADO`.
- `set_estado_paquete(paquete_id, estado, usuario, motivo=None)`: transición + evento (con cascada:
  no entregar sin calidad OK, etc.).
- Lecturas: `corte_real(of)`, `corte_real_por_talla(of)`, `resumen_desvio(of)`.

**P3 · Router `/paquetes`**
- Página del módulo + `data` (paquetes, reales por talla, desvío), `generar`, `estado` por paquete,
  `stickers` (imprimible). Auth por rol (numerador/corte/calidad).

**P4 · Frontend**
- Pantalla de **captura** (unidades por paquete + reales por talla/color + preview de rangos) — el mockup.
- **Lista de paquetes** con el flujo por paquete (stepper Numerado→Habilitado→Calidad→Entregado).
- Enganche desde el cockpit: fase **Numerado → módulo de paquetes** (igual que Tizado→Placas).

**P5 · Integración con el cockpit**
- Derivar el % de F4–F7 del estado de los paquetes; evitar doble captura.

**P6 · Alertas de desvío (Brecha 6)**
- Cuando `corte_real ≠ proyectado`: alerta en el módulo + aviso a PCP/costura (WS / Telegram).

**P7 · Reportes**
- Hoja de numeración (paquetes + rangos) en la **ficha PDF** y en el **Excel de placas/OF**.

**P8 · Tests + verificación**
- Generación de paquetes (split por tamaño, rangos correlativos, multicolor), transiciones de estado
  con cascada, cálculo de corte real y desvío.

---

## 7. Resumen del modelo (ERD textual)

```
ordenes_fabricacion (+ unidades_por_paquete)
        │ 1
        │ N
   of_paquetes ── sku_id ──► prenda_skus ──► prenda_catalogo (color)
        │ 1
        │ N
 of_paquete_eventos ── usuario_id ──► usuarios
```

Corte real, desvío, rangos, color y sticker = **derivados**. Sin columnas redundantes.
