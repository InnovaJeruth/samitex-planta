# Cambios técnicos · Integración SAP + Catálogo + OF

_Mapa de todo lo que se tocaría en el código, pros/contras y dudas para poder avanzar._
_Estado: análisis. No se ha programado nada de esto todavía._

---

## 1. Cambios en MODELOS (tablas / campos)

### 1.1 `OrdenFabricacion` (app/models/of.py)
**Campos nuevos:**
- `material_sap` (String) — **llave de enlace con el catálogo** (ej. 2000030884).
- `clase_orden` (String) — ZP41–ZP44 (institución / marca / reprocesos / serv. terceros).
- `centro` (String) — PP40.
- `sociedad` (String) — P040.
- `area_planificacion` (String) — PP40.
- `almacen` (String) — PR01.
- `autor_sap` (String) — código de usuario SAP (PALVA).
- `bom_sap` (String) — Nº lista de materiales (desempate de fit si hiciera falta).

**Campos reutilizados (cambia su origen/uso):**
- `numero_of` — ahora = Orden SAP (deja de ser autogenerado en OFs nuevas).
- `fecha_sap` — pasa de `Date` a `DateTime` (guarda fecha inicio extrema + hora creación).
- `fecha_apt` — recibe la fecha fin extrema (entrega).
- `tipo_cliente` — se **deriva** de `clase_orden`.

### 1.2 `PrendaCatalogo` (app/models/catalogo.py)
**Campos nuevos:**
- `material_sap` (String, único) — llave única del producto.
- `codigo_interno` (String) — código humano (3LC476); **NO es único** (se repite por color/talla/pack/versión), solo referencia.
- `bom_sap` (String, opcional).
- `estado_ficha` (String) — "PENDIENTE" / "COMPLETA" (para gates).

**Cambio estructural (el más delicado):**
- **Sacar `color` de `PrendaCatalogo`** y llevarlo al SKU.
- `fit` — **ya existe** (`PrendaCatalogo.fit` + constante `FITS_PRENDA`). Solo se autollenará desde la ficha técnica.

### 1.3 `PrendaSku` (app/models/catalogo.py)
- **Añadir `color`** → el SKU pasa de "talla" a "talla × color".
- `codigo_sku` ↔ material SAP de 13 díg.

### 1.4 Impacto en `OFPaquete` (app/models/paquete.py)
- Hoy `OFPaquete.color` lee `self.sku.prenda.color`. Al mover color al SKU, cambia a `self.sku.color`.
- Afecta numeración, calidad y reprocesos (todos usan color del bulto). **Es refactor contenido pero con tests que reajustar.**

### 1.5 Modelo de FICHA TÉCNICA (piezas / materiales / avíos)
- Reutiliza lo existente: `OFPieza` (o plantilla de piezas del catálogo), `CatalogoMp`, `CatalogoAvio`, `PrendaSku`.
- Se cargan desde la **plantilla estándar** (no desde el PDF de SAP).

---

## 2. Cambios en SERVICIOS
- `of_service` — creación de OF por import: mapeo de columnas, enlace por `material_sap`, herencia de fit, validación de estado de ficha (bloqueo de corte si incompleta).
- `catalogo` service — carga masiva desde SAP (identidades), importador de ficha técnica (plantilla → piezas + materiales + avíos), autollenado de color desde el botón SAP.
- `gate_service` — nuevo gate: "ficha completa" (piezas por UDP + materiales/avíos por ingeniería) antes de permitir corte.

---

## 3. Cambios en ROUTERS / ENDPOINTS
- **Importador de OF** — endpoint para subir el Excel de la COIS → crea OF(s) en borrador.
- **Importador de ficha técnica** — endpoint para subir la plantilla (piezas / materiales-avíos).
- **Carga masiva de catálogo** — script/endpoint para poblar los modelos PP desde SAP.
- Ajuste en creación de OF (hoy manual) para el nuevo origen SAP.

---

## 4. Cambios en TEMPLATES / UI
- Pantalla "Importar OF desde Excel SAP" (subida + previsualización + errores).
- Pantalla "Importar ficha técnica" (UDP piezas / ingeniería materiales-avíos).
- Formulario de OF: mostrar fit heredado, aviso si la prenda está incompleta.
- Armado de curva **color × talla** en la OF (hoy es solo por talla).
- Catálogo: reflejar SKU = talla × color y estado de ficha.

---

