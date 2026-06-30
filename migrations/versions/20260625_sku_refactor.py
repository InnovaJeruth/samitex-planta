"""
SKU Refactor: catalogo_tallas → prenda_skus + sku configs + color en prendas_catalogo
down_revision apunta a la ultima migracion existente.
"""
from alembic import op
import sqlalchemy as sa

revision    = '20260625_sku_refactor'
down_revision = '20260625_catalogo_mp_tallas'
branch_labels = None
depends_on    = None


def upgrade():
    # 1. Agregar columna color a prendas_catalogo
    op.add_column(
        'prendas_catalogo',
        sa.Column('color', sa.String(50), nullable=True)
    )

    # 2. Crear tabla prenda_skus (reemplaza catalogo_tallas)
    op.create_table(
        'prenda_skus',
        sa.Column('id',                 sa.Integer,     primary_key=True, autoincrement=True),
        sa.Column('prenda_catalogo_id', sa.Integer,     sa.ForeignKey('prendas_catalogo.id', ondelete='CASCADE'), nullable=False),
        sa.Column('talla',              sa.String(20),  nullable=False),
        sa.Column('codigo_sku',         sa.String(50),  nullable=True),
        sa.Column('orden',              sa.Integer,     nullable=False, server_default='0'),
        sa.Column('activo',             sa.Boolean,     nullable=False, server_default='1'),
        sa.Column('created_at',         sa.DateTime,    server_default=sa.text('GETDATE()')),
    )
    op.create_index('ix_prenda_skus_prenda',       'prenda_skus', ['prenda_catalogo_id'])
    op.create_index('ix_prenda_skus_prenda_talla', 'prenda_skus', ['prenda_catalogo_id', 'talla'], unique=True)

    # 3. Migrar filas existentes de catalogo_tallas → prenda_skus
    op.execute("""
        INSERT INTO prenda_skus (prenda_catalogo_id, talla, orden, activo, created_at)
        SELECT prenda_catalogo_id, talla, orden, activo, created_at
        FROM catalogo_tallas
    """)

    # 4. DROP catalogo_tallas (ya migrado)
    op.drop_index('ix_catalogo_tallas_prenda', table_name='catalogo_tallas')
    op.drop_table('catalogo_tallas')

    # 5. Crear tabla prenda_sku_mp_config
    op.create_table(
        'prenda_sku_mp_config',
        sa.Column('id',               sa.Integer,    primary_key=True, autoincrement=True),
        sa.Column('sku_id',           sa.Integer,    sa.ForeignKey('prenda_skus.id',  ondelete='CASCADE'),   nullable=False),
        sa.Column('mp_id',            sa.Integer,    sa.ForeignKey('catalogo_mp.id',  ondelete='NO ACTION'), nullable=False),
        sa.Column('consumo_override', sa.Float,      nullable=False),
        sa.Column('notas',            sa.String(200), nullable=True),
        sa.Column('created_at',       sa.DateTime,   server_default=sa.text('GETDATE()')),
        sa.Column('updated_at',       sa.DateTime,   server_default=sa.text('GETDATE()')),
    )
    op.create_index('ix_sku_mp_config_sku_mp', 'prenda_sku_mp_config', ['sku_id', 'mp_id'], unique=True)

    # 6. Crear tabla prenda_sku_avio_config
    op.create_table(
        'prenda_sku_avio_config',
        sa.Column('id',              sa.Integer,    primary_key=True, autoincrement=True),
        sa.Column('sku_id',          sa.Integer,    sa.ForeignKey('prenda_skus.id',    ondelete='CASCADE'),   nullable=False),
        sa.Column('avio_id',         sa.Integer,    sa.ForeignKey('catalogo_avios.id', ondelete='NO ACTION'), nullable=False),
        sa.Column('codigo_override', sa.String(50), nullable=True),
        sa.Column('notas',           sa.String(200), nullable=True),
        sa.Column('created_at',      sa.DateTime,   server_default=sa.text('GETDATE()')),
        sa.Column('updated_at',      sa.DateTime,   server_default=sa.text('GETDATE()')),
    )
    op.create_index('ix_sku_avio_config_sku_avio', 'prenda_sku_avio_config', ['sku_id', 'avio_id'], unique=True)


def downgrade():
    # Revertir en orden inverso
    op.drop_index('ix_sku_avio_config_sku_avio', table_name='prenda_sku_avio_config')
    op.drop_table('prenda_sku_avio_config')

    op.drop_index('ix_sku_mp_config_sku_mp', table_name='prenda_sku_mp_config')
    op.drop_table('prenda_sku_mp_config')

    # Recrear catalogo_tallas
    op.create_table(
        'catalogo_tallas',
        sa.Column('id',                 sa.Integer,    primary_key=True, autoincrement=True),
        sa.Column('prenda_catalogo_id', sa.Integer,    sa.ForeignKey('prendas_catalogo.id', ondelete='CASCADE'), nullable=False),
        sa.Column('talla',              sa.String(20), nullable=False),
        sa.Column('orden',              sa.Integer,    nullable=False, server_default='0'),
        sa.Column('activo',             sa.Boolean,    nullable=False, server_default='1'),
        sa.Column('created_at',         sa.DateTime,   server_default=sa.text('GETDATE()')),
    )
    op.create_index('ix_catalogo_tallas_prenda', 'catalogo_tallas', ['prenda_catalogo_id'])

    # Migrar de vuelta
    op.execute("""
        INSERT INTO catalogo_tallas (prenda_catalogo_id, talla, orden, activo, created_at)
        SELECT prenda_catalogo_id, talla, orden, activo, created_at
        FROM prenda_skus
    """)

    op.drop_index('ix_prenda_skus_prenda_talla', table_name='prenda_skus')
    op.drop_index('ix_prenda_skus_prenda',       table_name='prenda_skus')
    op.drop_table('prenda_skus')

    op.drop_column('prendas_catalogo', 'color')
