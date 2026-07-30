# Análisis SRS vs. Sistema Actual — Samitex Planta
**Fecha:** Julio 2026 | **SRS versión:** 1.0 | **Referencia:** SRS_Samitex_Requerimiento_a_Corte_v1.docx

---

## Resumen Ejecutivo

| Estado | Cantidad | % |
|---|---|---|
| ✅ Cumple completamente | 12 | 11% |
| 🟡 Cumple parcialmente | 22 | 20% |
| ❌ No existe | 66 | 59% |
| ➖ Excluido del alcance (SRS §6.3) | 10 | — |

El sistema actual cubre bien el núcleo operativo (OF, catálogo, corte, gates documentales), pero el SRS define un alcance sustancialmente mayor: módulos completos de Modelaje, Almacén, Compras, Habilitado y Calidad de Corte que no existen. Aproximadamente el 70% del SRS requiere desarrollo nuevo.

---

## Módulo Comercial (RF-001 a RF-006)

| Req | Descripción | Estado | Brecha | Esfuerzo |
|---|---|---|---|---|
| RF-001 | Registrar pedidos diferenciando Instituciones / Marca | 🟡 Parcial | La OF tiene `tipo_cliente` (INSTITUCIÓN/MARCA) pero no hay módulo de "pedido" previo a la OF; el flujo empieza directamente en la OF | Bajo |
| RF-002 | Cargar bases de tallaje desde Excel/CSV por cliente institucional | ❌ No existe | No hay importación de tablas de tallas por cliente. Curvas de tallas existen pero son distribución %, no medidas | Medio |
| RF-003 | Registrar pedidos de Marca con especificaciones de origen | 🟡 Parcial | Se puede crear OF de tipo MARCA pero no hay campos de especificaciones de origen del cliente marca | Bajo |
| RF-004 | Autonumeración correlativa de requerimiento | 🟡 Parcial | La OF tiene `numero_of` pero es ingresada manualmente. No hay autonumeración parametrizable | Bajo |
| RF-005 | Notificación automática a Desarrollo y Planeamiento al formalizar | 🟡 Parcial | Existe Telegram Bot pero no notificación por correo con registro de destinatarios | Bajo |
| RF-006 | Consultar estado del requerimiento en todo el flujo | 🟡 Parcial | La lista de OFs muestra estado; no hay vista de trazabilidad end-to-end tipo "expediente" | Medio |

---

## Módulo Diseño / Desarrollo — UDP (RF-010 a RF-016)

| Req | Descripción | Estado | Brecha | Esfuerzo |
|---|---|---|---|---|
| RF-010 | Registrar conceptualización con adjuntos (bocetos, referencias) | ❌ No existe | No hay módulo UDP. La OF acepta documentos pero no hay etapa de conceptualización | Medio |
| RF-011 | Registrar validaciones de muestra física con resultado aprobado/rechazado | ❌ No existe | Solo hay un gate "MUESTRA_APROBADA" como adjunto binario, sin historial de rechazos ni observaciones | Alto |
| RF-012 | Ciclo iterativo de re-diseño cuando la muestra es rechazada (versionado) | ❌ No existe | No existe lógica de ciclo iterativo ni versionado de muestras físicas | Alto |
| RF-013 | Elaborar y versionar Fichas Técnicas digitales | 🟡 Parcial | La Ficha Técnica existe como adjunto (archivo subido), no como formulario estructurado con campos | Alto |
| RF-014 | Elaborar Hojas de Costos vinculadas al requerimiento | ✅ Cumple | HojaCostos con versiones, líneas de costo, aprobación y historial implementado | — |
| RF-015 | Catálogo parametrizable de avíos con códigos y proveedores | 🟡 Parcial | Hay catálogo de avíos por prenda (CatalogoAvio) pero sin catálogo global de avíos con proveedores, códigos SAP ni precios históricos | Medio |
| RF-016 | Registro de aprobación formal del cliente con fecha, responsable y adjunto | 🟡 Parcial | Solo el campo de fecha en HojaCostos.aprobada_por; no hay registro completo de aprobación del cliente externo | Bajo |

---

## Módulo Modelaje (RF-020 a RF-025)

