# Samitex Planta — Sistema de Seguimiento de Producción

## Visión General

Sistema web interno para gestionar el ciclo completo de una Orden de Fabricación (OF) en la planta de Samitex: desde que el área comercial o de ingeniería la crea, hasta que sale el lote cortado y terminado hacia el cliente o una planta externa.

El sistema reemplaza el seguimiento manual en hojas de Excel y grupos de WhatsApp, centralizando trazabilidad, documentación y estado en tiempo real.

---

## Stack Técnico

| Capa | Tecnología |
|---|---|
| Backend | FastAPI + SQLAlchemy ORM |
| Base de datos (dev) | SQL Server (MSSQL) vía pyodbc |
| Base de datos (prod) | PostgreSQL — Supabase |
| Frontend | Jinja2 SSR + vanilla CSS/JS |
| Autenticación | Sesión con cookie + CSRF token |
| Notificaciones | Telegram Bot + WebSockets |
| PDF | WeasyPrint |
| Deploy | Branch `main` → `deploy` |

---

## Módulos del Sistema

### 1. Catálogo de Prendas

**Objetivo:** Mantener la ficha técnica maestra de cada prenda que produce Samitex, como base de referencia para todas las OFs.

**Estructura:**
- **Prenda BASE** — define la estructura técnica de una prenda (piezas, avíos, materiales, tallas)
- **Variante INSTITUCIÓN** — variante comercial con color y especificaciones propias, hereda estructura de la base
- **Variante MARCA** — igual que institución pero con flujo documental adicional (Ficha Técnica UDP)

**Datos por prenda:**
- Código único, nombre, tipo (SACO / PANTALÓN / CAMISA / PULLOVER), fit, color, composición
- Plantilla de piezas (cuáles partes se cortan y cuántas por juego)
- Avíos por sección (COSTURA / ACABADOS / EMBALAJE) con unidad y moneda
- Materiales principales (TELA_PRINCIPAL / ENTRETELA / FORRO) con consumo por talla
- SKUs por talla (XS–XXL) con precio y cantidad
- Documentos adjuntos (Ficha Técnica, Moldes, Muestra Aprobada)
- Historial de Hojas de Costos

**Filtros disponibles:** tipo base, tipo de cliente (BASE / INSTITUCIÓN / MARCA), marca/institución, búsqueda por nombre

**Estadísticas (filtradas en tiempo real):** total bases, total variantes, total SKUs, total piezas base

---

### 2. Órdenes de Fabricación (OF)

**Objetivo:** Núcleo del sistema. Cada OF representa un lote de producción con su ciclo de vida completo.

**Campos principales:**
- N° OF (único), cliente, tipo de prenda, prenda del catálogo vinculada
- Total de juegos (cantidad de prendas a producir)
- Tipo de cliente (INSTITUCIÓN / MARCA)
- Fecha de creación, fecha APT (fecha prometida al cliente)
- Responsable del seguimiento
- Estado: BORRADOR → ACTIVA → EN_PROCESO → COMPLETADA / ANULADA

**Tipos de OF:**
- **OF Regular** — pasa por todos los gates documentales antes de activarse
- **OF Muestra (es_muestra=True)** — fast-track sin gates; se activa inmediatamente para responder rápido a muestras de cliente

**Flujo de documentación (Gates):**

```
Cadena 1:
  Ficha Técnica → Hoja de Costos → SOLPED Prenda

Cadena 2 (paralela):
  Muestra Aprobada ─┬→ SOLPED MP → Orden de Compra → Confirmación Stock
                    └→ Reporte Tallas → Moldes Lectra
```

Una OF regular solo puede activarse cuando todos los gates obligatorios están completos. Cada gate tiene un área responsable (UDP, Ingeniería, Comercial, Logística, Modelista).

**Tercerización:**
- Una OF puede marcarse como tercerizada y asignarse a una planta externa
- Se registra fecha de envío, fecha de recepción estimada/real y juegos recibidos

---

### 3. Hoja de Costos

**Objetivo:** Documentar el costo unitario de fabricación de una prenda, con historial de versiones y aprobación formal.

**Estructura:**
- Versión numerada automáticamente por prenda
- Líneas de costo: descripción, cantidad, unidad, costo unitario, subtotal
- Estado: BORRADOR → APROBADA
- Registro de quién aprobó y cuándo
- Historial completo de versiones accesible desde el detalle de la prenda

---

### 4. Curvas de Tallas

**Objetivo:** Distribuir el total de juegos de una OF entre las tallas disponibles según una curva porcentual predefinida.

**Flujo:**
1. Supervisor crea una curva con nombre, OF vinculada y distribución por talla (XS a XXL)
2. El sistema valida que la suma de juegos distribuidos coincida con el total_juegos de la OF
3. La distribución queda guardada como referencia para el plan de corte

**Tipos de curva:** predefinidas por tipo de prenda o personalizadas por pedido

---

### 5. Plan de Corte

**Objetivo:** Organizar qué OFs se cortan juntas, en qué orden y en qué planta, optimizando el uso de tela.

**Funcionalidad:**
- Lista de OFs activas con capacidad para definir fecha de inicio y orden de corte
- Agrupación por tipo de prenda (no se cortan prendas distintas en el mismo tendido)
- Vinculación de curva de tallas y documento de distribución a la OF antes del corte
- Vista de Plan de Corte con semáforo de estado por OF

---

### 6. Seguimiento de Corte

**Objetivo:** Registrar avance real por pieza durante el proceso de corte, pieza a pieza.

