"""Agrega es_muestra a ordenes_fabricacion

Revision ID: 20260701_es_muestra
Revises: 20260630_terc_log
Create Date: 2026-07-01
"""
from alembic import op
import sqlalchemy as sa

revision = '20260701_es_muestra'
down_revision = '20260630_terc_log'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'ordenes_fabricacion',
        sa.Column('es_muestra', sa.Boolean(), nullable=False, server_default='0')
    )


def downgrade():
    op.drop_column('ordenes_fabricacion', 'es_muestra')
