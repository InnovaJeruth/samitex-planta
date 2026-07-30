# Fase 2 — Integrar el Requerimiento a la creación de la OF (manteniendo SAP)

_Análisis. No se programa hasta aprobar. Objetivo: que Planeamiento genere OFs
desde un requerimiento registrado, de forma natural, **sin quitar la carga del
Excel de SAP**._

---

## 1. Cómo se crea hoy la OF (lo real, en código)

Hay **dos caminos** que hoy escriben `OrdenFabricacion` directo:

1. **Import SAP** (`of_import_service.crear_of_desde_sap`): lee una fila del Excel
   COIS y crea la OF con `numero_of`, `material_sap`, `clase_orden`, `cantidad`,
   enlace a prenda por material, `omitir_gates` según clase, `tipo_cliente`, APT.
   **SAP es el dueño del `numero_of`.**
2. **Alta manual** (`POST /of/crear`): el planeador teclea `numero_of`, `cliente`,
   `tipo_prenda`, `prenda_catalogo_id` (opcional), `total_juegos`, APT, `tipo_cliente`.

En ambos, la **curva de tallas NO se carga al crear**. La OF nace con
`total_juegos` y la curva se asigna **después**, en el módulo de curvas/programación,
escribiendo `OFTallaDistribucion (of_id, sku_id, cantidad)`. Eso exige que la
**prenda exista y tenga SKUs por talla** (una talla → un SKU).

**Lo que ya trae la línea de requerimiento (Fase 1):** descripción/artículo,
tallaje A/B/C, **curva (talla+cantidad)**, total, prenda_catálogo (opcional),
y de la cabecera: cliente, APT, tipo. Es decir, casi todo lo que pide la OF —
**menos el `numero_of` y los campos propios de SAP** (clase_orden, material_sap, gates).

---

## 2. Los 3 "saltos" a resolver

- **A · Número de OF.** SAP lo emite; el requerimiento no lo tiene. Es el punto crítico.
- **B · Curva → OF.** La línea tiene la curva por talla; la OF la guarda por **SKU**.
  Si la prenda no está enlazada o no tiene SKUs por talla, no se puede volcar la curva automáticamente.
- **C · Campos SAP (clase_orden, material_sap, gates).** Sólo vienen del Excel.
  Una OF nacida del requerimiento no los tiene hasta que SAP la respalde.

---

## 3. Opciones (con pro y contra)

### Opción A — OF provisional desde el requerimiento + reconciliación con SAP
Planeamiento genera la OF en BORRADOR con **número provisional** (ej. `REQ-014-2026-L1`)
precargando prenda/cliente/curva/APT. Cuando llega el Excel SAP, el import
**adopta** esa OF (le pone el `numero_of` oficial + clase_orden + material_sap + gates)
en lugar de duplicar.

- **Pro:** se puede empezar a planificar/cortar **antes** de que SAP emita la orden; traza requerimiento→OF; SAP sigue siendo el dueño del número final.
- **Contra:** hay que resolver el **matching** SAP↔OF provisional (si falla, se duplica); el `numero_of` **cambia** (hay que propagarlo y mostrar historial); mientras es provisional corre sin los gates reales de SAP.

### Opción B — El requerimiento sólo "pre-arma", la OF real nace con SAP
La línea se marca "lista para OF" y guarda el pre-armado (prenda, curva, cliente).
La OF la sigue creando **SAP**; al importar, si hay un requerimiento pendiente que
matchea, **autocompleta** curva/prenda desde él. La OF **nunca** existe sin número SAP.

- **Pro:** cero cambio a la numeración; SAP siempre es la fuente; sin duplicados ni renumeración; riesgo mínimo.
- **Contra:** **no adelanta plazo** (no se corta antes de SAP); el beneficio es sólo "no re-teclear la curva"; **no resuelve** el caso institución muestra→producción sin SAP.

### Opción C — Dos orígenes de OF de primera clase (`origen = SAP | REQUERIMIENTO`)
La OF lleva `origen` y `requerimiento_linea_id`. Si `origen=REQUERIMIENTO`, el
número se asigna por **correlativo interno** (ej. `R-2026-000123`) y **no se espera
SAP** para esa OF. SAP alimenta sólo las de `origen=SAP`. La reconciliación con SAP
es opcional (enlace manual si luego aparece).

