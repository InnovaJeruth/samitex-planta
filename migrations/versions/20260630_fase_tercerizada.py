"""add fase_tercerizada to ordenes_fabricacion

Revision ID: 20260630_fase_terc
Revises: 20260630_fc_tc
Create Date: 2026-06-30
"""
from alembic import op
import sqlalchemy as sa

revision = "20260630_fase_terc"
down_revision = "20260630_fc_tc"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "ordenes_fabricacion",
        sa.Column("fase_tercerizada", sa.String(5), nullable=True),
    )


def downgrade():
    op.drop_column("ordenes_fabricacion", "fase_tercerizada")