> **Este módulo no existe en el sistema.** El sistema actual no tiene ninguna entidad relacionada con Modelaje, moldes CAD, tablas de tallas por cliente ni validación con Calidad. Todas son brechas completas.

| Req | Descripción | Estado | Esfuerzo |
|---|---|---|---|
| RF-020 | Recibir y visualizar ficha técnica aprobada como insumo de Modelaje | ❌ No existe | Medio |
| RF-021 | Construir y registrar tablas de tallas por estilo/cliente | ❌ No existe | Alto |
| RF-022 | Registrar moldes en Modaris con archivos CAD vinculados al requerimiento | ❌ No existe | Alto |
| RF-023 | Registrar variantes por talla (archivo por variante) | ❌ No existe | Medio |
| RF-024 | Gestionar validación de molde con Calidad: ciclo corrección | ❌ No existe | Alto |
| RF-025 | Publicar molde aprobado hacia Corte con control de versión | ❌ No existe | Medio |

**Costo total Modelaje:** módulo nuevo completo — estimado **4–6 semanas**.

---

## Módulo Planeamiento (RF-030 a RF-041)

| Req | Descripción | Estado | Brecha | Esfuerzo |
|---|---|---|---|---|
| RF-030 | Consolidar requerimiento + ficha + HdC en expediente de planificación | 🟡 Parcial | La OF agrupa documentos pero no hay "expediente" con vista consolidada | Medio |
| RF-031 | Explosión BOM desde ficha técnica (telas, avíos, consumos por talla/cantidad) | ❌ No existe | El catálogo tiene plantilla de piezas y avíos pero no calcula BOM automático multiplciando por total_juegos y curva de tallas | Muy alto |
| RF-032 | Backward scheduling para Instituciones (fechas inversas desde contrato) | ❌ No existe | No hay lógica de cálculo de fechas. Solo `fecha_apt` ingresada manualmente | Alto |
| RF-033 | Margen flexible de fechas para Marca | ❌ No existe | Mismo caso que RF-032 | Bajo (si va junto a RF-032) |
| RF-034 | Programa de costura por línea/taller con fechas | ❌ No existe | El sistema llega hasta corte; costura no está en scope actual | Muy alto |
| RF-035 | Registro de lead time con proveedores de tela | ❌ No existe | No hay módulo de proveedores | Bajo |
| RF-036 | Programa de corte por etapa con versión y fechas | 🟡 Parcial | Existe Plan de Corte pero sin versiones formales ni etapas | Medio |
| RF-037 | Crear OF asociada al requerimiento con ficha y HdC | ✅ Cumple | OF vinculada a prenda del catálogo; gates requieren Ficha Técnica y HdC | — |
| RF-038 | Imprimir OF en PDF estandarizado | 🟡 Parcial | Existe PDF de reporte de corte; no hay PDF de OF en formato formal | Bajo |
| RF-039 | Formalizar OF con notificación por correo (registro de destinatarios y fecha) | ❌ No existe | Solo Telegram. No hay correo ni registro de formalización con acuse | Medio |
| RF-040 | Registrar entrega de OF al Almacén con acuse | ❌ No existe | No hay flujo de entrega física/digital de OF a Almacén | Bajo |
| RF-041 | Dashboard de estatus diario de Corte para Planeamiento | 🟡 Parcial | Existe seguimiento de corte en tiempo real vía WebSocket; no hay reporte diario automático consolidado | Medio |

---

## Módulo Sourcing / Compras (RF-050 a RF-054)

> **Este módulo no existe.** El sistema no tiene inventario, stock ni órdenes de compra.

| Req | Descripción | Estado | Esfuerzo |
|---|---|---|---|
| RF-050 | Validar stock de tela contra BOM y reservar | ❌ No existe | Muy alto |
| RF-051 | Generar OC cuando no hay stock (con lead time Texcorp 45 días) | ❌ No existe | Muy alto |
| RF-052 | Gestionar avíos: full pack vs. compra por catálogo | 🟡 Parcial | Campo `estampado_activo` existe; no hay gestión de modalidades de avíos | Medio |
| RF-053 | Seguimiento a proveedores con hitos y alertas de atraso | ❌ No existe | Muy alto |
| RF-054 | Integración con SAP (registro/sincronización de compras) | ❌ No existe | Muy alto |

