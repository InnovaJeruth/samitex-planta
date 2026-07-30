"""Agrega omitir_gates a ordenes_fabricacion

OF de prueba: permite activar la OF sin gates documentales para trabajar
solo el proceso de corte y recabar data mientras se completa el flujo.

Revision ID: 20260708_omitir_gates
Revises: 20260701_es_muestra
Create Date: 2026-07-08
"""
from alembic import op
import sqlalchemy as sa

revision = '20260708_omitir_gates'
down_revision = '20260701_es_muestra'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'ordenes_fabricacion',
        sa.Column('omitir_gates', sa.Boolean(), nullable=False, server_default='0')
    )


def downgrade():
    op.drop_column('ordenes_fabricacion', 'omitir_gates')
