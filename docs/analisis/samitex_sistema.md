# Samitex Planta — Sistema de Gestión de Producción

> Mini-ERP para el área de Corte de Samitex. Gestiona Órdenes de Fabricación (OF) desde su creación hasta el cierre, con trazabilidad por pieza y fase, planificación Gantt y alertas Telegram.

**Stack:** FastAPI · SQLAlchemy · SQL Server · Jinja2 · Python 3.10+  
**Estado:** En producción interna (desarrollo activo)  
**Fecha doc:** 2026-06-22

---

## Arquitectura General

```
Browser
  └── FastAPI (Jinja2 SSR)
        ├── /auth         → Login JWT (cookie)
        ├── /of           → Órdenes de Fabricación
        ├── /corte        → Seguimiento de fases
        ├── /dashboard    → KPIs y métricas
        ├── /plantas      → Plantas externas (tercerización)
        ├── /comercial    → Requerimientos comerciales
        ├── /supervisor   → Programación supervisor
        ├── /admin        → Gestión usuarios
        └── /telegram     → Bot webhook (Telegram + Gemini)
              └── SQL Server (Windows Auth)
```

---

## Módulos del Sistema

### 1. Órdenes de Fabricación (OF)
Entidad central del sistema. Cada OF representa un pedido de producción de prendas.

**Estados posibles:**
```
BORRADOR → ACTIVA → EN_PROCESO → COMPLETADA
                 ↘ ANULADA
```

**Campos principales:**

| Campo | Tipo | Descripción |
|---|---|---|
| `numero_of` | String | Identificador único (ej: "48965") |
| `cliente` | String | Nombre del cliente |
| `tipo_prenda` | Enum | CAMISA, PANTALON, POLO, etc. |
| `total_juegos` | Integer | Cantidad de prendas a producir |
| `estado` | Enum | BORRADOR / ACTIVA / EN_PROCESO / COMPLETADA |
| `tipo_cliente` | Enum | INSTITUCION / RETAIL / EXPORTACION |
| `fecha_apt` | Date | Fecha de entrega comprometida |
| `fecha_inicio_plan` | Date | Fecha inicio planificada (Gantt) |
| `tercerizado` | Boolean | Si se envía a planta externa |
| `estado_docs` | Enum | PENDIENTE / COMPLETO |

**Documentos requeridos por área:**

| Documento | Área responsable |
|---|---|
| FICHA_TECNICA | Comercial |
| SOLPED_PRENDA | Comercial |
| SOLPED_MP | Logística |
| ORDEN_COMPRA | Logística |

> La OF pasa automáticamente a ACTIVA cuando todos los documentos están completos.

---

### 2. Fases de Producción
Cada OF tiene piezas, y cada pieza pasa por 7 fases secuenciales:

```
F1 Tizado → F2 Tendido → F3 Corte → F4 Numerado → F5 Fusionado → F6 Calidad → F7 Habilitado
```

- El avance se registra por cantidad (unidades procesadas por fase)
- Una fase se completa cuando cantidad_actual = max_cantidad
- La OF se completa cuando todas las piezas terminan F7

**Restricciones:**
- No se puede registrar más del máximo permitido
- Las fases tienen cascada: F2 no puede superar lo que terminó F1
- Se puede pausar/reanudar con registro de motivo

---

### 3. Plan de Corte (Gantt)
Vista de planificación visual con arrastre de barras.

**Funcionalidades:**
- Asignar fecha inicio arrastrando la barra de la OF
- Segmentos de color por fase dentro de cada barra
- Guardrail de capacidad diaria (configurable, default 500 juegos/día)
- Alerta si el día destino supera la capacidad
- Barras de carga diaria en la cabecera del Gantt
- Panel de cumplimiento: planificado vs real últimos 14 días

**Tabla `parametros_sistema`:**
| Clave | Valor default | Descripción |
|---|---|---|
| `corte_cap_diaria_juegos` | 500 | Máx. juegos programables por día |

---

### 4. Tercerización
Una OF puede enviarse a una planta externa.

**Flujo:**
```
Tercerizar (asignar planta) → ENVIADA → RECIBIDA → [manual → COMPLETADA]
```

**Plantas externas registradas:** tabla `plantas_externas` con nombre, RUC, contacto, dirección.

