# SAMITEX-PLANTA — Resumen del proyecto

## Qué es
Sistema web de seguimiento de producción textil, centrado en el **proceso de corte**
de una planta de confección. Registra Órdenes de Fabricación (OF), su documentación
previa (gates), el corte de tela por trazos/placas y el avance por pieza y talla.

## Stack técnico
- **Backend:** FastAPI (Python) + SQLAlchemy 2.0 ORM + Jinja2 (SSR, plantillas server-side).
- **BD:** Microsoft SQL Server (`mssql+pyodbc`, ODBC Driver 17).
- **Auth:** JWT en cookie HttpOnly (`samitex_token`) + protección CSRF. 14 roles (RolEnum:
  ADMIN, PLANEADOR, INGENIERIA, COMERCIAL, COMERCIAL_MARCA, PLANEAMIENTO_MARCA, UDP,
  LOGISTICA, CALIDAD, etc.).
- **Migraciones:** Alembic (deltas escritos a mano). `Base.metadata.create_all()` en
  `app/main.py` construye el esquema al arrancar (bootstrap). Head actual: `20260709_normaliz`.
- **Extras:** bot de Telegram, reportes PDF, WebSockets para actualizaciones en vivo,
  módulo de ingeniería industrial (fichas SAM, OLE, tendido, calidad, etc.).

## Dominio: proceso de corte (9 fases)
Orden de fases: `F1 Tizado → F2 Tendido → F3 Corte → F4 Numerado → F8 Estampado →
F9 Auditoría → F5 Fusionado → F6 Calidad → F7 Habilitado`.
- **F1–F3 (tela):** se gestionan por **trazos/placas** (markers). Un trazo agrupa tallas
  que se tienden y cortan juntas. `prendas = capas × veces`; `metros = capas × largo del
  tizado`. Tope de capas por placa (default 80, editable por OF). No se pueden cortar dos
  colores de tela en la misma mesa.
- **F4–F7 (confección/habilitado):** se registran por **pieza × talla** (granularidad fina),
  detrás del flag `corte_por_talla` en la OF (OFs nuevas = True; viejas = por pieza).

## Modelo de datos (núcleo)
- **Catálogo:** `prendas_catalogo` (prenda BASE define estructura; variantes INSTITUCION/MARCA
  con color propio) → `prenda_skus` (por talla), `catalogo_mp` (materia prima),
  `catalogo_avios` (avíos). Configs base↔variante (`prenda_mp_config`, `prenda_avio_config`)
  y overrides por SKU (`prenda_sku_mp_config`, `prenda_sku_avio_config`). `hojas_costos` +
  `hojas_costos_lineas` (con precios congelados/snapshot). `precios_historicos`.
- **Producción:** `ordenes_fabricacion` (OF) → `of_piezas` (piezas de la prenda),
  `of_fases_estado` (estado por pieza/fase/talla), `of_fase_tiempos` (inicio/fin prog. y real),
  `avance_registros` (log de avances), `of_talla_distribucion` (curva por talla de la OF).
- **Trazos:** `of_trazos` (cabecera: largo, capas, metraje teórico vs real, eficiencia) +
  `of_trazo_tallas` (tallas y veces por trazo).
- **Curvas de tallas:** `curvas_tallas` + `curvas_tallas_detalle` + `curvas_tallas_of`.
- **Tercerización:** `plantas_externas` + `terc_subproceso_log`, `terc_recepciones`,
  `terc_historial_fechas`.
- **Ingeniería:** 9 tablas `ing_*` (SAM, paradas, muestreo, tendido, calidad, OLE, fusionado,
  habilitado, ishikawa).

## Gates (requisitos documentales para activar una OF)
Cadena documental antes de activar: Ficha Técnica → Hoja de Costos → SOLPED Prenda, y en
paralelo Muestra Aprobada → (SOLPED MP → Orden de Compra → Confirmación Stock) y
(Reporte Tallas → Moldes Lectra). Flags para saltarse gates: `es_muestra` y `omitir_gates`
(OF de prueba, solo ADMIN/PLANEADOR).

## Estado actual (últimos cambios)
Se **recreó la BD limpia y normalizada** (se borró toda la data transaccional; se respaldó
y restauró catálogo + usuarios preservando IDs). Normalización aplicada:
- Eliminada `ordenes_fabricacion.planta_externa` (duplicaba `plantas_externas.nombre`).
- Eliminada columna huérfana `ordenes_fabricacion.fase_tercerizada`.
- Agregado `of_id` (FK) a las fichas `ing_*` (se conserva `of_numero` como clave de negocio).
- Corregido `ON DELETE RESTRICT` → `NO ACTION` (no soportado por SQL Server) en curvas de tallas.

**Verificado:** esquema en 3FN salvo denormalizaciones intencionales de caché
(`talla` junto a `sku_id`; snapshots de tercerización en OF; precios congelados en hojas de
costos). Sin columnas duplicadas ni huérfanos. Integridad referencial válida. Data restaurada:
12 usuarios, 14 prendas, 90 SKUs, 71 piezas, 7 MP, 31 avíos.