**Costo total Compras:** módulo nuevo completo + integración SAP — estimado **3–5 meses**.

---

## Módulo Almacén de Insumos (RF-060 a RF-068)

> **Este módulo no existe.** No hay ninguna entidad de inventario, kardex, rollos ni picking.

| Req | Descripción | Estado | Esfuerzo |
|---|---|---|---|
| RF-060 | Recepcionar insumos contra guía de remisión (OC + proveedor) | ❌ No existe | Muy alto |
| RF-061 | Inspección visual y validación de metraje por rollo | ❌ No existe | Alto |
| RF-062 | Generar e imprimir etiquetas de rollo con QR/código de barras | ❌ No existe | Alto |
| RF-063 | Kardex con trazabilidad por rollo, lote, familia y ubicación | ❌ No existe | Muy alto |
| RF-064 | Gestionar ubicaciones de almacenamiento por familia | ❌ No existe | Medio |
| RF-065 | Picking de tela según BOM/OF con escaneo de rollos | ❌ No existe | Muy alto |
| RF-066 | Picking de avíos según OF | ❌ No existe | Alto |
| RF-067 | Emitir nota de salida hacia Corte | ❌ No existe | Alto |
| RF-068 | Descarga automática de stock al emitir nota de salida | ❌ No existe | Alto |

**Costo total Almacén:** módulo nuevo completo con kardex + hardware (PDAs, lectores, impresoras) — estimado **2–4 meses** solo software.

---

## Módulo Corte — Trazado / Tendido / Máquina (RF-070 a RF-081)

| Req | Descripción | Estado | Brecha | Esfuerzo |
|---|---|---|---|---|
| RF-070 | Recibir variantes por talla desde Modelaje | ❌ No existe | No hay repositorio de archivos de variantes | Medio |
| RF-071 | Agrupar variantes para conformar trazo | ❌ No existe | Lógica no existe | Medio |
| RF-072 | Registrar trazo de Marker con archivo y métricas | ❌ No existe | No hay entidad Trazo | Alto |
| RF-073 | Registrar eficiencia del trazo y alertar fuera de 85–87% | ❌ No existe | No existe | Medio |
| RF-074 | Marcar bloqueo de áreas de fusionado | ❌ No existe | No existe | Bajo |
| RF-075 | Publicar trazo a carpeta compartida con control de versión | ❌ No existe | No existe | Bajo |
| RF-076 | Imprimir guía visual del trazo | ❌ No existe | No existe | Bajo |
| RF-077 | Registrar parámetros de máquina por corte | ❌ No existe | No existe | Medio |
| RF-078 | Registrar tendido: mesa, capas, metraje, rollos | ❌ No existe | No existe | Medio |
| RF-079 | Registrar tratamiento de orillo de marca | ❌ No existe | No existe | Bajo |
| RF-080 | Registrar ejecución del corte con inicio/fin/operador | 🟡 Parcial | El seguimiento de corte registra piezas cortadas por talla; no hay inicio/fin ni operador | Bajo |
| RF-081 | Registrar refilado de cuchilla (prioridad baja) | ❌ No existe | No existe | Bajo |

**Costo total Módulo Corte (parte nueva):** estimado **3–5 semanas**.

---

## Módulo Habilitado y Calidad de Corte (RF-090 a RF-100)

> **Este módulo no existe.** No hay paquetes, numerado, fusionado, inspección ni V°B°.

