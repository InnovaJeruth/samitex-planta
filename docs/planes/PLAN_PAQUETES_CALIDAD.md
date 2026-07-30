# Plan de acción — Paquetes, Calidad y Reprocesos (consolidado)

Diseño final para analizar **antes** de codear. Modelo normalizado (3FN, sin datos
repetidos), máquina de estados, plan por fases y dependencias. Confirmado con los
ISO de calidad y las respuestas de planta (jul-2026).

---

## 1. Objetivo y alcance

Cerrar el proceso de corte de F4 en adelante: **numerar+habilitar en paquetes**,
**fusionar las piezas que lo requieran**, **auditar en Calidad** (aprobadas /
rechazadas con su defecto), **reprocesar o rehacer** las rechazadas, **stand-by**
hasta completar, y **entregar a costura por paquete**. Con corte real vs
proyectado y aviso de desvío/tela.

---

## 2. Decisiones confirmadas (planta)

- **Numerado + Habilitado = un solo paso** (contar + agrupar + sticker). El paquete **nace en HABILITADO** con su rango (`numero_desde`–`numero_hasta`). Por ahora lo **sube el Supervisor de Corte** (tiene operarios que lo ejecutan).
- **Fusionado = DESPUÉS de habilitado, por pieza**, según la **ficha técnica** (ella indica qué piezas fusionan). Las piezas sin fusionado **esperan** a que terminen las que sí; **todas van juntas a Calidad**.
- **Calidad audita el LOTE completo (100%, no muestreo)** una vez habilitado+fusionado. **Separa aprobadas y rechazadas.**
- Por cada pieza rechazada, Calidad registra el **defecto (código CR)** y le **asigna el destino: REPROCESO** (arreglar: recorte / refusión) **o REHACER** (de nuevo). *(Merma / "segundas" existe por el instructivo de No Conformes, pero por ahora el foco es reproceso/rehacer.)*
- El reproceso lo hace **el proceso que Calidad asigne** (Corte / Fusionado); Calidad **solo valida**.
- **Reingreso:** la pieza corregida **vuelve a Calidad**, se **re-valida** y puede volver a rechazarse. **Conserva su mismo número.**
- **Stand-by:** el paquete espera hasta que **todas** sus piezas estén aprobadas; recién ahí se entrega.
- **Entregado = enviado a costura.**
- **Rehacer consume tela:** Planeamiento **actualiza el consumo (al mayor)** y **solicita más tela**.
- **Multicolor:** una OF del mismo modelo **puede cortar varias telas de distinto color**. Cada paquete sigue siendo **1 talla + 1 color** (vía `sku_id`). → **multicolor ya soportado, no se pospone.**
- Estados del paquete: `HABILITADO → POR_VALIDAR → (STAND_BY) → ENTREGADO`.

---

## 3. Modelo de datos (depurado — sin datos repetidos)

### Ya existente (P1, hecho)
- `of_paquetes` (id, of_id, sku_id, numero, numero_desde, cantidad, estado, timestamps).
  - **Ajuste:** `estado` = `HABILITADO / POR_VALIDAR / STAND_BY / ENTREGADO` (nace en HABILITADO).
  - Derivados (no se guardan): `numero_hasta`, `talla`, `color`.
- `of_paquete_eventos` (log de transiciones del paquete). **Ajuste:** quitar columna `motivo` (vive en rechazos).
- `ordenes_fabricacion.unidades_por_paquete`.

### Nueva `motivos_rechazo` (catálogo de defectos — CR01…CR53)
| Columna | Tipo | Nota |
|---|---|---|
| `id` | PK | |
| `codigo` | String único | `CR01`…`CR53` |
| `descripcion` | String | "ANGULO CURVO", "FUSIONADO MAL AFINADO", … |
| `severidad` | String, nullable | `MAYOR` / `MENOR` (informativo por ahora) |
| `activo` | Boolean | |

> El **tipo de reproceso y la fase destino NO van en el catálogo**: los **decide Calidad
> en cada rechazo** (por eso viven en `of_paquete_rechazos`, no aquí). Catálogo mínimo.

### Nueva `of_paquete_rechazos`
| Columna | Tipo | Nota |
|---|---|---|
| `id` | PK | |
| `paquete_id` | FK → `of_paquetes` (CASCADE) | |
| `motivo_id` | FK → `motivos_rechazo` | el defecto CR |
| `cantidad` | Integer | unidades rechazadas con ese defecto |
| `tipo` | String | `REPROCESO` / `REHACER` / `MERMA` (lo elige Calidad) |
| `fase_destino` | String | proceso al que Calidad lo manda (Corte / Fusionado) |
| `estado` | String | `PENDIENTE → EN_REPROCESO → REINGRESADO` (o `MERMA`) |
| `usuario_id` | FK → usuarios | quién rechazó |
| `created_at` / `updated_at` | DateTime | |

### Fusionado (qué piezas fusionan)
Viene de la **ficha técnica** (por pieza). **A confirmar:** si ese dato ya está en el
catálogo del sistema o hay que capturarlo (marca `fusiona` por pieza del modelo).

### Derivados (nunca se guardan)
`numero_hasta`, `talla`, `color`, **aprobadas** (`cantidad − Σ rechazos activos`),
**entregable** (`aprobadas + reingresados_ok`), **merma** (`Σ rechazos MERMA`),
**stand-by** (tiene rechazos sin resolver), **corte real** (`Σ paquetes`),
**desvío** (`real − proyectado`).

### Denormalización deliberada (documentada)
Los `estado` en `of_paquetes` y `of_paquete_rechazos` son **caché del último estado**
para lectura rápida — mismo patrón que `of_fases_estado` / `of_trazos`.