**Datos trackeados:**
- Fecha de envío
- Fecha de recepción estimada y real
- Juegos recibidos
- Recepciones parciales

---

### 5. Bot Telegram + Gemini
Bot de consulta en tiempo real para gerencia y comerciales.

**Comandos:**
- `/start` — saludo + chat_id
- `"Como va la OF 48965"` → estado detallado de la OF
- Cualquier pregunta → Gemini responde con contexto de todas las OFs

**Capacidades del bot:**
- Estado de OF específica (fases, piezas, avance %)
- Listado de OFs activas
- Información de tercerización y recepciones
- Últimos 10 registros de avance

**NO puede:** modificar datos, registrar avances, acceder al Gantt.

---

## Base de Datos — Tablas Principales

```
ordenes_fabricacion          ← entidad central
├── documentos_of            ← archivos subidos por área
├── of_piezas                ← piezas de cada OF
│   └── of_fase_estado       ← estado de cada fase por pieza
├── of_fase_tiempos          ← inicio/fin programado y real por fase
├── of_fase_paradas          ← pausas con motivo y duración
├── avance_registros         ← historial de registros de cantidad
└── of_historial_tercerizado ← log de cambios de tercerización

plantas_externas             ← talleres/plantas externas
usuarios                     ← auth + roles
fases_catalogo               ← definición de fases con duracion_horas_std
parametros_sistema           ← configuración clave-valor
```

---

## Roles y Permisos

| Rol | Permisos clave |
|---|---|
| ADMIN | Todo |
| GERENCIA | Dashboard, lectura general |
| PLANEADOR | Plan de Corte, Gantt, capacidad |
| SUPERVISOR | Seguimiento, registrar avance, pausar fases |
| COMERCIAL | Subir docs Ficha Técnica / Solped Prenda |
| LOGISTICA | Subir docs Solped MP / Orden Compra |

---

## APIs Internas Principales

| Método | Ruta | Descripción |
|---|---|---|
| PATCH | `/of/api/{id}/planificar` | Asignar fecha inicio / forzar capacidad |
| GET | `/of/api/carga-diaria` | Carga planificada + real por día |
| PATCH | `/of/api/config/capacidad` | Actualizar capacidad diaria (PLANEADOR+) |
| POST | `/corte/{of_id}/{fase_id}/registrar` | Registrar avance de fase |
| POST | `/corte/{of_id}/{fase_id}/pausar` | Pausar fase con motivo |
| GET | `/bot/api/of/{numero_of}` | Detalle OF para bot (requiere X-Bot-Key) |

---

## Pendientes / Mejoras Identificadas

- [ ] Auto-transición OF tercerizada RECIBIDA → COMPLETADA
- [ ] Tests Bloque C pendientes de verificar
- [ ] `duracion_horas_std` sin datos en varias fases → segmentos Gantt incompletos
- [ ] Responsive mobile en dashboard y seguimiento
- [ ] Alertas proactivas Telegram (OFs con retraso, capacidad al límite)

---

## Estructura de Archivos

```
samitex-planta/
├── app/
│   ├── main.py
│   ├── config.py              ← settings (env vars)
│   ├── constants.py           ← ORDEN_FASES, NOMBRES_FASE
│   ├── models/                ← SQLAlchemy ORM
│   │   ├── of.py
│   │   ├── pieza.py
│   │   ├── fase.py
│   │   ├── planta.py
│   │   ├── usuario.py
│   │   └── parametro.py
│   ├── routers/               ← FastAPI routers
│   │   ├── of.py              ← 1100+ líneas, router principal
│   │   ├── corte.py
│   │   ├── dashboard.py
│   │   ├── plantas.py
│   │   ├── telegram_bot.py
│   │   └── ...
│   ├── services/
│   │   └── of_service.py      ← lógica de negocio extraída
│   └── templates/
│       ├── base.html
│       ├── of/
│       │   ├── plan_corte.html   ← Gantt custom (1360+ líneas)
│       │   ├── detalle.html
│       │   └── lista.html
│       └── corte/
│           └── seguimiento.html
├── database/
│   └── scripts/               ← 16 migraciones SQL numeradas
└── tests/                     ← pytest (103 tests)
```

---

*Generado automáticamente por el agente IA · Samitex Planta · 2026-06-22*
