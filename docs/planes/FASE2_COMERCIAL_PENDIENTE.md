# Fase 2 — Módulo Comercial: Requerimientos ↔ OF
**Estado:** Pendiente de implementación  
**Fecha de análisis:** 2026-06-18  
**Prerequisito:** Fase 1 completada (router + templates frontend)

---

## Premisas confirmadas

- Toda OF (sin excepción, incluyendo ADMIN) sale de un requerimiento
- Correlativos separados: `RI-YYYY-NNN` (institución) y `RM-YYYY-NNN` (marca)
- El requerimiento es inmutable para el planeador — solo lectura
- `numero_of` sigue siendo de escritura libre (no autonumérico)
- Tallas en Fase 2 → JSON simple; tablas estructuradas quedan para Fase 3

---

## Flujo completo

```
COMERCIAL / COMERCIAL_MARCA crea requerimiento (N ítems/prendas)
        ↓  estado: "Enviado a producción"
PLANEADOR ve lista de requerimientos con badge INST/MARCA y progreso X/N
        ↓  entra al detalle del requerimiento
PLANEADOR selecciona ítem de prenda → "Crear OF"
        ↓  formulario OF pre-relleno (read-only los campos del requerimiento)
PLANEADOR ingresa: numero_of, responsable, estampado_activo
        ↓  OF creada y vinculada al ítem
Requerimiento actualiza progreso: 1/N → hasta N/N = completado
```

---

## Quién crea qué

| Usuario | Tipo de requerimiento | tipo_cliente en OF resultante |
|---|---|---|
| COMERCIAL | Institución → `RI-` | `INSTITUCION` |
| COMERCIAL_MARCA | Marca → `RM-` | `MARCA` |
| ADMIN | Elige al crear | Lo que elija |
| PLANEADOR | No crea requerimientos | Solo lee y crea OFs |

> `tipo_cliente` de la OF se hereda del requerimiento — el planeador no lo ingresa.

---

## Paso 1 — Migración SQL (3 scripts)

### Script: tabla `requerimientos`

```sql
CREATE TABLE requerimientos (
    id                INT IDENTITY(1,1) PRIMARY KEY,
    numero            VARCHAR(20) NOT NULL UNIQUE,   -- RI-2026-001 / RM-2026-001
    tipo              VARCHAR(15) NOT NULL,           -- INSTITUCION / MARCA
    origen            VARCHAR(10) NOT NULL,           -- contrato / oc
    nro_referencia    VARCHAR(50),                    -- N° contrato o N° OC
    proceso           VARCHAR(50),
    nro_licitacion    VARCHAR(50),
    unidad_ejecutora  VARCHAR(200),
    nro_cuadro        VARCHAR(50),
    cliente           VARCHAR(200) NOT NULL,
    ejecutivo         VARCHAR(100) NOT NULL,
    tipo_produccion   VARCHAR(20) NOT NULL,           -- produccion / muestra / stock
    gestion_tallas    VARCHAR(20) NOT NULL,           -- definida / medida / usuarios
    fecha_solicitud   DATE NOT NULL,
    fecha_apt         DATE,
    -- campos gestión tallas
    fecha_medidas     DATE,
    sede_medidas      VARCHAR(100),
    modalidad_medidas VARCHAR(100),
    fecha_limite_medidas DATE,
    canal_recepcion   VARCHAR(50),
    -- entrega
    lugar_entrega     VARCHAR(100),
    tipo_embalaje     VARCHAR(100),
    rotulado          VARCHAR(50),
    garantia          VARCHAR(50),
    -- meta
    observaciones     NVARCHAR(MAX),
    estado            VARCHAR(30) NOT NULL DEFAULT 'borrador',
    creado_por_id     INT NOT NULL REFERENCES usuarios(id),
    creado_en         DATETIME DEFAULT GETDATE()
);
```

### Script: tabla `requerimiento_items`

```sql
CREATE TABLE requerimiento_items (
    id                    INT IDENTITY(1,1) PRIMARY KEY,
    requerimiento_id      INT NOT NULL REFERENCES requerimientos(id) ON DELETE RESTRICT,
    articulo              VARCHAR(200) NOT NULL,
    tipo_prenda           VARCHAR(20) NOT NULL,    -- SACO / PANTALON / CAMISA / OTRO
    color                 VARCHAR(100),
    composicion           VARCHAR(200),
    proveedor             VARCHAR(100),
    codigo_tela           VARCHAR(50),
    zona_destino          VARCHAR(50),
    sistema_tallas        VARCHAR(5),              -- A / B / C
    tallas_json           NVARCHAR(MAX),           -- {"15": 5, "16": 8, ...} o NULL si medida/usuarios
    total_juegos          INT NOT NULL DEFAULT 0,
    of_id                 INT REFERENCES ordenes_fabricacion(id) ON DELETE SET NULL
);
```

