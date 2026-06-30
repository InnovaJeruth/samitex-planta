"""Add procedencia to catalogo_mp

Revision ID: 20260626_mp_procedencia
Revises: 20260626_variante_items
Create Date: 2026-06-26
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = '20260626_mp_procedencia'
down_revision = '20260626_variante_items'
branch_labels = None
depends_on = None


def _col_exists(table, col):
    bind = op.get_bind()
    return col in [c['name'] for c in inspect(bind).get_columns(table)]


def upgrade():
    if not _col_exists('catalogo_mp', 'procedencia'):
        op.add_column('catalogo_mp',
            sa.Column('procedencia', sa.String(20), nullable=True))


def downgrade():
    pass
