# Plan — Mejorar todo el front-end con la skill `emil-design-eng`

_Aplicar el criterio de diseño (feel, animación, easing, feedback, accesibilidad) a las
38 plantillas del sistema. Todo son cambios de CSS/JS inline en las plantillas — sin
backend, sin BD, sin migraciones. Riesgo bajo (estético/timing), reversible, validación
visual. `login.html` ya se hizo como piloto._

## Principio rector (de la skill)

**No sobre-animar.** Lo que se ve 100×/día no se anima; se prioriza el **feedback de
press**, las **entradas de modales/errores/toasts**, y la **coherencia de easing**. La
regla: `transform`/`opacity` solamente, `ease-out` fuerte, duraciones <300 ms, respetar
`prefers-reduced-motion`, y hover gateado para táctil.

---

## Fase 0 — Fundación de diseño en `base.html`  *(máximo impacto, 1 cambio → todo el sistema)*

`base.html` inyecta el nav, los toasts, `apiFetch`, y los estilos globales que casi todas
las pantallas heredan. Tocar aquí mejora ~90% del sistema de una sola vez.

- **Design tokens** en `:root`: `--ease-out: cubic-bezier(0.23,1,0.32,1)`,
  `--ease-in-out: cubic-bezier(0.77,0,0.175,1)`, y duraciones estándar (`--dur-fast: 140ms`,
  `--dur: 200ms`).
- **Botón global `.btn`**: `:active { transform: scale(0.97) }` + `transition: transform var(--dur-fast) var(--ease-out)`. (Hoy los `.btn` no tienen press feedback.)
- **Hover gateado**: envolver los `:hover` de `.btn`, filas de tabla, chips y links del nav en `@media (hover: hover) and (pointer: fine)`.
- **Toasts** (`showToast`): entrada/salida con `transform`+`opacity` (misma dirección), transición (no keyframes) para que sean interrumpibles; salida más rápida que entrada.
- **Menús del nav** (`.nav-dd-menu`): entrada `opacity` + `scale(0.97)` con `transform-origin` hacia el trigger, `ease-out`, <200 ms.
- **`prefers-reduced-motion`** global: bloque que quita movimiento (mantiene opacidad y spinners de carga).
- Verificación: recorrer 5–6 vistas y confirmar que nav, botones y toasts se sienten consistentes.

---

## Fase 1 — Componentes recurrentes (patrones repetidos entre plantillas)

- **Modal de confirmación** (el `confirmar()` custom que reemplazó al `confirm()`): entrada `scale(0.95)`+opacity desde el centro (modal = origen centro), `ease-out`, <250 ms; fondo (backdrop) con fade.
- **Tarjetas / paneles** (`.pm-card`, listas, cockpit): hover gateado; en cargas con varios ítems, **stagger** opcional 30–80 ms (decorativo, sin bloquear).
- **Inputs / selects**: anillo de foco con `ease-out` (como en login).
- **Tablas**: sin animar filas en tablas grandes (se ven mucho); solo hover sutil gateado.
- **Spinners**: unificar a ~0.6 s (se percibe más rápido).

---

## Fase 2 — Pantallas por prioridad (tráfico / impacto)

**Alta (hot-path, muchos usuarios):**
- `dashboard/index.html` — KPIs, cascada, heatmap. Entradas sutiles, sin animar lo que refresca seguido.
- `of/planta_corte.html`, `of/calidad_cola.html`, `of/reprocesos.html`, `of/fusionado.html` — operación diaria de planta: press feedback, transiciones de estado, modales.
- `of/lista.html`, `of/detalle.html` — navegación central de OFs.

**Media:**
- `catalogo/*` (lista, detalle, form_prenda, tipo_cambio), `supervisor/*` (curvas, programación), `of/trazos.html`, `of/planeamiento.html`, `of/plan_corte.html`, `of/gerencia.html`, `of/derivados.html`, `comercial/*`, `requerimiento_prod_form.html`, `corte/seguimiento.html`.

**Baja:**
- `admin/usuarios.html`, `of/import_sap.html`, `of/crear.html`, `of/editar_piezas.html`, `plantas/*`.
- `pdf/*` **excluidas** (se renderizan a PDF con xhtml2pdf; no aplican animaciones).

---

## Fase 3 — Animaciones de Analítica (ya existen — solo afinar)

`analitica/process_mining.html` ya tiene: simulación (token stepper), ruta crítica y la
animación estilo Celonis. Son **explicativas/ocasionales** → animar está justificado, pero:
- Afinar curvas a `--ease-out` / `--ease-in-out` y revisar duraciones.
- **`prefers-reduced-motion`**: la animación Celonis mueve cientos de tokens → debe **omitirse o reducirse** bajo reduced-motion (importante para accesibilidad).
- `analitica/chat.html`: micro-transiciones de la respuesta/tabla.

---

## Criterios de aceptación por pantalla (checklist de la skill)

- `transition` con propiedades específicas (nunca `all`).
- Botones/pressables con `scale(0.97)` al presionar.
- Entradas desde `scale(0.95)`+`opacity` (nunca `scale(0)`).
- `ease-out` (jamás `ease-in`); duraciones UI <300 ms.
- Solo se animan `transform`/`opacity`.
- Popovers origin-aware; modales centrados.
- Hover gateado; `prefers-reduced-motion` respetado.

---

## Enfoque técnico, orden y riesgo

- **Dónde vive el CSS común:** hoy es inline. Recomendación: hacer la **Fase 0 inline en `base.html`** (rápido, bajo riesgo). Si más adelante se ejecuta el `PLAN_STATIC_Y_UPLOADS` (externalizar CSS/JS), esos tokens y reglas globales se mudan a `static/css/app.css` — este trabajo es el momento natural para hacerlo.
- **Incremental, no big-bang:** una fase/pantalla por vez, con **revisión visual** (no hay tests de UI). `pytest` se corre igual como red de seguridad (no debería cambiar).
- **Riesgo:** bajo — solo estilos/timing; reversible archivo por archivo. El único cuidado es no romper layouts al tocar estilos compartidos → por eso Fase 0 se revisa en varias vistas antes de seguir.

## Recomendación de arranque

**Fase 0 (base.html)** es, con diferencia, la de mayor retorno: press feedback en todos los
botones, toasts y menús coherentes, y accesibilidad, con un solo archivo. Después, las 3–4
pantallas de **planta (Alta prioridad)**, que son las de uso diario. El resto es pulido
incremental que se puede hacer cuando haya tiempo.
