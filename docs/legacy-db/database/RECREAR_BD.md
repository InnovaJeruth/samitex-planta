# Recrear la BD limpia (wipe + normalización)

Borra toda la data transaccional y recrea el esquema ya normalizado, restaurando
solo el catálogo + usuarios desde un backup. **No pierdes prendas, variantes,
piezas, materias primas, avíos ni usuarios.** Sí se borran OFs, trazos, avances,
fichas de ingeniería y demás data de proceso.

## Qué cambia en el esquema (normalización)
- `ordenes_fabricacion.planta_externa` — **eliminada** (duplicaba `plantas_externas.nombre`; ahora se lee vía `planta_id`).
- `ordenes_fabricacion.fase_tercerizada` — columna huérfana **eliminada**.
- Fichas `ing_*` — nueva columna `of_id` (FK opcional a `ordenes_fabricacion`); `of_numero` se mantiene como clave de negocio para el llenado libre.

## Pasos (en el venv, con acceso a la BD)

1. **Backup del catálogo** (¡primero, antes de borrar nada!):
   ```
   python export_catalogo.py
   ```
   Genera `catalogo_backup.json`. Revisa que los conteos cuadren
   (usuarios, prendas, SKUs, piezas, MP, avíos, configs).

2. **Borrar el esquema.** En SQL Server Management Studio, sobre `SAMITEX-PLANTA`:
   ```sql
   -- Opción simple: recrear la base entera
   USE master;
   ALTER DATABASE [SAMITEX-PLANTA] SET SINGLE_USER WITH ROLLBACK IMMEDIATE;
   DROP DATABASE [SAMITEX-PLANTA];
   CREATE DATABASE [SAMITEX-PLANTA];
   ```
   (Si prefieres no recrear la base, basta con dropear todas las tablas.)

3. **Construir el esquema limpio.** Arranca el app una vez; `create_all()` crea
   todas las tablas desde los modelos (ya con los cambios de normalización):
   ```
   uvicorn app.main:app
   ```
   Detén el server cuando arranque sin errores.

4. **Alinear Alembic** con el esquema recién creado:
   ```
   alembic stamp head
   ```
   (El head ahora es `20260709_normaliz`. Los deltas futuros se aplican con
   `alembic upgrade head`.)

5. **Restaurar el catálogo + usuarios:**
   ```
   python import_catalogo.py
   ```
   Preserva los IDs originales (usa `IDENTITY_INSERT`), así que las relaciones
   base↔variante, piezas y configs siguen apuntando bien. Solo importa sobre
   tablas vacías; si una ya tiene filas, la salta.

## Notas
- El backup guarda fechas como texto ISO; `import_catalogo.py` las reconvierte a
  `date`/`datetime` según el tipo de columna (probado en round-trip).
- Para un entorno que **no** se borra (BD ya en uso), no recrees nada: aplica el
  delta con `alembic upgrade head` (la revisión `20260709_normaliz` quita
  `planta_externa`/`fase_tercerizada` y agrega `of_id` a las fichas `ing_`).
- Ver también `database/MIGRACIONES.md`.
