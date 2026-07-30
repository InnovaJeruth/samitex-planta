"""of_trazo_movimientos — historial por sesión de tendido/corte

Registra cada carga de tendido/corte (capas de la sesión, acumulado, usuario,
fecha) para auditoría, además del acumulado que ya vive en of_trazos.

Revision ID: 20260710_trazo_mov
Revises: 20260710_capas_cort
Create Date: 2026-07-10
"""
from alembic import op
import sqlalchemy as sa

revision = '20260710_trazo_mov'
down_revision = '20260710_capas_cort'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if 'of_trazo_movimientos' in insp.get_table_names():
        return
    op.create_table(
        'of_trazo_movimientos',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('trazo_id', sa.Integer(), sa.ForeignKey('of_trazos.id', ondelete='CASCADE'), nullable=False),
        sa.Column('tipo', sa.String(length=10), nullable=False),
        sa.Column('capas', sa.Integer(), nullable=False),
        sa.Column('acumulado', sa.Integer(), nullable=False),
        sa.Column('usuario_id', sa.Integer(), sa.ForeignKey('usuarios.id'), nullable=True),
        sa.Column('observacion', sa.String(length=300), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
    )
    op.create_index('ix_of_trazo_mov_trazo', 'of_trazo_movimientos', ['trazo_id', 'tipo'])


def downgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if 'of_trazo_movimientos' in insp.get_table_names():
        op.drop_index('ix_of_trazo_mov_trazo', table_name='of_trazo_movimientos')
        op.drop_table('of_trazo_movimientos')
