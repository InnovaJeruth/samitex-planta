# Base de datos y migraciones — fuente única (Alembic)

Esta guía unifica cómo se construye y evoluciona el esquema. **Alembic es la
fuente de verdad hacia adelante.** `env.py` importa todos los modelos, así que
`autogenerate` detecta cualquier cambio del modelo.

## Estado
- Cadena de migraciones **lineal, un solo head** (`alembic upgrade head` funciona).
- `migrations/env.py` con `target_metadata = Base.metadata` y `compare_type=True`.
- Los scripts en `database/scripts/` son **legado** (referencia histórica). No
  usarlos para cambios nuevos.

## Cambios de esquema (flujo normal)
1. Editar el modelo en `app/models/…`.
2. Generar la migración comparando modelos vs BD:
   ```
   alembic revision --autogenerate -m "descripcion_del_cambio"
   ```
3. **Revisar** el archivo generado (borrar ruido, ajustar defaults/constraints).
4. Aplicar:
   ```
   alembic upgrade head
   ```

## ⚠️ Sobre `--autogenerate` (importante)
NO se recomienda un "sync" masivo por autogenerate contra esta BD. Se probó y el
diff salió casi todo **ruido** (tipos nativos de SQL Server vs genéricos —
NVARCHAR/DATETIME2/DECIMAL—, nombres de índices propios) y con **DROPs
peligrosos** (`ordenes_fabricacion.fase_tercerizada`, `terc_subproceso_log.*`,
tabla `catalogo_tallas`) que romperían el app y perderían datos.

Conclusión práctica:
- **Bootstrap del esquema = `create_all()`** (al arrancar el app). Es la fuente
  de verdad del esquema base; construye una BD nueva completa desde los modelos.
- **Alembic = deltas explícitos escritos a mano** (como todas las migraciones de
  este proyecto). Es el registro de cambios versionado.
- Si usas `autogenerate` para UN cambio nuevo puntual, **revisa a fondo** el
  archivo y borra todo el ruido (type changes, índices, DROPs no deseados) antes
  de aplicarlo. Para cambios simples suele ser más seguro escribir la migración
  a mano.

## BD nueva (entorno limpio)
1. Arrancar el app una vez → `create_all()` crea todo el esquema desde los modelos.
2. `alembic stamp head` para alinear Alembic con esa BD.
(Los deltas futuros se aplican con `alembic upgrade head`.)

## BD existente ya en uso
- No recrear nada. Solo aplicar migraciones pendientes con `alembic upgrade head`.
- Si nunca se corrió Alembic contra ella: `alembic stamp <baseline>` y luego
  `alembic upgrade head`.

> Nota: `create_all()` en `app/main.py` se mantiene como comodidad de arranque.
> Una vez hecho el `sync_modelos`, Alembic y los modelos quedan alineados y el
> `create_all` deja de ocultar drift.