### Script: tabla `req_secuencias` (correlativos)

```sql
CREATE TABLE req_secuencias (
    tipo          VARCHAR(10) PRIMARY KEY,   -- INST / MARCA
    anio          INT NOT NULL,
    ultimo_numero INT NOT NULL DEFAULT 0
);

-- Seed inicial
INSERT INTO req_secuencias VALUES ('INST', 2026, 0);
INSERT INTO req_secuencias VALUES ('MARCA', 2026, 0);
```

### Script: ALTER en `ordenes_fabricacion`

```sql
ALTER TABLE ordenes_fabricacion
ADD requerimiento_item_id INT NULL
    REFERENCES requerimiento_items(id) ON DELETE SET NULL;
```

> **CRÍTICO:** Este script debe correrse ANTES de desplegar el código nuevo.
> Si se despliega código primero, el sistema cae completo porque SQLAlchemy
> intenta SELECT sobre una columna que no existe en la tabla.

---

## Paso 2 — Modelos Python

**Nuevo archivo:** `app/models/requerimiento.py`
- Clase `Requerimiento` → tabla `requerimientos`
- Clase `RequerimientoItem` → tabla `requerimiento_items`
- Relaciones con string-based references para evitar importación circular:
  - `relationship("RequerimientoItem", back_populates="requerimiento")`
  - `relationship("OrdenFabricacion", foreign_keys="[RequerimientoItem.of_id]")`

**Modificar:** `app/models/of.py`
- Agregar: `requerimiento_item_id = Column(Integer, ForeignKey("requerimiento_items.id"), nullable=True)`
- Agregar relación: `relationship("RequerimientoItem", foreign_keys=[requerimiento_item_id])`

**Modificar:** `app/main.py`
- Importar `app.models.requerimiento` antes del `create_all` para que SQLAlchemy registre ambos modelos

---

## Paso 3 — Router `comercial.py` (nuevos endpoints)

| Endpoint | Acción | Roles |
|---|---|---|
| `POST /comercial/api/crear` | Guarda requerimiento, genera correlativo, estado=borrador | COMERCIAL, COMERCIAL_MARCA, ADMIN |
| `PATCH /comercial/api/{id}/enviar` | Estado → enviado | mismo |
| `GET /comercial/{id}` | Página detalle | COMERCIAL, COMERCIAL_MARCA, PLANEADOR, ADMIN |
| `DELETE /comercial/api/{id}` | Solo si borrador y sin OFs vinculadas | COMERCIAL, COMERCIAL_MARCA, ADMIN |

### Lógica del correlativo (con UPDLOCK para evitar race condition)

```
1. BEGIN TRANSACTION
2. SELECT tipo, anio, ultimo_numero FROM req_secuencias WITH (UPDLOCK) WHERE tipo = X
3. Si anio != año_actual → resetear ultimo_numero = 0, actualizar anio
4. nuevo_numero = ultimo_numero + 1
5. UPDATE req_secuencias SET ultimo_numero = nuevo_numero
6. COMMIT
7. numero = f"RI-{anio}-{nuevo_numero:03d}" o f"RM-{anio}-{nuevo_numero:03d}"
```

### Asignación automática de tipo

- COMERCIAL → tipo = INSTITUCION, prefijo RI
- COMERCIAL_MARCA → tipo = MARCA, prefijo RM
- ADMIN → campo `tipo` en el formulario (debe elegir)

---

## Paso 4 — Router `of.py` (modificaciones)

### `GET /of/nuevo`
- Acepta query param opcional `?req_item_id=X`
- Si viene: carga el ítem, valida que no tenga OF ya (`item.of_id IS NULL`), pasa datos al template
- Si no viene: redirigir a `/comercial/` (ya no hay creación directa)

### `POST /of/api/crear`
- `requerimiento_item_id` en schema Pydantic: **opcional** (default None)
- Validación de negocio en el endpoint: si el usuario no es ADMIN, debe venir con req_item_id
- Si viene req_item_id: validar que el ítem exista y no tenga OF asignada
- Al crear: `item.of_id = nueva_of.id`
- `tipo_cliente` se hereda del requerimiento padre — no lo ingresa el planeador

### `PATCH /of/api/{id}/anular` (modificar el existente)
- Al anular una OF: `UPDATE requerimiento_items SET of_id = NULL WHERE of_id = {of_id}`
- Esto libera el ítem para que el planeador pueda crear una nueva OF

---

## Paso 5 — Templates

### `comercial/lista.html` (actualizar)
- Columna badge: `🏛 INST` (azul) / `🏷 MARCA` (morado)
- Columna progreso: `1/3` + barra visual
- Estados con color: Borrador (gris), Enviado (azul), En producción (ámbar), Completado (verde)

