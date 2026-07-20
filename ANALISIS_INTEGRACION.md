# Informe — Integración de los dos sistemas de planta Samitex

Comparativa entre **SAMITEX-PLANTA** (este proyecto) y **Corte-Planta** (el del README
adjunto), y cómo conectarlos para no duplicar esfuerzo.

---

## 1. Resumen ejecutivo

Son dos sistemas que **se solapan en el nombre ("corte") pero cubren alcances distintos**:

- **Corte-Planta (B)** modela el **flujo completo de la planta** — Almacén → Corte → Calidad → Entrega — a nivel de "subáreas" por orden, con historial de eventos. Es **ancho y poco profundo** en el corte (el corte es una subárea con corte real + metraje sobrante).
- **SAMITEX-PLANTA (A, este)** modela **el proceso de corte en detalle** — 9 fases (Tizado→Habilitado), placas/trazos, tendido/corte por partes, pieza×talla, gates documentales, catálogo de prendas/variantes/MP/avíos, tercerización, reportes. Es **profundo y angosto** en el corte.

**Conclusión:** no compiten, se **complementan**. La mejor jugada no es fusionarlos ni duplicar módulos, sino **definir una frontera clara de responsabilidades** y un **puente de datos** por la OF. B como orquestador del flujo de planta; A como el "motor de corte" detallado.

---

## 2. Qué hace cada uno

| Dimensión | Corte-Planta (B) | SAMITEX-PLANTA (A, este) |
|---|---|---|
| Stack | SPA JS vanilla + Supabase (Postgres) | FastAPI + SQLAlchemy + SQL Server + Jinja SSR |
| Auth | Propia: usuario + PIN (bcrypt), RPC | JWT en cookie HttpOnly + CSRF |
| Roles | 5 áreas (almacen, corte, calidad, ingeniería, gerencia) | 14 roles finos |
| Alcance | **Flujo planta**: Almacén (telas/avíos) → Corte → Calidad → Entrega PL/TLL | **Proceso de corte**: F1–F9, placas, pieza×talla, gates, catálogo |
| Orden | `of` + `color` + `nro_req` | `numero_of` (único) + variante de catálogo |
| Estado | Event-sourcing (tabla `eventos`, estado = último evento) | Estado por fila (`of_fases_estado`) + log de avances |
| Corte (detalle) | 1 subárea: corte real + metraje sobrante | 9 fases con tiempos, paradas, tendido/corte por capas |
| Tela / metros | despachados, devueltos, usados | proyectado vs real (m/prenda), placas, desvío |
| Calidad | subárea aprobado/rechazado | fase F6 (por pieza/talla) |
| Entrega | PL/TLL (planta/taller) | — (cierra en F7 Habilitado) |
| Catálogo | — (no tiene) | prendas base/variantes, SKUs, MP, avíos, hoja de costos |
| Reportes | Excel por día | PDF ficha OF + Excel placas + auditoría |
| Gerencia | Panel KPIs + alertas + Excel | Dashboard KPIs + reporte PDF |

---

## 3. Dónde se solapan (riesgo de doble esfuerzo)

1. **La orden de fabricación.** Ambos guardan la OF con color, tipo de prenda, fechas y cantidades. Es el mayor solapamiento → candidata #1 a **fuente única**.
2. **El corte.** B tiene `corte_planta` (corte real, metraje sobrante); A tiene todo el detalle. Si ambos capturan corte, se **duplica el dato** y se contradicen.
3. **Metros de tela.** B: despachados/devueltos/usados. A: proyectado/real/desvío por placa. Miden lo mismo desde distinto nivel.
4. **Calidad.** B subárea `calidad_corte`; A fase F6. Mismo concepto.
5. **Gerencia / KPIs / Excel por día.** Ambos lo tienen.
6. **Ingeniería crea órdenes + importa Excel.** Ambos.

## 4. Dónde se complementan (sin choque)

- **B aporta lo que A no tiene:** Almacén (telas y avíos), Entrega PL/TLL, y la visión de **flujo completo de planta** con calidad de avíos.
- **A aporta lo que B no tiene:** detalle fino de corte (placas, tendido/corte por partes, tiempos, paradas), **catálogo** de prendas/variantes/MP/avíos con costos, gates documentales y trazabilidad.

---

## 5. Diferencias técnicas que condicionan la integración