| Req | Descripción | Estado | Esfuerzo |
|---|---|---|---|
| RF-090 | Numerar piezas correlativamente con trazabilidad | ❌ No existe | Alto |
| RF-091 | Conformar paquetes 1:1 de 40 piezas | ❌ No existe | Alto |
| RF-092 | Emitir ticket de paquete con QR (OF, talla, cantidad, correlativo) | ❌ No existe | Alto |
| RF-093 | Identificar si el estilo requiere fusionado | 🟡 Parcial | Campo `estampado_activo` existe en la OF | Bajo |
| RF-094 | Registrar prueba de temperatura de fusionado | ❌ No existe | Medio |
| RF-095 | Registrar fusionado con temperatura aplicada (150–155 °C) | ❌ No existe | Medio |
| RF-096 | Inspección de calidad por paquete (conforme/no conforme) | ❌ No existe | Alto |
| RF-097 | Gestionar reproceso de paquetes no conformes | ❌ No existe | Alto |
| RF-098 | V°B° digital con usuario, fecha y hora | ❌ No existe | Medio |
| RF-099 | Despacho a Costura con acuse de recepción | ❌ No existe | Medio |
| RF-100 | Estatus diario automático a Planeamiento | 🟡 Parcial | Hay seguimiento en tiempo real; no hay reporte diario automático | Bajo |

**Costo total Habilitado + Calidad:** módulo nuevo completo — estimado **4–6 semanas**.

---

## Requerimientos Transversales (RF-110 a RF-119)

| Req | Descripción | Estado | Brecha | Esfuerzo |
|---|---|---|---|---|
| RF-110 | RBAC completo por módulo y acción | ✅ Cumple | Roles: ADMIN, SUPERVISOR, PLANEAMIENTO, COMERCIAL, LECTURA | — |
| RF-111 | Trazabilidad end-to-end requerimiento → paquete Costura | 🟡 Parcial | Solo desde OF hasta corte; faltan módulos intermedios | Muy alto (depende de otros módulos) |
| RF-112 | Bitácora de auditoría inmutable (quién, qué, cuándo) | ❌ No existe | Hay timestamps en modelos pero no bitácora formal de transacciones | Medio |
| RF-113 | Catálogos parametrizables (clientes, proveedores, telas, familias, mesas, máquinas) | 🟡 Parcial | Hay catálogo de prendas, plantas, usuarios; faltan catálogos de proveedores, telas, mesas de corte, máquinas | Alto |
| RF-114 | Notificaciones y alertas configurables | 🟡 Parcial | Telegram Bot existe; no hay alertas configurables por usuario ni por umbral | Medio |
| RF-115 | Dashboard con indicadores (eficiencia trazo, cumplimiento fechas, no conformidades) | 🟡 Parcial | Dashboard base existe; indicadores de eficiencia y calidad no existen | Alto |
| RF-116 | Adjuntar documentos en cada etapa | ✅ Cumple | DocumentoOF, PrendaDocumento implementados | — |
| RF-117 | Exportar a Excel y PDF | 🟡 Parcial | PDF de reporte de corte existe; exportación Excel no existe | Medio |
| RF-118 | Etiquetas y tickets con QR/código de barras | ❌ No existe | No hay generación de QR ni integración con impresoras térmicas | Alto |
| RF-119 | Búsqueda global por N° requerimiento, OF, estilo, cliente o paquete | ❌ No existe | Búsquedas existen por módulo; no hay búsqueda global unificada | Medio |

---

## Requerimientos No Funcionales

| Req | Descripción | Estado | Brecha |
|---|---|---|---|
| RNF-01 | Interfaz responsive + PDAs/escáneres | 🟡 Parcial | Diseño desktop-first; no optimizado para PDAs ni pantallas táctiles |
| RNF-02 | Disponibilidad 99% | 🟡 Parcial | Depende de infraestructura de deploy; no evaluado |
| RNF-03 | Respuesta ≤ 2s transaccional, ≤ 1s etiquetas | 🟡 Parcial | No se ha medido formalmente; etiquetas no existen |
| RNF-04 | Auth + RBAC + contraseñas cifradas + expiración de sesión | ✅ Cumple | Implementado con cookies CSRF y hash de contraseñas |
| RNF-05 | Bitácora inmutable de transacciones críticas | ❌ No existe | No hay tabla de auditoría separada |
| RNF-06 | Integridad transaccional en movimientos de stock | ➖ N/A | No existe módulo de stock |
| RNF-07 | Integración SAP + intercambio archivos CAD | ❌ No existe | No hay integración de ningún tipo con SAP ni Lectra |
| RNF-08 | 50 usuarios concurrentes mínimo | 🟡 No evaluado | FastAPI es async; no se ha hecho prueba de carga |
| RNF-09 | Backups diarios automáticos con retención 30 días | ❌ No existe | No implementado en la aplicación (depende del DBA del servidor) |
| RNF-10 | Chrome/Edge + impresoras térmicas + lectores QR | 🟡 Parcial | Compatible con navegadores; no hay soporte de hardware de planta |
| RNF-11 | Arquitectura modular; catálogos sin cambios de código | ✅ Cumple | FastAPI con routers separados por módulo; catálogos editables vía admin |
| RNF-12 | Evidencias de aprobación conservadas para auditoría | 🟡 Parcial | Documentos adjuntos se conservan; no hay registro inmutable firmado |

