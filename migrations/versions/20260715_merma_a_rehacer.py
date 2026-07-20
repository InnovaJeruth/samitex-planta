"""Merma siempre se rehace: CR13 (hueco) pasa de MERMA a CORTE (cortar nueva)

Regla de negocio: una pieza irrecuperable no se pierde, se rehace. 'Merma' queda
solo como desperdicio de material (informativo). CR13 estaba como MERMA → CORTE.

Revision ID: 20260715_merma_a_rehacer
Revises: 20260715_destinos_alt
Create Date: 2026-07-15
"""
from alembic import op
import sqlalchemy as sa

revision = '20260715_merma_a_rehacer'
down_revision = '20260715_destinos_alt'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    if 'motivos_rechazo' in set(sa.inspect(bind).get_table_names()):
        op.execute(sa.text("UPDATE motivos_rechazo SET destino='CORTE' WHERE codigo='CR13'"))


def downgrade():
    bind = op.get_bind()
    if 'motivos_rechazo' in set(sa.inspect(bind).get_table_names()):
        op.execute(sa.text("UPDATE motivos_rechazo SET destino='MERMA' WHERE codigo='CR13'"))
