"""Agregar columnas extra a of_fases_estado (eficiencia, temperatura, tratamiento, motivo)

Revision ID: fases_estado_extra_cols_v1
Revises: fix_codigo_null_index_v1
Create Date: 2026-06-24
"""
from typing import Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text, inspect

revision: str = 'fases_estado_extra_cols_v1'
down_revision: Union[str, None] = 'fix_codigo_null_index_v1'
branch_labels = None
depends_on = None


def _col_exists(conn, table: str, col: str) -> bool:
    insp = inspect(conn)
    return col in [c["name"] for c in insp.get_columns(table)]


def upgrade() -> None:
    conn = op.get_bind()

    if not _col_exists(conn, 'of_fases_estado', 'eficiencia_tizado'):
        op.add_column('of_fases_estado',
            sa.Column('eficiencia_tizado', sa.Float(), nullable=True))

    if not _col_exists(conn, 'of_fases_estado', 'temperatura_fusion'):
        op.add_column('of_fases_estado',
            sa.Column('temperatura_fusion', sa.Float(), nullable=True))

    if not _col_exists(conn, 'of_fases_estado', 'tratamiento_orillo'):
        op.add_column('of_fases_estado',
            sa.Column('tratamiento_orillo', sa.Boolean(), nullable=True))

    if not _col_exists(conn, 'of_fases_estado', 'motivo_rechazo'):
        op.add_column('of_fases_estado',
            sa.Column('motivo_rechazo', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('of_fases_estado', 'motivo_rechazo')
    op.drop_column('of_fases_estado', 'tratamiento_orillo')
    op.drop_column('of_fases_estado', 'temperatura_fusion')
    op.drop_column('of_fases_estado', 'eficiencia_tizado')