- **Pro:** soporta el caso **sin Excel SAP** que quieres a futuro; ambos flujos coexisten limpios; sin renumeración.
- **Contra:** **dos espacios de numeración** conviviendo (hay que evitar colisiones y dejar clarísimo cuál es cuál); si el mismo pedido llega luego por SAP, riesgo de OF duplicada salvo control; hay que **definir gates/clase** para el origen REQUERIMIENTO sin apoyarse en SAP.

---

## 4. Recomendación: híbrido por etapas (B → A → C)

Lo más natural y de menor riesgo es **reutilizar el mismo núcleo de creación de OF**
y que el requerimiento sólo lo **alimente**, avanzando por capas:

- **Fase 2.1 (base, bajo riesgo):** unificar la creación en **un solo servicio
  `crear_of(...)`** que hoy está duplicado (import SAP y alta manual lo llamarían).
  Añadir a la OF los campos de trazabilidad `origen` y `requerimiento_linea_id`
  (aditivo, nullable). Nada cambia para el usuario todavía.
- **Fase 2.2 (valor inmediato, estilo B):** botón **"Generar OF"** por línea en un
  requerimiento **REGISTRADO** → abre el alta de OF **precargada** (prenda, cliente,
  tipo, total, APT, y la **curva** volcada a `OFTallaDistribucion` si la prenda tiene
  SKUs). El planeador **confirma/teclea el `numero_of`** (igual que hoy tecleas el
  `numero_req`; correlativo más adelante). SAP sigue **intacto**.
- **Fase 2.3 (reconciliación, estilo A):** al importar SAP, si el `numero_of` ya
  existe como OF de `origen=REQUERIMIENTO`, **enlazar y completar** (clase_orden,
  material_sap, gates) en vez de duplicar. Match por número + material/cliente.
- **Fase 2.4 (caso sin SAP, estilo C):** habilitar correlativo interno para
  `origen=REQUERIMIENTO` (muestra/institución) y definir su política de gates.

Así: **SAP se mantiene** como está, ganas de inmediato el "no re-teclear la curva",
y dejas la puerta abierta al caso sin-SAP sin renumerar nada de golpe.

---

## 5. Puntos de contacto técnicos (para dimensionar)

- **Modelo OF (aditivo):** `origen` (SAP/REQUERIMIENTO/MANUAL, default según camino),
  `requerimiento_linea_id` (FK nullable). Migración aditiva.
- **Refactor `crear_of`:** extraer un servicio único que hoy vive repetido en
  `of_import_service.crear_of_desde_sap` y `routers/of.py::crear_of`. Riesgo medio
  (toca dos flujos probados) → se hace con tests de regresión antes de cambiar nada visible.
- **Volcado de curva:** reutilizar el mismo mecanismo del módulo de curvas
  (`OFTallaDistribucion` + `auto_generar_piezas`). **Requiere prenda con SKUs por talla.**
- **Estado de la línea:** la línea de requerimiento pasa a `OF_GENERADA` (evita
  generar dos OFs de la misma línea).

---

## 6. Riesgos principales

- **Duplicar OFs** si el mismo pedido entra por requerimiento y luego por SAP → se
  mitiga con la reconciliación (2.3) y el enlace `requerimiento_linea_id`.
- **Curva sin SKUs:** si la prenda de la línea no tiene SKUs por talla, no se puede
  volcar la curva automática → se crea la OF sin distribución (como hoy) y se completa
  en el módulo de curvas. Decidir si auto-crear SKUs faltantes.
- **Numeración doble** (correlativo interno vs SAP) en 2.4 → aislar rangos y marcar
  visualmente el origen.
- **Refactor de `crear_of`:** es el único cambio que toca código probado; se blinda con tests.

---

## 7. Decisiones abiertas (para ti)

1. En 2.2, el `numero_of` de una OF desde requerimiento: **¿lo teclea el planeador
   ahora** (como el numero_req) y correlativo después? (asumo que sí).
2. **¿Una línea = una OF?** ¿O una línea con "terno" puede dividirse en varias OFs?
   (en Fase 1 quedó fuera; aquí hay que definirlo).
3. Si la prenda de la línea **no tiene SKUs por talla**, ¿la OF se crea sin curva
   (se completa luego) o el sistema **auto-crea los SKUs** del catálogo?
4. Gates para OFs de `origen=REQUERIMIENTO` (sin clase SAP): ¿corren con gates
   normales o `omitir_gates` hasta que SAP las respalde?
