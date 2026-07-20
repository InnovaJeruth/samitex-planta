"""Catálogo: hereda_ficha (variante usa ficha de la base o propia)

Aditivo. Bandera por variante: True = hereda la ficha (piezas/materiales) de su
base; False = ficha propia (override).

Revision ID: 20260718_catalogo_hereda_ficha
Revises: 20260717_catalogo_base_id
Create Date: 2026-07-18
"""
from alembic import op
import sqlalchemy as sa

revision = '20260718_catalogo_hereda_ficha'
down_revision = '20260717_catalogo_base_id'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if 'prendas_catalogo' not in set(insp.get_table_names()):
        return
    cols = {c['name'] for c in insp.get_columns('prendas_catalogo')}
    if 'hereda_ficha' not in cols:
        op.add_column('prendas_catalogo',
                      sa.Column('hereda_ficha', sa.Boolean(), nullable=False, server_default='1'))


def downgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if 'prendas_catalogo' not in set(insp.get_table_names()):
        return
    cols = {c['name'] for c in insp.get_columns('prendas_catalogo')}
    if 'hereda_ficha' in cols:
        op.drop_column('prendas_catalogo', 'hereda_ficha')
