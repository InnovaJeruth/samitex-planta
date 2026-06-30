"""Tabla auditoria_documento_of para trazabilidad de docs en OFs

Revision ID: 20260626_auditoria_docs_of
Revises: 20260626_mp_procedencia
Create Date: 2026-06-26
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision     = '20260626_auditoria_docs_of'
down_revision = '20260626_mp_procedencia'
branch_labels = None
depends_on    = None


def _table_exists(table):
    bind = op.get_bind()
    return table in inspect(bind).get_table_names()


def upgrade():
    if not _table_exists('auditoria_documento_of'):
        op.create_table(
            'auditoria_documento_of',
            sa.Column('id',             sa.Integer(),     nullable=False),
            sa.Column('of_id',          sa.Integer(),     nullable=False),
            sa.Column('tipo',           sa.String(50),    nullable=False),
            sa.Column('accion',         sa.String(20),    nullable=False),
            sa.Column('nombre_archivo', sa.String(255),   nullable=True),
            sa.Column('usuario_id',     sa.Integer(),     nullable=True),
            sa.Column('created_at',     sa.DateTime(),    server_default=sa.text('GETDATE()'), nullable=True),
            sa.ForeignKeyConstraint(['of_id'],      ['ordenes_fabricacion.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['usuario_id'], ['usuarios.id']),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index('ix_auditoria_doc_of_of_id', 'auditoria_documento_of', ['of_id'])


def downgrade():
    pass