**Flujo:**
- El operario ingresa las piezas cortadas por talla para cada componente de la OF
- El sistema calcula avance porcentual vs. el total esperado
- Semáforo visual: verde (al día), amarillo (riesgo), rojo (atrasado)
- Reporte PDF descargable con resumen de avance

---

### 7. Programación / Supervisor

**Objetivo:** Vista consolidada para que el supervisor de planta gestione la carga de trabajo semanal.

**Funcionalidad:**
- Lista de OFs activas con estado de avance
- Acceso a curvas de tallas por OF
- Indicadores de OFs próximas a APT
- Vista de plantas externas con estado de OFs tercerizadas

---

### 8. Comercial — Requerimientos de Muestra

**Objetivo:** Canal rápido para que el área comercial registre pedidos de muestra sin pasar por el flujo documental completo.

**Flujo:**
- Área Comercial crea un Requerimiento de Muestra con: N° RM, cliente, prenda del catálogo, fecha APT, descripción/referencia
- Se genera automáticamente una OF con `es_muestra=True`
- La OF aparece en la lista de órdenes con badge "MUESTRA" y row verde diferenciado
- El planeador le asigna fecha de inicio desde la lista de OFs

---

### 9. Plantas Externas

**Objetivo:** Gestionar las plantas subcontratistas a las que se tercerizan lotes de producción.

**Datos por planta:** nombre, RUC, contacto, dirección, estado (activa/inactiva)
**Vista de detalle:** lista de OFs asignadas con estado de recepción

---

### 10. Administración

**Objetivo:** Gestión de usuarios del sistema.

**Roles:**
- ADMIN — acceso total
- SUPERVISOR — gestión de corte y programación
- PLANEAMIENTO — gestión de OFs y plan de corte
- COMERCIAL — creación de muestras y seguimiento comercial
- LECTURA — solo visualización

---

### 11. Dashboard

**Objetivo:** Vista resumen del estado actual de la producción.

**Indicadores planificados:**
- OFs activas vs. completadas vs. atrasadas
- OFs próximas a APT (próximos 7 días)
- Avance de corte en curso
- Alertas de gates pendientes por área

---

## Modelo de Datos — Entidades Principales

```
PrendaCatalogo
  ├── PlantillaPieza       (piezas por prenda)
  ├── CatalogoAvio         (avíos por sección)
  ├── CatalogoMp           (materiales principales)
  ├── PrendaSku            (tallas y precios)
  ├── PrendaDocumento      (archivos adjuntos)
  └── HojaCostos
        └── HojaCostosLinea

OrdenFabricacion
  ├── prenda_catalogo_id → PrendaCatalogo
  ├── DocumentoOF          (archivos de gates)
  ├── PiezaOF              (distribución por pieza y talla)
  ├── RegistroCorte        (avance real de corte)
  ├── planta_id → PlantaExterna
  └── responsable_id → Usuario

CurvaTallas
  ├── of_id → OrdenFabricacion
  └── CurvaTallasDetalle   (% y juegos por talla)

Usuario
  └── rol: ADMIN | SUPERVISOR | PLANEAMIENTO | COMERCIAL | LECTURA
```

---

## Flujo Completo de una OF Regular

```
1. Ingeniería / Comercial crea la OF (estado: BORRADOR)
   └── Elige prenda del catálogo → se heredan piezas automáticamente

2. Documentación por gates (orden obligatorio):
   ├── Ficha Técnica (UDP / Comercial)
   ├── Hoja de Costos (Ingeniería)
   ├── SOLPED Prenda (Comercial)
   ├── Muestra Aprobada (Comercial)
   ├── SOLPED MP + Orden de Compra + Confirmación Stock (Logística)
   └── Reporte Tallas + Moldes Lectra (Modelista)

3. Gates completos → OF se activa (estado: ACTIVA)

4. Planeamiento asigna fecha de inicio y orden en el Plan de Corte

5. Supervisor vincula curva de tallas → genera distribución por talla

6. Corte inicia (estado: EN_PROCESO)
   └── Operarios registran piezas cortadas por talla

7. Corte completado → PDF de reporte generado

8. OF completada o enviada a planta externa (estado: COMPLETADA)
```

---

## Flujo de una OF Muestra (Fast-Track)

```
1. Comercial crea Requerimiento de Muestra
   └── Se genera OF con es_muestra=True (estado: ACTIVA inmediatamente)

2. Planeador asigna fecha de inicio desde lista de OFs

3. Corte y seguimiento igual que OF regular
   (aparece con badge MUESTRA en verde en todas las listas)
```

---

## Notificaciones

- **Telegram Bot:** alertas automáticas cuando una OF cambia de estado o un gate vence
- **WebSockets:** actualización en tiempo real del avance de corte en la vista de seguimiento

---

## Estado Actual del Desarrollo

| Módulo | Estado |
|---|---|
| Autenticación y roles | Completo |
| Catálogo de prendas | Completo |
| Órdenes de Fabricación | Completo |
| Gates documentales | Completo |
| Hoja de Costos con versiones | Completo |
| Curvas de Tallas | Completo |
| Plan de Corte | Completo |
| Seguimiento de Corte | Completo |
| OF Muestra (fast-track) | Completo |
| Plantas Externas | Completo |
| Comercial (lista + formulario) | Completo |
| Reporte PDF corte | Completo |
| Dashboard con indicadores | Pendiente (base lista) |
| Rediseño visual (login, catálogo, OFs, muestra) | Completo |
| Exportación Excel Hoja de Costos | Pendiente |