---

## 4. Máquinas de estado

**Paquete:** `HABILITADO → POR_VALIDAR → ENTREGADO`, con desvío a `STAND_BY` si al
validar quedan rechazos; vuelve a `POR_VALIDAR` cuando reingresan y se re-valida.
(El numerado y el fusionado son a nivel de pieza; el paquete se crea habilitado.)

**Rechazo (pieza):** `PENDIENTE → EN_REPROCESO → REINGRESADO` (vuelve a Calidad y
se re-valida) o `→ MERMA`. El operario del proceso asignado hace `EN_REPROCESO → REINGRESADO`.

**Flujo completo:**
`Numerado/Habilitado (Supervisor Corte) → Fusionado por pieza (si ficha lo pide) →
Calidad audita el lote → aprobadas siguen / rechazadas a Reproceso o Rehacer →
reingreso → re-validación → paquete completo → Entregado a costura`.

---

## 5. Plan por fases

| Fase | Entregable | Verificación |
|---|---|---|
| **Q1 · Modelo + migración** | `motivos_rechazo` (+seed CR01–CR53), `of_paquete_rechazos`; ampliar `of_paquetes.estado`; quitar `of_paquete_eventos.motivo` | Esquema + FKs + único; migración compila |
| **Q2 · Servicio calidad/reproceso** | `validar_lote(aprobadas, rechazos[{motivo, cant, tipo, fase}])`, `marcar_reingresado`, re-validación, recálculo estado/entregable/desvío | Tests: parcial, stand-by→entregado, reingreso, desvío |
| **Q3 · Cola de Calidad (por rol, transversal a OFs)** | Router + pantalla: lotes habilitados por validar + panel aprobar/rechazar con defecto CR + destino | TestClient: listar, validar, rechazar, reingreso |
| **Q4 · Bandeja de reprocesos (por proceso/operario)** | Router + pantalla agrupada por proceso (Recorte/Refusión/Rehacer), con OF+color+talla+paquete + "Reingresar" | TestClient: listar por proceso, reingresar |
| **Q5 · Fusionado por pieza + integrar cockpit** | Marca `fusiona` por pieza (ficha), espera de fusionado antes de Calidad; F6/F7 del cockpit derivados de paquetes | Revisión de flujo, sin doble captura |
| **Q6 · Tela / PCP + alertas** | `REHACER` → actualizar consumo (al mayor) y solicitar tela a PCP; alerta de desvío | Test de desvío/consumo |
| **Q7 · Catálogo de defectos (admin)** | Pantalla alta/edición de `motivos_rechazo` (Calidad/Admin) | CRUD básico |
| **Q8 · Reportes** | Reporte de auditoría de corte por prenda (formato FR-GC-CR-001/002/003) + hoja de numeración en PDF/Excel | Genera PDF/Excel |
| **Q9 · Tests + verificación** | Suite completa del subsistema | Todo verde |

**Orden:** Q1 → Q2 → Q3 → Q4 (flujo usable de punta a punta) → Q5 → Q6 → Q7 → Q8 → Q9.

---

## 6. Dependencias / pendientes menores

1. **`Clasificacion_defectos_corte.xlsx`** — opcional: si quieren pre-sugerir REPROCESO/REHACER por defecto (igual Calidad decide al momento).
2. **Fusionado por pieza:** confirmar si la ficha técnica del sistema ya marca qué piezas fusionan, o hay que capturarlo.
3. **Numeración con multicolor:** definir si el correlativo es continuo o reinicia por color (default: continuo por OF).
4. **Tela para rehacer (Q6):** coordinar el "actualizar consumo al mayor / solicitar" con PCP / el otro sistema.
5. **Roles del sistema:** por ahora Supervisor de Corte sube numerado/habilitado; mapear Calidad y operarios de reproceso a usuarios.

---

## 7. Anexo — Catálogo de defectos de corte (de FR-GC-CR-001/002/003)

CR01 Ángulo curvo · CR02 Ángulo asimétrico · CR03 Ángulo fuera de medida · CR04 Corte
incompleto · CR05 Corte incorrecto · CR06 Desalineado · CR07 Descasado · CR08
Deshermanado · CR09 Ensanche incorrecto · CR10 Entretela incorrecta · CR11 Escalado
incorrecto · CR12 Fusionado mal afinado · CR13 Hueco · CR14 Mal aplomado · CR15 Mal
bloqueado · CR16 Mal cambio de pieza · CR17 Mal empalme · CR18 Mal enumerado · CR19
Mal habilitado · CR20 Mal rebaje · CR21 Mal tendido · CR22 Manchas (origen corte) ·
CR23 Marcas de goma · CR24 Margen incorrecto · CR25 Matching incorrecto · CR26 Medida
incorrecta x mal corte · CR27 Medida incorrecta x molde equiv. · CR28 Molde incorrecto ·
CR29 Pieza asimétrica · CR30 Pieza deforme · CR31 Pieza faltante · CR32 Pieza incorrecta ·
CR33 Pieza mal fusionada · CR34 Pieza sin enumerar · CR35 Pieza sin fusionar · CR36
Piezas con orillo · CR37 Piquete fuera de medida · CR38 Piquete fuera de posición · CR39
Punto sucio · CR40 Sentido de tela invertido · CR41 Sesgado · CR42 Sin bloquear · CR43
Sin perforación · CR44 Sin piquete · CR45 Sin variante · CR46 Soplado · CR47 Tajo fuera
de medida · CR48 Tendido tensionado · CR49 Tizado incompleto · CR50 Tizado incorrecto ·
CR51 Tizado montado · CR52 Tono entre piezas · CR53 Variante incorrecto.
