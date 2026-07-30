"""Fusionado: tiempos de inicio/fin por bulto

Aditivo. Agrega of_paquetes.fusionado_inicio y fusionado_fin para el módulo de
Fusionado (registrar cuándo empieza y termina cada bulto).

Revision ID: 20260715_fusionado_tiempos
Revises: 20260714_bulto_por_pieza
Create Date: 2026-07-15
"""
from alembic import op
import sqlalchemy as sa

revision = '20260715_fusionado_tiempos'
down_revision = '20260714_bulto_por_pieza'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if 'of_paquetes' not in set(insp.get_table_names()):
        return
    cols = {c['name'] for c in insp.get_columns('of_paquetes')}
    if 'fusionado_inicio' not in cols:
        op.add_column('of_paquetes', sa.Column('fusionado_inicio', sa.DateTime(), nullable=True))
    if 'fusionado_fin' not in cols:
        op.add_column('of_paquetes', sa.Column('fusionado_fin', sa.DateTime(), nullable=True))


def downgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if 'of_paquetes' not in set(insp.get_table_names()):
        return
    cols = {c['name'] for c in insp.get_columns('of_paquetes')}
    if 'fusionado_fin' in cols:
        op.drop_column('of_paquetes', 'fusionado_fin')
    if 'fusionado_inicio' in cols:
        op.drop_column('of_paquetes', 'fusionado_inicio')
