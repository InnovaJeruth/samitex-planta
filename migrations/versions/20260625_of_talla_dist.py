"""
Fase 3: tabla of_talla_distribucion para curva de tallas en OF
"""
from alembic import op
import sqlalchemy as sa

revision      = '20260625_of_talla_dist'
down_revision = '20260625_sku_refactor'
branch_labels = None
depends_on    = None


def upgrade():
    op.create_table(
        'of_talla_distribucion',
        sa.Column('id',       sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('of_id',    sa.Integer, sa.ForeignKey('ordenes_fabricacion.id', ondelete='CASCADE'),   nullable=False),
        sa.Column('sku_id',   sa.Integer, sa.ForeignKey('prenda_skus.id',         ondelete='NO ACTION'), nullable=False),
        sa.Column('cantidad', sa.Integer, nullable=False, server_default='0'),
    )
    op.create_index('ix_of_talla_dist_of',      'of_talla_distribucion', ['of_id'])
    op.create_index('ix_of_talla_dist_of_sku',  'of_talla_distribucion', ['of_id', 'sku_id'], unique=True)


def downgrade():
    op.drop_index('ix_of_talla_dist_of_sku', table_name='of_talla_distribucion')
    op.drop_index('ix_of_talla_dist_of',     table_name='of_talla_distribucion')
    op.drop_table('of_talla_distribucion')
