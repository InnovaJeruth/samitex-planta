"""Hoja de numeración: candado de cierre + auditoría de reapertura

Aditivo. Agrega ordenes_fabricacion.hoja_numeracion_cerrada (+ por/at) y la
tabla of_numeracion_reaperturas (quién reabre una hoja cerrada, cuándo y por qué).

Revision ID: 20260716_hoja_numeracion_cierre
Revises: 20260715_reproceso_hitos
Create Date: 2026-07-16
"""
from alembic import op
import sqlalchemy as sa

revision = '20260716_hoja_numeracion_cierre'
down_revision = '20260715_reproceso_hitos'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tablas = set(insp.get_table_names())

    if 'ordenes_fabricacion' in tablas:
        cols = {c['name'] for c in insp.get_columns('ordenes_fabricacion')}
        if 'hoja_numeracion_cerrada' not in cols:
            op.add_column('ordenes_fabricacion',
                           sa.Column('hoja_numeracion_cerrada', sa.Boolean(),
                                     nullable=False, server_default=sa.text('0')))
        if 'hoja_numeracion_cerrada_por' not in cols:
            op.add_column('ordenes_fabricacion',
                           sa.Column('hoja_numeracion_cerrada_por', sa.Integer(),
                                     sa.ForeignKey('usuarios.id'), nullable=True))
        if 'hoja_numeracion_cerrada_at' not in cols:
            op.add_column('ordenes_fabricacion',
                           sa.Column('hoja_numeracion_cerrada_at', sa.DateTime(), nullable=True))

    if 'of_numeracion_reaperturas' not in tablas:
        op.create_table(
            'of_numeracion_reaperturas',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('of_id', sa.Integer(),
                      sa.ForeignKey('ordenes_fabricacion.id', ondelete='CASCADE'), nullable=False),
            sa.Column('usuario_id', sa.Integer(), sa.ForeignKey('usuarios.id'), nullable=True),
            sa.Column('motivo', sa.String(length=300), nullable=False),
            sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        )
        op.create_index('ix_of_numeracion_reaperturas_of', 'of_numeracion_reaperturas', ['of_id'])


def downgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tablas = set(insp.get_table_names())

    if 'of_numeracion_reaperturas' in tablas:
        op.drop_index('ix_of_numeracion_reaperturas_of', table_name='of_numeracion_reaperturas')
        op.drop_table('of_numeracion_reaperturas')

    if 'ordenes_fabricacion' in tablas:
        cols = {c['name'] for c in insp.get_columns('ordenes_fabricacion')}
        if 'hoja_numeracion_cerrada_at' in cols:
            op.drop_column('ordenes_fabricacion', 'hoja_numeracion_cerrada_at')
        if 'hoja_numeracion_cerrada_por' in cols:
            op.drop_column('ordenes_fabricacion', 'hoja_numeracion_cerrada_por')
        if 'hoja_numeracion_cerrada' in cols:
            op.drop_column('ordenes_fabricacion', 'hoja_numeracion_cerrada')
