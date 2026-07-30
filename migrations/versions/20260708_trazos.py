"""Crea of_trazos y of_trazo_tallas (Fase A — fases de tela por trazo)

Aditivo: no modifica tablas existentes.

Revision ID: 20260708_trazos
Revises: 20260708_fecha_sap
Create Date: 2026-07-08
"""
from alembic import op
import sqlalchemy as sa

revision = '20260708_trazos'
down_revision = '20260708_fecha_sap'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'of_trazos',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('of_id', sa.Integer(), sa.ForeignKey('ordenes_fabricacion.id', ondelete='CASCADE'), nullable=False),
        sa.Column('nombre', sa.String(length=30), nullable=False),
        sa.Column('largo', sa.Float(), nullable=True),
        sa.Column('capas', sa.Integer(), nullable=True),
        sa.Column('metraje_teorico', sa.Float(), nullable=True),
        sa.Column('metraje_real', sa.Float(), nullable=True),
        sa.Column('eficiencia', sa.Float(), nullable=True),
        sa.Column('estado_tizado', sa.String(length=15), nullable=False, server_default='PENDIENTE'),
        sa.Column('estado_tendido', sa.String(length=15), nullable=False, server_default='PENDIENTE'),
        sa.Column('estado_corte', sa.String(length=15), nullable=False, server_default='PENDIENTE'),
        sa.Column('orden', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index('ix_of_trazos_of', 'of_trazos', ['of_id'])

    op.create_table(
        'of_trazo_tallas',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('trazo_id', sa.Integer(), sa.ForeignKey('of_trazos.id', ondelete='CASCADE'), nullable=False),
        sa.Column('sku_id', sa.Integer(), sa.ForeignKey('prenda_skus.id'), nullable=False),
        sa.Column('talla', sa.String(length=20), nullable=False),
        sa.Column('cantidad', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('orden', sa.Integer(), nullable=False, server_default='0'),
    )
    op.create_index('ix_of_trazo_tallas_trazo_sku', 'of_trazo_tallas', ['trazo_id', 'sku_id'], unique=True)


def downgrade():
    op.drop_index('ix_of_trazo_tallas_trazo_sku', table_name='of_trazo_tallas')
    op.drop_table('of_trazo_tallas')
    op.drop_index('ix_of_trazos_of', table_name='of_trazos')
    op.drop_table('of_trazos')
