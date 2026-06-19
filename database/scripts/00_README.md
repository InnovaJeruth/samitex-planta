# Scripts de Base de Datos — SAMITEX-PLANTA

Ejecutar en orden sobre la BD `SAMITEX-PLANTA` en `PANO0142\SQLEXPRESS`.

| Script | Descripción |
|---|---|
| `01_create_tables.sql` | Crea todas las tablas, constraints e índices |
| `02_insert_fases_roles.sql` | Inserta las 9 fases del proceso de corte + usuario admin inicial |
| `03_insert_plantillas.sql` | Inserta las plantillas de piezas: SACO (11), PANTALÓN (7), CAMISA (8) |

## Cómo ejecutar

```sql
-- En SQL Server Management Studio:
-- 1. Conectar a PANO0142\SQLEXPRESS
-- 2. Abrir cada script en orden
-- 3. Ejecutar (F5)
```

## Credenciales admin iniciales

- **Usuario:** `admin`
- **Contraseña:** `Admin2026!`
- Cambiar en primer ingreso desde el panel de administración.
