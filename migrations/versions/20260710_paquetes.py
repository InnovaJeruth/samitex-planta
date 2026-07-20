"""Paquetes de numeración: of_paquetes + of_paquete_eventos + unidades_por_paquete

Módulo de hoja de numeración (Numerado F4 → Habilitado F7 por paquete).

Revision ID: 20260710_paquetes
Revises: 20260710_trazo_mov
Create Date: 2026-07-10
"""
from alembic import op
import sqlalchemy as sa

revision = '20260710_paquetes'
down_revision = '20260710_trazo_mov'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tablas = set(insp.get_table_names())

    of_cols = {c['name'] for c in insp.get_columns('ordenes_fabricacion')}
    if 'unidades_por_paquete' not in of_cols:
        op.add_column('ordenes_fabricacion', sa.Column('unidades_por_paquete', sa.Integer(), nullable=True))

    if 'of_paquetes' not in tablas:
        op.create_table(
            'of_paquetes',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('of_id', sa.Integer(), sa.ForeignKey('ordenes_fabricacion.id', ondelete='CASCADE'), nullable=False),
            sa.Column('sku_id', sa.Integer(), sa.ForeignKey('prenda_skus.id'), nullable=False),
            sa.Column('numero', sa.Integer(), nullable=False),
            sa.Column('numero_desde', sa.Integer(), nullable=False),
            sa.Column('cantidad', sa.Integer(), nullable=False),
            sa.Column('estado', sa.String(length=15), nullable=False, server_default='NUMERADO'),
            sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
            sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
            sa.UniqueConstraint('of_id', 'numero', name='uq_of_paquete_num'),
        )
        op.create_index('ix_of_paquetes_of_sku', 'of_paquetes', ['of_id', 'sku_id'])

    if 'of_paquete_eventos' not in tablas:
        op.create_table(
            'of_paquete_eventos',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('paquete_id', sa.Integer(), sa.ForeignKey('of_paquetes.id', ondelete='CASCADE'), nullable=False),
            sa.Column('estado', sa.String(length=15), nullable=False),
            sa.Column('motivo', sa.String(length=200), nullable=True),
            sa.Column('usuario_id', sa.Integer(), sa.ForeignKey('usuarios.id'), nullable=True),
            sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        )
        op.create_index('ix_of_paquete_eventos_paquete', 'of_paquete_eventos', ['paquete_id'])


def downgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tablas = set(insp.get_table_names())
    if 'of_paquete_eventos' in tablas:
        op.drop_index('ix_of_paquete_eventos_paquete', table_name='of_paquete_eventos')
        op.drop_table('of_paquete_eventos')
    if 'of_paquetes' in tablas:
        op.drop_index('ix_of_paquetes_of_sku', table_name='of_paquetes')
        op.drop_table('of_paquetes')
    of_cols = {c['name'] for c in insp.get_columns('ordenes_fabricacion')}
    if 'unidades_por_paquete' in of_cols:
        op.drop_column('ordenes_fabricacion', 'unidades_por_paquete')
