# Hoja de Costos digital — Documento para las áreas involucradas

**Propósito:** definir juntos el flujo de la Hoja de Costos (HDC) dentro del sistema, para que cada área confirme cómo participa y qué datos aporta. Con sus respuestas se construye el flujo correcto y se lleva al proyecto.

**Cómo responder:** cada área revisa su sección y responde las preguntas en la columna/espacio de respuesta. Las decisiones transversales (final del documento) las confirma Gerencia / Ingeniería de HDC.

---

## 1. Objetivo del módulo
Digitalizar la Hoja de Costos para que:
- Se arme con la participación ordenada de cada área (cada una sube su dato).
- Se **versione** (guardar el historial y reutilizar HDC pasadas).
- Se **apruebe** formalmente antes de ser el costo "oficial".
- Permita comparar el **costo estimado** (HDC) contra el **costo real** de producción.

---

## 2. Flujo propuesto (para validar)

**MARCA**
1. **Comercial Marca** solicita el costo de producción de una prenda.
2. **Ingeniero de HDC** arma la HDC pidiendo datos a las áreas.
3. **Gerencia** aprueba.
4. Se procede a **fabricación**.
(Aplica a prenda nueva o desde cero.)

**INSTITUCIÓN**
1. **Comercial** hace un **requerimiento de muestra**.
2. **UDP** realiza los diseños (piezas / ficha).
3. **Ingeniero de HDC** arma la HDC pidiendo datos a las áreas.
4. **Gerencia** aprueba → fabricación / cotización a la licitación.
(Licitación nueva = desde cero; licitación repetida de años pasados = se puede **reutilizar** la HDC anterior.)

**Datos por área (quién aporta qué):**
- **Logística** → precios de materiales y avíos.
- **Planta** → minutaje de mano de obra (min. por operación, % eficiencia, costo por minuto) y servicios de terceros (lavandería, teñido, bordado, estampado…).
- **UDP** → piezas y estructura de la prenda.
- **Ingeniero de HDC** → consolida y arma la HDC.
- **Gerencia (Planta y General)** → aprueban.

---

## 3. Preguntas por área

### 3.1 Comercial (Marca e Institución)
1. ¿La **solicitud de costos** (Marca) y el **requerimiento de muestra** (Institución) deben **crearse dentro del sistema** por Comercial, o se piden por fuera y el Ingeniero de HDC solo inicia la HDC?
2. ¿Qué **datos mínimos** manda Comercial al solicitar? (cliente, prenda/modelo, cantidad estimada, fecha objetivo, ¿algo más?)
3. Cuando la HDC queda **aprobada**, ¿Comercial necesita que el sistema le **devuelva el costo** para cotizar al cliente, o solo que habilite la fabricación?
4. ¿Comercial necesita ver el **estado** de su solicitud (en qué área está, si ya se aprobó)?

**Respuestas Comercial:**
> …

---

### 3.2 UDP (diseño / piezas)
1. En Institución, ¿el Ingeniero de HDC debe **esperar** a que UDP termine los diseños/piezas antes de pedir costos, o pueden ir **en paralelo**?
2. ¿UDP sube las piezas por **plantilla Excel**, o las carga en pantalla?
3. ¿Las piezas de una prenda **nueva** se crean siempre desde cero, o a veces se **parten de un modelo parecido** existente?

**Respuestas UDP:**
> …

---

### 3.3 Ingeniero de HDC (encargado / consolidador)
1. ¿El rol "Ingeniero de HDC" es una **persona/rol específico** distinto de Ingeniería general? (para crearlo en el sistema)
2. Al necesitar recostear una prenda ya trabajada, ¿la **reutilización** de la HDC pasada la elige el Ingeniero **manualmente** de un histórico, o el sistema la **sugiere** automáticamente?
3. Para reutilizar una HDC pasada, ¿cómo se identifica la anterior: por la **misma prenda/modelo**, por **cliente**, o búsqueda libre?
4. ¿Con qué frecuencia cambian precios/minutos entre una HDC y otra (para decidir si conviene "confirmar sin cambios" o siempre re-pedir)?

**Respuestas Ingeniero de HDC:**
> …

---

### 3.4 Logística (precios)
1. ¿Logística sube los **precios** por **plantilla Excel** (código de material, precio, moneda, proveedor, unidad de compra, factor), o los edita en pantalla?
2. ¿Manejan **precio por material** independiente de la prenda (un catálogo de precios único) o el precio va **por prenda**?
3. ¿En qué **moneda** vienen los precios y cómo se maneja el **tipo de cambio** (fijo, el del día)?
4. ¿Cuándo un material aún **no tiene precio** (nuevo/importado), qué colocan mientras tanto?

**Respuestas Logística:**
> …

---

### 3.5 Planta (minutaje + servicios)
1. ¿Planta sube el **minutaje** (min. estándar, % eficiencia, costo por minuto por operación: corte, costura, acabado) por **Excel** o en pantalla?
2. El **costo por minuto**, ¿es el mismo para todas las operaciones o distinto por operación/área?
3. Los **servicios de terceros** (lavandería, teñido, bordado, estampado…): ¿su costo es **por prenda** y viene de una cotización del tercero?
4. Para el **costo real**, ¿el costo por minuto real es el **mismo** de la HDC o Planta define uno distinto según lo que pasó en producción?

**Respuestas Planta:**
> …

---

### 3.6 Gerencia (Planta y General) — aprobación
Regla propuesta: **Gerente de Planta** aprueba primero; luego **Gerente General** da la aprobación final. Si **Gerente General** aprueba primero, ya no se requiere la del Gerente de Planta.
1. ¿Confirman esta regla de aprobación?
2. ¿Se necesita **firma / registro** de quién aprobó y cuándo (auditoría)?
3. ¿Puede Gerencia **devolver** la HDC (rechazarla) con un motivo para que se corrija?

**Respuestas Gerencia:**
> …

---

## 4. Decisiones transversales a confirmar
1. **Costo real por OF:** se calculará con lo que el sistema ya captura en producción (tela real, cantidad, merma, tiempos) usando **precios estándar** primero, y **precios reales de compra** (SAP/SOLPED) en una fase posterior. ¿De acuerdo?
2. **Precios reales de compra a futuro:** ¿vendrán de **SAP (SOLPED/OC)** o los carga **Logística** manualmente?
3. **Notificaciones:** cuando un área tiene una solicitud pendiente, ¿se avisa por **correo / la misma app / otro**?
4. **Versionado:** cada HDC aprobada queda como **versión oficial** con su historial. ¿De acuerdo?

---

## 5. Resumen de lo que se necesita de cada área para arrancar
| Área | Qué necesitamos que confirmen |
|---|---|
| Comercial | Cómo entra la solicitud/requerimiento y qué devuelve el sistema |
| UDP | Si diseñan antes o en paralelo; cómo suben piezas |
| Ingeniero HDC | Rol específico; cómo reutilizan HDC pasadas |
| Logística | Formato de precios; moneda/tipo de cambio |
| Planta | Formato de minutaje; costo por minuto; servicios |
| Gerencia | Regla de aprobación y auditoría |

_Con estas respuestas se define el flujo definitivo y se estructura el desarrollo por bloques._
