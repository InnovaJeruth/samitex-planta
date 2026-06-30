"""Catálogo de prendas: nueva tabla prendas_catalogo, migración plantilla_piezas y ordenes_fabricacion

Revision ID: catalogo_prendas_v1
Revises: ingenieria_tablas_v1
Create Date: 2026-06-24

PREREQUISITO: Ejecutar reset_ofs.sql antes de aplicar esta migración.
"""
from typing import Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

revision: str = 'catalogo_prendas_v1'
down_revision: Union[str, None] = 'ingenieria_tablas_v1'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── 1. Crear tabla prendas_catalogo (solo si no existe — create_all pudo haberla creado) ──
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = inspector.get_table_names()

    if 'prendas_catalogo' not in existing_tables:
        op.create_table(
            'prendas_catalogo',
            sa.Column('id',             sa.Integer(),     nullable=False),
            sa.Column('codigo',         sa.String(30),    nullable=False),
            sa.Column('nombre',         sa.String(150),   nullable=False),
            sa.Column('tipo_base',      sa.String(20),    nullable=False),
            sa.Column('descripcion',    sa.String(500),   nullable=True),
            sa.Column('imagen_ruta',    sa.String(500),   nullable=True),
            sa.Column('activo',         sa.Boolean(),     nullable=False, server_default='1'),
            sa.Column('creado_por_rol', sa.String(30),    nullable=True),
            sa.Column('created_at',     sa.DateTime(),    server_default=sa.text('GETDATE()')),
            sa.Column('updated_at',     sa.DateTime(),    server_default=sa.text('GETDATE()')),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index('ix_prendas_catalogo_id',         'prendas_catalogo', ['id'])
        op.create_index('ix_prendas_catalogo_codigo',     'prendas_catalogo', ['codigo'], unique=True)
        op.create_index('ix_prendas_catalogo_tipo_activo','prendas_catalogo', ['tipo_base', 'activo'])

    # ── 2. Sembrar prendas base (si aún no existen) ──────────────────────────
    op.execute(text("""
        IF NOT EXISTS (SELECT 1 FROM prendas_catalogo WHERE codigo = 'SACO-BASE')
        INSERT INTO prendas_catalogo (codigo, nombre, tipo_base, descripcion, activo, creado_por_rol)
        VALUES
            ('SACO-BASE',    'Saco Base',    'SACO',    'Plantilla base para sacos',     1, 'SISTEMA'),
            ('PANT-BASE',    'Pantalon Base','PANTALON','Plantilla base para pantalones', 1, 'SISTEMA'),
            ('CAM-BASE',     'Camisa Base',  'CAMISA',  'Plantilla base para camisas',   1, 'SISTEMA'),
            ('OTRO-BASE',    'Otro Base',    'OTRO',    'Plantilla base para otros',      1, 'SISTEMA')
    """))

    # ── 3. Modificar plantilla_piezas ────────────────────────────────────────
    # 3a. Agregar columna prenda_catalogo_id (nullable inicialmente)
    op.add_column('plantilla_piezas',
        sa.Column('prenda_catalogo_id', sa.Integer(), nullable=True))
    op.add_column('plantilla_piezas',
        sa.Column('imagen_ruta', sa.String(500), nullable=True))

    # 3b. Poblar prenda_catalogo_id desde tipo_prenda (mapeo por tipo_base)
    op.execute(text("""
        UPDATE pp
        SET pp.prenda_catalogo_id = pc.id
        FROM plantilla_piezas pp
        JOIN prendas_catalogo pc ON pc.tipo_base = pp.tipo_prenda
        WHERE pc.codigo LIKE '%-BASE'
    """))

    # 3c. Para filas sin match (tipo_prenda no reconocido) → asignar OTRO-BASE
    op.execute(text("""
        UPDATE plantilla_piezas
        SET prenda_catalogo_id = (SELECT id FROM prendas_catalogo WHERE codigo = 'OTRO-BASE')
        WHERE prenda_catalogo_id IS NULL
    """))

    # 3d. Hacer NOT NULL y crear FK
    op.alter_column('plantilla_piezas', 'prenda_catalogo_id',
                    existing_type=sa.Integer(), nullable=False)
    op.create_foreign_key(
        'fk_plantilla_prenda_catalogo',
        'plantilla_piezas', 'prendas_catalogo',
        ['prenda_catalogo_id'], ['id']
    )
    op.create_index('ix_plantilla_piezas_prenda_orden', 'plantilla_piezas',
                    ['prenda_catalogo_id', 'orden'])

    # 3e. Eliminar columna tipo_prenda de plantilla_piezas
    #     SQL Server auto-genera nombres de CHECK constraints con nombres truncados,
    #     por eso buscamos por columna via sys.columns en vez de LIKE por nombre.
    op.execute(text("""
        DECLARE @cname NVARCHAR(200)
        SELECT @cname = cc.name
        FROM sys.check_constraints cc
        JOIN sys.columns c
          ON cc.parent_object_id = c.object_id
         AND cc.parent_column_id = c.column_id
        WHERE cc.parent_object_id = OBJECT_ID('plantilla_piezas')
          AND c.name = 'tipo_prenda'
        IF @cname IS NOT NULL
            EXEC('ALTER TABLE plantilla_piezas DROP CONSTRAINT [' + @cname + ']')
    """))
    op.drop_column('plantilla_piezas', 'tipo_prenda')

    # ── 4. Modificar ordenes_fabricacion ─────────────────────────────────────
    # 4a. Eliminar CHECK constraint del Enum tipo_prenda (si existe)
    #     Buscar por columna para evitar problemas con nombres truncados.
    op.execute(text("""
        DECLARE @cname NVARCHAR(200)
        SELECT @cname = cc.name
        FROM sys.check_constraints cc
        JOIN sys.columns c
          ON cc.parent_object_id = c.object_id
         AND cc.parent_column_id = c.column_id
        WHERE cc.parent_object_id = OBJECT_ID('ordenes_fabricacion')
          AND c.name = 'tipo_prenda'
        IF @cname IS NOT NULL
            EXEC('ALTER TABLE ordenes_fabricacion DROP CONSTRAINT [' + @cname + ']')
    """))

    # 4b. Cambiar tipo_prenda de Enum (VARCHAR con CHECK) a VARCHAR libre
    op.alter_column('ordenes_fabricacion', 'tipo_prenda',
                    existing_type=sa.String(20),
                    type_=sa.String(50),
                    nullable=False)

    # 4c. Agregar columna prenda_catalogo_id (nullable)
    op.add_column('ordenes_fabricacion',
        sa.Column('prenda_catalogo_id', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'fk_of_prenda_catalogo',
        'ordenes_fabricacion', 'prendas_catalogo',
        ['prenda_catalogo_id'], ['id']
    )

    # 4d. Poblar prenda_catalogo_id desde tipo_prenda existente
    op.execute(text("""
        UPDATE of2
        SET of2.prenda_catalogo_id = pc.id
        FROM ordenes_fabricacion of2
        JOIN prendas_catalogo pc ON pc.tipo_base = of2.tipo_prenda
        WHERE pc.codigo LIKE '%-BASE'
    """))

    # ── 5. Crear carpetas para uploads (se crearán físicamente en el router) ─
    # (no requiere SQL, el router se encarga de os.makedirs)


def downgrade() -> None:
    # Revertir en orden inverso

    # ordenes_fabricacion
    op.drop_constraint('fk_of_prenda_catalogo', 'ordenes_fabricacion', type_='foreignkey')
    op.drop_column('ordenes_fabricacion', 'prenda_catalogo_id')
    op.alter_column('ordenes_fabricacion', 'tipo_prenda',
                    existing_type=sa.String(50),
                    type_=sa.String(20),
                    nullable=False)

    # plantilla_piezas: restaurar tipo_prenda
    op.add_column('plantilla_piezas',
        sa.Column('tipo_prenda', sa.String(20), nullable=True))
    op.execute(text("""
        UPDATE pp
        SET pp.tipo_prenda = pc.tipo_base
        FROM plantilla_piezas pp
        JOIN prendas_catalogo pc ON pc.id = pp.prenda_catalogo_id
    """))
    op.alter_column('plantilla_piezas', 'tipo_prenda', nullable=False)
    op.drop_index('ix_plantilla_piezas_prenda_orden', 'plantilla_piezas')
    op.drop_constraint('fk_plantilla_prenda_catalogo', 'plantilla_piezas', type_='foreignkey')
    op.drop_column('plantilla_piezas', 'imagen_ruta')
    op.drop_column('plantilla_piezas', 'prenda_catalogo_id')

    # prendas_catalogo
    op.drop_index('ix_prendas_catalogo_tipo_activo', 'prendas_catalogo')
    op.drop_index('ix_prendas_catalogo_codigo',      'prendas_catalogo')
    op.drop_index('ix_prendas_catalogo_id',          'prendas_catalogo')
    op.drop_table('prendas_catalogo')
