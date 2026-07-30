# Glosario — Samitex Planta

Términos de negocio y técnicos que aparecen en el ERP.

## Negocio / producción

- **OF (Orden de Fabricación)** — Unidad central de producción: una prenda en
  varias tallas, con su curva, fases y documentos. Estados: BORRADOR, ACTIVA,
  EN_PROCESO, COMPLETADA, ANULADA.
- **Proceso de Corte** — El ámbito del sistema: de la tela cortada hasta la
  entrega a Costura. Fases F1–F7 (más F8/F9 opcionales).
- **Fases F1–F7** — F1 Tizado, F2 Tendido, F3 Corte (fases de **tela**); F4
  Numerado, F5 Fusionado, F6 Calidad, F7 Liberado/Habilitado (por **talla**).
  F8 Estampado y F9 Auditoría son opcionales.
- **Placa / Trazo (marker)** — Disposición de moldes sobre la tela. Combina
  **capas × veces** por talla; determina metros y prendas obtenidas. Las fases de
  tela (F1–F3) se gestionan por placas.
- **Capa** — Cada tendido de tela apilado; el corte procesa todas las capas a la
  vez. Hay un **tope de capas** por máquina.
- **Curva de tallas** — Distribución de cantidades por talla de un pedido/OF.
- **Bulto / Paquete** — Grupo de prendas numeradas por pieza×talla (tope
  `unidades_por_paquete`, default 49). Ciclo: HABILITADO → FUSIONADO →
  POR_VALIDAR → ENTREGADO / STAND_BY.
- **Numeración / Hoja de numeración** — F4: se generan los bultos. La hoja se
  cierra con un **candado** y puede **reabrirse** con motivo.
- **Fusionado** — Adherir entretela con calor/presión a las piezas que lo
  requieren (F5). Solo piezas con `fusionado=True`.
- **Calidad / Reproceso** — F6 valida bultos; los rechazos (catálogo
  `MotivoRechazo`, códigos CR01…CR53) se enrutan a reproceso por estación o se
  derivan (Modelista/Gerencia/Externo). "Rehacer" corta tela nueva y genera merma.
- **Liberado / Habilitado** — F7: la prenda cortada se entrega a Costura.
- **Merma** — Material perdido (p. ej. al rehacer piezas rechazadas); informativa.
- **Tercerización** — Enviar la OF a una **planta externa** (taller); se registran
  envío, recepción y subprocesos.
- **Gate** — Requisito documental/de código SAP que debe cumplirse para activar
  la OF (ficha técnica, hoja de costos, SOLPED, orden de compra, etc.).
- **Semáforo** — Indicador de una OF por su fecha APT: VENCIDO / ALERTA / A_TIEMPO.
- **APT** — Fecha de entrega comprometida de la OF.

## Catálogo / costeo

- **Prenda BASE vs VARIANTE** — La base define la ficha técnica; las variantes
  (Institución/Marca) cuelgan de ella (`base_id`) y aportan color y `material_sap`.
- **Herencia de ficha (`hereda_ficha`)** — Una variante toma piezas, materiales,
  avíos, servicios y mano de obra de su base, salvo override.
- **SKU** — Variante por **talla** de una prenda (`prenda_skus`).
- **MP (Materia Prima)** — Tela, entretela, forro, accesorios (con consumo y
  factores de conversión).
- **Avío** — Insumo de confección por sección: COSTURA / ACABADOS / EMBALAJE
  (botones, hilos, etiquetas…).
- **MOD (Mano de Obra Directa)** — Tiempos y costo por operación (corte, costura,
  acabado).
- **Hoja de costos (HDC)** — Costeo de la prenda (BORRADOR/APROBADA) con snapshot
  de precios y tipo de cambio del día.

## Comercial

- **Requerimiento** — Captura estructurada del pedido comercial (Fase 1): cabecera
  + líneas + curva. Tipos: MUESTRA / PRODUCCIÓN / STOCK.
- **Tallaje (A/B/C)** — Sistema de tallas de una línea: **A** cuello, **B**
  numérico, **C** letra.
- **Licitación** — Proceso de compra (frecuente en clientes Institución).

## SAP / integración

- **COIS** — Transacción SAP cuyo export Excel se importa para crear OFs.
- **Clase de orden (ZP41–ZP44)** — Tipo de OF en SAP: ZP41 Institución, ZP42
  Marca, ZP43 Reprocesos, ZP44 Servicios de terceros.
- **`material_sap`** — Código de material que enlaza la OF/variante con la prenda
  del catálogo.
- **SOLPED** — Solicitud de pedido (SAP). Aparece como gate y en reprocesos por
  falta de tela.

## Técnico

- **Gate (técnico)** — En `corte_service`, regla de cascada entre fases (una fase
  no supera a la anterior).
- **RAG / Text-to-SQL** — Chat analítico que traduce lenguaje natural a SQL de
  solo lectura sobre vistas de negocio.
- **DFG (Directly-Follows Graph)** — Grafo de "qué actividad sigue a cuál",
  base del Process Mining.
- **Ruta crítica (CPM)** — La secuencia de bultos/fases que determina el fin de
  la OF (considerando el paralelismo de bultos).
- **Gate documental** — Ver "Gate" en Negocio.
- **Semáforo / OLE / FPY / SAM** — Indicadores: estado por fecha; eficiencia
  global (OLE); rendimiento a la primera (FPY); tiempo estándar (SAM).