## 5. MIGRACIONES (Alembic)
- Nuevos campos de OF y de catálogo.
- `fecha_sap` Date → DateTime.
- Mover `color` de prenda a SKU (migración de datos).
- **Reconstrucción del catálogo desde cero** (el actual es data falsa → se borra).
- _Pendiente aparte:_ correr `alembic upgrade head` de la hoja de numeración (ya programada, falta aplicar en BD).

---

## 6. COMPONENTES NUEVOS (resumen)
1. Carga masiva de catálogo SAP (6,044 modelos PP como identidades).
2. Plantilla + importador de ficha técnica (UDP + ingeniería).
3. Importador de OF desde Excel COIS.
4. Armado de curva color × talla.
5. Gate de "ficha completa" antes de cortar.

---

## 7. PROS Y CONTRAS de las decisiones grandes

### Reconstruir el catálogo desde cero (borrar el actual)
- **Pro:** catálogo limpio, alineado a SAP, sin data falsa. Estructura correcta (base + SKU color×talla).
- **Contra:** los 6,044 modelos nacen vacíos de ficha; completar es trabajo progresivo. (No se pierde nada real: el actual es falso.)

### Llave por `material_sap` (no por código humano)
- **Pro:** único por producto+fit; nunca confunde Modern/Slim; robusto ante códigos repetidos (color/talla/pack/-2/-3).
- **Contra:** hay que capturar y mantener el material SAP en el catálogo.

### Color como eje del SKU (talla × color)
- **Pro:** multicolor natural; el paquete "1 talla + 1 color" calza directo; resuelve pendiente de numeración multicolor.
- **Contra:** toca `OFPaquete.color`, numeración, calidad y reprocesos; migración de datos; reajustar tests. **Es el cambio de mayor riesgo.**

### No autocrear la prenda desde la OF (UDP la crea primero)
- **Pro:** dato maestro limpio y con dueño (UDP); evita basura/duplicados desde texto de la OF.
- **Contra:** exige que la prenda exista antes (se cubre con la precarga masiva).

### Fit desde la cabecera de la ficha técnica
- **Pro:** confiable (SAP no lo tiene; la ficha sí lo dice explícito). Se hereda a la OF por material.
- **Contra:** depende de que la plantilla se llene con disciplina.

### Precarga masiva vs bajo demanda
- **Precarga (6,044):** "no hay prenda" casi nunca aparece; cómodo. Contra: catálogo grande con muchas fichas pendientes.
- **Bajo demanda:** catálogo crece solo con lo que se produce. Contra: cada modelo nuevo bloquea la primera OF hasta que UDP lo cree.

---

## 8. DUDAS PENDIENTES para avanzar

**Del catálogo / prenda:**
1. ¿Precargamos los 6,044 modelos PP, o creación bajo demanda?
2. Versiones `-2` / `-3` de un mismo código: ¿reedición comercial (misma prenda) o cambio técnico (prenda distinta)?
3. "SURTIDO COLOR": confirmado que se **ignora** — ¿algún caso donde sí se corta surtido?

**Del fit:**
4. Confirmar con diseño / Service Desk si SAP tiene un campo de entalle exportable (el personal no estaba 100% seguro).
5. Confirmar que el `material_sap` es único por producto+fit (José Modern ≠ José Slim en número de material).

**De las clases de orden:**
6. Reprocesos (ZP43) y servicios terceros (ZP44): ¿qué `tipo_cliente` les toca para gates/hoja de costos, o saltan gates?

**Del flujo:**
7. ¿La OF puede crearse con la prenda existente pero **incompleta** (sin piezas/materiales) y completar por gates? (propuesto: sí)
8. ¿Quién puede subir cada importador? (OF = planeamiento; ficha piezas = UDP; ficha materiales/avíos = ingeniería) — confirmar.

**Temas relacionados aún abiertos (de antes):**
9. Excedente de tela (solo Marca): Gerente de Planta decide con qué talla. Falta el punto donde se registra.
10. Entrega de rollos de tela a Corte: quién la registra (Logística / Supervisor / rol Almacén) y si un rollo se reparte entre OFs.

---

## 9. Orden sugerido para programar (por bloques, aprobables uno a uno)
1. **Modelos + migración** (campos OF, catálogo, color→SKU, fit autollenable).
2. **Carga masiva de catálogo SAP** (identidades PP).
3. **Plantilla + importador de ficha técnica** (piezas / materiales-avíos).
4. **Importador de OF** (Excel COIS → OF, enlace por material, herencia de fit).
5. **Curva color × talla** en la OF.
6. **Gate de ficha completa** antes de cortar.
7. **Tests + verificación** en cada bloque.
