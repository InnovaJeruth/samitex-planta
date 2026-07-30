"""of_trazos.capas_tendidas — tendido por partes (acumulado)

Agrega el acumulador de capas realmente tendidas para permitir registrar el
tendido en varias sesiones (ej: 30 y luego 20) hasta cubrir lo planeado.

Revision ID: 20260710_capas_tend
Revises: 20260709_normaliz
Create Date: 2026-07-10
"""
from alembic import op
import sqlalchemy as sa

revision = '20260710_capas_tend'
down_revision = '20260709_normaliz'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    cols = {c['name'] for c in insp.get_columns('of_trazos')}
    if 'capas_tendidas' not in cols:
        op.add_column(
            'of_trazos',
            sa.Column('capas_tendidas', sa.Integer(), nullable=False, server_default='0'),
        )


def downgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    cols = {c['name'] for c in insp.get_columns('of_trazos')}
    if 'capas_tendidas' in cols:
        op.drop_column('of_trazos', 'capas_tendidas')
