"""Crear tabla prenda_documentos

Revision ID: prenda_documentos_v1
Revises: pieza_codigo_v1
Create Date: 2026-06-24
"""
from typing import Union
from alembic import op
import sqlalchemy as sa

revision: str = 'prenda_documentos_v1'
down_revision: Union[str, None] = 'pieza_codigo_v1'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'prenda_documentos',
        sa.Column('id',                 sa.Integer(),     nullable=False),
        sa.Column('prenda_catalogo_id', sa.Integer(),     nullable=False),
        sa.Column('tipo',               sa.String(30),    nullable=False),
        sa.Column('nombre_archivo',     sa.String(255),   nullable=False),
        sa.Column('ruta_archivo',       sa.String(500),   nullable=False),
        sa.Column('descripcion',        sa.String(300),   nullable=True),
        sa.Column('subido_por_id',      sa.Integer(),     nullable=True),
        sa.Column('created_at',         sa.DateTime(),    server_default=sa.text('GETDATE()')),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['prenda_catalogo_id'], ['prendas_catalogo.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['subido_por_id'],      ['usuarios.id']),
    )
    op.create_index('ix_prenda_documentos_prenda', 'prenda_documentos', ['prenda_catalogo_id'])


def downgrade() -> None:
    op.drop_index('ix_prenda_documentos_prenda', 'prenda_documentos')
    op.drop_table('prenda_documentos')
