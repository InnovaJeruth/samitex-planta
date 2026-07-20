# SAMITEX-PLANTA — Documentación del sistema

Sistema de seguimiento de Órdenes de Fabricación (OF) del área de corte de planta.
Estado a jul-2026. **164 tests en verde.**

---

## 1. Stack y arranque

- **Backend:** FastAPI + SQLAlchemy 2.0 + Jinja2 (SSR).
- **BD:** SQL Server (`mssql+pyodbc`, Driver 17). Tests en SQLite en memoria.
- **Auth:** JWT en cookie HttpOnly + CSRF. 14 roles.
- **Migraciones:** Alembic. Bootstrap adicional con `create_all()` + seed de fases.
- **Tiempo real:** WebSocket por OF (`ws_manager`).

Arranque local (PowerShell):

```powershell
cd samitex-planta
.\.venv\Scripts\Activate.ps1
alembic upgrade head        # aplica migraciones
pytest -q                   # corre la suite
uvicorn app.main:app --reload
```

BD: `PANO0142\SQLEXPRESS` / `SAMITEX-PLANTA` (Windows auth).

---

## 2. Estructura de carpetas

```
app/
  main.py            # app FastAPI, CSRF middleware, registro de routers, seed fases
  config.py          # settings (.env)
  constants.py       # ORDEN_FASES, NOMBRES_FASE, tope por paquete, etc.
  database/          # connection (engine, Base, get_db), seed
  core/              # auth (JWT/roles), csrf, templates, websocket_manager
  models/            # SQLAlchemy: of, pieza, fase, catalogo, curva_tallas,
                     #   ingenieria, planta, parametro, trazo, paquete, usuario
  services/          # of_service, corte_service, gate_service, trazo_service,
                     #   paquete_service, semaforo_service
  routers/           # auth, dashboard, of, corte, piezas, admin, ws, plantas,
                     #   comercial, supervisor, telegram_bot, pdf_report,
                     #   ingenieria, catalogo, curvas, hoja_costos, trazos, paquetes
  templates/         # base.html + of/, corte/, ...
migrations/versions/ # cadena Alembic
tests/               # pytest (164)
```

---

## 3. Proceso de corte — fases

`ORDEN_FASES = [F1, F2, F3, F4, F8, F9, F5, F6, F7]`

| Fase | Nombre | Dónde se gestiona |
|---|---|---|
| F1 | Tizado | Placas de corte (tela) |
| F2 | Tendido | Placas de corte (tela) |
| F3 | Corte | Placas de corte (tela) |
| F4 | Numerado | Paquetes (hoja de numeración) |
| F5 | Fusionado | Módulo Fusionado |
| F6 | Calidad | Cola de Calidad |
| F7 | **Liberado** (antes "Habilitado") | derivado de paquetes (entregado a costura) |
| F8 | Estampado | (si `estampado_activo`) |
| F9 | Auditoría | — |

En el cockpit (`/corte/<of>`), **F4/F5/F6/F7 se derivan de los paquetes** (no hay doble captura). F1–F3 (tela) vienen de Placas.

---

## 4. Modelo de datos (tablas)

### Núcleo OF / ingeniería / catálogo (preexistente)
- `ordenes_fabricacion` — la OF (numero_of, cliente, tipo_prenda, total_juegos, estado, tipo_cliente, estado_docs, prenda_catalogo_id, corte_por_talla, omitir_gates, es_muestra, tercerizado, fase_tercerizada, unidades_por_paquete, …).
- `of_piezas` — piezas de la OF (nombre, material, cantidad_x_prenda, **fusionado**).
- `of_talla_distribucion` — curva: cantidad por sku (talla).
- `of_fases_estado` — avance por (pieza × talla × fase) del sistema viejo.
- `of_fase_tiempos`, `of_fase_paradas`, `avance_registro` — tiempos, paradas, log de avance.
- `prenda_catalogo`, `prenda_skus`, `variantes`, `hojas_costos`, avíos, MP, `documentos_of` (gates), curvas de tallas.
- `of_trazos`, `of_trazo_talla`, `of_trazo_movimientos` — placas de corte / tendido / consumo de tela.

### Subsistema Paquetes / Calidad / Reprocesos (lo construido)

**`of_paquetes`** — el **bulto** (grano = talla + color + **tipo de pieza**):

| Columna | Nota |
|---|---|
| id, of_id (FK CASCADE), sku_id (talla+color), **pieza_id** (FK of_piezas) | |
| numero | correlativo del bulto por pieza (continuo entre tallas) |
| numero_desde, cantidad | rango de prenda + prendas del bulto (numero_hasta = derivado) |
| estado | `HABILITADO → FUSIONADO → POR_VALIDAR → STAND_BY → ENTREGADO` |
| fusionado_inicio, fusionado_fin | tiempos del módulo Fusionado |
| Único: `(of_id, pieza_id, numero)` | |

**`of_paquete_eventos`** — log de transiciones del bulto.

**`motivos_rechazo`** — catálogo de defectos de corte (CR01–CR53, de FR-GC-CR-001/002/003):