### `comercial/detalle.html` (nuevo)
- Cabecera: número REQ, badge tipo, cliente, fechas, creado por, estado
- Tabla de ítems:

| Artículo | Tipo | Tallas | Total | OF vinculada | Acción |
|---|---|---|---|---|---|
| Camisa Oxford | CAMISA | A | 23 | — | [Crear OF] |
| Pantalón drill | PANTALON | B | 23 | OF-45632 ✓ | [Ver OF →] |

- Botón "Crear OF" → `/of/nuevo?req_item_id={id}`
- Link "Ver OF →" → `/of/{of_id}`

### `of/crear.html` (modificar)
- Detecta `req_item_id` en URL
- Si viene: bloque superior de solo lectura con datos del requerimiento (tipo_prenda, cliente, fecha_apt, total_juegos, tipo_cliente)
- El planeador solo completa: `numero_of`, `responsable`, `estampado_activo`
- Campo `tipo_cliente` desaparece del formulario (heredado)

### `of/lista.html` (modificar)
- Botón "+ Nueva OF" → cambia a "Ir a Requerimientos" → `/comercial/`
- Columna opcional: badge "REQ" para OFs que vienen de requerimiento

### `of/detalle.html` (modificar)
- Sección nueva: si `of.requerimiento_item_id` existe, mostrar banner con:
  "Creada desde requerimiento RI-2026-003 — Ítem: Camisa Oxford"
- Siempre con `{% if of.requerimiento_item %}` — nunca asumir que existe

---

## Riesgos identificados y mitigaciones

| # | Riesgo | Severidad | Mitigación |
|---|---|---|---|
| A | create_all no altera tablas — app cae si SQL no se corre primero | Crítico | SQL ANTES del código. Campo nullable para backward compat |
| B | Importación circular entre of.py y requerimiento.py | Crítico | String-based relationships en SQLAlchemy |
| C | Templates acceden a relaciones nullable de OFs antiguas | Alto | `{% if of.requerimiento_item %}` en todos los accesos |
| D | POST OF incompatible si req_item_id se hace required | Alto | Campo opcional en Pydantic, validación en lógica de negocio |
| E | JS condicional de pre-relleno en crear.html | Medio | Verificar existencia de variable antes de usar |
| F | Dashboard rompe si hace joins con nueva relación | Medio | `lazy="select"` en relación, no agregar joinedload |
| G | of_id huérfano al anular OF | Alto | Al anular OF, limpiar requerimiento_items.of_id |

---

## Tallas — Hoja de ruta (Fases futuras)

### Fase 2 (esta fase)
- `tallas_json` (NVARCHAR) en `requerimiento_items` — JSON simple
- `gestión = definida`: grid completo en JSON + total_juegos calculado
- `gestión = medida/usuarios`: tallas_json = NULL, solo total estimado
- La OF hereda `total_juegos` del ítem
- Acceso al JSON solo desde Python — nunca queries SQL sobre el JSON

### Fase 3 (futura)
**Tabla `requerimiento_item_tallas`**
```
id, requerimiento_item_id, talla, cantidad_pedida, estado (estimado/confirmado)
```
- Flujo para completar tallas pendientes (gestión medida/usuarios)
- Quien completa: el mismo COMERCIAL/COMERCIAL_MARCA que creó el requerimiento
- Estado: estimado → confirmado cuando llegan las medidas reales

**Tabla `of_tallas`**
```
id, of_id, talla, cantidad_of
```
- Se llena al crear la OF copiando de `requerimiento_item_tallas`
- Independiente del requerimiento — producción puede ajustar sin modificar el pedido
- `of.total_juegos` pasa a ser `SUM(of_tallas.cantidad_of)`

### Fase 4 (futura lejana)
- Importación de tallas desde Excel (pedidos de 300+ colaboradores)
- `of_fase_tallas` — rastreo de cuántas prendas de cada talla pasaron por cada fase de corte

---

## Orden de implementación seguro

```
1. Correr script SQL (ALTER + CREATE nuevas tablas)
2. Crear app/models/requerimiento.py
3. Modificar app/models/of.py (agregar FK)
4. Actualizar imports en app/main.py
5. Ampliar app/routers/comercial.py (POST + PATCH + GET detalle)
6. Modificar app/routers/of.py (GET/POST nuevo + limpiar en anulación)
7. Crear comercial/detalle.html
8. Actualizar comercial/lista.html
9. Modificar of/crear.html (pre-relleno)
10. Modificar of/lista.html (botón nueva OF)
11. Modificar of/detalle.html (banner requerimiento)
12. Validar Jinja2 en todos los templates nuevos/modificados
13. Probar con OFs antiguas (sin requerimiento) — verificar que no rompan
14. Probar flujo completo: crear req → enviar → crear OF desde ítem → progreso
```

---

*Análisis completado: 2026-06-18*
