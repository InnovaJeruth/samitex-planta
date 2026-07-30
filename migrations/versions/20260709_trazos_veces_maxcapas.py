"""Alinea trazos al Excel: veces por talla + max_capas por OF

Aditivo: veces en of_trazo_tallas (composición del dibujo) y max_capas en
ordenes_fabricacion (override del tope de capas por placa).

Revision ID: 20260709_trazos_veces
Revises: 20260708_trazos
Create Date: 2026-07-09
"""
from alembic import op
import sqlalchemy as sa

revision = '20260709_trazos_veces'
down_revision = '20260708_trazos'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    cols_trazo_tallas = {c['name'] for c in insp.get_columns('of_trazo_tallas')}
    if 'veces' not in cols_trazo_tallas:
        op.add_column('of_trazo_tallas', sa.Column('veces', sa.Integer(), nullable=False, server_default='1'))
    cols_of = {c['name'] for c in insp.get_columns('ordenes_fabricacion')}
    if 'max_capas' not in cols_of:
        op.add_column('ordenes_fabricacion', sa.Column('max_capas', sa.Integer(), nullable=True))


def downgrade():
    op.drop_column('ordenes_fabricacion', 'max_capas')
    op.drop_column('of_trazo_tallas', 'veces')
