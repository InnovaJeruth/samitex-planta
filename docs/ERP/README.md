# Documentación del ERP — Samitex Planta

Sistema de seguimiento y control del **Proceso de Corte** de una planta textil,
integrado con SAP. Gestiona Órdenes de Fabricación (OF) desde su importación
hasta la entrega a Costura, con catálogo de prendas, costeo, calidad/reprocesos,
analítica de procesos y un chat analítico (NL→SQL) de solo lectura.

## Índice de la documentación

| Documento | Contenido |
|---|---|
| [ARQUITECTURA.md](ARQUITECTURA.md) | Stack, capas, flujo request-response, WebSocket, RAG, concurrencia. Con diagrama. |
| [BASE_DE_DATOS.md](BASE_DE_DATOS.md) | Esquema de la BD por dominios, tablas, FKs y herencia. Con diagrama ER. |
| [DOMINIO_Y_FLUJO.md](DOMINIO_Y_FLUJO.md) | Ciclo de vida de la OF, fases F1–F7, placas, paquetes, calidad/reprocesos, catálogo y herencia, requerimientos. |
| [SEGURIDAD.md](SEGURIDAD.md) | Autenticación JWT, roles y accesos, CSRF, rate-limit, RAG guard, secretos y endurecimiento. |
| [API_ENDPOINTS.md](API_ENDPOINTS.md) | Inventario de routers y endpoints con sus restricciones de rol. |
| [CONFIGURACION.md](CONFIGURACION.md) | Variables de entorno (`.env`) y su propósito. |
| [GLOSARIO.md](GLOSARIO.md) | Términos de negocio (OF, placa, bulto, gate, tallaje, etc.). |

> Documentación complementaria de operación/despliegue fuera de esta carpeta:
> `docs/DESPLIEGUE_CONCURRENCIA.md`, `docs/TAREAS_EN_FONDO.md`.

## Resumen del stack

- **Backend:** FastAPI (Python) con renderizado del lado del servidor (Jinja2).
- **ORM:** SQLAlchemy 2.0 · **Migraciones:** Alembic.
- **Base de datos:** Microsoft SQL Server (driver `pyodbc`, síncrono).
- **Tiempo real:** WebSocket (avisos de avance por OF).
- **Analítica:** motor de Process Mining propio + Chat analítico RAG (Text-to-SQL) sobre Gemini u Ollama, en modo solo lectura.
- **Integración:** importación de OFs desde el export Excel de SAP (transacción COIS).

## Mapa mental de módulos

- **Comercial / Requerimientos** — captura estructurada de pedidos (Fase 1).
- **Catálogo de prendas** — fichas técnicas con herencia base→variante, materiales, avíos, servicios, mano de obra y hoja de costos.
- **Órdenes de Fabricación (OF)** — creación manual o import SAP, gates documentales, planificación.
- **Proceso de Corte** — fases F1–F7 (tela por placas, luego por talla), numeración en bultos, calidad y reprocesos, tercerización.
- **Analítica** — Process Mining (DFG, cuellos, ruta crítica, animación) y Chat analítico.
- **Administración** — usuarios y roles.

## Cómo arrancar (desarrollo)

```
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --port 8000
```

Para producción y dimensionamiento, ver `docs/DESPLIEGUE_CONCURRENCIA.md`.
