"""hojas_costos_y_precios_historicos

Revision ID: d7285d68364d
Revises: 20260626_curvas_tallas
Create Date: 2026-06-30 17:00:05.083283+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'd7285d68364d'
down_revision: Union[str, None] = '20260626_curvas_tallas'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('hojas_costos',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('prenda_catalogo_id', sa.Integer(), nullable=False),
    sa.Column('estado', sa.String(length=20), nullable=False),
    sa.Column('notas', sa.Text(), nullable=True),
    sa.Column('total_mp', sa.Float(), nullable=True),
    sa.Column('total_avios', sa.Float(), nullable=True),
    sa.Column('total_general', sa.Float(), nullable=True),
    sa.Column('moneda_base', sa.String(length=5), nullable=False),
    sa.Column('creado_por_id', sa.Integer(), nullable=True),
    sa.Column('aprobado_por_id', sa.Integer(), nullable=True),
    sa.Column('aprobado_at', sa.DateTime(), nullable=True),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
    sa.ForeignKeyConstraint(['aprobado_por_id'], ['usuarios.id'], ),
    sa.ForeignKeyConstraint(['creado_por_id'], ['usuarios.id'], ),
    sa.ForeignKeyConstraint(['prenda_catalogo_id'], ['prendas_catalogo.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_hojas_costos_id'), 'hojas_costos', ['id'], unique=False)
    op.create_index('ix_hojas_costos_prenda', 'hojas_costos', ['prenda_catalogo_id'], unique=False)

    op.create_table('precios_historicos',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('tipo', sa.String(length=10), nullable=False),
    sa.Column('item_id', sa.Integer(), nullable=False),
    sa.Column('nombre_item', sa.String(length=200), nullable=False),
    sa.Column('precio_anterior', sa.Float(), nullable=True),
    sa.Column('precio_nuevo', sa.Float(), nullable=True),
    sa.Column('moneda', sa.String(length=5), nullable=True),
    sa.Column('registrado_por_id', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
    sa.ForeignKeyConstraint(['registrado_por_id'], ['usuarios.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_precios_historicos_id'), 'precios_historicos', ['id'], unique=False)
    op.create_index('ix_precios_historicos_item', 'precios_historicos', ['tipo', 'item_id'], unique=False)

    op.create_table('hojas_costos_lineas',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('hoja_id', sa.Integer(), nullable=False),
    sa.Column('tipo', sa.String(length=10), nullable=False),
    sa.Column('item_id', sa.Integer(), nullable=False),
    sa.Column('seccion', sa.String(length=30), nullable=True),
    sa.Column('nombre', sa.String(length=200), nullable=False),
    sa.Column('unidad_medida', sa.String(length=20), nullable=True),
    sa.Column('consumo_unitario', sa.Float(), nullable=False),
    sa.Column('pct_adicional', sa.Float(), nullable=False),
    sa.Column('precio_snapshot', sa.Float(), nullable=True),
    sa.Column('moneda', sa.String(length=5), nullable=True),
    sa.Column('subtotal', sa.Float(), nullable=True),
    sa.Column('editado_manual', sa.Boolean(), nullable=True),
    sa.Column('notas', sa.String(length=300), nullable=True),
    sa.Column('orden', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
    sa.ForeignKeyConstraint(['hoja_id'], ['hojas_costos.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_hojas_costos_lineas_hoja', 'hojas_costos_lineas', ['hoja_id'], unique=False)
    op.create_index(op.f('ix_hojas_costos_lineas_id'), 'hojas_costos_lineas', ['id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_hojas_costos_lineas_hoja', table_name='hojas_costos_lineas')
    op.drop_index(op.f('ix_hojas_costos_lineas_id'), table_name='hojas_costos_lineas')
    op.drop_table('hojas_costos_lineas')
    op.drop_index('ix_precios_historicos_item', table_name='precios_historicos')
    op.drop_index(op.f('ix_precios_historicos_id'), table_name='precios_historicos')
    op.drop_table('precios_historicos')
    op.drop_index('ix_hojas_costos_prenda', table_name='hojas_costos')
    op.drop_index(op.f('ix_hojas_costos_id'), table_name='hojas_costos')
    op.drop_table('hojas_costos')
