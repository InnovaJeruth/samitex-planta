"""Ajuste B: sku_id + talla en avance_registros (trazabilidad por talla)

Aditivo. Registros viejos quedan con sku_id/talla NULL (flujo por pieza).

Revision ID: 20260709_avance_sku
Revises: 20260709_corte_talla
Create Date: 2026-07-09
"""
from alembic import op
import sqlalchemy as sa

revision = '20260709_avance_sku'
down_revision = '20260709_corte_talla'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('avance_registros', sa.Column('sku_id', sa.Integer(), nullable=True))
    op.add_column('avance_registros', sa.Column('talla', sa.String(length=20), nullable=True))


def downgrade():
    op.drop_column('avance_registros', 'talla')
    op.drop_column('avance_registros', 'sku_id')
