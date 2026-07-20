# Merge Guide — rama `desarrollo/sebastian` → `deploy`

> Commit a integrar: `307c11e`  
> Fecha: 2026-07-01  
> Rama origen: `desarrollo/sebastian`

---

## Qué se hizo en este commit

| Área | Cambio |
|------|--------|
| Tercerización por fase | Nueva UI y endpoints para tercerizar fases individuales en OFs EN_PROCESO |
| Recepciones parciales | Acumulación de juegos recibidos hasta completar total; fase se marca automáticamente |
| Curva de tallas | Cantidades editables antes del primer envío; bloqueadas después de vincular una OF |
| Curva actualiza su detalle | Al enviar a una OF con cantidades ajustadas, `curva_tallas_detalle` también se actualiza |
| Redirect muestra | Fix: al crear requerimiento de muestra redirige a `/of/{id}/detalle` |
| Catálogo MOLDE fix | Mapeo `MOLDE → MOLDES_LECTRA` al vincular documentos |

---

## Archivos modificados

```
app/routers/of.py
app/routers/corte.py
app/routers/curvas.py          ⚠️  usa shutil / os — ver sección Storage
app/routers/catalogo.py
app/routers/comercial.py
app/services/gate_service.py
app/services/of_service.py
app/templates/of/detalle.html
app/templates/supervisor/curva_detalle.html
app/templates/comercial/requerimiento_form.html
```

### Migraciones nuevas (correr `alembic upgrade head` en producción)

| Archivo | Qué hace |
|---------|----------|
| `20260630_fase_tercerizada.py` | Añade `fase_tercerizada VARCHAR(5)` nullable a `ordenes_fabricacion` |
| `20260630_terc_log.py` | Crea tabla `terc_subproceso_log` + columna `fase_id` en `terc_recepciones` |
| `20260701_es_muestra.py` | Añade `es_muestra BOOLEAN DEFAULT false` a `ordenes_fabricacion` |

**Cadena de revisiones Alembic:**
```
20260630_fc_tc → 20260630_fase_terc → 20260630_terc_log → 20260701_es_muestra
```
Asegúrate de que `20260630_fc_tc` ya exista en `deploy` antes de correr el upgrade.

---

## ⚠️ Compatibilidad PostgreSQL — acciones requeridas

### 1. Migration `20260701_es_muestra.py` — `server_default='0'`

```python
# Actual (SQL Server):
sa.Column('es_muestra', sa.Boolean(), nullable=False, server_default='0')

# Cambiar a (PostgreSQL):
sa.Column('es_muestra', sa.Boolean(), nullable=False, server_default='false')
```

### 2. `curvas.py` — operaciones de archivo deben usar `storage.py`

`curvas.py` usa escritura directa a disco. En producción necesita usar `app/services/storage.py`. Hay dos funciones afectadas:

**Función `api_adjuntar_doc` (subir archivo a curva):**
```python
# Actual (local):
upload_dir = os.path.join(settings.UPLOAD_DIR, "curvas", str(curva_id))
os.makedirs(upload_dir, exist_ok=True)
filepath = os.path.join(upload_dir, filename)
with open(filepath, "wb") as f:
    f.write(contenido)
# y también: os.remove(curva.ruta_archivo)

# Reemplazar por:
from app.services.storage import save_bytes, delete
ruta = save_bytes(contenido, f"curvas/{curva_id}", filename)
if curva.ruta_archivo:
    delete(curva.ruta_archivo)
```

**Función `api_vincular_ofs` (copiar archivo a carpeta de OF):**
```python
# Actual (local):
import shutil as _shutil
of_upload_dir = os.path.join(settings.UPLOAD_DIR, str(of_id))
os.makedirs(of_upload_dir, exist_ok=True)
copia_ruta = os.path.join(of_upload_dir, copia_nombre)
_shutil.copy2(curva.ruta_archivo, copia_ruta)

# Reemplazar por — leer el archivo y guardarlo con storage:
from app.services.storage import save_bytes, delete, read_bytes
contenido = read_bytes(curva.ruta_archivo)   # si storage.py tiene read_bytes
copia_ruta = save_bytes(contenido, str(of_id), copia_nombre)
# y los os.remove(doc_ex.ruta_archivo) → delete(doc_ex.ruta_archivo)
```

