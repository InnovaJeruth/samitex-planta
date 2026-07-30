# API y endpoints — Samitex Planta

Los routers se registran en `app/main.py`. Salvo `/health`, `/auth/login`,
`/ws/*` y estáticos, **todo endpoint exige sesión** (`get_current_user`). Muchos
además restringen por conjunto de roles (`ROLES_*`, ver [SEGURIDAD.md](SEGURIDAD.md)).

## Infraestructura

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/health` | Healthcheck público (liveness + estado de BD). |
| — | `/static/*` | Archivos estáticos. |
| WS | `/ws/of/{of_numero}` | Suscripción a avisos de avance de una OF. |

Middlewares: `TrustedHostMiddleware` (Host), `CSRFMiddleware` (doble cookie +
cabeceras de seguridad).

## Autenticación · `/auth`

| Método | Ruta | Descripción |
|---|---|---|
| GET/POST | `/auth/login` | Página / autenticación (JWT en cookie, rate-limit). |
| GET | `/auth/me` | Usuario autenticado. |
| GET/POST | `/auth/logout` | Cierra sesión (revoca JTI). |

## Dashboard · (sin prefijo)

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/` | Dashboard principal. |
| GET | `/api/ofs-resumen` | Resumen de OFs (JSON). |

## Órdenes de Fabricación · `/of`

Mutaciones bajo `ROLES_PLANEAMIENTO`; import bajo `ROLES_IMPORT_OF`.

Listado/detalle (`/`, `/plan-corte`, `/{of_id}/detalle`, `/crear`), creación
(`POST /api/crear`), import SAP (`GET/POST /import-sap`, `/api/import-sap`),
piezas (`/api/{of_id}/piezas`, `/piezas/plantilla`, `/editar-piezas`),
documentos y gates (`/api/{of_id}/documentos`, `/api/documentos/{doc_id}/descargar`,
`/api/{of_id}/gates`, `PATCH /api/{of_id}/codigos`), activación/planificación
(`/api/{of_id}/activar`, `PATCH /api/{of_id}/planificar`), distribución de tallas
(`/api/{of_id}/tallas-dist`) y tercerización
(`/api/{of_id}/tercerizar[...]`).

## Proceso de Corte · `/corte`

Escritura bajo `ROLES_CORTE`. Cockpit (`/{of_id}`), estado (`/api/{of_id}/estado`,
`/estado-talla`), avance (`/api/{of_id}/avance`, `/completar`, `/talla-bulk`,
`/fase-bulk`, `/avance-bulk`, `/completar-bulk`), historial y reversión
(`/api/{of_id}/historial`, `/revertir/{registro_id}`), fases
(`/api/{of_id}/fases/strip`, `/fases/{fase_id}/iniciar`), paradas
(`/api/{of_id}/pausar`, `/reanudar`, `/paradas`).

## Trazos / placas · `/trazos`

Escritura bajo `ROLES_TRAZO`. Armador (`/{of_id}`), datos (`/api/{of_id}/data`),
fase de tela (`/api/{of_id}/fase/{fase_tela}/iniciar`), crear/eliminar placa
(`/api/{of_id}/crear`, `DELETE /api/trazo/{trazo_id}`), tope de capas
(`/api/{of_id}/max-capas`), tendido/corte (`/api/trazo/{trazo_id}/tendido`,
`/corte`), reporte Excel (`/api/{of_id}/reporte-excel`), movimientos.

## Paquetes / Numeración · `/paquetes`

Roles por vista: numerar `ROLES_NUMERAR`, calidad `ROLES_CALIDAD`, reproceso
`ROLES_REPROCESO`, fusionado `ROLES_FUSIONADO`, gerencia `ROLES_GERENCIA`, etc.

Bandejas: calidad, planeamiento (+ KPIs y SOLPED), reprocesos, planta-corte,
gerencia, derivados, fusionado. Cockpit por OF (`/{of_id}`, `/api/{of_id}/data`).
Numeración (`/api/{of_id}/numeracion/iniciar`, `/reabrir`, `/tope`, `/generar`).
Estados y calidad (`/api/paquete/{id}/estado`, `/validar`,
`/api/{of_id}/talla/{sku_id}/enviar`, `/aprobar-calidad`). Reprocesos
(`/api/rechazo/{id}/tomar|reingresar|terminar|falta-tela|tela-recibida`),
gerencia (`/gerencia/aprobar|rehacer`), dar OK (`/api/rechazo/{id}/ok`),
fusionado/re-fusionado.

## Catálogo de prendas · `/catalogo`

Edición bajo `ROLES_EDITOR_CATALOGO`. Listado/detalle/edición de prendas, herencia
de ficha (`/api/{id}/hereda-ficha`), piezas, imágenes, documentos (subir/copiar a
OFs), avíos, materia prima (MP), SKUs y tallas (con overrides por variante y por
SKU), OFs activas de la prenda, vincular muestra/documento.

## Hoja de costos · `/catalogo` (compartido)

Edición `ROLES_EDITOR_HDC`, aprobación `ROLES_APROBAR_HDC`, tipo de cambio
`ROLES_TC`. Prefill, obtener/guardar/aprobar hoja, historial de versiones e
historial de precios; endpoints de tipo de cambio del día.

## Curvas de tallas · `/curvas`

Acceso `ROLES_ACCESO_CURVAS`, edición `ROLES_EDITOR_CURVAS`. Listado, nueva,
detalle, crear/adjuntar/descargar, vincular a OFs, historial por prenda.

## Comercial · `/comercial` y Requerimientos · `/requerimientos`

Comercial: listado, nueva muestra (`ROLES_CREAR`). Requerimientos: listado/detalle
(`ROLES_REQ_VER`), crear/editar/registrar/eliminar y datos auxiliares (tallajes,
prendas) (`ROLES_REQ_EDITAR`).

## Supervisor · `/supervisor` y Plantas · `/plantas`

Supervisor: programación de tiempos de máquina (`ROLES_PROGRAMAR`). Plantas
externas: CRUD y activación (`ROLES_PLANTAS`).

## Ingeniería · `/ing`

Auth a nivel de router. Registros de ingeniería industrial: fichas, SAM, paradas,
muestreo, tendido, calidad (FPY), OLE, fusionado, habilitado e Ishikawa
(crear/listar/editar/eliminar).

## Reportes · (sin prefijo)

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/dashboard/reporte-pdf` | PDF del dashboard. |
| GET | `/of/{of_id}/reporte-pdf` | Ficha/reporte PDF de la OF. |

## Analítica · `/analitica` y Chat RAG · `/api`

Restringidos a `ROLES_ANALITICA` (solo lectura). Analítica: página, casos, DFG,
tiempos, KPIs, simulación, ruta crítica, animación. Chat: `GET/POST /api/chat`
(NL→SQL con barreras de seguridad).

## Administración · `/admin`

Todo bajo `ADMIN` (`require_roles`). Panel, crear usuario, activar/desactivar,
cambiar contraseña.