1. **Bases distintas:** SQL Server (A) vs Postgres/Supabase (B). No comparten BD directamente → integración por **API/servicio**, no por tablas compartidas.
2. **Identidad de la OF distinta:** A usa `numero_of` único; B usa la tripleta `of + color + nro_req`. Hay que definir una **clave común** (lo natural: `of + color + nro_req`, y que A guarde `nro_req`/`color` — A ya tiene color en la variante).
3. **Auth distinta:** JWT (A) vs PIN (B). Para llamadas máquina-a-máquina conviene un **token de servicio** aparte, no reusar el login humano.
4. **Modelo de estado distinto:** event-sourcing (B) vs estado por fila (A). El puente debe traducir (ej. "F7 Habilitado completo" de A → evento `corte_planta = ENTREGADO` en B).

---

## 6. Opciones de integración

### Opción 1 — Frontera de responsabilidades + puente de datos (recomendada)
Cada sistema es dueño de su etapa; se sincroniza solo lo necesario por la OF.

- **B = orquestador del flujo** (Almacén, Calidad, Entrega, gerencia global).
- **A = motor de corte** (todo F1–F7, placas, catálogo, consumo).
- **Puente:** cuando B crea/programa una orden, se la **empuja a A** (o A la lee); cuando A termina el corte (o por fase), **devuelve a B** el resultado (corte real, metros usados, estado) como un evento.
- Pros: mínimo re-trabajo, cada equipo sigue en su stack, bajo acoplamiento.
- Cons: hay que construir y mantener el puente (2 endpoints + un job de sync) y acordar la clave de OF.

### Opción 2 — Un sistema "maestro de órdenes" + el otro como módulo
Uno manda (fuente única de la OF) y el otro consume por API.
- Ej.: B maestro de órdenes → A recibe las de corte por API y publica avances.
- Pros: una sola alta de OF. Cons: acopla más; define dependencia dura.

### Opción 3 — Consolidar en uno solo
Migrar todo a A o todo a B.
- Pros: cero duplicación a largo plazo. Cons: **esfuerzo alto**, reescribir módulos maduros de un lado; no recomendado ahora.

---

## 7. Recomendación

**Opción 1**, con esta frontera:

| Etapa | Dueño |
|---|---|
| Alta/programación de la OF | Definir **uno** (sugerido: donde ya se cargan hoy más órdenes) |
| Almacén telas/avíos | B |
| **Corte (F1–F7, placas, tela, tiempos)** | **A** |
| Calidad de corte | A (detalle) → espeja estado a B |
| Calidad avíos, Entrega PL/TLL | B |
| Catálogo prendas/MP/avíos/costos | A |
| KPIs de planta (end-to-end) | B |

Y un **puente mínimo**: 
1. Sync de la OF (alta + fechas + cantidades) del maestro hacia el otro.
2. A publica "corte terminado / avance" → B lo registra como evento de `corte_planta`.

---

## 8. Mapeo de datos clave (para el puente)

| Concepto | A (SAMITEX-PLANTA) | B (Corte-Planta) |
|---|---|---|
| Clave de orden | `numero_of` (+ variante/color) | `of` + `color` + `nro_req` |
| Prenda | `tipo_prenda` / variante catálogo | `tipo_prenda`, `articulo`, `modelo` |
| Cantidad | `total_juegos` (prendas) | `corte_proyectado` |
| Corte real | Σ avance F3/F7 | `corte_real` |
| Metros usados | placas (capas×largo) / consumo real | `metros_usados` (despachados − devueltos) |
| Fecha que ordena | `fecha_apt` / `fecha_inicio_plan` | `fecha_programada` |
| Estado de corte | fases F1–F7 | subárea `corte_planta` |

**Falta acordar:** que A almacene `nro_req` (hoy no lo tiene explícito) para casar la clave con B.

---

## 9. Riesgos

- **Doble captura de corte** si no se define quién es dueño → datos que no cuadran. (Riesgo #1.)
- **Clave de OF inconsistente** (numero_of vs of+color+nro_req) → registros que no se casan.
- **Dos fuentes de "metros"** con definiciones distintas → KPIs contradictorios.
- **Sincronización no incremental** en B (trae todo cada 60s) → si el puente escala, revisar volumen.
- **Mantener dos stacks** (SQL Server + Supabase) tiene costo operativo permanente.

---

## 10. Próximos pasos sugeridos

1. Reunión de las dos partes para **acordar la frontera** (tabla del punto 7) y **quién es dueño de la OF**.
2. Definir la **clave común** de OF (agregar `nro_req`/`color` donde falte).
3. Especificar el **puente**: 2 endpoints (alta/actualización de OF ↔ avance de corte) + formato + auth de servicio.
4. Prueba piloto con 1–2 OFs reales antes de conectar en producción.
5. No construir en A lo que B ya hace (Almacén/Entrega) ni en B lo que A ya hace (detalle de corte/catálogo).
