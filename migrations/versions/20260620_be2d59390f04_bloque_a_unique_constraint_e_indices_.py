"""bloque_a_unique_constraint_e_indices_compuestos

Revision ID: be2d59390f04
Revises: 60e404ad390e
Create Date: 2026-06-20 04:25:22.353864+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'be2d59390f04'
down_revision: Union[str, None] = '60e404ad390e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _constraint_exists(conn, name: str) -> bool:
    result = conn.execute(
        sa.text("SELECT 1 FROM sys.objects WHERE type IN ('UQ','C') AND name = :n"),
        {"n": name},
    )
    return result.fetchone() is not None


def _index_exists(conn, name: str) -> bool:
    result = conn.execute(
        sa.text("SELECT 1 FROM sys.indexes WHERE name = :n"),
        {"n": name},
    )
    return result.fetchone() is not None


def upgrade() -> None:
    conn = op.get_bind()

    # UniqueConstraint: evita duplicados (of_id, pieza_id, fase_id) en of_fases_estado
    if not _constraint_exists(conn, "uq_of_pieza_fase"):
        op.create_unique_constraint(
            "uq_of_pieza_fase",
            "of_fases_estado",
            ["of_id", "pieza_id", "fase_id"],
        )

    # Índice compuesto: acelera filter_by(of_id, fase_id) — query más frecuente en corte.py
    if not _index_exists(conn, "ix_of_fase_estado_of_fase"):
        op.create_index(
            "ix_of_fase_estado_of_fase",
            "of_fases_estado",
            ["of_id", "fase_id"],
        )

    # Índice compuesto: acelera historial y reversiones filter_by(of_id) + order_by(created_at)
    if not _index_exists(conn, "ix_avance_registros_of_fecha"):
        op.create_index(
            "ix_avance_registros_of_fecha",
            "avance_registros",
            ["of_id", "created_at"],
        )


def downgrade() -> None:
    conn = op.get_bind()
    if _index_exists(conn, "ix_avance_registros_of_fecha"):
        op.drop_index("ix_avance_registros_of_fecha", table_name="avance_registros")
    if _index_exists(conn, "ix_of_fase_estado_of_fase"):
        op.drop_index("ix_of_fase_estado_of_fase", table_name="of_fases_estado")
    if _constraint_exists(conn, "uq_of_pieza_fase"):
        op.drop_constraint("uq_of_pieza_fase", table_name="of_fases_estado")
