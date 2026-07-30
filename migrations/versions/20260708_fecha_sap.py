"""Agrega fecha_sap a ordenes_fabricacion

Fecha en que la OF se creo/subio en SAP (puede ser anterior a la fecha
de creacion en este sistema, que se guarda en fecha_creacion).

Revision ID: 20260708_fecha_sap
Revises: 20260708_omitir_gates
Create Date: 2026-07-08
"""
from alembic import op
import sqlalchemy as sa

revision = '20260708_fecha_sap'
down_revision = '20260708_omitir_gates'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'ordenes_fabricacion',
        sa.Column('fecha_sap', sa.Date(), nullable=True)
    )


def downgrade():
    op.drop_column('ordenes_fabricacion', 'fecha_sap')
