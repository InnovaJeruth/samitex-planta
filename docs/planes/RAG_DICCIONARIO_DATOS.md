# Diccionario de datos — Capa semántica del RAG (Chat analítico)

_Fuente de verdad de lo que el modelo Text-to-SQL debe entender. El contexto que
consume el LLM se deriva de aquí (esquema + relaciones + glosario + ejemplos), pero
en forma compacta. Mantener este doc al día cuando cambie el modelo de datos._

Regla base del chat: **solo lectura**, sobre un **whitelist** de tablas/vistas. No
se expone toda la BD (empeora al modelo y arriesga datos sensibles).

---

## 1. Glosario del negocio

- **OF** (orden de fabricación): unidad central de producción; produce una prenda en varias tallas.
- **Fases:** F1 Tizado · F2 Tendido · F3 Corte (tela) · F4 Numerado · F5 Fusionado · F6 Costura · F7 Liberado (calidad).
- **OF atrasada:** `fecha_apt < hoy` y `estado <> 'COMPLETADA'`.
- **Bulto / paquete:** grupo de prendas numeradas (`of_paquetes`).
- **Rework / reproceso:** bultos rechazados en calidad (`of_paquete_rechazos`, `of_reproceso_hitos`).
- **Estados OF:** BORRADOR · ACTIVA · EN_PROCESO · COMPLETADA.
- **Estados de bulto:** HABILITADO · FUSIONADO · POR_VALIDAR · ENTREGADO · STAND_BY.
- **tipo_cliente:** INSTITUCION · MARCA.

---

## 2. Tablas del whitelist (Ola 1)

**Núcleo OF**

- `ordenes_fabricacion` — la OF. Claves: `numero_of` (ej. "4000010011"), `cliente`, `estado`, `total_juegos` (prendas), `fecha_apt` (entrega comprometida), `tipo_cliente`, `clase_orden`, `prenda_catalogo_id`.
- `of_talla_distribucion` — cantidades por talla (SKU) dentro de la OF: `of_id`, `sku_id`, `cantidad`.
- `of_piezas` — piezas que componen la OF: `of_id`, nombre, material.

**Tela y corte (F1–F3)**

- `of_trazos` — placas/tizados: capas, prendas por placa (`of_id`).
- `of_trazo_tallas` — tallas dibujadas en cada placa (`trazo_id`).
- `of_fase_tiempos` — inicio/fin real por fase: `of_id`, `fase_id` (F1..F7), `inicio_real`, `fin_real`. Nota: para esta OF suele tener poblados solo F1–F4.
- `of_fases_estado` — estado por pieza×talla×fase (`of_id`).
- `of_fase_paradas` — paradas por fase (tiempo perdido) (`of_id`).

**Numeración, fusionado, calidad, reprocesos (F4–F7)**

- `of_paquetes` — bultos: `of_id`, `estado`, `cantidad`, `fusionado_inicio`, `fusionado_fin`.
- `of_paquete_eventos` — transiciones de estado del bulto: `paquete_id`, `estado`, `created_at`, `usuario_id`.
- `of_paquete_rechazos` — rechazos de calidad: `paquete_id`, `motivo_id`, `cantidad`, `estado`. **No tiene `of_id`.**
- `motivos_rechazo` — catálogo de motivos: `codigo`, `descripcion`.
- `of_reproceso_hitos` — hitos del reproceso: `rechazo_id`, etapa, `at`.

**Catálogo y comercial**

- `prendas_catalogo` — prendas: `codigo`, `nombre`, `tipo_base`.
- `prenda_skus` — variantes por talla: `prenda_catalogo_id`, `talla`.
- `requerimientos` / `requerimiento_lineas` / `requerimiento_linea_tallas` — demanda comercial (cabecera → líneas → curva).

**Identidad**

- `vw_usuarios` (vista segura) — para "quién hizo X" (unir por `usuario_id`). Solo `id, nombre, username, rol, activo`; NUNCA contraseñas ni tokens. La tabla base `usuarios` está fuera del whitelist y denegada al login read-only.

