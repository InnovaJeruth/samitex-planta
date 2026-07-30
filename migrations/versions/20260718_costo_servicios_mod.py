"""Ficha de costos: catalogo_servicios (terceros) + catalogo_mod (mano de obra)

Aditivo. Dos tablas nuevas ligadas a la prenda BASE, heredadas por las variantes:
otros servicios de terceros y mano de obra directa por operación.

Revision ID: 20260718_costo_servicios_mod
Revises: 20260718_catalogo_hereda_ficha
Create Date: 2026-07-18
"""
from alembic import op
import sqlalchemy as sa

revision = '20260718_costo_servicios_mod'
down_revision = '20260718_catalogo_hereda_ficha'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tablas = set(insp.get_table_names())

    if 'catalogo_servicios' not in tablas:
        op.create_table(
            'catalogo_servicios',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('prenda_catalogo_id', sa.Integer(),
                      sa.ForeignKey('prendas_catalogo.id', ondelete='CASCADE'), nullable=False),
            sa.Column('nombre', sa.String(length=60), nullable=False),
            sa.Column('costo', sa.Float(), nullable=True),
            sa.Column('moneda', sa.String(length=5), nullable=True),
            sa.Column('proveedor', sa.String(length=150), nullable=True),
            sa.Column('orden', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('activo', sa.Boolean(), nullable=False, server_default='1'),
        )
        op.create_index('ix_catalogo_servicios_prenda', 'catalogo_servicios', ['prenda_catalogo_id'])

    if 'catalogo_mod' not in tablas:
        op.create_table(
            'catalogo_mod',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('prenda_catalogo_id', sa.Integer(),
                      sa.ForeignKey('prendas_catalogo.id', ondelete='CASCADE'), nullable=False),
            sa.Column('operacion', sa.String(length=40), nullable=False),
            sa.Column('min_std', sa.Float(), nullable=False, server_default='0'),
            sa.Column('pct_eficiencia', sa.Float(), nullable=False, server_default='1'),
            sa.Column('costo_minuto', sa.Float(), nullable=False, server_default='0'),
            sa.Column('moneda', sa.String(length=5), nullable=True),
            sa.Column('orden', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('activo', sa.Boolean(), nullable=False, server_default='1'),
        )
        op.create_index('ix_catalogo_mod_prenda', 'catalogo_mod', ['prenda_catalogo_id'])


def downgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tablas = set(insp.get_table_names())
    if 'catalogo_mod' in tablas:
        op.drop_index('ix_catalogo_mod_prenda', table_name='catalogo_mod')
        op.drop_table('catalogo_mod')
    if 'catalogo_servicios' in tablas:
        op.drop_index('ix_catalogo_servicios_prenda', table_name='catalogo_servicios')
        op.drop_table('catalogo_servicios')
