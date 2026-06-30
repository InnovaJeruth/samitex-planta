"""factor_conversion y tipo_cambio en hoja costos

Revision ID: 20260630_fc_tc
Revises: d7285d68364d
Create Date: 2026-06-30

Agrega:
  - catalogo_avios.factor_conversion
  - catalogo_mp.unidad_compra
  - catalogo_mp.factor_conversion
  - hojas_costos.tipo_cambio
  - hojas_costos_lineas.unidad_compra
  - hojas_costos_lineas.factor_conversion
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '20260630_fc_tc'
down_revision: Union[str, None] = 'd7285d68364d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('catalogo_avios',
        sa.Column('factor_conversion', sa.Float(), nullable=False, server_default='1'))

    op.add_column('catalogo_mp',
        sa.Column('unidad_compra', sa.String(length=20), nullable=True))
    op.add_column('catalogo_mp',
        sa.Column('factor_conversion', sa.Float(), nullable=False, server_default='1'))

    op.add_column('hojas_costos',
        sa.Column('tipo_cambio', sa.Float(), nullable=False, server_default='3.70'))

    op.add_column('hojas_costos_lineas',
        sa.Column('unidad_compra', sa.String(length=20), nullable=True))
    op.add_column('hojas_costos_lineas',
        sa.Column('factor_conversion', sa.Float(), nullable=False, server_default='1'))


def downgrade() -> None:
    op.drop_column('hojas_costos_lineas', 'factor_conversion')
    op.drop_column('hojas_costos_lineas', 'unidad_compra')
    op.drop_column('hojas_costos', 'tipo_cambio')
    op.drop_column('catalogo_mp', 'factor_conversion')
    op.drop_column('catalogo_mp', 'unidad_compra')
    op.drop_column('catalogo_avios', 'factor_conversion')
