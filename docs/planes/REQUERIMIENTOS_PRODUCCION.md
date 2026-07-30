# Requerimientos (Muestra / Producción / Stock) — Plan Fase 1

_Diseño. No se programa hasta aprobar. Enfoque en 2 fases para no romper el flujo actual._

- **Fase 1 (esta):** Comercial **crea y registra** el requerimiento (captura estructurada, reemplaza el Excel). **No genera OFs.**
- **Fase 2 (después):** Planeamiento **elige un ítem y genera la OF**. Aquí se resuelven numeración-sin-SAP y "terno = N OFs".

Regla base: **todo es aditivo** (tablas y pantallas nuevas). No se toca `es_muestra`, ni el import SAP, ni las OFs existentes.

---

## 1. Modelo de datos (3 tablas nuevas)

**`requerimientos`** (cabecera — campos del Excel)
| Campo | Tipo | Nota |
|---|---|---|
| id | PK | |
| numero_req | str, único | "014-2026" |
| tipo | str | MUESTRA / PRODUCCION / STOCK |
| cliente | str | |
| proceso | str | ej. "PÚBLICO" |
| licitacion | str, null | "LICITACIÓN PÚBLICA … Nº 001-2026" |
| fecha_solicitud | date | |
| fecha_apt | date, null | entrega APT |
| ejecutivo | str, null | ejecutivo de cuentas |
| fecha_absolucion | date, null | |
| nota | text, null | |
| estado | str | BORRADOR → REGISTRADO |
| creado_por_id | FK usuarios | |
| created_at / updated_at | datetime | |

**`requerimiento_lineas`** (ítems — campos del Excel)
| Campo | Tipo | Nota |
|---|---|---|
| id | PK | |
| requerimiento_id | FK | |
| grupo | str, null | "PRIMER TERNO", "ZONA SELVA" (subtítulo) |
| item_num / sub_item | str, null | |
| articulo | str | código del Excel (LYI278…) |
| descripcion | str | BLUSA/SACO/PANTALÓN… |
| composicion | str, null | |
| proveedor_tela | str, null | |
| codigo_tela | str, null | |
| color | str, null | |
| tallaje | str | 'A' / 'B' / 'C' (qué sistema usa) |
| total | int | debe = suma de la curva |
| prenda_catalogo_id | FK, **null** | enlace OPCIONAL al catálogo |
| orden | int | |

**`requerimiento_linea_tallas`** (curva de tallas por línea)
| Campo | Tipo |
|---|---|
| id | PK |
| linea_id | FK |
| talla | str |
| cantidad | int |

**Tallajes (constantes):**
- **A:** 14.5, 15, 15.5, 16, 16.5, 17, 17.5, 18
- **B:** 28, 30, 32, 34, 36, 38, 40, 42
- **C:** XS, S, M, L, XL, 2XL, 3XL

**Integridad:** `numero_req` único; validar `total = Σ curva`; línea sin prenda permitida (queda texto).

---

## 2. Regla de la prenda (definida)

- La línea **siempre** lleva texto (`articulo` + `descripcion`); el enlace `prenda_catalogo_id` es **opcional**.
- **Muestra:** normalmente solo texto (la prenda aún no existe; UDP la crea después).
- **Producción / Stock:** se **espera** seleccionar la prenda del catálogo (ya creada); si aún no está, queda el texto y Planeamiento la resuelve en Fase 2.
- No se obliga a crear la prenda antes → no bloquea el caso institución (muestra primero).

---

## 3. UI (Comercial)

- **Lista de requerimientos** (nuevo) con filtro por tipo/estado.
- **Form nuevo/editar requerimiento:**
  - Cabecera (campos §1).
  - **Líneas dinámicas** (agregar/quitar), agrupables por "grupo".
  - Por línea: selector de **tallaje (A/B/C)** que muestra las columnas de talla correspondientes, **grilla de cantidades**, **total autocalculado**, y **autocomplete opcional** de prenda del catálogo.
  - Guardar como BORRADOR o REGISTRAR.
- El flujo de **muestra actual se deja intacto** (coexisten); más adelante se unifica.

---

## 4. Roles

- **Crear/editar requerimiento:** Comercial (ROLES_CREAR de comercial) + ADMIN.
- **Ver:** Comercial + Planeamiento + gerencia.
- (Fase 2: Planeamiento será quien genere las OFs.)

---

## 5. Fuera de alcance de la Fase 1 (van en Fase 2)

- Generar OFs desde el requerimiento (lo hará Planeamiento).
- Numeración de OF sin SAP.
- "Terno" = varias OFs.
- Gates por tipo, enlace definitivo a prenda.
- Importar el Excel (Opción C, fase posterior).

---

## 6. Migración y compatibilidad

- Migración Alembic **aditiva** (3 tablas nuevas). Cero cambios a tablas existentes.
- No se toca el módulo de muestra actual ni las OFs.

---

## 7. Sub-pasos de construcción (Fase 1)

1. **RP-1** · Modelos (`Requerimiento`, `RequerimientoLinea`, `RequerimientoLineaTalla`) + registro en conftest.
2. **RP-2** · Migración Alembic aditiva.
3. **RP-3** · Constantes de tallaje + `requerimiento_service` (crear/editar/validar total, listar).
4. **RP-4** · Router Comercial (endpoints crear/listar/detalle/editar) + roles.
5. **RP-5** · UI (lista + form con líneas dinámicas y grilla de tallas).
6. **RP-6** · Tests (creación, validación total = Σ curva, tallaje) + verificación pytest.

Cada sub-paso se entrega y se corre pytest, igual que las fases anteriores.

---

## 8. Preguntas abiertas (menores, no bloquean el diseño)

- ¿El `numero_req` lo digita Comercial o lo autogenera el sistema (correlativo)?
- ¿Un requerimiento puede mezclar tallajes A/B/C entre sus líneas? (el Excel sí lo permite → asumimos que sí, por línea).
- ¿"Grupo" (terno/zona) es solo etiqueta visual en Fase 1? (asumimos que sí).
