"""
Safe sync: agrega columnas/tablas que pudieron haberse saltado en aplicacion manual.
Todos los pasos usan IF NOT EXISTS / try-except para ser idempotentes.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

revision      = '20260626_safe_sync'
down_revision = '20260625_of_talla_dist'
branch_labels = None
depends_on    = None


def _col_exists(conn, table, column):
    r = conn.execute(text(
        "SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS "
        "WHERE TABLE_NAME=:t AND COLUMN_NAME=:c"
    ), {"t": table, "c": column})
    return r.scalar() > 0


def _table_exists(conn, table):
    r = conn.execute(text(
        "SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES "
        "WHERE TABLE_NAME=:t"
    ), {"t": table})
    return r.scalar() > 0


def upgrade():
    conn = op.get_bind()

    # 1. color en prendas_catalogo
    if not _col_exists(conn, 'prendas_catalogo', 'color'):
        op.add_column('prendas_catalogo',
            sa.Column('color', sa.String(50), nullable=True))

    # 2. prenda_sku_mp_config
    if not _table_exists(conn, 'prenda_sku_mp_config'):
        op.create_table(
            'prenda_sku_mp_config',
            sa.Column('id',               sa.Integer,     primary_key=True, autoincrement=True),
            sa.Column('sku_id',           sa.Integer,     sa.ForeignKey('prenda_skus.id',  ondelete='CASCADE'),   nullable=False),
            sa.Column('mp_id',            sa.Integer,     sa.ForeignKey('catalogo_mp.id',  ondelete='NO ACTION'), nullable=False),
            sa.Column('consumo_override', sa.Float,       nullable=False),
            sa.Column('notas',            sa.String(200), nullable=True),
            sa.Column('created_at',       sa.DateTime,    server_default=sa.text('GETDATE()')),
            sa.Column('updated_at',       sa.DateTime,    server_default=sa.text('GETDATE()')),
        )
        op.create_index('ix_sku_mp_config_sku_mp', 'prenda_sku_mp_config', ['sku_id', 'mp_id'], unique=True)

    # 3. prenda_sku_avio_config
    if not _table_exists(conn, 'prenda_sku_avio_config'):
        op.create_table(
            'prenda_sku_avio_config',
            sa.Column('id',              sa.Integer,     primary_key=True, autoincrement=True),
            sa.Column('sku_id',          sa.Integer,     sa.ForeignKey('prenda_skus.id',    ondelete='CASCADE'),   nullable=False),
            sa.Column('avio_id',         sa.Integer,     sa.ForeignKey('catalogo_avios.id', ondelete='NO ACTION'), nullable=False),
            sa.Column('codigo_override', sa.String(50),  nullable=True),
            sa.Column('notas',           sa.String(200), nullable=True),
            sa.Column('created_at',      sa.DateTime,    server_default=sa.text('GETDATE()')),
            sa.Column('updated_at',      sa.DateTime,    server_default=sa.text('GETDATE()')),
        )
        op.create_index('ix_sku_avio_config_sku_avio', 'prenda_sku_avio_config', ['sku_id', 'avio_id'], unique=True)

    # 4. of_talla_distribucion (por si of_talla_dist tampoco se aplicó)
    if not _table_exists(conn, 'of_talla_distribucion'):
        op.create_table(
            'of_talla_distribucion',
            sa.Column('id',        sa.Integer, primary_key=True, autoincrement=True),
            sa.Column('of_id',     sa.Integer, sa.ForeignKey('ordenes_fabricacion.id', ondelete='CASCADE'), nullable=False),
            sa.Column('talla',     sa.String(20), nullable=False),
            sa.Column('cantidad',  sa.Integer,    nullable=False, server_default='0'),
            sa.Column('created_at', sa.DateTime,  server_default=sa.text('GETDATE()')),
            sa.Column('updated_at', sa.DateTime,  server_default=sa.text('GETDATE()')),
        )
        op.create_index('ix_of_talla_dist_of', 'of_talla_distribucion', ['of_id'])
        op.create_index('ix_of_talla_dist_of_talla', 'of_talla_distribucion', ['of_id', 'talla'], unique=True)


def downgrade():
    pass  # safe sync no necesita downgrade
