"""Tablas curvas_tallas, curvas_tallas_detalle, curvas_tallas_of

Revision ID: 20260626_curvas_tallas
Revises: 20260626_auditoria_docs_of
Create Date: 2026-06-26
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision      = '20260626_curvas_tallas'
down_revision = '20260626_auditoria_docs_of'
branch_labels = None
depends_on    = None


def _table_exists(table):
    bind = op.get_bind()
    return table in inspect(bind).get_table_names()


def upgrade():
    if not _table_exists('curvas_tallas'):
        op.create_table(
            'curvas_tallas',
            sa.Column('id',                 sa.Integer(),     nullable=False),
            sa.Column('prenda_catalogo_id', sa.Integer(),     nullable=False),
            sa.Column('nombre',             sa.String(150),   nullable=True),
            sa.Column('notas',              sa.String(500),   nullable=True),
            sa.Column('nombre_archivo',     sa.String(255),   nullable=True),
            sa.Column('ruta_archivo',       sa.String(500),   nullable=True),
            sa.Column('activo',             sa.Boolean(),     nullable=False, server_default='1'),
            sa.Column('creado_por_id',      sa.Integer(),     nullable=True),
            sa.Column('created_at',         sa.DateTime(),    server_default=sa.text('GETDATE()'), nullable=True),
            sa.Column('updated_at',         sa.DateTime(),    server_default=sa.text('GETDATE()'), nullable=True),
            sa.ForeignKeyConstraint(['prenda_catalogo_id'], ['prendas_catalogo.id']),
            sa.ForeignKeyConstraint(['creado_por_id'],      ['usuarios.id']),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index('ix_curvas_tallas_prenda', 'curvas_tallas', ['prenda_catalogo_id'])

    if not _table_exists('curvas_tallas_detalle'):
        op.create_table(
            'curvas_tallas_detalle',
            sa.Column('id',       sa.Integer(),  nullable=False),
            sa.Column('curva_id', sa.Integer(),  nullable=False),
            sa.Column('sku_id',   sa.Integer(),  nullable=False),
            sa.Column('talla',    sa.String(20), nullable=False),
            sa.Column('cantidad', sa.Integer(),  nullable=False, server_default='0'),
            sa.Column('orden',    sa.Integer(),  nullable=False, server_default='0'),
            sa.ForeignKeyConstraint(['curva_id'], ['curvas_tallas.id'],  ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['sku_id'],   ['prenda_skus.id']),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index('ix_curva_detalle_curva_sku', 'curvas_tallas_detalle', ['curva_id', 'sku_id'], unique=True)

    if not _table_exists('curvas_tallas_of'):
        op.create_table(
            'curvas_tallas_of',
            sa.Column('id',             sa.Integer(), nullable=False),
            sa.Column('curva_id',       sa.Integer(), nullable=False),
            sa.Column('of_id',          sa.Integer(), nullable=False),
            sa.Column('enviado_por_id', sa.Integer(), nullable=True),
            sa.Column('created_at',     sa.DateTime(), server_default=sa.text('GETDATE()'), nullable=True),
            sa.ForeignKeyConstraint(['curva_id'],       ['curvas_tallas.id'],        ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['of_id'],          ['ordenes_fabricacion.id'],  ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['enviado_por_id'], ['usuarios.id']),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index('ix_curva_of_curva_of', 'curvas_tallas_of', ['curva_id', 'of_id'], unique=True)


def downgrade():
    pass