---

## 3. Vistas de negocio (recomendado usarlas)

- `vw_of_fases` — **tiempos por fase de cada OF, unificados y con nombre**
  (Tizado/Tendido/Corte/Numerado/Fusionado/Calidad), con `inicio`, `fin`, `minutos`, `orden`.
  Junta `of_fase_tiempos` (F1–F4) + `of_paquetes` (Fusionado) + `of_paquete_eventos` (Calidad),
  igual que el módulo de Analítica. **Para cualquier pregunta de tiempos/duración por fase, usar esta vista** en vez de armar joins crudos. Script: `scripts/sql/vw_of_fases.sql`.

---

## 4. Relaciones (joins) clave

- `of_piezas.of_id`, `of_fase_tiempos.of_id`, `of_fases_estado.of_id`, `of_fase_paradas.of_id`, `of_trazos.of_id`, `of_talla_distribucion.of_id`, `of_paquetes.of_id` → `ordenes_fabricacion.id`
- `of_trazo_tallas.trazo_id` → `of_trazos.id`
- `of_talla_distribucion.sku_id` → `prenda_skus.id`
- `of_paquete_eventos.paquete_id`, `of_paquete_rechazos.paquete_id` → `of_paquetes.id`
- `of_reproceso_hitos.rechazo_id` → `of_paquete_rechazos.id`
- `of_paquete_rechazos.motivo_id` → `motivos_rechazo.id`
- `ordenes_fabricacion.prenda_catalogo_id`, `prenda_skus.prenda_catalogo_id` → `prendas_catalogo.id`
- `requerimiento_lineas.requerimiento_id` → `requerimientos.id`; `requerimiento_linea_tallas.linea_id` → `requerimiento_lineas.id`

**Trampa frecuente:** `of_paquete_rechazos` y `of_paquete_eventos` **no** tienen `of_id`.
Para filtrar por OF hay que pasar por `of_paquetes` (`paquete_id → of_paquetes.id → of_paquetes.of_id`).

---

## 5. Ejemplos pregunta → SQL (few-shots)

- "¿Cuántas OF están activas?" →
  `SELECT COUNT(*) FROM ordenes_fabricacion WHERE estado IN ('ACTIVA','EN_PROCESO');`
- "OF atrasadas con su cliente" →
  `SELECT TOP 200 numero_of, cliente, fecha_apt, estado FROM ordenes_fabricacion WHERE fecha_apt < CAST(GETDATE() AS DATE) AND estado <> 'COMPLETADA' ORDER BY fecha_apt;`
- "Duración de cada fase de la OF X" →
  `SELECT fase, minutos FROM vw_of_fases WHERE numero_of = 'X' ORDER BY orden;`
- "Rechazos por motivo de la OF X" →
  `SELECT m.descripcion, COUNT(*) AS total FROM of_paquete_rechazos r JOIN of_paquetes p ON p.id=r.paquete_id JOIN motivos_rechazo m ON m.id=r.motivo_id JOIN ordenes_fabricacion o ON o.id=p.of_id WHERE o.numero_of='X' GROUP BY m.descripcion ORDER BY total DESC;`

---

## 6. Cómo ampliar (olas siguientes)

Sumar dominios al whitelist **solo cuando se necesiten** (no abrir toda la BD):

- **Costos:** `hojas_costos`, `hojas_costos_lineas`, `catalogo_servicios`, `catalogo_mod`, `precios_historicos`.
- **Tercerización/logística:** `terc_recepciones`, `terc_subproceso_log`, `terc_historial_fechas`, `plantas_externas`.

Para cada dominio nuevo: agregar tablas al `WHITELIST`, sus descripciones, sus relaciones
y 1–2 few-shots. Si una pregunta requiere lógica de negocio compleja, crear una **vista**
(como `vw_of_fases`) en vez de esperar que el modelo arme el cálculo.
