"""of_trazos.capas_cortadas — corte por partes (acumulado)

Permite registrar el corte en varias sesiones (por si hay paradas), igual que
el tendido. Acumula hasta cubrir lo planeado (tz.capas).

Revision ID: 20260710_capas_cort
Revises: 20260710_capas_tend
Create Date: 2026-07-10
"""
from alembic import op
import sqlalchemy as sa

revision = '20260710_capas_cort'
down_revision = '20260710_capas_tend'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    cols = {c['name'] for c in insp.get_columns('of_trazos')}
    if 'capas_cortadas' not in cols:
        op.add_column(
            'of_trazos',
            sa.Column('capas_cortadas', sa.Integer(), nullable=False, server_default='0'),
        )


def downgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    cols = {c['name'] for c in insp.get_columns('of_trazos')}
    if 'capas_cortadas' in cols:
        op.drop_column('of_trazos', 'capas_cortadas')