---

## Tabla de Esfuerzo por Módulo Faltante

| Módulo | Estado actual | Esfuerzo estimado | Observaciones |
|---|---|---|---|
| Módulo Comercial (mejoras) | Parcial | 1 semana | Autonumeración, notificaciones correo, vista expediente |
| Módulo UDP / Diseño | No existe | 4–6 semanas | Ficha técnica estructurada, ciclo de muestras, versionado |
| Módulo Modelaje | No existe | 4–6 semanas | Tablas tallas, moldes CAD, validación con Calidad |
| Módulo Planeamiento (mejoras) | Parcial | 3–4 semanas | BOM, backward scheduling, programa costura, PDF OF |
| Módulo Compras | No existe | 8–12 semanas | Stocks, OC, proveedores, lead times |
| Integración SAP | No existe | 8–16 semanas | Depende de API SAP disponible; puede ser muy complejo |
| Módulo Almacén | No existe | 8–12 semanas | Kardex, kardex, picking, notas de salida, QR |
| Módulo Corte (ampliación) | Parcial | 3–5 semanas | Trazo, tendido, eficiencia, máquina |
| Módulo Habilitado + Calidad | No existe | 4–6 semanas | Paquetes, fusionado, inspección, V°B°, despacho |
| Transversales | Parcial | 2–3 semanas | Bitácora, exportación Excel, búsqueda global, QR |
| Hardware (PDAs, impresoras) | No existe | Variable | No es desarrollo de software; es adquisición + configuración |

**Total estimado de desarrollo:** **~45–70 semanas-desarrollador** para implementar el SRS completo desde el estado actual. Con un equipo de 2 desarrolladores, equivale aproximadamente a **6–9 meses adicionales** de trabajo.

---

## Priorización Recomendada

### Prioridad 1 — Completar lo que ya existe (2–4 semanas)
- Autonumeración de N° OF/Requerimiento
- PDF de OF estandarizado
- Exportación Excel (Hoja de Costos, listado de OFs)
- Bitácora de auditoría básica
- Búsqueda global

### Prioridad 2 — Módulos de alto valor operativo (2–3 meses)
- BOM automático desde catálogo × total_juegos × curva de tallas
- Módulo de Habilitado y Calidad de Corte (paquetes, V°B°, despacho a Costura)
- Dashboard de estatus diario de Corte para Planeamiento
- Generación de QR para paquetes

### Prioridad 3 — Módulos nuevos complejos (3–6 meses)
- Módulo UDP / Diseño (ficha técnica estructurada, ciclo de muestras)
- Módulo Modelaje
- Módulo Almacén (kardex, picking, notas de salida)

### Prioridad 4 — Integraciones externas (según disponibilidad SAP)
- Integración SAP (el mayor riesgo del proyecto; depende de APIs disponibles en la empresa)
- Integración con carpetas compartidas de archivos CAD (Modaris/Marker)

---

## Conclusión

El sistema actual es una base sólida y funcional para el flujo OF → Plan de Corte → Seguimiento. Cubre bien la columna vertebral del proceso. Sin embargo, el SRS define un sistema ERP de manufactura completo que incluye 5 módulos adicionales que actualmente no existen (Modelaje, Compras, Almacén, Habilitado, Calidad) y una integración con SAP que por sí sola puede ser tan compleja como todo lo demás junto.

La recomendación es avanzar por fases, priorizando los módulos de mayor impacto operativo inmediato antes de abordar las integraciones externas.
