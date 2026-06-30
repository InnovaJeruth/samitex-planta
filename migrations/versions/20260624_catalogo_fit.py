"""Agregar campo fit a prendas_catalogo

Revision ID: catalogo_fit_v1
Revises: catalogo_prendas_v1
Create Date: 2026-06-24
"""
from typing import Union
from alembic import op
import sqlalchemy as sa

revision: str = 'catalogo_fit_v1'
down_revision: Union[str, None] = 'catalogo_prendas_v1'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('prendas_catalogo',
        sa.Column('fit', sa.String(30), nullable=True))


def downgrade() -> None:
    op.drop_column('prendas_catalogo', 'fit')