> Si `storage.py` no tiene `read_bytes`, agrégalo o usa `shutil.copy2` solo en dev y `save_bytes` en prod con flag `APP_ENV`.

### 3. Sin raw SQL nuevo

No se agregaron consultas con `TOP`, `GETDATE()`, `ISNULL()` ni `NVARCHAR`. Las migraciones usan tipos SQLAlchemy estándar (`String`, `Boolean`, `DateTime`, `Integer`). ✓

---

## Conflictos esperados en el merge

### `app/routers/curvas.py`
`deploy` probablemente ya tiene `curvas.py` adaptado con `storage.py`. Al mergear:
- Mantener la lógica de storage de `deploy`
- Integrar la nueva lógica de negocio de `sebastian` (actualizar `curva.detalle`, acumular cantidades)

### `app/routers/of.py`
Archivo grande. Revisar que el nuevo endpoint `GET /api/{of_id}/fases-pendientes` y los cambios en `api_registrar_recepcion` no colisionen con adaptaciones PostgreSQL ya hechas en `deploy`.

### `app/routers/catalogo.py`
`deploy` ya tiene este archivo con `storage.py`. Integrar solo el mapeo de tipos:
```python
_TIPO_CATALOGO_A_OF = {"MOLDE": "MOLDES_LECTRA"}
tipo_doc = _TIPO_CATALOGO_A_OF.get(body.tipo, body.tipo)
```

---

## Tablas nuevas en la base de datos

> El `.bak` de SQL Server ya las incluye. En Supabase hay que crearlas manualmente o via `alembic upgrade head`.

### `terc_subproceso_log`

```sql
CREATE TABLE terc_subproceso_log (
    id                    SERIAL PRIMARY KEY,
    of_id                 INTEGER NOT NULL REFERENCES ordenes_fabricacion(id),
    planta_id             INTEGER NOT NULL REFERENCES plantas_externas(id),
    fase_id               VARCHAR(5),
    estado                VARCHAR(20) NOT NULL DEFAULT 'PROGRAMADO',
    juegos_enviados       INTEGER,
    juegos_recibidos      INTEGER,
    fecha_programado      TIMESTAMP DEFAULT NOW(),
    fecha_envio           DATE,
    fecha_recepcion_est   DATE,
    fecha_recepcion_real  DATE,
    fecha_completado      TIMESTAMP,
    observacion           TEXT,
    usuario_creo_id       INTEGER REFERENCES usuarios(id),
    usuario_envio_id      INTEGER REFERENCES usuarios(id),
    usuario_recepcion_id  INTEGER REFERENCES usuarios(id)
);
```

### Columnas nuevas en tablas existentes

| Tabla | Columna | Tipo | Default |
|-------|---------|------|---------|
| `ordenes_fabricacion` | `fase_tercerizada` | `VARCHAR(5)` | NULL |
| `ordenes_fabricacion` | `es_muestra` | `BOOLEAN` | `false` |
| `terc_recepciones` | `fase_id` | `VARCHAR(5)` | NULL |

---

## Variables de entorno nuevas

Ninguna variable nueva en `config.py` en este commit. ✓

---

## Checklist para el desarrollador de deploy

- [ ] Cambiar `server_default='0'` → `'false'` en `20260701_es_muestra.py`
- [ ] Adaptar `curvas.py`: reemplazar `shutil`/`os.makedirs`/`open` por `storage.save_bytes` y `storage.delete`
- [ ] Correr `alembic upgrade head` en Supabase (3 migraciones nuevas)
- [ ] Verificar que la cadena de revisiones Alembic esté conectada desde `20260630_fc_tc`
- [ ] Probar flujo: crear OF muestra → redirige a `/of/{id}/detalle` ✓
- [ ] Probar flujo: curva de tallas → ajustar cantidades → enviar → verifica que OF y curva muestren los valores correctos

---

*Generado para commit `307c11e` — rama `desarrollo/sebastian` — 2026-07-01*