| Columna | Nota |
|---|---|
| codigo (CR##), descripcion, severidad | |
| **destino** | área fija del defecto (CORTE, FUSIONADO, DESMANCHADO, HABILITADO, TENDIDO, TIZADO, MODELISTA, GERENCIA, EXTERNO) |
| **destinos_alt** | alternativas (Calidad elige) — solo CR42/43/44/47 (Corte/Modelista), CR53 (Modelista/Tizado) |
| **rehacer_default** | irrecuperable → siempre rehacer (CR13 hueco) |
| activo | |

**`of_paquete_rechazos`** — piezas rechazadas de un bulto:

| Columna | Nota |
|---|---|
| paquete_id (FK CASCADE), motivo_id (FK), cantidad | |
| **destino** | área elegida (validada contra el catálogo) |
| **rehacer** | corta nueva (usa tela) |
| **solped** | N° SOLPED (SAP) para la tela del rehacer (trazabilidad) |
| estado | `PENDIENTE → EN_REPROCESO → ESPERA_TELA → REINGRESADO` |
| usuario_id, created_at, updated_at | |

**Derivados (no se guardan):** numero_hasta, talla, color, aprobadas, entregable, merma (material), corte_real, desvío.

---

## 5. Flujo del bulto (Calidad + Reprocesos)

```
Habilitado (numerar+sticker, Supervisor Corte)
  → [Fusionado] (solo piezas fus; iniciar/terminar en módulo Fusionado)
  → Por validar (Calidad audita el lote)
      → Aprobar todo → ENTREGADO (Liberado, a costura)
      → Rechazar N (con defecto CR + destino) → STAND-BY
          → Reproceso por área (Corte, Fusión, Desmanche, Habilitado, Tendido, Tizado)
              → Reingresar → (fusible vuelve a Fusionado; si no, a Calidad) → revalida
          → Rehacer (corta nueva, usa tela):
              → si hay tela: corta de retazo → reingresa
              → si NO hay tela: ESPERA_TELA → Panel Planeamiento
                   → registrar SOLPED (SAP) → "Tela recibida" → vuelve a Corte
Cierre: cuando todos los bultos quedan ENTREGADO → la OF pasa a COMPLETADA (gate a costura).
```

**Reglas de negocio clave:**
- **Nunca se pierde la unidad:** toda pieza irrecuperable se **rehace**. "Merma" = solo **desperdicio de material** (informativo), no baja lo entregado.
- **Destino por defecto** (autocompletado del catálogo, no editable salvo alternativas). Gerencia decide en los casos escalados; Modelista/Externo son "derivados".
- **Rehacer sin tela:** SOLPED/compra/entrega física viven en **SAP/Almacén**; este sistema registra el requerimiento, el N° de SOLPED y la recepción.

---

## 6. Roles, pantallas y endpoints

| Pantalla | Ruta | Rol |
|---|---|---|
| Hoja de numeración / bultos por talla | `/paquetes/<of_id>` | Supervisor Corte / Planeador / Admin |
| Cola de Calidad (transversal) | `/paquetes/calidad` | Calidad / Supervisor / Planeador / jefaturas |
| Bandeja de reprocesos (por área) | `/paquetes/reprocesos` | Corte / Fusionado / Supervisor / Admin |
| Módulo de Fusionado | `/paquetes/fusionado` | Fusionado / Supervisor / Admin |
| Panel de Planeamiento (tela + OFs) | `/paquetes/planeamiento` | Planeador / Admin |
| Cockpit de corte (F1–F7) | `/corte/<of_id>` | Corte / supervisión |

**Endpoints principales (`/paquetes/...`):**
`api/{of}/data`, `api/{of}/generar`, `api/{of}/tope`, `api/{of}/talla/{sku}/enviar` (lote a fusionado/calidad), `api/{of}/talla/{sku}/fusionado` (iniciar/terminar), `api/paquete/{id}/estado`, `api/paquete/{id}/validar`, `api/paquete/{id}/fusionado/iniciar|terminar`, `api/rechazo/{id}/tomar|reingresar|falta-tela|tela-recibida`, `api/calidad/data`, `api/reprocesos/data`, `api/fusionado/data`, `api/planeamiento/data`, `api/planeamiento/solped`.

---

## 7. Migraciones del subsistema (cadena, jul-2026)

`…_paquetes` → `_calidad_rechazos` (catálogo + 53 defectos) → `_bulto_por_pieza` → `_fusionado_tiempos` → `_destinos_defecto` (destino por CR) → `_destinos_alt` (alternativas + CR28/CR30→Gerencia) → `_merma_a_rehacer` (CR13→Corte) → `_rehacer_default` (CR13 siempre rehacer) → `_solped_tela` (SOLPED).

---

## 8. Pendientes

- **C5 — Cola de Gerencia + derivados:** pantalla donde Gerencia decide **Aprobar/pasa o Rehacer** los rechazos con destino Gerencia; y vista de **derivados** (Modelista/Externo), que hoy no tienen dónde gestionarse.
- **C6 — Admin del catálogo de defectos:** editar destino / alternativas / rehacer_default de cada CR sin tocar código.
- **C7 — Cierre de tests** + limpieza de constantes de merma en desuso.
- **UI:** cuando falta SOLPED, mostrar "Falta SOLPED" en vez del botón gris "Tela recibida" (claridad).
- **Q1–Q4 previos ya cerrados**; multicolor por OF soportado en el modelo.

---

## 9. Notas de operación

- Aplicar siempre `alembic upgrade head` tras un pull; el módulo requiere que las OFs tengan **piezas** (de la ficha) para generar bultos.
- El **tope** de prendas por bulto es configurable por OF (`unidades_por_paquete`, default 49).
- El desperdicio de tela por rehacer se avisa a Planeamiento; el pedido real de tela es en SAP.
