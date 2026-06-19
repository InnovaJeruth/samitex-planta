# Samitex Planta — Sistema de Seguimiento de Producción

Sistema web interno para el área de Planta de Samitex. Reemplaza el seguimiento manual en Excel. Inicia con el Proceso de Corte y está diseñado para escalar a todos los procesos del flujo de venta institucional.

## Stack tecnológico

| Capa | Tecnología |
|---|---|
| Backend | Python 3.11 + FastAPI |
| Templates | Jinja2 (server-side rendering) |
| Tiempo real | WebSockets (FastAPI) |
| Base de datos | SQL Server (SAMITEX-PLANTA) |
| ORM | SQLAlchemy 2.0 |
| Auth | JWT + bcrypt |
| Servidor | Uvicorn (ASGI) |

## Estructura del proyecto

```
samitex-planta/
│
├── app/                        # Aplicación principal
│   ├── main.py                 # Entry point FastAPI
│   ├── config.py               # Configuración desde .env
│   │
│   ├── core/                   # Núcleo transversal
│   │   ├── auth.py             # JWT, login, roles
│   │   └── websocket_manager.py# Broadcast tiempo real
│   │
│   ├── database/
│   │   └── connection.py       # Engine SQLAlchemy + get_db()
│   │
│   ├── models/                 # Tablas de BD (SQLAlchemy)
│   │   ├── usuario.py          # Usuarios y roles
│   │   ├── of.py               # Órdenes de Fabricación + Documentos
│   │   ├── pieza.py            # Piezas (plantillas + OF)
│   │   └── fase.py             # Fases, estados, registros de avance
│   │
│   ├── schemas/                # Validación Pydantic (request/response)
│   │   ├── of.py
│   │   ├── pieza.py
│   │   └── fase.py
│   │
│   ├── routers/                # Endpoints por módulo
│   │   ├── auth.py             # POST /auth/login
│   │   ├── dashboard.py        # GET / (listado OFs + semáforo)
│   │   ├── of.py               # CRUD /of
│   │   ├── corte.py            # GET/POST /corte/{of_id}/fases
│   │   ├── piezas.py           # CRUD /piezas
│   │   ├── admin.py            # /admin (usuarios, config)
│   │   └── ws.py               # WebSocket /ws/of/{numero}
│   │
│   ├── services/               # Lógica de negocio
│   │   ├── of_service.py       # Activación OF, validaciones
│   │   ├── corte_service.py    # Motor de fases
│   │   └── semaforo_service.py # Cálculo de semáforo
│   │
│   └── templates/              # HTML Jinja2
│       ├── base.html
│       ├── auth/login.html
│       ├── dashboard/index.html
│       ├── of/crear.html · lista.html · detalle.html
│       ├── corte/seguimiento.html
│       └── admin/usuarios.html
│
├── static/                     # CSS, JS, imágenes
│   ├── css/
│   ├── js/
│   └── img/
│
├── database/scripts/           # Scripts SQL a ejecutar en BD
│   ├── 00_README.md
│   ├── 01_create_tables.sql
│   ├── 02_insert_fases_roles.sql
│   └── 03_insert_plantillas.sql
│
├── migrations/                 # Alembic (migraciones futuras)
├── tests/                      # pytest
├── .env.example                # Plantilla de configuración
├── requirements.txt            # Dependencias producción
├── requirements-dev.txt        # Dependencias desarrollo
└── setup_env.bat               # Script de setup Windows
```

## Inicio rápido

```bash
# 1. Setup del entorno (primera vez)
setup_env.bat

# 2. Configurar credenciales
# Editar .env con datos de BD y claves secretas

# 3. Ejecutar scripts SQL en orden
# SQL Server Management Studio → SAMITEX-PLANTA → ejecutar scripts 01, 02, 03

# 4. Iniciar servidor
.venv\Scripts\activate
uvicorn app.main:app --reload --port 8000

# 5. Abrir en navegador
# http://localhost:8000
# http://localhost:8000/api/docs  (Swagger, solo en DEBUG=True)
```

## Roles del sistema

| Rol | Permisos |
|---|---|
| ADMIN | Acceso total, gestión de usuarios |
| GERENTE_PLANTA | Todas las OFs, reportes, aprobaciones |
| JEFE_PLANTA | Gestión operativa de OFs |
| GERENCIA | Solo lectura + reportes ejecutivos |
| PLANEADOR | Crear/editar OFs, registrar avances |
| SUPERVISOR_CORTE | Ver y registrar avances de corte |
| SOLO_LECTURA | Solo visualización |

## Procesos cubiertos (v1.0)

- [x] Creación de Orden de Fabricación
- [x] Proceso de Corte (9 fases)
- [ ] Proceso de Costura *(v2.0)*
- [ ] Proceso de Acabado *(v2.0)*
- [ ] Proceso de Distribución *(v2.0)*
