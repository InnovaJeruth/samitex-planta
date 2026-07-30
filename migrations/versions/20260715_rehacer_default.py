"""Rehacer por defecto: motivos_rechazo.rehacer_default (irrecuperables → siempre rehacer)

CR13 (hueco) es irrecuperable: no se recorta, se corta nueva. Se marca rehacer_default
para que en Calidad la casilla 'rehacer' salga activada y fija.

Revision ID: 20260715_rehacer_default
Revises: 20260715_merma_a_rehacer
Create Date: 2026-07-15
"""
from alembic import op
import sqlalchemy as sa

revision = '20260715_rehacer_default'
down_revision = '20260715_merma_a_rehacer'
branch_labels = None
depends_on = None

SIEMPRE_REHACER = ("CR13",)


def upgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if 'motivos_rechazo' not in set(insp.get_table_names()):
        return
    cols = {c['name'] for c in insp.get_columns('motivos_rechazo')}
    if 'rehacer_default' not in cols:
        op.add_column('motivos_rechazo',
                      sa.Column('rehacer_default', sa.Boolean(), nullable=False, server_default=sa.text('0')))
    for codigo in SIEMPRE_REHACER:
        op.execute(sa.text("UPDATE motivos_rechazo SET rehacer_default=1 WHERE codigo=:c").bindparams(c=codigo))


def downgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if 'motivos_rechazo' not in set(insp.get_table_names()):
        return
    cols = {c['name'] for c in insp.get_columns('motivos_rechazo')}
    if 'rehacer_default' in cols:
        op.drop_column('motivos_rechazo', 'rehacer_default')
