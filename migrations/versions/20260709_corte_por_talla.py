"""Fase B: corte por talla — flag en OF + sku_id/talla en OFFaseEstado

Aditivo. Las OFs existentes quedan con corte_por_talla=False (flujo por pieza,
sku_id NULL); las nuevas nacen con True (F4–F7 por pieza×talla).

Revision ID: 20260709_corte_talla
Revises: 20260709_trazos_veces
Create Date: 2026-07-09
"""
from alembic import op
import sqlalchemy as sa

revision = '20260709_corte_talla'
down_revision = '20260709_trazos_veces'
branch_labels = None
depends_on = None


def upgrade():
    # Flag por OF (existentes = False → flujo por pieza)
    op.add_column('ordenes_fabricacion',
                  sa.Column('corte_por_talla', sa.Boolean(), nullable=False, server_default='0'))
    # Talla en el estado de fase (F4–F7 cuando corte_por_talla)
    op.add_column('of_fases_estado', sa.Column('sku_id', sa.Integer(), nullable=True))
    op.add_column('of_fases_estado', sa.Column('talla', sa.String(length=20), nullable=True))
    # Unique ahora incluye sku_id (permite varias tallas por pieza×fase)
    op.drop_constraint('uq_of_pieza_fase', 'of_fases_estado', type_='unique')
    op.create_unique_constraint('uq_of_pieza_fase_sku', 'of_fases_estado',
                                ['of_id', 'pieza_id', 'fase_id', 'sku_id'])


def downgrade():
    op.drop_constraint('uq_of_pieza_fase_sku', 'of_fases_estado', type_='unique')
    op.create_unique_constraint('uq_of_pieza_fase', 'of_fases_estado',
                                ['of_id', 'pieza_id', 'fase_id'])
    op.drop_column('of_fases_estado', 'talla')
    op.drop_column('of_fases_estado', 'sku_id')
    op.drop_column('ordenes_fabricacion', 'corte_por_talla')
